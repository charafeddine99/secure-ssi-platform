"""Sprint 15 Integration Tests — OID4VP 9-Point Verification Matrix & Adaptive AI Policy Engine.

Master Implementation Plan Section 13, 14, 15:
1. Dynamic AI evaluation via Fraud Client.
2. Strict Cryptographic Failure Hierarchy invariant (AI cannot override cryptographic/status failure).
3. Critical risk (score >= 85) triggers automatic quarantine and logs WALLET_LOCKED audit event.
4. Quarantined DIDs are immediately locked out from subsequent presentation verification.
5. Adaptive policy states: LOW (ALLOW), MEDIUM (STEP_UP / REJECT), HIGH/CRITICAL (REJECT + QUARANTINE).
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.infrastructure.cache_and_anchor import blockchain_anchor
from app.application.services.oid4vp_service import fraud_client
from app.api.v1 import dependencies
from app.domain.oid4vp import ConsentAction, ConsentDecision
client = TestClient(app)

PASSWORDS = {
    "admin": "Admin-Prototype-2026!",
    "issuer": "Issuer-Prototype-2026!",
    "verifier": "Verifier-Prototype-2026!",
    "holder": "Holder-Prototype-2026!",
}

def _get_headers(c: TestClient, role: str) -> dict[str, str]:
    res = c.post(
        "/api/v1/auth/token",
        json={"username": f"{role}@example.test", "password": PASSWORDS[role]},
    )
    assert res.status_code == 200, f"Auth failed for {role}: {res.text}"
    token = res.json()["accessToken"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def clean_state(monkeypatch: pytest.MonkeyPatch):
    # Keep these API tests isolated from a mutable host Fraud Service and its
    # persistent quarantine state. The fallback case below still exercises the
    # real client behavior against an intentionally unreachable local port.
    monkeypatch.setattr(fraud_client, "base_url", "http://127.0.0.1:1")
    monkeypatch.setattr(fraud_client, "report_event", lambda **kwargs: None)
    blockchain_anchor._anchored_events.clear()
    blockchain_anchor._quarantined_subjects.clear()
    yield
    blockchain_anchor._anchored_events.clear()
    blockchain_anchor._quarantined_subjects.clear()


def _create_mock_vp_token(
    *,
    subject_did: str | None = None,
    issuer_did: str = "did:web:issuer.example",
    expired: bool = False,
    invalid_signature: bool = False,
    nonce: str = "fresh-session-nonce-12345",
    private_key: Any | None = None,
) -> dict[str, Any]:
    from app.infrastructure.fixtures.signed_credentials import (
        build_local_proof_service,
        build_signed_presentation,
    )
    from app.infrastructure.crypto.local_holder_key_provider import SYNTHETIC_HOLDER_DID

    effective_subject_did = subject_did or SYNTHETIC_HOLDER_DID
    now = datetime.now(timezone.utc)
    valid_from = (now - timedelta(days=30)).isoformat().replace("+00:00", "Z")
    valid_until = (
        (now - timedelta(days=2)).isoformat().replace("+00:00", "Z")
        if expired
        else (now + timedelta(days=365)).isoformat().replace("+00:00", "Z")
    )

    unsigned_vc: dict[str, Any] = {
        "@context": [
            "https://www.w3.org/ns/credentials/v2",
            "https://secure-ssi.example/contexts/university-affiliation/v1",
        ],
        "id": "urn:uuid:00000000-0000-4000-8000-000000000001",
        "type": [
            "VerifiableCredential",
            "UniversityAffiliationCredential",
        ],
        "issuer": issuer_did,
        "validFrom": valid_from,
        "validUntil": valid_until,
        "credentialSubject": {
            "id": effective_subject_did,
            "affiliation": "student",
            "programCode": "SYN-CS-001",
            "degree": "Bachelor of Science",
            "graduationYear": 2026,
        },
    }

    if invalid_signature:
        signed_vc: dict[str, Any] = dict(unsigned_vc)
        proof_payload: dict[str, Any] = {
            "@context": list(unsigned_vc["@context"]),
            "type": "DataIntegrityProof",
            "cryptosuite": "eddsa-jcs-2022",
            "created": now.isoformat().replace("+00:00", "Z"),
            "verificationMethod": f"{issuer_did}#key-1",
            "proofPurpose": "assertionMethod",
            "proofValue": "zInvalidSignatureValueThatFailsCryptoVerification1234567890",
        }
        signed_vc["proof"] = proof_payload
    else:
        proof_service = build_local_proof_service(clock=lambda: now)
        signed_vc = proof_service.sign_credential(unsigned_vc)

    return build_signed_presentation(
        signed_vc,
        nonce=nonce,
        domain="http://testserver/verifier",
        holder_did=effective_subject_did,
        private_key=private_key,
    )


def _record_test_consent(session_id: str, vp_token: dict[str, Any]) -> None:
    """Persist the explicit synthetic Holder decision required by OID4VP."""
    manager = dependencies.get_mongo_connection_manager()
    sessions = dependencies.get_verification_session_repository(manager=manager)
    stored = sessions.get_by_session_id(session_id)
    assert stored is not None
    credential = vp_token["verifiableCredential"][0]
    subject = credential["credentialSubject"]
    sessions.record_consent(
        stored.session_id,
        consent_decision=ConsentDecision(
            session_id=stored.session_id,
            verifier_did=stored.verifier_did,
            client_id=stored.client_id,
            purpose=stored.purpose,
            nonce=stored.nonce,
            holder_did=vp_token["holder"],
            decision=ConsentAction.APPROVE,
            approved_credentials=(credential["id"],),
            requested_claims=stored.requested_fields,
            approved_claims={key: value for key, value in subject.items() if key != "id"},
            expires_at=stored.expires_at,
        ),
        expected_version=stored.version,
    )


def _set_server_risk_score(monkeypatch: pytest.MonkeyPatch, score: int) -> None:
    """Control the server evaluator in tests; request JSON is never the score source."""
    monkeypatch.setattr(
        fraud_client,
        "evaluate_presentation_risk",
        lambda **kwargs: {
            "risk_score": score,
            "reasons": ["controlled server-side test signal"],
            "model_version": "test-server-heuristic-v1",
            "risk_signals": ["test_server_signal"],
            "advisory_only": True,
            "source": "fraud_service",
        },
    )



def test_crypto_failure_hierarchy_zero_ai_risk_cannot_override_bad_signature(monkeypatch):
    """Hierarchy Invariant: Even if AI risk score is 0, invalid signature MUST be REJECTED."""
    _set_server_risk_score(monkeypatch, 0)
    # 1. Create session
    verifier_hdrs = _get_headers(client, "verifier")
    req_res = client.post("/api/v1/oid4vp/requests", json={
        "purpose": "Academic Evaluation Matrix Test",
        "requestedCredentialTypes": ["UniversityAffiliationCredential"],
        "requestedFields": ["degree", "programCode"],
        "ttlSeconds": 300,
    }, headers=verifier_hdrs)
    assert req_res.status_code == 201
    session_id = req_res.json()["sessionId"]
    nonce = req_res.json()["nonce"]

    # 2. Present with invalid proof/signature but 0 AI risk score
    vp_token = _create_mock_vp_token(invalid_signature=True, nonce=nonce)
    post_res = client.post("/api/v1/oid4vp/response", json={
        "sessionId": session_id,
        "vpToken": vp_token,
        "aiRiskScore": 0,
    })
    assert post_res.status_code == 200
    res = post_res.json()["result"]

    assert res["signatureValid"] is False
    assert res["aiRiskScore"] == 0
    assert res["aiRiskLevel"] == "LOW"
    assert res["finalPolicyResult"] == "REJECTED", "AI score 0 must not override signature failure"


def test_crypto_failure_hierarchy_zero_ai_risk_cannot_override_expiration(monkeypatch):
    """Hierarchy Invariant: Even if AI risk score is 0, expired credential MUST be REJECTED."""
    _set_server_risk_score(monkeypatch, 0)
    verifier_hdrs = _get_headers(client, "verifier")
    req_res = client.post("/api/v1/oid4vp/requests", json={
        "purpose": "Expiration Hierarchy Test",
        "requestedCredentialTypes": ["UniversityAffiliationCredential"],
        "requestedFields": ["degree"],
        "ttlSeconds": 300,
    }, headers=verifier_hdrs)
    session_id = req_res.json()["sessionId"]
    nonce = req_res.json()["nonce"]

    vp_token = _create_mock_vp_token(expired=True, nonce=nonce)
    post_res = client.post("/api/v1/oid4vp/response", json={
        "sessionId": session_id,
        "vpToken": vp_token,
        "aiRiskScore": 0,
    })
    assert post_res.status_code == 200
    res = post_res.json()["result"]

    assert res["expirationValid"] is False
    assert res["aiRiskScore"] == 0
    assert res["finalPolicyResult"] == "REJECTED"


def test_crypto_failure_hierarchy_zero_ai_risk_cannot_override_nonce_mismatch(monkeypatch):
    """Hierarchy Invariant: Replay prevention nonce mismatch must reject regardless of AI score."""
    _set_server_risk_score(monkeypatch, 0)
    verifier_hdrs = _get_headers(client, "verifier")
    req_res = client.post("/api/v1/oid4vp/requests", json={
        "purpose": "Replay Nonce Test",
        "requestedCredentialTypes": ["UniversityAffiliationCredential"],
        "requestedFields": ["degree"],
        "ttlSeconds": 300,
    }, headers=verifier_hdrs)
    session_id = req_res.json()["sessionId"]

    # Replay token with old or different nonce
    vp_token = _create_mock_vp_token(nonce="wrong-stale-replay-nonce")
    post_res = client.post("/api/v1/oid4vp/response", json={
        "sessionId": session_id,
        "vpToken": vp_token,
        "aiRiskScore": 0,
    })
    assert post_res.status_code == 200
    res = post_res.json()["result"]

    assert res["challengeValid"] is False
    assert res["finalPolicyResult"] == "REJECTED"


def test_adaptive_policy_low_risk_acceptance(monkeypatch):
    """Valid cryptographic checks + LOW AI risk (< 40) => ACCEPTED."""
    _set_server_risk_score(monkeypatch, 15)
    verifier_hdrs = _get_headers(client, "verifier")
    req_res = client.post("/api/v1/oid4vp/requests", json={
        "purpose": "Legitimate User Test",
        "requestedCredentialTypes": ["UniversityAffiliationCredential"],
        "requestedFields": ["degree", "programCode"],
        "ttlSeconds": 300,
    }, headers=verifier_hdrs)
    session_id = req_res.json()["sessionId"]
    nonce = req_res.json()["nonce"]

    vp_token = _create_mock_vp_token(nonce=nonce)
    _record_test_consent(session_id, vp_token)
    post_res = client.post("/api/v1/oid4vp/response", json={
        "sessionId": session_id,
        "vpToken": vp_token,
        "aiRiskScore": 15,
        "disclosedClaims": {"degree": "Bachelor of Science"},
    })
    assert post_res.status_code == 200
    res = post_res.json()["result"]

    assert res["credentialValid"] is True
    assert res["signatureValid"] is True
    assert res["aiRiskLevel"] == "LOW"
    assert res["finalPolicyResult"] == "ACCEPTED"
    assert res["details"]["quarantineTriggered"] is False


def test_adaptive_policy_medium_risk_step_up_required(monkeypatch):
    """Valid cryptographic checks + MEDIUM AI risk (40-69) => REJECTED (requires step up)."""
    _set_server_risk_score(monkeypatch, 55)
    verifier_hdrs = _get_headers(client, "verifier")
    req_res = client.post("/api/v1/oid4vp/requests", json={
        "purpose": "Step-up Auth Test",
        "requestedCredentialTypes": ["UniversityAffiliationCredential"],
        "requestedFields": ["degree"],
        "ttlSeconds": 300,
    }, headers=verifier_hdrs)
    session_id = req_res.json()["sessionId"]
    nonce = req_res.json()["nonce"]

    vp_token = _create_mock_vp_token(nonce=nonce)
    post_res = client.post("/api/v1/oid4vp/response", json={
        "sessionId": session_id,
        "vpToken": vp_token,
        "aiRiskScore": 55,
    })
    assert post_res.status_code == 200
    res = post_res.json()["result"]

    assert res["aiRiskLevel"] == "MEDIUM"
    assert res["finalPolicyResult"] == "REJECTED"


def test_adaptive_policy_critical_risk_triggers_auto_quarantine_and_lockout(monkeypatch):
    """Valid cryptographic checks + CRITICAL AI risk (>= 85) => REJECTED + Auto-Quarantine."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    from app.infrastructure.crypto.multibase import encode_base58_btc
    from app.infrastructure.crypto.local_holder_key_provider import ED25519_MULTICODEC_PREFIX

    _set_server_risk_score(monkeypatch, 95)
    attacker_priv = Ed25519PrivateKey.generate()
    pub_bytes = attacker_priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    multibase = encode_base58_btc(ED25519_MULTICODEC_PREFIX + pub_bytes)
    subject_did = f"did:key:{multibase}"

    verifier_hdrs = _get_headers(client, "verifier")
    # Step 1: Attempt presentation with critical attack telemetry
    req_res = client.post("/api/v1/oid4vp/requests", json={
        "purpose": "Attack Presentation Test",
        "requestedCredentialTypes": ["UniversityAffiliationCredential"],
        "requestedFields": ["degree"],
        "ttlSeconds": 300,
    }, headers=verifier_hdrs)
    session_id = req_res.json()["sessionId"]
    nonce = req_res.json()["nonce"]

    vp_token = _create_mock_vp_token(subject_did=subject_did, nonce=nonce, private_key=attacker_priv)
    _record_test_consent(session_id, vp_token)
    post_res = client.post("/api/v1/oid4vp/response", json={
        "sessionId": session_id,
        "vpToken": vp_token,
        "aiRiskScore": 95,  # Critical brute-force / impossible travel score
    })
    assert post_res.status_code == 200
    res = post_res.json()["result"]

    assert res["aiRiskLevel"] == "CRITICAL"
    assert res["finalPolicyResult"] == "REJECTED"
    assert res["details"]["quarantineTriggered"] is True

    # Verify local quarantine state and receipt-backed optional digest status separately.
    assert blockchain_anchor.is_quarantined(subject_did) is True
    anchor_state = res["details"]["quarantineAnchor"]
    assert anchor_state["status"] in {"CONFIRMED", "FAILED", "OFFLINE", "SUBMITTED", "UNANCHORED"}
    if anchor_state["status"] == "CONFIRMED":
        assert anchor_state["txHash"].startswith("0x")
        assert anchor_state["blockNumber"] is not None
    else:
        assert anchor_state["txHash"] is None

    # Step 2: Subsequent presentation attempt by the same quarantined DID must be locked out
    req_res2 = client.post("/api/v1/oid4vp/requests", json={
        "purpose": "Subsequent Attack Attempt",
        "requestedCredentialTypes": ["UniversityAffiliationCredential"],
        "requestedFields": ["degree"],
        "ttlSeconds": 300,
    }, headers=verifier_hdrs)
    session_id2 = req_res2.json()["sessionId"]
    nonce2 = req_res2.json()["nonce"]

    _set_server_risk_score(monkeypatch, 0)
    vp_token2 = _create_mock_vp_token(subject_did=subject_did, nonce=nonce2, private_key=attacker_priv)
    post_res2 = client.post("/api/v1/oid4vp/response", json={
        "sessionId": session_id2,
        "vpToken": vp_token2,
        "aiRiskScore": 0,  # Attacker tries low score now
    })
    assert post_res2.status_code == 200
    res2 = post_res2.json()["result"]

    assert res2["finalPolicyResult"] == "REJECTED"
    assert "quarantine" in res2["details"]["evaluations"]["revocation"].lower()


