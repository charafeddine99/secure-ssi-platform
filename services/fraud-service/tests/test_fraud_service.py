import time
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.application.hybrid_detector import detector
from app.core import security
from app.core.security import FraudPrincipal

client = TestClient(app)
SERVICE_TOKEN = "fraud-test-internal-service-token-32bytes"
SERVICE_HEADERS = {"X-Internal-Service-Token": SERVICE_TOKEN}
ADMIN_HEADERS = {"Authorization": "Bearer test-admin-token"}


def evaluate(payload):
    return client.post(
        "/api/v1/fraud/evaluate", json=payload, headers=SERVICE_HEADERS
    )

@pytest.fixture(autouse=True)
def reset_detector_state(monkeypatch):
    """Her test öncesi karantina hafızasını sıfırlar."""
    monkeypatch.setattr(security, "FRAUD_INTERNAL_SERVICE_TOKEN", SERVICE_TOKEN)
    detector._quarantined_dids.clear()
    yield

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json().get("status") == "healthy"

def test_normal_user_evaluation_low_risk():
    payload = {
        "did": "did:key:z6MkuNormalUser123",
        "action": "presentation_verification",
        "client_ip": "192.168.1.50",
        "user_agent": "Mozilla/5.0 NormalBrowser",
        "failed_attempts": 0,
        "geo_distance_km": 5.0,
        "time_since_last_action_sec": 300.0,
        "presentation_frequency_10m": 1,
        "device_fingerprint": "fingerprint-abc",
        "device_fingerprint_match": True,
        "is_tor_or_proxy": False
    }
    response = evaluate(payload)
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] == "LOW"
    assert data["recommended_action"] == "ALLOW"
    assert data["is_anomaly"] is False
    assert data["risk_score"] < 0.30

def test_impossible_travel_returns_critical_advice_without_mutating_quarantine():
    payload = {
        "did": "did:key:z6MkuImpossibleTraveler",
        "action": "presentation_verification",
        "client_ip": "185.220.101.5",
        "user_agent": "Mozilla/5.0 Malicious",
        "failed_attempts": 0,
        "geo_distance_km": 3000.0,  # 3000 km in 60 seconds!
        "time_since_last_action_sec": 60.0,
        "presentation_frequency_10m": 1,
        "device_fingerprint": "fingerprint-unknown",
        "device_fingerprint_match": False,
        "is_tor_or_proxy": False
    }
    response = evaluate(payload)
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] in ("HIGH", "CRITICAL")
    assert data["is_anomaly"] is True
    assert any("İmkansız seyahat" in r for r in data["reasons"])
    assert detector.is_quarantined(payload["did"]) is False

    repeated = evaluate(payload)
    assert repeated.status_code == 200
    assert repeated.json()["risk_score"] == data["risk_score"]
    assert repeated.json()["risk_level"] == data["risk_level"]
    assert detector.is_quarantined(payload["did"]) is False

def test_brute_force_failure_requires_step_up_or_review():
    payload = {
        "did": "did:key:z6MkuBruteForceTarget",
        "action": "login",
        "client_ip": "192.168.1.100",
        "user_agent": "Mozilla/5.0",
        "failed_attempts": 4,
        "geo_distance_km": 0.0,
        "time_since_last_action_sec": 10.0,
        "presentation_frequency_10m": 5,
        "device_fingerprint": "fingerprint-abc",
        "device_fingerprint_match": True,
        "is_tor_or_proxy": False
    }
    response = evaluate(payload)
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] in ("MEDIUM", "HIGH")
    assert data["recommended_action"] in ("REQUIRE_STEP_UP_AUTH", "MANUAL_REVIEW")

