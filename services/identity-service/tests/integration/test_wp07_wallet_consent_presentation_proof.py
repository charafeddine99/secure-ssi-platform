from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.infrastructure.crypto.local_holder_key_provider import SYNTHETIC_HOLDER_DID
from app.infrastructure.fixtures.signed_credentials import (
    build_local_proof_service,
    build_signed_presentation,
)

client = TestClient(app)

PASSWORDS = {
    "holder": "Holder-Prototype-2026!",
    "verifier": "Verifier-Prototype-2026!",
}


def _get_verifier_token() -> str:
    res = client.post(
        "/api/v1/auth/token",
        json={"username": "verifier@example.test", "password": PASSWORDS["verifier"]},
    )
    assert res.status_code == 200, f"Verifier auth failed: {res.text}"
    return res.json()["accessToken"]


def _build_signed_vc(
    *,
    credential_type: str = "UniversityAffiliationCredential",
    claims: dict[str, Any] | None = None,
    holder_did: str = SYNTHETIC_HOLDER_DID,
    issuer_did: str = "did:web:issuer.example",
) -> dict[str, Any]:
    now = datetime.now(UTC)
    raw_vc = {
        "@context": [
            "https://www.w3.org/ns/credentials/v2",
            "https://secure-ssi.example/contexts/university-affiliation/v1",
        ],
        "id": f"urn:uuid:{uuid.uuid4()}",
        "type": ["VerifiableCredential", credential_type],
        "issuer": issuer_did,
        "validFrom": (now - timedelta(days=10)).isoformat().replace("+00:00", "Z"),
        "validUntil": (now + timedelta(days=365)).isoformat().replace("+00:00", "Z"),
        "credentialSubject": {
            "id": holder_did,
            "affiliation": "student",
            "programCode": "SYN-CS-2026",
            "degree": "Master of Science",
            "graduationYear": 2026,
            **(claims or {}),
        },
    }
    proof_service = build_local_proof_service(clock=lambda: now)
    return proof_service.sign_credential(raw_vc)


def _create_oid4vp_session(
    *,
    purpose: str = "Verification of academic affiliation and degree",
    requested_fields: list[str] | None = None,
    ttl_seconds: int = 600,
) -> dict[str, Any]:
    token = _get_verifier_token()
    headers = {"Authorization": f"Bearer {token}"}
    fields = requested_fields or ["affiliation", "degree", "programCode", "graduationYear"]
    res = client.post(
        "/api/v1/oid4vp/requests",
        json={
            "purpose": purpose,
            "requestedCredentialTypes": ["UniversityAffiliationCredential"],
            "requestedFields": fields,
            "ttlSeconds": ttl_seconds,
        },
        headers=headers,
    )
    assert res.status_code == 201, f"Failed to create session: {res.text}"
    return res.json()


# ==============================================================================
# SECTION A: INTEGRATION GOLDEN PATH & REJECTION JOURNEY
# ==============================================================================


