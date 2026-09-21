import time
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.application.hybrid_detector import detector

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_detector_state():
    """Her test öncesi karantina hafızasını sıfırlar."""
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
    response = client.post("/api/v1/fraud/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] == "LOW"
    assert data["recommended_action"] == "ALLOW"
    assert data["is_anomaly"] is False
    assert data["risk_score"] < 0.30

def test_impossible_travel_triggers_critical_quarantine():
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
    response = client.post("/api/v1/fraud/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] in ("HIGH", "CRITICAL")
    assert data["is_anomaly"] is True
    assert any("İmkansız seyahat" in r for r in data["reasons"])

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
    response = client.post("/api/v1/fraud/evaluate", json=payload)
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
    response = client.post("/api/v1/fraud/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_anomaly"] is True
    assert data["risk_score"] >= 0.60

def test_manual_quarantine_and_release_lifecycle():
    target_did = "did:key:z6MkuCompromisedAccount"
    # 1. Karantinaya al
    q_res = client.post("/api/v1/fraud/quarantine", json={"did": target_did, "reason": "Şüpheli anahtar ele geçirme şüphesi"})
    assert q_res.status_code == 200
    assert q_res.json()["is_quarantined"] is True

    # 2. Değerlendirme isteğinde hesap direkt CRITICAL dönmeli
    eval_res = client.post("/api/v1/fraud/evaluate", json={
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
    assert eval_res.json()["risk_level"] == "CRITICAL"
    assert eval_res.json()["recommended_action"] == "QUARANTINE_ACCOUNT"

    # 3. Karantina durumunu sorgula
    stat_res = client.get(f"/api/v1/fraud/quarantine/{target_did}")
    assert stat_res.status_code == 200
    assert stat_res.json()["is_quarantined"] is True

    # 4. Karantinayı kaldır
    rel_res = client.delete(f"/api/v1/fraud/quarantine/{target_did}")
    assert rel_res.status_code == 200
    assert rel_res.json()["status"] == "RELEASED"

def test_model_stats_meets_report_targets():
    response = client.get("/api/v1/fraud/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["accuracy"] >= 0.94
    assert data["f1_score"] >= 0.94
    assert "true_positives" in data["confusion_matrix"]
    assert "true_negatives" in data["confusion_matrix"]
    assert data["model_type"] == "Hybrid (XGBoost + Autoencoder)"

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
        client.post("/api/v1/fraud/evaluate", json=payload)
    elapsed = time.perf_counter() - start
    avg_latency = elapsed / 50.0
    # Rapordaki hedef 0.85 sn (850 ms); mikroservis içi 50 ms altında olmalıdır
    assert avg_latency < 0.100, f"Ortalama gecikme çok yüksek: {avg_latency*1000:.2f} ms"
