"""WP-01 Negative-Test Hardening & Fail-Closed Invariant Verification.

Work Package: WP-01 (Fail-Closed Verification Foundation)
Primary Gaps:
- GAP-01: OID4VP nonce/challenge replay bypass
- GAP-03: Signature verification exception catch-all fallback
- Expiration timestamp parsing fail-closed

This suite verifies that any missing, malformed, expired, mismatched, or exceptional
security input strictly produces a negative verification outcome (fail-closed).
Never convert an exception or missing security proof into verified=True.
"""

from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime, timedelta
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.infrastructure.fixtures.signed_credentials import build_local_proof_service
from app.domain.oid4vp import VerificationSessionStatus

client = TestClient(app)

PASSWORDS = {
    "admin": "Admin-Prototype-2026!",
    "issuer": "Issuer-Prototype-2026!",
    "verifier": "Verifier-Prototype-2026!",
    "holder": "Holder-Prototype-2026!",
}


def _get_verifier_token() -> str:
    res = client.post(
        "/api/v1/auth/token",
        json={"username": "verifier@example.test", "password": PASSWORDS["verifier"]},
    )
    assert res.status_code == 200, f"Auth failed: {res.text}"
    return res.json()["accessToken"]


def _create_oid4vp_session(token: str, *, ttl_seconds: int = 600) -> tuple[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    req_payload = {
        "purpose": "WP-01 Fail-Closed Verification Test",
        "requestedCredentialTypes": ["UniversityAffiliationCredential"],
        "requestedFields": ["degree", "gpa"],
        "ttlSeconds": ttl_seconds,
    }
    res = client.post("/api/v1/oid4vp/requests", json=req_payload, headers=headers)
    assert res.status_code == 201, f"Create session failed: {res.text}"
    data = res.json()
    return data["sessionId"], data["nonce"]


def _build_valid_signed_vc(*, expired: bool = False) -> dict:
    now = datetime.now(UTC)
    valid_from = (now - timedelta(days=30)).isoformat().replace("+00:00", "Z")
    if expired:
        valid_until = (now - timedelta(days=2)).isoformat().replace("+00:00", "Z")
    else:
        valid_until = (now + timedelta(days=365)).isoformat().replace("+00:00", "Z")

    raw_vc = {
        "@context": [
            "https://www.w3.org/ns/credentials/v2",
            "https://secure-ssi.example/contexts/university-affiliation/v1",
        ],
        "id": f"urn:uuid:{uuid.uuid4()}",
        "type": ["VerifiableCredential", "UniversityAffiliationCredential"],
        "issuer": "did:web:issuer.example",
        "validFrom": valid_from,
        "validUntil": valid_until,
        "credentialSubject": {
            "id": "did:key:z6Mkf5rGMoatrSj1f4CyvuHBeXJELe9RPdzo2PKGNCKVtZxP",
            "degree": "MSc Computer Science",
            "gpa": "3.95",
        },
    }
    proof_service = build_local_proof_service(clock=lambda: now)
    return proof_service.sign_credential(raw_vc)


# ==============================================================================
# GAP-01: Challenge / Nonce / Replay / Session Binding Negative Tests
# ==============================================================================


def test_gap01_missing_nonce_fails_closed():
    """A presentation lacking a nonce must fail challenge validation."""
    token = _get_verifier_token()
    session_id, nonce = _create_oid4vp_session(token)
    vc = _build_valid_signed_vc()

    # VP proof has no nonce
    vp_token = {
        "type": ["VerifiablePresentation"],
        "verifiableCredential": [vc],
        "proof": {
            "type": "DataIntegrityProof",
            "proofValue": "zMockProof",
        },
    }
    res = client.post("/api/v1/oid4vp/response", json={"sessionId": session_id, "vpToken": vp_token})
    assert res.status_code == 200
    result = res.json()["result"]
    assert result["challengeValid"] is False, "Missing nonce must never pass"
    assert result["finalPolicyResult"] == "REJECTED"


def test_gap01_mismatched_nonce_fails_closed():
    """A presentation submitting a nonce differing from session.nonce must fail."""
    token = _get_verifier_token()
    session_id, nonce = _create_oid4vp_session(token)
    vc = _build_valid_signed_vc()

    vp_token = {
        "type": ["VerifiablePresentation"],
        "verifiableCredential": [vc],
        "proof": {
            "type": "DataIntegrityProof",
            "nonce": "completely-different-nonce-99999",
            "proofValue": "zMockProof",
        },
    }
    res = client.post("/api/v1/oid4vp/response", json={"sessionId": session_id, "vpToken": vp_token})
    assert res.status_code == 200
    result = res.json()["result"]
    assert result["challengeValid"] is False, "Mismatched nonce must never pass"
    assert result["finalPolicyResult"] == "REJECTED"


def test_gap01_missing_proof_object_fails_closed():
    """A presentation with missing or non-dict proof must fail challenge validation."""
    token = _get_verifier_token()
    session_id, nonce = _create_oid4vp_session(token)
    vc = _build_valid_signed_vc()

    vp_token = {
        "type": ["VerifiablePresentation"],
        "verifiableCredential": [vc],
        # No 'proof' object
    }
    res = client.post("/api/v1/oid4vp/response", json={"sessionId": session_id, "vpToken": vp_token})
    assert res.status_code == 200
    result = res.json()["result"]
    assert result["challengeValid"] is False, "Missing proof must fail challenge check"
    assert result["finalPolicyResult"] == "REJECTED"


def test_gap01_non_existent_session_returns_404():
    """Submitting a presentation against an unknown session must return 404."""
    vc = _build_valid_signed_vc()
    vp_token = {
        "type": ["VerifiablePresentation"],
        "verifiableCredential": [vc],
        "proof": {
            "type": "DataIntegrityProof",
            "nonce": "any-nonce",
            "proofValue": "zMockProof",
        },
    }
    res = client.post("/api/v1/oid4vp/response", json={"sessionId": "session_nonexistent_12345", "vpToken": vp_token})
    assert res.status_code == 404


def test_gap01_expired_session_fails_verification():
    """An expired verification session must reject responses with 410 Gone."""
    token = _get_verifier_token()
    # Create session with 1 second TTL
    session_id, nonce = _create_oid4vp_session(token, ttl_seconds=1)
    vc = _build_valid_signed_vc()

    # Manually expire session in repository to simulate timeout
    from dataclasses import replace
    from app.api.v1.dependencies import get_verification_session_repository, get_mongo_connection_manager
    manager = get_mongo_connection_manager()
    session_repo = get_verification_session_repository(manager)
    session = session_repo.get_by_session_id(session_id)
    assert session is not None
    # Set created_at and expires_at in the past
    past_created = datetime.now(UTC) - timedelta(minutes=10)
    past_expires = datetime.now(UTC) - timedelta(minutes=5)
    session_repo._collection.update_one(
        {"sessionId": session_id},
        {"$set": {"createdAt": past_created, "expiresAt": past_expires}},
    )


    vp_token = {
        "type": ["VerifiablePresentation"],
        "verifiableCredential": [vc],
        "proof": {
            "type": "DataIntegrityProof",
            "nonce": nonce,
            "proofValue": "zMockProof",
        },
    }
    res = client.post("/api/v1/oid4vp/response", json={"sessionId": session_id, "vpToken": vp_token})
    assert res.status_code == 410, "Expired session must return 410 Gone"


def test_gap01_replayed_presentation_fails_closed():
    """A replayed presentation against an already-consumed/verified session must be rejected."""
    token = _get_verifier_token()
    session_id, nonce = _create_oid4vp_session(token)
    vc = _build_valid_signed_vc()

    vp_token = {
        "type": ["VerifiablePresentation"],
        "verifiableCredential": [vc],
        "proof": {
            "type": "DataIntegrityProof",
            "nonce": nonce,
            "proofValue": "zMockProof",
        },
    }
    # First submission: success
    res1 = client.post("/api/v1/oid4vp/response", json={"sessionId": session_id, "vpToken": vp_token, "aiRiskScore": 10})
    assert res1.status_code == 200
    assert res1.json()["result"]["finalPolicyResult"] == "ACCEPTED"

    # Second submission (replay): must be rejected (409 Conflict or 400 Already Consumed)
    res2 = client.post("/api/v1/oid4vp/response", json={"sessionId": session_id, "vpToken": vp_token, "aiRiskScore": 10})
    assert res2.status_code == 409, "Replaying to a consumed session must return 409"


# ==============================================================================
# GAP-03: Signature Verification Fail-Closed Negative Tests
# ==============================================================================


def test_gap03_tampered_payload_fails_signature_verification():
    """Tampering with credentialSubject after signing must fail signature verification."""
    token = _get_verifier_token()
    session_id, nonce = _create_oid4vp_session(token)
    vc = _build_valid_signed_vc()

    # Attacker tampers with the subject claims
    tampered_vc = copy.deepcopy(vc)
    tampered_vc["credentialSubject"]["gpa"] = "4.00"  # Modified claim

    vp_token = {
        "type": ["VerifiablePresentation"],
        "verifiableCredential": [tampered_vc],
        "proof": {
            "type": "DataIntegrityProof",
            "nonce": nonce,
            "proofValue": "zMockProof",
        },
    }
    res = client.post("/api/v1/oid4vp/response", json={"sessionId": session_id, "vpToken": vp_token, "aiRiskScore": 5})
    assert res.status_code == 200
    result = res.json()["result"]
    assert result["signatureValid"] is False, "Tampered payload must fail signature verification"
    assert result["finalPolicyResult"] == "REJECTED"


def test_gap03_altered_proof_value_fails_signature_verification():
    """Altering the proofValue signature bytes must fail signature verification."""
    token = _get_verifier_token()
    session_id, nonce = _create_oid4vp_session(token)
    vc = _build_valid_signed_vc()

    # Corrupt the signature multibase
    corrupted_vc = copy.deepcopy(vc)
    orig_val = corrupted_vc["proof"]["proofValue"]
    # Flip last character
    flipped = orig_val[:-1] + ("A" if orig_val[-1] != "A" else "B")
    corrupted_vc["proof"]["proofValue"] = flipped

    vp_token = {
        "type": ["VerifiablePresentation"],
        "verifiableCredential": [corrupted_vc],
        "proof": {
            "type": "DataIntegrityProof",
            "nonce": nonce,
            "proofValue": "zMockProof",
        },
    }
    res = client.post("/api/v1/oid4vp/response", json={"sessionId": session_id, "vpToken": vp_token, "aiRiskScore": 5})
    assert res.status_code == 200
    result = res.json()["result"]
    assert result["signatureValid"] is False, "Altered signature must fail verification"
    assert result["finalPolicyResult"] == "REJECTED"


def test_gap03_missing_proof_object_fails_signature_verification():
    """A credential missing the proof block entirely must fail signature verification."""
    token = _get_verifier_token()
    session_id, nonce = _create_oid4vp_session(token)
    vc = _build_valid_signed_vc()

    unproven_vc = copy.deepcopy(vc)
    del unproven_vc["proof"]

    vp_token = {
        "type": ["VerifiablePresentation"],
        "verifiableCredential": [unproven_vc],
        "proof": {
            "type": "DataIntegrityProof",
            "nonce": nonce,
            "proofValue": "zMockProof",
        },
    }
    res = client.post("/api/v1/oid4vp/response", json={"sessionId": session_id, "vpToken": vp_token, "aiRiskScore": 5})
    assert res.status_code == 200
    result = res.json()["result"]
    assert result["signatureValid"] is False, "Missing proof must fail signature check"
    assert result["finalPolicyResult"] == "REJECTED"


def test_gap03_unsupported_proof_cryptosuite_fails_signature_verification():
    """A credential with an unsupported or unknown cryptosuite must fail signature verification."""
    token = _get_verifier_token()
    session_id, nonce = _create_oid4vp_session(token)
    vc = _build_valid_signed_vc()

    legacy_vc = copy.deepcopy(vc)
    legacy_vc["proof"]["type"] = "Ed25519Signature2020"
    legacy_vc["proof"].pop("cryptosuite", None)

    vp_token = {
        "type": ["VerifiablePresentation"],
        "verifiableCredential": [legacy_vc],
        "proof": {
            "type": "DataIntegrityProof",
            "nonce": nonce,
            "proofValue": "zMockProof",
        },
    }
    res = client.post("/api/v1/oid4vp/response", json={"sessionId": session_id, "vpToken": vp_token, "aiRiskScore": 5})
    assert res.status_code == 200
    result = res.json()["result"]
    assert result["signatureValid"] is False, "Unsupported proof suite must fail fail-closed"
    assert result["finalPolicyResult"] == "REJECTED"


def test_gap03_structural_proof_without_valid_signature_never_passes():
    """Structural presence of proofValue without valid cryptographic verification must NEVER pass."""
    token = _get_verifier_token()
    session_id, nonce = _create_oid4vp_session(token)

    fake_vc = {
        "@context": ["https://www.w3.org/ns/credentials/v2"],
        "id": f"urn:uuid:{uuid.uuid4()}",
        "type": ["VerifiableCredential", "UniversityAffiliationCredential"],
        "issuer": "did:web:attacker.example",
        "validFrom": "2026-01-01T00:00:00Z",
        "validUntil": "2027-01-01T00:00:00Z",
        "credentialSubject": {
            "id": "did:key:z6Mkf5rGMoatrSj1f4CyvuHBeXJELe9RPdzo2PKGNCKVtZxP",
            "degree": "MSc Computer Science",
        },
        "proof": {
            "type": "DataIntegrityProof",
            "cryptosuite": "eddsa-jcs-2022",
            "created": "2026-06-01T00:00:00Z",
            "verificationMethod": "did:web:attacker.example#key-1",
            "proofPurpose": "assertionMethod",
            "proofValue": "zFakeProofValueThatLooksValidStructurally123456789",
        },
    }

    vp_token = {
        "type": ["VerifiablePresentation"],
        "verifiableCredential": [fake_vc],
        "proof": {
            "type": "DataIntegrityProof",
            "nonce": nonce,
            "proofValue": "zMockProof",
        },
    }
    res = client.post("/api/v1/oid4vp/response", json={"sessionId": session_id, "vpToken": vp_token, "aiRiskScore": 0})
    assert res.status_code == 200
    result = res.json()["result"]
    assert result["signatureValid"] is False, "Structural presence alone must NOT pass"
    assert result["finalPolicyResult"] == "REJECTED"


# ==============================================================================
# Expiration Parsing Fail-Closed Tests
# ==============================================================================


def test_malformed_valid_until_fails_closed():
    """A malformed validUntil timestamp string must fail expiration check fail-closed."""
    token = _get_verifier_token()
    session_id, nonce = _create_oid4vp_session(token)
    vc = _build_valid_signed_vc()
    vc["validUntil"] = "NOT-A-VALID-ISO-DATE-STRING"

    vp_token = {
        "type": ["VerifiablePresentation"],
        "verifiableCredential": [vc],
        "proof": {
            "type": "DataIntegrityProof",
            "nonce": nonce,
            "proofValue": "zMockProof",
        },
    }
    res = client.post("/api/v1/oid4vp/response", json={"sessionId": session_id, "vpToken": vp_token, "aiRiskScore": 0})
    assert res.status_code == 200
    result = res.json()["result"]
    assert result["expirationValid"] is False, "Malformed timestamp must fail expiration check"
    assert result["finalPolicyResult"] == "REJECTED"


def test_expired_credential_fails_closed():
    """An expired credential must fail expiration check."""
    token = _get_verifier_token()
    session_id, nonce = _create_oid4vp_session(token)
    vc = _build_valid_signed_vc(expired=True)

    vp_token = {
        "type": ["VerifiablePresentation"],
        "verifiableCredential": [vc],
        "proof": {
            "type": "DataIntegrityProof",
            "nonce": nonce,
            "proofValue": "zMockProof",
        },
    }
    res = client.post("/api/v1/oid4vp/response", json={"sessionId": session_id, "vpToken": vp_token, "aiRiskScore": 0})
    assert res.status_code == 200
    result = res.json()["result"]
    assert result["expirationValid"] is False, "Expired credential must fail expiration check"
    assert result["finalPolicyResult"] == "REJECTED"


# ==============================================================================
# Positive Golden Path Verification Test
# ==============================================================================


def test_positive_golden_path_verification_succeeds():
    """A completely valid signed credential and matching nonce must succeed with ACCEPTED."""
    token = _get_verifier_token()
    session_id, nonce = _create_oid4vp_session(token)
    vc = _build_valid_signed_vc(expired=False)

    vp_token = {
        "type": ["VerifiablePresentation"],
        "verifiableCredential": [vc],
        "proof": {
            "type": "DataIntegrityProof",
            "nonce": nonce,
            "proofValue": "zMockProof",
        },
    }
    res = client.post(
        "/api/v1/oid4vp/response",
        json={
            "sessionId": session_id,
            "vpToken": vp_token,
            "disclosedClaims": {"degree": "MSc Computer Science"},
            "aiRiskScore": 10,
        },
    )
    assert res.status_code == 200
    result = res.json()["result"]
    assert result["credentialValid"] is True
    assert result["issuerTrusted"] is True
    assert result["signatureValid"] is True
    assert result["holderBindingValid"] is True
    assert result["expirationValid"] is True
    assert result["challengeValid"] is True
    assert result["revocationStatusClear"] is True
    assert result["aiRiskLevel"] == "LOW"
    assert result["finalPolicyResult"] == "ACCEPTED"