def test_wp07_golden_path_consent_claim_minimization_and_real_presentation_proof():
    """
    Real End-to-End Golden Path:
    1. Verifier creates OID4VP request session with DCQL.
    2. Holder evaluates candidate credentials against session DCQL.
    3. Holder explicitly APPROVES a minimized claim subset and rejects others.
    4. Wallet records authoritative domain consent bound to session & nonce.
    5. Real cryptographic presentation is constructed with DataIntegrityProof eddsa-jcs-2022.
    6. Verifier receives Direct Post and verifies 9 points + consent compliance.
    7. Unapproved claim is omitted from final payload without breaking cryptography.
    """
    session_data = _create_oid4vp_session(requested_fields=["affiliation", "degree"])
    session_id = session_data["sessionId"]
    nonce = session_data["nonce"]
    verifier_did = session_data["verifierDid"]
    client_id = session_data["clientId"]
    purpose = session_data["purpose"]

    # Step 2: Holder evaluates candidate credentials with DCQL
    stored_vc = _build_signed_vc()
    eval_res = client.post(
        f"/api/v1/oid4vp/requests/{session_id}/evaluate-dcql",
        json={"candidateCredentials": [stored_vc]},
    )
    assert eval_res.status_code == 200
    assert eval_res.json()["isSatisfied"] is True

    # Step 3 & 4: Holder records explicit domain consent with claim minimization
    # Approved: affiliation, degree. Omitted/Rejected: programCode, graduationYear
    approved_claims = {
        "affiliation": "student",
        "degree": "Master of Science",
    }
    rejected_claims = ["programCode", "graduationYear"]

    consent_res = client.post(
        f"/api/v1/oid4vp/requests/{session_id}/consent",
        json={
            "decision": "APPROVE",
            "holderDid": SYNTHETIC_HOLDER_DID,
            "approvedCredentials": [stored_vc["id"]],
            "approvedClaims": approved_claims,
            "rejectedClaims": rejected_claims,
            "verifierDid": verifier_did,
            "clientId": client_id,
            "nonce": nonce,
            "purpose": purpose,
        },
    )
    assert consent_res.status_code == 200, f"Consent record failed: {consent_res.text}"
    c_data = consent_res.json()
    assert c_data["consentStatus"] == "APPROVED"
    assert c_data["decision"] == "APPROVE"
    assert "degree" in c_data["approvedClaims"]

    # Step 5: Presentation construction bound to consent
    pres_res = client.post(
        "/api/v1/oid4vp/presentation",
        json={
            "sessionId": session_id,
            "disclosedClaims": approved_claims,
            "holderDid": SYNTHETIC_HOLDER_DID,
            "verifiableCredentials": [stored_vc],
        },
    )
    assert pres_res.status_code == 200, f"Presentation creation failed: {pres_res.text}"
    vp_token = pres_res.json()["vpToken"]

    # Invariant: Unapproved claims MUST NOT appear in the presented credentialSubject
    vc_in_vp = vp_token["verifiableCredential"][0]
    subject = vc_in_vp["credentialSubject"]
    assert "degree" in subject
    assert "affiliation" in subject
    assert "graduationYear" not in subject, "Unapproved claim 'graduationYear' leaked into payload!"
    assert "programCode" not in subject, "Unapproved claim 'programCode' leaked into payload!"

    # Real presentation proof exists
    vp_proof = vp_token["proof"]
    assert vp_proof["type"] == "DataIntegrityProof"
    assert vp_proof["cryptosuite"] == "eddsa-jcs-2022"
    assert vp_proof["proofPurpose"] == "authentication"
    assert vp_proof["challenge"] == nonce
    assert vp_proof["proofValue"] != "zMockHolderPresentationProofValue2026"

    # Step 6: Verifier receives presentation via Direct Post
    post_res = client.post(
        "/api/v1/oid4vp/response",
        json={
            "sessionId": session_id,
            "vpToken": vp_token,
            "disclosedClaims": approved_claims,
            "aiRiskScore": 10,
        },
    )
    assert post_res.status_code == 200, f"Direct post failed: {post_res.text}"
    result = post_res.json()["result"]

    assert result["credentialValid"] is True
    assert result["issuerTrusted"] is True
    assert result["signatureValid"] is True
    assert result["holderBindingValid"] is True
    assert result["expirationValid"] is True
    assert result["revocationStatusClear"] is True
    assert result["challengeValid"] is True
    assert result["details"]["dcql"]["satisfied"] is True
    assert result["finalPolicyResult"] == "ACCEPTED"
    assert result["details"]["evaluations"]["consent"] == "Authorized by holder consent"
    assert result["details"]["dataMinimization"]["status"] in ("FULL_DISCLOSURE", "SELECTIVE_DISCLOSURE_APPLIED")

    # Session status verified
    poll_res = client.get(f"/api/v1/oid4vp/requests/{session_id}")
    assert poll_res.status_code == 200
    assert poll_res.json()["status"] == "VERIFIED"


