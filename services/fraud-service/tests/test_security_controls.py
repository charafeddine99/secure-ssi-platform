from __future__ import annotations

import time

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.subject import subject_key
from app.application.hybrid_detector import detector
from app.core import security
from app.core.config import CORS_ORIGINS
from app.core.security import FraudPrincipal
from app.main import app
from app.ml.feature_store import SlidingWindowFeatureStore, feature_store


client = TestClient(app)
SERVICE_TOKEN = "fraud-test-internal-service-token-32bytes"
SERVICE_HEADERS = {"X-Internal-Service-Token": SERVICE_TOKEN}
ADMIN_HEADERS = {"Authorization": "Bearer authorized-admin"}
HOLDER_HEADERS = {"Authorization": "Bearer authorized-holder"}
EVALUATION = {
    "did": "did:key:z6MkuSecurityTest",
    "action": "presentation_verification",
    "failed_attempts": 0,
    "geo_distance_km": 0,
    "presentation_frequency_10m": 1,
}


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch):
    monkeypatch.setattr(security, "FRAUD_INTERNAL_SERVICE_TOKEN", SERVICE_TOKEN)

    async def introspect(token: str) -> FraudPrincipal:
        if token == "authorized-admin":
            return FraudPrincipal(
                "admin-1",
                frozenset({"admin"}),
                frozenset({"admin:operations:read"}),
            )
        if token == "authorized-holder":
            return FraudPrincipal(
                "holder-1",
                frozenset({"holder"}),
                frozenset({"wallets:read"}),
            )
        if token == "identity-unavailable":
            raise HTTPException(status_code=503, detail="Identity unavailable")
        raise HTTPException(status_code=401, detail="Invalid bearer")

    monkeypatch.setattr(security, "_introspect_bearer_token", introspect)
    detector._quarantined_dids.clear()
    with feature_store._lock:
        feature_store._did_events.clear()
        feature_store._known_devices.clear()
        feature_store._last_action_time.clear()
        feature_store._last_known_geo.clear()


def test_public_health_and_model_metadata_remain_public_but_evaluation_requires_auth():
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/fraud/stats").status_code == 200
    assert client.post("/api/v1/fraud/evaluate", json=EVALUATION).status_code == 401


def test_evaluation_uses_identity_authoritative_bearer_and_fails_closed():
    accepted = client.post(
        "/api/v1/fraud/evaluate", json=EVALUATION, headers=HOLDER_HEADERS
    )
    assert accepted.status_code == 200
    assert accepted.json()["advisory_only"] is True

    invalid = client.post(
        "/api/v1/fraud/evaluate",
        json=EVALUATION,
        headers={"Authorization": "Bearer invalid"},
    )
    unavailable = client.post(
        "/api/v1/fraud/evaluate",
        json=EVALUATION,
        headers={"Authorization": "Bearer identity-unavailable"},
    )
    assert invalid.status_code == 401
    assert unavailable.status_code == 503


def test_internal_event_ingestion_requires_configured_service_credential():
    payload = {
        "event_id": "event-security-1",
        "event_type": "LOGIN_FAILED",
        "did": "did:key:z6MkuServiceEvent",
        "client_ip": "192.0.2.10",
        "user_agent": "private-agent-string",
        "device_fingerprint": "private-device-fingerprint",
        "timestamp": time.time(),
        "metadata": {"failure_reason": "private-reason"},
    }
    path = "/api/v1/fraud/events"
    assert client.post(path, json=payload).status_code == 401
    assert client.post(path, json=payload, headers=HOLDER_HEADERS).status_code == 401
    assert client.post(
        path,
        json=payload,
        headers={"X-Internal-Service-Token": "wrong-service-token"},
    ).status_code == 401
    accepted = client.post(path, json=payload, headers=SERVICE_HEADERS)
    assert accepted.status_code == 201
    assert accepted.json()["status"] == "INGESTED"

    security.FRAUD_INTERNAL_SERVICE_TOKEN = ""
    unavailable = client.post(path, json=payload, headers=SERVICE_HEADERS)
    assert unavailable.status_code == 503