def test_dynamic_ai_risk_service_outage_is_explicit_and_fail_closed(monkeypatch):
    """An unavailable risk dependency never becomes a synthetic LOW decision."""
    from app.application.services.oid4vp_service import fraud_client
    from app.infrastructure.clients.fraud_client import FraudRiskUnavailableError

    def unavailable(**_kwargs):
        raise FraudRiskUnavailableError("RISK_UNAVAILABLE")

    monkeypatch.setattr(fraud_client, "evaluate_presentation_risk", unavailable)
    verifier_hdrs = _get_headers(client, "verifier")
    req_res = client.post("/api/v1/oid4vp/requests", json={
        "purpose": "Dynamic Evaluation Test",
        "requestedCredentialTypes": ["UniversityAffiliationCredential"],
        "requestedFields": ["degree"],
        "ttlSeconds": 300,
    }, headers=verifier_hdrs)
    session_id = req_res.json()["sessionId"]
    nonce = req_res.json()["nonce"]

    # Client-supplied telemetry and scores must not control the server evaluator.
    vp_token = _create_mock_vp_token(nonce=nonce)
    _record_test_consent(session_id, vp_token)
    post_res = client.post("/api/v1/oid4vp/response", json={
        "sessionId": session_id,
        "vpToken": vp_token,
        "aiRiskScore": 95,
        "failedAttempts": 5,
        "isTorOrProxy": True,
        "presentationFrequency10m": 20,
    })
    assert post_res.status_code == 200
    res = post_res.json()["result"]

    assert res["credentialValid"] is True
    assert res["signatureValid"] is True
    assert res["aiRiskScore"] is None
    assert res["aiRiskLevel"] == "UNAVAILABLE"
    assert res["finalPolicyResult"] == "REJECTED"
    risk_evidence = res["details"]["aiRisk"]
    assert risk_evidence["source"] == "fraud_service"
    assert risk_evidence["status"] == "UNAVAILABLE"
    assert risk_evidence["reason"] == "RISK_UNAVAILABLE"
    assert risk_evidence["score"] is None
    assert res["details"]["evaluations"]["ai_fraud"].startswith(
        "Risk assessment unavailable"
    )
    assert risk_evidence["advisoryOnly"] is True