def test_wp07_denial_journey_explicit_holder_rejection():
    """
    Explicit Holder Rejection Path:
    1. Verifier creates request session.
    2. Holder reviews and explicitly REJECTS presentation consent.
    3. Session status transitions to REJECTED.
    4. Presentation creation is blocked (409 Conflict).
    5. Direct post submission is blocked (409 Conflict).
    6. Verifier polls session and sees explicit truthful REJECTED status.
    """
    session_data = _create_oid4vp_session()
    session_id = session_data["sessionId"]
    nonce = session_data["nonce"]

    # Holder rejects consent
    reject_res = client.post(
        f"/api/v1/oid4vp/requests/{session_id}/consent",
        json={
            "decision": "REJECT",
            "holderDid": SYNTHETIC_HOLDER_DID,
            "rejectedClaims": ["affiliation", "degree"],
            "rejectionReason": "Holder declined sharing academic attributes",
            "nonce": nonce,
        },
    )
    assert reject_res.status_code == 200
    r_data = reject_res.json()
    assert r_data["status"] == "REJECTED"
    assert r_data["consentStatus"] == "REJECTED"

    # Attempting to construct presentation for rejected session must fail
    pres_res = client.post(
        "/api/v1/oid4vp/presentation",
        json={
            "sessionId": session_id,
            "disclosedClaims": {"degree": "Master of Science"},
            "holderDid": SYNTHETIC_HOLDER_DID,
        },
    )
    assert pres_res.status_code == 409

    # Attempting direct post on rejected session must fail
    stored_vc = _build_signed_vc()
    vp = build_signed_presentation(
        stored_vc,
        nonce=nonce,
        domain=session_data.get("clientId", "http://testserver/verifier"),
        holder_did=SYNTHETIC_HOLDER_DID,
    )
    post_res = client.post(
        "/api/v1/oid4vp/response",
        json={"sessionId": session_id, "vpToken": vp, "aiRiskScore": 10},
    )
    assert post_res.status_code == 409

    # Verifier sees truthful rejection
    poll_res = client.get(f"/api/v1/oid4vp/requests/{session_id}")
    assert poll_res.status_code == 200
    poll_data = poll_res.json()
    assert poll_data["status"] == "REJECTED"
    assert poll_data["consentStatus"] == "REJECTED"


# ==============================================================================
# SECTION B: SECURITY NEGATIVE TESTS (SECTION 18 MATRIX)
# ==============================================================================


def test_wp07_security_negative_rejected_claim_in_payload_fails_closed():
    """Negative Test: If rejected claim leaks into presented credential, verification rejects."""
    session_data = _create_oid4vp_session()
    session_id = session_data["sessionId"]
    nonce = session_data["nonce"]
    client_id = session_data.get("clientId", "http://testserver/verifier")

    stored_vc = _build_signed_vc()

    # Holder approves 'affiliation', explicitly rejects 'degree'
    client.post(
        f"/api/v1/oid4vp/requests/{session_id}/consent",
        json={
            "decision": "APPROVE",
            "holderDid": SYNTHETIC_HOLDER_DID,
            "approvedCredentials": [stored_vc["id"]],
            "approvedClaims": {"affiliation": "student"},
            "rejectedClaims": ["degree"],
        },
    )

    # Malicious or buggy client still includes 'degree' in target VC credentialSubject
    vp = build_signed_presentation(
        stored_vc,  # contains degree
        nonce=nonce,
        domain=client_id,
        holder_did=SYNTHETIC_HOLDER_DID,
    )

    post_res = client.post(
        "/api/v1/oid4vp/response",
        json={
            "sessionId": session_id,
            "vpToken": vp,
            "disclosedClaims": {"affiliation": "student", "degree": "Master of Science"},
            "aiRiskScore": 10,
        },
    )
    assert post_res.status_code == 200
    res_data = post_res.json()["result"]
    assert res_data["finalPolicyResult"] == "REJECTED"
    assert "rejected by holder consent" in res_data["details"]["evaluations"]["consent"]


def test_wp07_security_negative_forged_unapproved_claim_in_presentation_creation():
    """Negative Test: Client requests presentation with claims not authorized in recorded consent."""
    session_data = _create_oid4vp_session()
    session_id = session_data["sessionId"]

    stored_vc = _build_signed_vc()

    # Consent only approves 'affiliation'
    client.post(
        f"/api/v1/oid4vp/requests/{session_id}/consent",
        json={
            "decision": "APPROVE",
            "holderDid": SYNTHETIC_HOLDER_DID,
            "approvedCredentials": [stored_vc["id"]],
            "approvedClaims": {"affiliation": "student"},
            "rejectedClaims": ["degree"],
        },
    )

    # Client attempts to generate presentation disclosing 'degree'
    pres_res = client.post(
        "/api/v1/oid4vp/presentation",
        json={
            "sessionId": session_id,
            "disclosedClaims": {"affiliation": "student", "degree": "Master of Science"},
            "holderDid": SYNTHETIC_HOLDER_DID,
        },
    )
    assert pres_res.status_code == 400
    assert "not authorized by holder consent" in pres_res.text


