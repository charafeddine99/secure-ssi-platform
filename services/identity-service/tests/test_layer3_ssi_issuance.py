"""Regression tests for the retired pre-WP-08 Identity Service prototype."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from ssi_layer3_service import app, blockchain_manager

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "retired"
    assert data["supported"] is False
    assert data["replacement"] == "Identity Service app.main:app"


def test_successful_credential_issuance_low_risk():
    """The retired service rejects issuance instead of issuing synthetic VCs."""
    response = client.post(
        "/api/issue_credential",
        json={"did_id": "did:key:synthetic", "claims": {"label": "demo"}},
    )
    assert response.status_code == 410
    assert response.json()["error"] == "LEGACY_IDENTITY_SERVICE_RETIRED"


def test_high_risk_rejection_and_blockchain_quarantine():
    """The retired service cannot trigger a direct address/reason chain write."""
    payload = {
        "wallet_address": "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
        "did_id": "did:key:synthetic-attacker",
        "ip_address": "192.0.2.10",
        "device_fingerprint": "synthetic-test-fixture",
        "recent_failed_attempts": 8,
    }

    with patch.object(blockchain_manager, "quarantine_wallet") as quarantine:
        response = client.post("/api/issue_credential", json=payload)
        assert response.status_code == 410
        assert response.json()["error"] == "LEGACY_IDENTITY_SERVICE_RETIRED"
        quarantine.assert_not_called()

    manual = client.post(
        "/api/quarantine_wallet",
        json={"wallet_address": payload["wallet_address"], "reason": "synthetic test"},
    )
    assert manual.status_code == 410
    assert manual.json()["error"] == "LEGACY_IDENTITY_SERVICE_RETIRED"