def test_tor_proxy_combined_risk():
    payload = {
        "did": "did:key:z6MkuTorUser",
        "action": "presentation_verification",
        "client_ip": "198.51.100.1",
        "user_agent": "TorBrowser",
        "failed_attempts": 1,
        "geo_distance_km": 800.0,
        "time_since_last_action_sec": 600.0,
        "presentation_frequency_10m": 8,
        "device_fingerprint": "unknown-fingerprint",
        "device_fingerprint_match": False,
        "is_tor_or_proxy": True
    }
    response = evaluate(payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_anomaly"] is True
    assert data["risk_score"] >= 0.60

def test_manual_quarantine_and_release_lifecycle(monkeypatch):
    async def admin_identity(_token):
        return FraudPrincipal(
            subject="admin-test",
            roles=frozenset({"admin"}),
            permissions=frozenset({"admin:operations:read"}),
        )

    monkeypatch.setattr(security, "_introspect_bearer_token", admin_identity)
    target_did = "did:key:z6MkuCompromisedAccount"
    # 1. Karantinaya al
    q_res = client.post(
        "/api/v1/fraud/quarantine",
        json={"did": target_did, "reason": "Şüpheli anahtar ele geçirme şüphesi"},
        headers=ADMIN_HEADERS,
    )
    assert q_res.status_code == 200
    assert q_res.json()["is_quarantined"] is True

    # 2. Risk evaluation remains advisory and does not change the explicit state.
    eval_res = evaluate({
        "did": target_did,
        "action": "presentation_verification",
        "client_ip": "127.0.0.1",
        "user_agent": "Mozilla",
        "failed_attempts": 0,
        "geo_distance_km": 0.0,
        "time_since_last_action_sec": 100.0,
        "presentation_frequency_10m": 1,
        "device_fingerprint": "xyz",
        "device_fingerprint_match": True,
        "is_tor_or_proxy": False
    })
    assert eval_res.status_code == 200
    assert eval_res.json()["risk_level"] == "LOW"
    assert eval_res.json()["recommended_action"] == "ALLOW"
    assert detector.is_quarantined(target_did) is True

    # 3. Karantina durumunu sorgula
    stat_res = client.get(
        f"/api/v1/fraud/quarantine/{target_did}", headers=ADMIN_HEADERS
    )
    assert stat_res.status_code == 200
    assert stat_res.json()["is_quarantined"] is True
    assert stat_res.json()["effect_scope"] == "fraud-service-only"

    # 4. Karantinayı kaldır
    rel_res = client.delete(
        f"/api/v1/fraud/quarantine/{target_did}", headers=ADMIN_HEADERS
    )
    assert rel_res.status_code == 200
    assert rel_res.json()["status"] == "RELEASED"
    assert rel_res.json()["effect_scope"] == "fraud-service-only"

def test_model_stats_report_heuristic_status_without_model_metrics():
    response = client.get("/api/v1/fraud/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["model_type"] == "Deterministic rule-based heuristic engine"
    assert data["model_version"] == "rule-heuristic-v1"
    assert data["model_status"] == "NOT_TRAINED"
    assert data["evaluation_status"] == "NO_INDEPENDENT_LABELLED_EVALUATION"
    assert data["dataset_label"] == "[DEMO LAB / SYNTHETIC]"
    assert data["advisory_only"] is True
    assert "impossible_travel" in data["risk_signals"]
    assert not {"accuracy", "f1_score", "confusion_matrix", "last_trained"}.intersection(data)


def test_evaluation_returns_versioned_advisory_heuristic():
    response = evaluate({
        "did": "did:key:z6MkuHeuristicMetadata",
        "failed_attempts": 0,
        "geo_distance_km": 0,
        "presentation_frequency_10m": 1,
        "device_fingerprint_match": True,
        "is_tor_or_proxy": False,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["model_version"] == "rule-heuristic-v1"
    assert "failed_attempt_velocity" in data["risk_signals"]
    assert data["advisory_only"] is True
    assert "heuristic_breakdown" in data
    assert "model_breakdown" not in data

def test_inference_latency_benchmark():
    payload = {
        "did": "did:key:z6MkuBenchmarkUser",
        "action": "presentation_verification",
        "client_ip": "10.0.0.1",
        "user_agent": "BenchmarkAgent",
        "failed_attempts": 1,
        "geo_distance_km": 20.0,
        "time_since_last_action_sec": 120.0,
        "presentation_frequency_10m": 2,
        "device_fingerprint": "bench-fp",
        "device_fingerprint_match": True,
        "is_tor_or_proxy": False
    }
    start = time.perf_counter()
    for _ in range(50):
        evaluate(payload)
    elapsed = time.perf_counter() - start
    avg_latency = elapsed / 50.0
    # Rapordaki hedef 0.85 sn (850 ms); mikroservis içi 50 ms altında olmalıdır
    assert avg_latency < 0.100, f"Ortalama gecikme çok yüksek: {avg_latency*1000:.2f} ms"