def test_client_supplied_risk_score_and_telemetry_are_ignored(monkeypatch):
    """Direct Post cannot select a low score or spoof server-side behavior signals."""
    captured: dict[str, Any] = {}

    def evaluate(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {
            "risk_score": 15,
            "reasons": [],
            "model_version": "test-server-heuristic-v1",
            "risk_signals": ["server_signal"],
            "advisory_only": True,
            "source": "fraud_service",
        }

    monkeypatch.setattr(fraud_client, "evaluate_presentation_risk", evaluate)
    verifier_hdrs = _get_headers(client, "verifier")
    req_res = client.post(
        "/api/v1/oid4vp/requests",
        json={
            "purpose": "Untrusted risk input test",
            "requestedCredentialTypes": ["UniversityAffiliationCredential"],
            "requestedFields": ["degree"],
            "ttlSeconds": 300,
        },
        headers=verifier_hdrs,
    )
    assert req_res.status_code == 201
    vp_token = _create_mock_vp_token(nonce=req_res.json()["nonce"])

    response = client.post(
        "/api/v1/oid4vp/response",
        headers={"User-Agent": "trusted-test-client/1.0"},
        json={
            "sessionId": req_res.json()["sessionId"],
            "vpToken": vp_token,
            "aiRiskScore": 0,
            "clientIp": "127.0.0.1",
            "userAgent": "forged-client-agent",
            "deviceFingerprint": "forged-trusted-device",
            "deviceFingerprintMatch": True,
            "isTorOrProxy": False,
            "failedAttempts": 0,
            "geoDistanceKm": 0,
            "timeSinceLastActionSec": 999999,
            "presentationFrequency10m": 1,
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()["result"]
    assert result["aiRiskScore"] == 15
    assert result["aiRiskLevel"] == "LOW"
    assert result["details"]["aiRisk"]["modelVersion"] == "test-server-heuristic-v1"
    assert captured["client_ip"] == "testclient"
    assert captured["user_agent"] == "trusted-test-client/1.0"
    assert captured["failed_attempts"] == 0
    assert captured["is_tor_or_proxy"] is False
    assert captured["geo_distance_km"] == 0
    assert captured["time_since_last_action_sec"] == 0
    assert captured["presentation_frequency_10m"] == 1
    assert captured["device_fingerprint"] is None
    assert captured["device_fingerprint_match"] is True
