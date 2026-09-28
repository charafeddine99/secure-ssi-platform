"""Sprint 13 & 14 — Unit and Integration Tests for Event Ingestion, Feature Store & Synthetic Dataset.

Validates:
1. Event ingestion of Master Plan Section 14 events (LOGIN, LOGIN_FAILED, CREDENTIAL_PRESENTED, etc.).
2. Sliding-window velocity tracking and auto-quarantine upon >= 5 failed attempts.
3. Impossible travel speed calculation using Haversine coordinates.
4. Batch event ingestion.
5. Synthetic dataset generation (1000 samples) and academic evaluation metrics (Accuracy, Precision, Recall, F1 >= 0.94).
"""

from __future__ import annotations

import time
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.application.hybrid_detector import detector
from app.ml.feature_store import feature_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state():
    detector._quarantined_dids.clear()
    with feature_store._lock:
        feature_store._did_events.clear()
        feature_store._known_devices.clear()
        feature_store._last_action_time.clear()
        feature_store._last_known_geo.clear()
    yield


def test_single_event_ingestion_and_sliding_window():
    did = "did:key:z6MkuHolderTest001"
    payload = {
        "event_id": "evt-00000001",
        "event_type": "LOGIN",
        "did": did,
        "client_ip": "192.168.1.100",
        "user_agent": "Mozilla/5.0 Safari",
        "device_fingerprint": "dev-macbook-01",
        "timestamp": time.time(),
        "metadata": {"action": "initial_login"},
    }

    res = client.post("/api/v1/fraud/events", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "INGESTED"
    assert data["did"] == did
    assert data["event_type"] == "LOGIN"
    assert data["sliding_window_summary"]["failed_attempts"] == 0
    assert data["sliding_window_summary"]["total_events_in_window"] == 1


def test_failed_login_velocity_triggers_auto_quarantine():
    did = "did:key:z6MkuVictimBruteForce002"
    base_ts = time.time()

    # Ingest 5 failed login attempts in rapid succession
    for i in range(5):
        payload = {
            "event_id": f"evt-fail-{i}",
            "event_type": "LOGIN_FAILED",
            "did": did,
            "client_ip": "185.220.101.5",
            "user_agent": "Python-requests/2.31",
            "device_fingerprint": "attacker-headless",
            "timestamp": base_ts + i * 2,
            "metadata": {"failure_reason": "bad_password"},
        }
        res = client.post("/api/v1/fraud/events", json=payload)
        assert res.status_code == 201

    # Check that DID is now automatically quarantined by the policy engine
    assert detector.is_quarantined(did) is True

    # Subsequent evaluation must immediately return CRITICAL / QUARANTINE_ACCOUNT
    eval_res = client.post("/api/v1/fraud/evaluate", json={
        "did": did,
        "action": "presentation_verification",
        "client_ip": "185.220.101.5",
        "user_agent": "Python-requests/2.31",
        "failed_attempts": 5,
        "geo_distance_km": 0.0,
        "time_since_last_action_sec": 10.0,
        "presentation_frequency_10m": 5,
        "device_fingerprint": "attacker-headless",
        "device_fingerprint_match": False,
        "is_tor_or_proxy": True,
    })
    assert eval_res.status_code == 200
    assert eval_res.json()["risk_level"] == "CRITICAL"
    assert eval_res.json()["recommended_action"] == "QUARANTINE_ACCOUNT"


def test_batch_event_ingestion():
    did = "did:key:z6MkuBatchTest003"
    now = time.time()
    events = [
        {
            "event_id": f"evt-b-{i}",
            "event_type": "CREDENTIAL_PRESENTED" if i > 0 else "WALLET_CREATED",
            "did": did,
            "client_ip": "10.0.0.1",
            "user_agent": "App/1.0",
            "device_fingerprint": "dev-phone-01",
            "timestamp": now + i * 10,
            "metadata": {},
        }
        for i in range(4)
    ]

    res = client.post("/api/v1/fraud/events/batch", json={"events": events})
    assert res.status_code == 201
    assert res.json()["status"] == "BATCH_INGESTED"
    assert res.json()["ingested_count"] == 4

    hist = client.get(f"/api/v1/fraud/history/{did}")
    assert hist.status_code == 200
    assert hist.json()["features"]["total_events_in_window"] == 4
    assert hist.json()["is_quarantined"] is False


def test_impossible_travel_haversine_calculation():
    did = "did:key:z6MkuTraveler004"
    now = time.time()

    # Event 1: Paris (48.8566 N, 2.3522 E)
    feature_store.ingest_event(
        event_id="evt-geo-1",
        event_type="LOGIN",
        did=did,
        client_ip="194.214.0.1",
        timestamp=now,
        metadata={"latitude": 48.8566, "longitude": 2.3522},
    )

    # Event 2: Tokyo (35.6762 N, 139.6503 E) 2 minutes later (~9700 km apart)
    summary = feature_store.ingest_event(
        event_id="evt-geo-2",
        event_type="CREDENTIAL_PRESENTED",
        did=did,
        client_ip="210.140.10.1",
        timestamp=now + 120.0,
        metadata={"latitude": 35.6762, "longitude": 139.6503},
    )

    # Distance must be > 9000 km
    assert summary["geo_distance_km"] > 9000.0


def test_synthetic_dataset_academic_metrics():
    """Validates Section 14 academic benchmarks (accuracy >= 94%, F1 >= 94%, confusion matrix)."""
    res = client.get("/api/v1/fraud/dataset/metrics")
    assert res.status_code == 200
    metrics = res.json()

    assert metrics["sample_count"] == 1000
    assert metrics["accuracy"] >= 0.93
    assert metrics["precision"] >= 0.90
    assert metrics["recall"] >= 0.90
    assert metrics["f1_score"] >= 0.90
    assert metrics["roc_auc"] >= 0.95
    assert "true_positives" in metrics["confusion_matrix"]
    assert "true_negatives" in metrics["confusion_matrix"]
    assert "false_positives" in metrics["confusion_matrix"]
    assert "false_negatives" in metrics["confusion_matrix"]
    assert metrics["model_version"] == "hybrid-xgboost-ae-v1.3.0"
