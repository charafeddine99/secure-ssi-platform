import pytest
from fastapi.testclient import TestClient
from standalone_fraud_api import app, FeatureNormalizationPipeline, HybridFraudDetectionEngine

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data


def test_legitimate_authentication_low_risk():
    """
    Legitimate authentication event with 0 failed attempts and normal local IP
    should evaluate to low risk score and is_fraudulent == False.
    """
    payload = {
        "did_id": "did:key:z6MkuLegitUser12345",
        "timestamp": 1726938000,  # ~17:00 UTC (normal business hours)
        "ip_address": "192.168.1.100",
        "device_fingerprint": "device_trusted_macbook_pro_m2",
        "recent_failed_attempts": 0
    }
    response = client.post("/api/fraud_detection", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "risk_score" in data
    assert "is_fraudulent" in data
    assert 0 <= data["risk_score"] <= 100
    assert data["risk_score"] < 40
    assert data["is_fraudulent"] is False
    assert data["did_id"] == payload["did_id"]


def test_high_risk_brute_force_attack():
    """
    Anomalous high-frequency attack with high failed attempts and suspicious proxy IP
    should exceed the security threshold (> 70) and flag is_fraudulent == True.
    """
    payload = {
        "did_id": "did:key:z6MkuVictimAccount999",
        "timestamp": 1726974000,  # 03:00 UTC (unusual middle-of-the-night hour)
        "ip_address": "185.220.101.5",  # High-risk proxy/Tor exit node subnet
        "device_fingerprint": "unseen_linux_curl_headless_fp",
        "recent_failed_attempts": 9
    }
    response = client.post("/api/fraud_detection", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["risk_score"] >= 70
    assert data["is_fraudulent"] is True
    assert any("failed" in r.lower() or "ip" in r.lower() for r in data["reasons"])


def test_validation_error_on_empty_did():
    """
    Empty DID string must be rejected with HTTP 400.
    """
    payload = {
        "did_id": "   ",
        "timestamp": 1726938000,
        "ip_address": "127.0.0.1",
        "device_fingerprint": "fp12345678",
        "recent_failed_attempts": 0
    }
    response = client.post("/api/fraud_detection", json=payload)
    assert response.status_code == 400
    assert "cannot be blank" in response.json()["detail"]


def test_validation_error_on_negative_attempts():
    """
    Negative failed attempt count must be rejected with HTTP 422 or 400.
    """
    payload = {
        "did_id": "did:key:z6MkuTestUser",
        "timestamp": 1726938000,
        "ip_address": "127.0.0.1",
        "device_fingerprint": "fp12345678",
        "recent_failed_attempts": -3
    }
    response = client.post("/api/fraud_detection", json=payload)
    assert response.status_code in [400, 422]


def test_pipeline_normalization_bounds():
    """
    Verify pandas DataFrame extraction and scikit-learn MinMaxScaler scaling.
    All normalized features must reside strictly within [0.0, 1.0].
    """
    pipeline = FeatureNormalizationPipeline()
    norm_df, feature_vec = pipeline.process_and_normalize(
        did_id="did:key:z6MkuTestBounds",
        timestamp=1726938000,
        ip_address="192.168.1.50",
        device_fingerprint="trusted_hw_fp_001",
        recent_failed_attempts=2
    )

    assert norm_df.shape == (1, 6)
    assert len(feature_vec) == 6
    assert all(0.0 <= val <= 1.0 for val in feature_vec)


def test_hybrid_engine_components():
    """
    Verify both the XGBoost supervised probability and Autoencoder reconstruction MSE.
    """
    engine = HybridFraudDetectionEngine()
    import numpy as np
    dummy_features = np.array([0.8, 0.1, 1.0, 0.9, 0.8, 0.85])
    result = engine.evaluate(dummy_features)

    assert "risk_score" in result
    assert "is_fraudulent" in result
    assert "anomaly_score" in result
    assert "reconstruction_mse" in result
    assert result["is_fraudulent"] is True
    assert result["risk_score"] > 70