def test_holder_cannot_read_or_mutate_another_dids_admin_quarantine():
    did = "did:key:z6MkuPrivateHistory"
    detector.quarantine(did, "private reason")

    history = client.get(f"/api/v1/fraud/history/{did}", headers=HOLDER_HEADERS)
    state = client.get(f"/api/v1/fraud/quarantine/{did}", headers=HOLDER_HEADERS)
    mutate = client.delete(f"/api/v1/fraud/quarantine/{did}", headers=HOLDER_HEADERS)
    assert history.status_code == 403
    assert state.status_code == 403
    assert mutate.status_code == 403
    assert detector.is_quarantined(did) is True

    admin_state = client.get(f"/api/v1/fraud/quarantine/{did}", headers=ADMIN_HEADERS)
    assert admin_state.status_code == 200
    assert admin_state.json()["effect_scope"] == "fraud-service-only"


def test_privileged_synthetic_metrics_require_admin():
    assert client.get("/api/v1/fraud/dataset/metrics").status_code == 401
    assert client.get(
        "/api/v1/fraud/dataset/metrics", headers=HOLDER_HEADERS
    ).status_code == 403


def test_browser_cors_does_not_allow_arbitrary_origins_or_internal_secret_header():
    allowed_preflight = client.options(
        "/api/v1/fraud/evaluate",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    response = client.options(
        "/api/v1/fraud/evaluate",
        headers={
            "Origin": "https://attacker.invalid",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,x-internal-service-token",
        },
    )
    assert allowed_preflight.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "x-internal-service-token" not in allowed_preflight.headers.get(
        "access-control-allow-headers", ""
    ).lower()
    assert response.headers.get("access-control-allow-origin") != "https://attacker.invalid"
    assert "*" not in CORS_ORIGINS


def test_event_store_discards_raw_identifiers_and_purges_derived_state():
    store = SlidingWindowFeatureStore(window_retention_sec=10)
    now = time.time()
    store.ingest_event(
        event_id="raw-event-id-do-not-retain",
        event_type="LOGIN",
        did="did:key:privacy-test",
        client_ip="203.0.113.9",
        user_agent="raw-user-agent-do-not-retain",
        device_fingerprint="raw-device-fingerprint-do-not-retain",
        timestamp=now,
        metadata={
            "failure_reason": "raw-metadata-do-not-retain",
            "latitude": 48.8566,
            "longitude": 2.3522,
        },
    )

    event = store._did_events[subject_key("did:key:privacy-test")][0]
    retained_repr = repr((event, store._known_devices, store._last_action_time))
    assert set(event) == {"event_type", "timestamp"}
    assert "raw-event-id-do-not-retain" not in retained_repr
    assert "203.0.113.9" not in retained_repr
    assert "raw-user-agent-do-not-retain" not in retained_repr
    assert "raw-device-fingerprint-do-not-retain" not in retained_repr
    assert "raw-metadata-do-not-retain" not in retained_repr
    assert all(
        "raw-device-fingerprint-do-not-retain" not in value
        for value in store._known_devices[subject_key("did:key:privacy-test")]
    )
    assert store._last_known_geo[subject_key("did:key:privacy-test")] == (48.9, 2.4)
    assert (48.8566, 2.3522) not in store._last_known_geo.values()

    store.get_features("did:key:privacy-test", current_timestamp=now + 11)
    assert subject_key("did:key:privacy-test") not in store._did_events
    assert subject_key("did:key:privacy-test") not in store._known_devices
    assert subject_key("did:key:privacy-test") not in store._last_action_time
    assert subject_key("did:key:privacy-test") not in store._last_known_geo


def test_feature_store_bounds_event_and_did_cardinality():
    store = SlidingWindowFeatureStore(
        window_retention_sec=60, max_tracked_dids=2, max_events_per_did=2
    )
    now = time.time()
    for index in range(3):
        store.ingest_event(
            event_id=f"event-{index}",
            event_type="LOGIN",
            did="did:key:bounded",
            timestamp=now + index,
        )
    assert len(store._did_events[subject_key("did:key:bounded")]) == 2

    store.ingest_event(
        event_id="event-other-1", event_type="LOGIN", did="did:key:other-1", timestamp=now
    )
    store.ingest_event(
        event_id="event-other-2", event_type="LOGIN", did="did:key:other-2", timestamp=now
    )
    assert len(store._did_events) == 2
    assert subject_key("did:key:bounded") not in store._did_events
    assert "did:key:bounded" not in store._known_devices
