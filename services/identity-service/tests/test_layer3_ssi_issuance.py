import pytest
from fastapi.testclient import TestClient
from ssi_layer3_service import app, blockchain_manager, EMERGENCY_RECOVERY_ADDRESS

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["blockchain_connected"] is True


def test_successful_credential_issuance_low_risk():
    """
    Legitimate user verification with 0 failed attempts and trusted network.
    AI evaluates low risk (<= 70), SSI service issues W3C JSON-LD VC.
    """
    payload = {
        "wallet_address": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
        "did_id": "did:key:z6MkuLegitStudent999",
        "ip_address": "192.168.1.100",
        "device_fingerprint": "device_trusted_macbook_pro",
        "recent_failed_attempts": 0
    }

    response = client.post("/api/issue_credential", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "SUCCESS"
    assert data["risk_score"] <= 70

    # Validate W3C JSON-LD structure
    vc = data["verifiable_credential"]
    assert "@context" in vc
    assert "https://www.w3.org/2018/credentials/v1" in vc["@context"]
    assert "VerifiableCredential" in vc["type"]
    assert vc["credentialSubject"]["id"] == payload["did_id"]
    assert vc["credentialSubject"]["walletAddress"] == payload["wallet_address"]

    # Validate Linked Data Proof
    assert "proof" in vc
    assert vc["proof"]["type"] == "Ed25519Signature2020"
    assert "proofValue" in vc["proof"]


def test_high_risk_rejection_and_blockchain_quarantine():
    """
    Attack simulation with 8 failed attempts and suspicious proxy IP.
    AI evaluates risk > 70.
    SSI service MUST reject with HTTP 403 and immediately submit an on-chain
    quarantine transaction to EmergencyRecovery.sol contract.
    """
    target_wallet = "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC"  # Hardhat Account #2

    payload = {
        "wallet_address": target_wallet,
        "did_id": "did:key:z6MkuAttackerCompromisedAccount",
        "ip_address": "185.220.101.5",  # Suspicious IP
        "device_fingerprint": "unseen_linux_curl_headless_attacker",
        "recent_failed_attempts": 8  # Explicit requirement: 8 failed attempts
    }

    response = client.post("/api/issue_credential", json=payload)

    # Must be rejected with HTTP 403 Forbidden
    assert response.status_code == 403
    data = response.json()

    assert data["error"] == "CREDENTIAL_ISSUANCE_REJECTED"
    assert data["risk_score"] > 70
    assert data["is_fraudulent"] is True

    # Validate Blockchain Quarantine execution
    quarantine_info = data["blockchain_quarantine"]
    assert quarantine_info["contract_address"].lower() == EMERGENCY_RECOVERY_ADDRESS.lower()
    assert quarantine_info["quarantined_wallet"].lower() == target_wallet.lower()
    assert quarantine_info["transaction_hash"].startswith("0x")
    assert quarantine_info["on_chain_quarantined"] is True

    # Query the live blockchain smart contract directly to verify state
    on_chain_status = blockchain_manager.check_is_quarantined(target_wallet)
    assert on_chain_status is True, "Target wallet must be locked/quarantined on the EmergencyRecovery contract!"