def test_wp07_security_negative_cross_session_consent_tamper_fails():
    """Negative Test: Consent recorded with wrong nonce or verifier fails binding validation."""
    session_data = _create_oid4vp_session()
    session_id = session_data["sessionId"]

    # Mismatched nonce
    res_nonce = client.post(
        f"/api/v1/oid4vp/requests/{session_id}/consent",
        json={
            "decision": "APPROVE",
            "holderDid": SYNTHETIC_HOLDER_DID,
            "approvedCredentials": ["cred_1"],
            "approvedClaims": {"affiliation": "student"},
            "nonce": "forged_nonce_999999",
        },
    )
    assert res_nonce.status_code == 400
    assert "Nonce mismatch" in res_nonce.text

    # Mismatched verifier_did
    res_verifier = client.post(
        f"/api/v1/oid4vp/requests/{session_id}/consent",
        json={
            "decision": "APPROVE",
            "holderDid": SYNTHETIC_HOLDER_DID,
            "approvedCredentials": ["cred_1"],
            "approvedClaims": {"affiliation": "student"},
            "verifierDid": "did:web:attacker.example",
        },
    )
    assert res_verifier.status_code == 400
    assert "Verifier DID mismatch" in res_verifier.text

    # Mismatched purpose
    res_purpose = client.post(
        f"/api/v1/oid4vp/requests/{session_id}/consent",
        json={
            "decision": "APPROVE",
            "holderDid": SYNTHETIC_HOLDER_DID,
            "approvedCredentials": ["cred_1"],
            "approvedClaims": {"affiliation": "student"},
            "purpose": "A completely different purpose",
        },
    )
    assert res_purpose.status_code == 400
    assert "Purpose mismatch" in res_purpose.text


def test_wp07_security_negative_expired_session_consent_denied():
    """Negative Test: Consent cannot be recorded for an expired session."""
    session_data = _create_oid4vp_session(ttl_seconds=1)
    session_id = session_data["sessionId"]

    # Wait or mock expiry
    from app.main import app
    from app.api.v1.dependencies import get_oid4vp_service
    service = app.dependency_overrides.get(get_oid4vp_service, None)

    from app.api.v1.dependencies import get_mongo_connection_manager
    manager = get_mongo_connection_manager()
    past_created = datetime.now(UTC) - timedelta(minutes=10)
    past_expires = datetime.now(UTC) - timedelta(minutes=5)
    manager.database["verification_sessions"].update_one(
        {"sessionId": session_id},
        {"$set": {"createdAt": past_created, "expiresAt": past_expires}},
    )

    res = client.post(
        f"/api/v1/oid4vp/requests/{session_id}/consent",
        json={
            "decision": "APPROVE",
            "holderDid": SYNTHETIC_HOLDER_DID,
            "approvedCredentials": ["cred_1"],
            "approvedClaims": {"affiliation": "student"},
        },
    )
    assert res.status_code == 410, f"Expected 410 Gone, got: {res.status_code} - {res.text}"


def test_wp07_security_negative_reused_consent_after_consumption():
    """Negative Test: Consent cannot be modified or re-recorded after session is verified."""
    session_data = _create_oid4vp_session()
    session_id = session_data["sessionId"]
    nonce = session_data["nonce"]
    client_id = session_data.get("clientId", "http://testserver/verifier")

    stored_vc = _build_signed_vc()

    # Step 1: Record consent
    client.post(
        f"/api/v1/oid4vp/requests/{session_id}/consent",
        json={
            "decision": "APPROVE",
            "holderDid": SYNTHETIC_HOLDER_DID,
            "approvedCredentials": [stored_vc["id"]],
            "approvedClaims": {"affiliation": "student"},
        },
    )

    # Step 2: Submit valid presentation -> Session consumed
    pres_res = client.post(
        "/api/v1/oid4vp/presentation",
        json={
            "sessionId": session_id,
            "disclosedClaims": {"affiliation": "student"},
            "holderDid": SYNTHETIC_HOLDER_DID,
        },
    )
    assert pres_res.status_code == 200
    vp_token = pres_res.json()["vpToken"]

    post_res = client.post(
        "/api/v1/oid4vp/response",
        json={"sessionId": session_id, "vpToken": vp_token, "aiRiskScore": 10},
    )
    assert post_res.status_code == 200

    # Step 3: Try recording consent again on consumed session -> 409 Conflict
    re_consent = client.post(
        f"/api/v1/oid4vp/requests/{session_id}/consent",
        json={
            "decision": "APPROVE",
            "holderDid": SYNTHETIC_HOLDER_DID,
            "approvedCredentials": [stored_vc["id"]],
            "approvedClaims": {"affiliation": "student"},
        },
    )
    assert re_consent.status_code == 409


