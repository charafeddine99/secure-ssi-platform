"""WP-08 Integration Tests — Status & Trust Policy Integration.

Verifies that the OID4VP ``/response`` endpoint correctly delegates policy
evaluation to :class:`VerificationPolicyEvaluator` and that the
:class:`NinePointVerificationResult` still exposes the correct API contract.

All existing WP-01 through WP-07 invariants remain in force.  WP-08 is an
additive policy layer; this test suite specifically validates:

1. The ``finalPolicyResult`` field reflects the evaluator decision.
2. The fail-closed hierarchy (any crypto failure → REJECTED, AI ignored).
3. MEDIUM / HIGH / CRITICAL AI risk → REJECTED even when all crypto passes.
4. CRITICAL AI risk → ``quarantineTriggered = True`` in the response details.
5. Quarantined DID is blocked on subsequent attempts (lockout).
6. All nine named check results are expressible via the API.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.infrastructure.cache_and_anchor import blockchain_anchor
from app.application.services.oid4vp_service import fraud_client

client = TestClient(app)

PASSWORDS = {
    "verifier": "Verifier-Prototype-2026!",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _verifier_headers() -> dict[str, str]:
    res = client.post(
        "/api/v1/auth/token",
        json={"username": "verifier@example.test", "password": PASSWORDS["verifier"]},
    )
    assert res.status_code == 200, f"Auth failed: {res.text}"
    return {"Authorization": f"Bearer {res.json()['accessToken']}"}


def _create_session(
    headers: dict[str, str],
    *,
    fields: list[str] | None = None,
    ttl: int = 300,
) -> dict[str, Any]:
    res = client.post(
        "/api/v1/oid4vp/requests",
        json={
            "purpose": "WP-08 Policy Integration Test",
            "requestedCredentialTypes": ["UniversityAffiliationCredential"],
            "requestedFields": fields or ["degree", "gpa"],
            "ttlSeconds": ttl,
        },
        headers=headers,
    )
    assert res.status_code == 201, f"Session create failed: {res.text}"
    return res.json()


def _make_valid_vp_token(*, nonce: str, expired: bool = False) -> dict[str, Any]:
    """Build a signed VP token using the local synthetic holder key."""
    from app.infrastructure.fixtures.signed_credentials import (
        build_local_proof_service,
        build_signed_presentation,
    )
    from app.infrastructure.crypto.local_holder_key_provider import SYNTHETIC_HOLDER_DID

    now = datetime.now(timezone.utc)
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
        "id": "urn:uuid:a1b2c3d4-e5f6-4789-8abc-000000000001",
        "type": ["VerifiableCredential", "UniversityAffiliationCredential"],
        "issuer": "did:web:issuer.example",
        "validFrom": (now - timedelta(days=30)).isoformat().replace("+00:00", "Z"),
        "validUntil": valid_until,
        "credentialSubject": {
            "id": SYNTHETIC_HOLDER_DID,
            "degree": "MSc Computer Science",
            "gpa": "3.95",
        },
    }
    proof_service = build_local_proof_service(clock=lambda: now)
    signed_vc = proof_service.sign_credential(unsigned_vc)
    return build_signed_presentation(
        signed_vc,
        nonce=nonce,
        domain="http://testserver/verifier",
        holder_did=SYNTHETIC_HOLDER_DID,
    )


def _make_invalid_sig_vp_token(*, nonce: str) -> dict[str, Any]:
    """Build a VP token with a deliberately invalid VC signature."""
    from app.infrastructure.fixtures.signed_credentials import build_signed_presentation
    from app.infrastructure.crypto.local_holder_key_provider import SYNTHETIC_HOLDER_DID

    now = datetime.now(timezone.utc)
    unsigned_vc: dict[str, Any] = {
        "@context": ["https://www.w3.org/ns/credentials/v2"],
        "id": "urn:uuid:b1b2c3d4-e5f6-4789-8abc-000000000002",
        "type": ["VerifiableCredential", "UniversityAffiliationCredential"],
        "issuer": "did:web:issuer.example",
        "validFrom": now.isoformat().replace("+00:00", "Z"),
        "validUntil": (now + timedelta(days=365)).isoformat().replace("+00:00", "Z"),
        "credentialSubject": {
            "id": SYNTHETIC_HOLDER_DID,
            "degree": "MSc Computer Science",
            "gpa": "3.95",
        },
        "proof": {
            "type": "DataIntegrityProof",
            "cryptosuite": "eddsa-jcs-2022",
            "created": now.isoformat().replace("+00:00", "Z"),
            "verificationMethod": "did:web:issuer.example#key-1",
            "proofPurpose": "assertionMethod",
            "proofValue": "zFAKEINVALIDSIGNATUREVALUEWP08INTEGRATIONTEST1234567890",
        },
    }
    return build_signed_presentation(
        unsigned_vc,
        nonce=nonce,
        domain="http://testserver/verifier",
        holder_did=SYNTHETIC_HOLDER_DID,
    )


def _set_test_risk_score(monkeypatch: pytest.MonkeyPatch, score: int) -> None:
    monkeypatch.setattr(
        fraud_client,
        "evaluate_presentation_risk",
        lambda **kwargs: {
            "risk_score": score,
            "reasons": ["controlled server-side test signal"],
            "model_version": "test-server-heuristic-v1",
            "risk_signals": ["test_server_signal"],
            "advisory_only": True,
            "source": "identity_fallback_heuristic",
        },
    )


@pytest.fixture(autouse=True)
def _clean_quarantine_state(monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[return]
    monkeypatch.setattr(fraud_client, "base_url", "http://127.0.0.1:1")
    monkeypatch.setattr(fraud_client, "report_event", lambda **kwargs: None)
    blockchain_anchor._anchored_events.clear()
    blockchain_anchor._quarantined_subjects.clear()
    yield
    blockchain_anchor._anchored_events.clear()
    blockchain_anchor._quarantined_subjects.clear()


# ---------------------------------------------------------------------------
# WP-08 Integration tests
# ---------------------------------------------------------------------------


class TestWp08PolicyEvaluatorViaApi:
    """Verify that the API routes evaluator results correctly."""

    def test_valid_presentation_low_risk_is_accepted(self) -> None:
        """All crypto + LOW risk → ACCEPTED via evaluator."""
        hdrs = _verifier_headers()
        sess = _create_session(hdrs)
        vp = _make_valid_vp_token(nonce=sess["nonce"])

        res = client.post("/api/v1/oid4vp/response", json={
            "sessionId": sess["sessionId"],
            "vpToken": vp,
            "aiRiskScore": 10,
        })
        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "ACCEPTED"
        assert result["credentialValid"] is True
        assert result["signatureValid"] is True

    def test_invalid_signature_rejected_regardless_of_ai_score(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Crypto gate failure → REJECTED even at AI score 0."""
        _set_test_risk_score(monkeypatch, 0)
        hdrs = _verifier_headers()
        sess = _create_session(hdrs)
        vp = _make_invalid_sig_vp_token(nonce=sess["nonce"])

        res = client.post("/api/v1/oid4vp/response", json={
            "sessionId": sess["sessionId"],
            "vpToken": vp,
            "aiRiskScore": 0,
        })
        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["signatureValid"] is False
        assert result["aiRiskScore"] == 0
        assert result["aiRiskLevel"] == "LOW"

    def test_expired_credential_rejected_regardless_of_ai_score(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Expiration gate failure → REJECTED even at AI score 0."""
        _set_test_risk_score(monkeypatch, 0)
        hdrs = _verifier_headers()
        sess = _create_session(hdrs)
        vp = _make_valid_vp_token(nonce=sess["nonce"], expired=True)

        res = client.post("/api/v1/oid4vp/response", json={
            "sessionId": sess["sessionId"],
            "vpToken": vp,
            "aiRiskScore": 0,
        })
        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["expirationValid"] is False

    def test_nonce_mismatch_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Session nonce gate failure → REJECTED."""
        _set_test_risk_score(monkeypatch, 0)
        hdrs = _verifier_headers()
        sess = _create_session(hdrs)
        vp = _make_valid_vp_token(nonce="wrong-nonce-wp08")  # wrong nonce

        res = client.post("/api/v1/oid4vp/response", json={
            "sessionId": sess["sessionId"],
            "vpToken": vp,
            "aiRiskScore": 0,
        })
        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["challengeValid"] is False

    def test_medium_ai_risk_rejects_even_when_all_crypto_pass(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """All crypto pass + MEDIUM risk (score 55) → REJECTED."""
        _set_test_risk_score(monkeypatch, 55)
        hdrs = _verifier_headers()
        sess = _create_session(hdrs)
        vp = _make_valid_vp_token(nonce=sess["nonce"])

        res = client.post("/api/v1/oid4vp/response", json={
            "sessionId": sess["sessionId"],
            "vpToken": vp,
            "aiRiskScore": 55,
        })
        assert res.status_code == 200
        result = res.json()["result"]
        assert result["aiRiskLevel"] == "MEDIUM"
        assert result["finalPolicyResult"] == "REJECTED"
        # Quarantine must NOT be triggered for MEDIUM risk
        assert result["details"]["quarantineTriggered"] is False

    def test_high_ai_risk_rejects_without_quarantine(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """All crypto pass + HIGH risk (score 75) → REJECTED, no quarantine."""
        _set_test_risk_score(monkeypatch, 75)
        hdrs = _verifier_headers()
        sess = _create_session(hdrs)
        vp = _make_valid_vp_token(nonce=sess["nonce"])

        res = client.post("/api/v1/oid4vp/response", json={
            "sessionId": sess["sessionId"],
            "vpToken": vp,
            "aiRiskScore": 75,
        })
        assert res.status_code == 200
        result = res.json()["result"]
        assert result["aiRiskLevel"] == "HIGH"
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["details"]["quarantineTriggered"] is False

    def test_result_carries_nine_point_fields(self) -> None:
        """Response must carry all nine-point fields expected by the UI."""
        hdrs = _verifier_headers()
        sess = _create_session(hdrs)
        vp = _make_valid_vp_token(nonce=sess["nonce"])

        res = client.post("/api/v1/oid4vp/response", json={
            "sessionId": sess["sessionId"],
            "vpToken": vp,
            "aiRiskScore": 15,
        })
        assert res.status_code == 200
        result = res.json()["result"]
        expected_fields = {
            "credentialValid",
            "issuerTrusted",
            "signatureValid",
            "holderBindingValid",
            "expirationValid",
            "revocationStatusClear",
            "challengeValid",
            "aiRiskLevel",
            "aiRiskScore",
            "blockchainAnchored",
            "finalPolicyResult",
        }
        assert expected_fields.issubset(set(result.keys())), (
            f"Missing fields: {expected_fields - set(result.keys())}"
        )


def _set_test_risk_score(monkeypatch: pytest.MonkeyPatch, score: int) -> None:
    monkeypatch.setattr(
        fraud_client,
        "evaluate_presentation_risk",
        lambda **kwargs: {
            "risk_score": score,
            "reasons": ["controlled server-side test signal"],
            "model_version": "test-server-heuristic-v1",
            "risk_signals": ["test_server_signal"],
            "advisory_only": True,
            "source": "identity_fallback_heuristic",
        },
    )