def test_wp07_security_negative_tampered_holder_presentation_proof_fails():
    """Negative Test: Tampered DataIntegrityProof on VerifiablePresentation fails holder binding."""
    session_data = _create_oid4vp_session()
    session_id = session_data["sessionId"]
    nonce = session_data["nonce"]

    # Record consent
    client.post(
        f"/api/v1/oid4vp/requests/{session_id}/consent",
        json={
            "decision": "APPROVE",
            "holderDid": SYNTHETIC_HOLDER_DID,
            "approvedCredentials": ["cred_1"],
            "approvedClaims": {"affiliation": "student"},
        },
    )

    pres_res = client.post(
        "/api/v1/oid4vp/presentation",
        json={
            "sessionId": session_id,
            "disclosedClaims": {"affiliation": "student"},
            "holderDid": SYNTHETIC_HOLDER_DID,
        },
    )
    assert pres_res.status_code == 200
    vp_token = pres_res.json()["vpToken"]

    # Tamper presentation proofValue
    vp_token["proof"]["proofValue"] = "z2TamperedProofValue999999999999999999999999999999"

    post_res = client.post(
        "/api/v1/oid4vp/response",
        json={"sessionId": session_id, "vpToken": vp_token, "aiRiskScore": 10},
    )
    assert post_res.status_code == 200
    res_data = post_res.json()["result"]
    assert res_data["holderBindingValid"] is False
    assert res_data["finalPolicyResult"] == "REJECTED"


def test_wp07_security_negative_empty_credential_selection_rejected():
    """Negative Test: Consent cannot be approved without selecting at least one credential."""
    session_data = _create_oid4vp_session()
    session_id = session_data["sessionId"]

    res = client.post(
        f"/api/v1/oid4vp/requests/{session_id}/consent",
        json={
            "decision": "APPROVE",
            "holderDid": SYNTHETIC_HOLDER_DID,
            "approvedCredentials": [],  # Empty
            "approvedClaims": {"affiliation": "student"},
        },
    )
    assert res.status_code == 400
    assert "At least one credential must be selected" in res.text


def test_wp07_security_negative_simultaneously_approved_and_rejected_claim():
    """Negative Test: A claim cannot be simultaneously approved and rejected."""
    session_data = _create_oid4vp_session()
    session_id = session_data["sessionId"]

    res = client.post(
        f"/api/v1/oid4vp/requests/{session_id}/consent",
        json={
            "decision": "APPROVE",
            "holderDid": SYNTHETIC_HOLDER_DID,
            "approvedCredentials": ["cred_1"],
            "approvedClaims": {"degree": "Master of Science"},
            "rejectedClaims": ["degree"],  # Contradiction
        },
    )
    assert res.status_code == 400
    assert "simultaneously approved and rejected" in res.text


def test_wp07_privacy_audit_log_contains_no_raw_claims_or_private_keys():
    """Privacy Invariant: Verify audit records for consent & presentation do NOT log raw claims or keys."""
    from app.api.v1.dependencies import get_audit_event_repository

    session_data = _create_oid4vp_session()
    session_id = session_data["sessionId"]

    client.post(
        f"/api/v1/oid4vp/requests/{session_id}/consent",
        json={
            "decision": "APPROVE",
            "holderDid": SYNTHETIC_HOLDER_DID,
            "approvedCredentials": ["cred_1"],
            "approvedClaims": {"degree": "Confidential Degree Data", "affiliation": "student"},
            "rejectedClaims": ["programCode"],
        },
    )

    from app.api.v1.dependencies import get_mongo_connection_manager, get_audit_event_repository
    manager = get_mongo_connection_manager()
    audit_repo = get_audit_event_repository(manager=manager)
    events = audit_repo.list_by_subject(session_id)
    assert len(events) > 0

    for ev in events:
        # Check metadata does not leak sensitive raw claim strings
        meta_str = str(ev.metadata)
        assert "Confidential Degree Data" not in meta_str, f"Audit event leaked raw claim value: {meta_str}"
        assert "private_key" not in meta_str.lower()
        assert "d_multibase" not in meta_str.lower()
