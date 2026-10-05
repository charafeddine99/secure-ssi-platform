from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.infrastructure.fixtures.signed_credentials import (
    build_local_proof_service,
    build_signed_presentation,
)
from app.infrastructure.crypto.local_holder_key_provider import (
    SYNTHETIC_HOLDER_DID,
    SYNTHETIC_HOLDER_KEY_REFERENCE,
    LocalHolderKeyProvider,
)
from app.domain.trust_registry import TrustRole, TrustStatus
from app.api.v1.dependencies import (
    get_trust_registry_service,
    get_mongo_connection_manager,
    get_trust_registry_repository,
)

client = TestClient(app)

PASSWORDS = {
    "admin": "Admin-Prototype-2026!",
    "issuer": "Issuer-Prototype-2026!",
    "verifier": "Verifier-Prototype-2026!",
    "holder": "Holder-Prototype-2026!",
}


def _get_token(role: str) -> str:
    res = client.post(
        "/api/v1/auth/token",
        json={"username": f"{role}@example.test", "password": PASSWORDS[role]},
    )
    assert res.status_code == 200, f"Auth failed for {role}: {res.text}"
    return res.json()["accessToken"]


def _create_oid4vp_session(token: str) -> tuple[str, str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    req_payload = {
        "purpose": "WP-03 Trust Registry Verification Test",
        "requestedCredentialTypes": ["UniversityAffiliationCredential"],
        "requestedFields": ["degree", "gpa"],
        "ttlSeconds": 600,
    }
    res = client.post("/api/v1/oid4vp/requests", json=req_payload, headers=headers)
    assert res.status_code == 201, f"Create session failed: {res.text}"
    data = res.json()
    return data["sessionId"], data["nonce"], data.get("clientId", "http://testserver/verifier")


def _build_signed_vc_with_issuer(issuer_did: str, *, cred_type: str = "UniversityAffiliationCredential") -> dict[str, Any]:
    now = datetime.now(UTC)
    raw_vc = {
        "@context": [
            "https://www.w3.org/ns/credentials/v2",
            "https://secure-ssi.example/contexts/university-affiliation/v1",
        ],
        "id": f"urn:uuid:{uuid.uuid4()}",
        "type": ["VerifiableCredential", cred_type],
        "issuer": issuer_did,
        "validFrom": (now - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
        "validUntil": (now + timedelta(days=365)).isoformat().replace("+00:00", "Z"),
        "credentialSubject": {
            "id": SYNTHETIC_HOLDER_DID,
            "degree": "Computer Science",
            "gpa": "3.85",
        },
    }
    if issuer_did == "did:web:issuer.example":
        proof_svc = build_local_proof_service()
        return proof_svc.sign_credential(raw_vc)
    else:
        raw_vc["proof"] = {
            "type": "DataIntegrityProof",
            "cryptosuite": "eddsa-jcs-2022",
            "created": now.isoformat().replace("+00:00", "Z"),
            "verificationMethod": f"{issuer_did}#key-1",
            "proofPurpose": "assertionMethod",
            "proofValue": "zMockProofValueForUntrustedIssuer",
        }
        return raw_vc


# ==============================================================================
# 1. Trust Lookup & Format Tests
# ==============================================================================

def test_exact_registered_issuer_is_trusted() -> None:
    admin_token = _get_token("admin")
    did = "did:web:exact-test-uni.example"
    
    # Register issuer
    res = client.post(
        "/api/v1/trust-registry/issuers",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "issuerDid": did,
            "organizationName": "Exact Test University",
            "permittedCredentialTypes": ["VerifiableCredential", "UniversityAffiliationCredential"],
            "validDays": 30,
        },
    )
    assert res.status_code == 201, f"Register failed: {res.text}"

    # Evaluate
    eval_res = client.post(
        "/api/v1/trust-registry/evaluate",
        json={"issuerDid": did, "credentialTypes": ["UniversityAffiliationCredential"]},
    )
    assert eval_res.status_code == 200
    data = eval_res.json()
    assert data["isTrusted"] is True
    assert data["status"] == "active"
    assert data["reason"] == "ISSUER_TRUST_VALID"


def test_unknown_issuer_is_untrusted_fail_closed() -> None:
    eval_res = client.post(
        "/api/v1/trust-registry/evaluate",
        json={"issuerDid": "did:web:unknown-rogue-issuer.org"},
    )
    assert eval_res.status_code == 200
    data = eval_res.json()
    assert data["isTrusted"] is False
    assert data["reason"] == "ISSUER_NOT_IN_TRUST_REGISTRY"


def test_similar_did_with_wrong_suffix_is_untrusted() -> None:
    admin_token = _get_token("admin")
    registered_did = "did:web:test-hospital.example"
    client.post(
        "/api/v1/trust-registry/issuers",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "issuerDid": registered_did,
            "organizationName": "Test Hospital",
            "permittedCredentialTypes": ["VerifiableCredential"],
        },
    )

    # Attempt similar DIDs (substring, suffix, prefix attacks)
    for attack_did in [
        f"{registered_did}:fake",
        f"{registered_did}/path",
        "did:web:test-hospital.example.attacker.com",
    ]:
        eval_res = client.post(
            "/api/v1/trust-registry/evaluate",
            json={"issuerDid": attack_did},
        )
        assert eval_res.status_code == 200
        assert eval_res.json()["isTrusted"] is False, f"Expected {attack_did} to be untrusted"


def test_malformed_did_fails_closed() -> None:
    for malformed in ["", "not-a-did", "http://example.com", "did:", "   "]:
        eval_res = client.post(
            "/api/v1/trust-registry/evaluate",
            json={"issuerDid": malformed},
        )
        assert eval_res.status_code == 200
        data = eval_res.json()
        assert data["isTrusted"] is False
        assert data["reason"] in ("MALFORMED_ISSUER_DID", "ISSUER_NOT_IN_TRUST_REGISTRY")


# ==============================================================================
# 2. Lifecycle Tests (Active, Suspended, Revoked, Expired)
# ==============================================================================

def test_suspended_trust_record_is_untrusted() -> None:
    admin_token = _get_token("admin")
    did = "did:web:suspension-test.example"
    
    # Register
    reg_res = client.post(
        "/api/v1/trust-registry/issuers",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "issuerDid": did,
            "organizationName": "Suspension Test Entity",
        },
    )
    assert reg_res.status_code == 201
    record_id = reg_res.json()["id"]

    # Verify active
    eval_1 = client.post("/api/v1/trust-registry/evaluate", json={"issuerDid": did})
    assert eval_1.json()["isTrusted"] is True

    # Suspend
    suspend_res = client.post(
        f"/api/v1/trust-registry/issuers/{record_id}/suspend",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reason": "Security investigation underway"},
    )
    assert suspend_res.status_code == 200
    assert suspend_res.json()["trustStatus"] == "suspended"

    # Evaluate suspended -> untrusted
    eval_2 = client.post("/api/v1/trust-registry/evaluate", json={"issuerDid": did})
    assert eval_2.json()["isTrusted"] is False
    assert eval_2.json()["reason"] == "ISSUER_TRUST_SUSPENDED"


def test_revoked_trust_record_is_untrusted() -> None:
    admin_token = _get_token("admin")
    did = "did:web:revocation-test.example"
    
    # Register
    reg_res = client.post(
        "/api/v1/trust-registry/issuers",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"issuerDid": did, "organizationName": "Revocation Test Entity"},
    )
    record_id = reg_res.json()["id"]

    # Revoke
    rev_res = client.post(
        f"/api/v1/trust-registry/issuers/{record_id}/revoke",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reason": "Compromised key infrastructure"},
    )
    assert rev_res.status_code == 200
    assert rev_res.json()["trustStatus"] == "revoked"

    # Evaluate revoked -> untrusted
    eval_res = client.post("/api/v1/trust-registry/evaluate", json={"issuerDid": did})
    assert eval_res.json()["isTrusted"] is False
    assert eval_res.json()["reason"] == "ISSUER_TRUST_REVOKED"


def test_expired_trust_record_is_untrusted() -> None:
    manager = get_mongo_connection_manager()
    repo = get_trust_registry_repository(manager)
    svc = get_trust_registry_service(repo)

    did = "did:web:expired-trust.example"
    past = datetime.now(UTC) - timedelta(days=60)
    expired = datetime.now(UTC) - timedelta(days=10)

    # Register with past validity
    svc.register_trusted_issuer(
        actor_id="admin@example.test",
        issuer_did=did,
        organization_name="Expired Institution",
        valid_from=past,
        valid_until=expired,
    )

    eval_res = client.post("/api/v1/trust-registry/evaluate", json={"issuerDid": did})
    assert eval_res.json()["isTrusted"] is False
    assert eval_res.json()["reason"] == "ISSUER_TRUST_EXPIRED"


def test_not_yet_valid_trust_record_is_untrusted() -> None:
    manager = get_mongo_connection_manager()
    repo = get_trust_registry_repository(manager)
    svc = get_trust_registry_service(repo)

    did = "did:web:future-trust.example"
    future_start = datetime.now(UTC) + timedelta(days=10)
    future_end = datetime.now(UTC) + timedelta(days=365)

    svc.register_trusted_issuer(
        actor_id="admin@example.test",
        issuer_did=did,
        organization_name="Future Institution",
        valid_from=future_start,
        valid_until=future_end,
    )

    eval_res = client.post("/api/v1/trust-registry/evaluate", json={"issuerDid": did})
    assert eval_res.json()["isTrusted"] is False
    assert eval_res.json()["reason"] == "ISSUER_TRUST_NOT_YET_VALID"


# ==============================================================================
# 3. Scope & Permitted Credential Types Tests
# ==============================================================================

def test_scoped_trust_credential_types() -> None:
    admin_token = _get_token("admin")
    did = "did:web:law-school.example"
    
    client.post(
        "/api/v1/trust-registry/issuers",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "issuerDid": did,
            "organizationName": "Law School",
            "permittedCredentialTypes": ["LawDegreeCredential", "BarAdmissionCredential"],
        },
    )

    # In scope
    eval_in_scope = client.post(
        "/api/v1/trust-registry/evaluate",
        json={"issuerDid": did, "credentialTypes": ["LawDegreeCredential"]},
    )
    assert eval_in_scope.json()["isTrusted"] is True

    # Out of scope
    eval_out_of_scope = client.post(
        "/api/v1/trust-registry/evaluate",
        json={"issuerDid": did, "credentialTypes": ["MedicalDoctorCredential"]},
    )
    assert eval_out_of_scope.json()["isTrusted"] is False
    assert eval_out_of_scope.json()["reason"] == "ISSUER_TRUST_OUT_OF_SCOPE"


# ==============================================================================
# 4. Security & RBAC Authorization Tests
# ==============================================================================

def test_holder_cannot_mutate_trust_registry() -> None:
    holder_token = _get_token("holder")
    res = client.post(
        "/api/v1/trust-registry/issuers",
        headers={"Authorization": f"Bearer {holder_token}"},
        json={
            "issuerDid": "did:web:malicious-injection.example",
            "organizationName": "Malicious Injection Org",
        },
    )
    assert res.status_code == 403, f"Holder should not be allowed to register issuers: {res.text}"


def test_verifier_cannot_mutate_trust_registry() -> None:
    verifier_token = _get_token("verifier")
    res = client.post(
        "/api/v1/trust-registry/issuers",
        headers={"Authorization": f"Bearer {verifier_token}"},
        json={
            "issuerDid": "did:web:verifier-injected.example",
            "organizationName": "Verifier Injected Org",
        },
    )
    assert res.status_code == 403, f"Verifier should not be allowed to register issuers: {res.text}"


def test_unauthenticated_cannot_mutate_trust_registry() -> None:
    res = client.post(
        "/api/v1/trust-registry/issuers",
        json={
            "issuerDid": "did:web:anon-injected.example",
            "organizationName": "Anonymous Injected Org",
        },
    )
    assert res.status_code in (401, 403)


def test_duplicate_issuer_record_rejected() -> None:
    admin_token = _get_token("admin")
    did = "did:web:duplicate-test.example"
    
    res1 = client.post(
        "/api/v1/trust-registry/issuers",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"issuerDid": did, "organizationName": "Original Org"},
    )
    assert res1.status_code == 201

    res2 = client.post(
        "/api/v1/trust-registry/issuers",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"issuerDid": did, "organizationName": "Duplicate Org"},
    )
    assert res2.status_code == 409, f"Expected 409 conflict on duplicate DID: {res2.text}"


# ==============================================================================
# 5. Full OID4VP Verifier Integration Tests (Fail-Closed Trust in Direct Post)
# ==============================================================================

def test_verifier_rejects_untrusted_issuer_presentation() -> None:
    """Verifies that an issuer DID matching did:web: prefix but NOT in Trust Registry is rejected."""
    verifier_token = _get_token("verifier")
    session_id, nonce, client_id = _create_oid4vp_session(verifier_token)

    # Build signed VC from UNTRUSTED issuer
    untrusted_did = "did:web:rogue-unregistered-academy.xyz"
    vc = _build_signed_vc_with_issuer(untrusted_did)

    # Build valid cryptographic presentation signed by holder
    vp = build_signed_presentation(
        vc,
        nonce=nonce,
        domain=client_id,
        holder_did=SYNTHETIC_HOLDER_DID,
    )

    res = client.post(
        "/api/v1/oid4vp/response",
        json={"sessionId": session_id, "vpToken": vp},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "PROCESSED"
    result = data["result"]
    assert result["issuerTrusted"] is False
    assert result["finalPolicyResult"] == "REJECTED"
    assert "trust" in result["details"]
    assert result["details"]["trust"]["trusted"] is False
    assert result["details"]["trust"]["reason"] == "ISSUER_NOT_IN_TRUST_REGISTRY"


def test_verifier_accepts_registered_trusted_issuer_presentation() -> None:
    """Verifies that the pre-seeded trusted issuer (Demo University) passes trust evaluation."""
    verifier_token = _get_token("verifier")
    session_id, nonce, client_id = _create_oid4vp_session(verifier_token)

    # Build signed VC from pre-seeded issuer
    trusted_did = "did:web:issuer.example"
    vc = _build_signed_vc_with_issuer(trusted_did)

    vp = build_signed_presentation(
        vc,
        nonce=nonce,
        domain=client_id,
        holder_did=SYNTHETIC_HOLDER_DID,
    )

    res = client.post(
        "/api/v1/oid4vp/response",
        json={"sessionId": session_id, "vpToken": vp},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "PROCESSED"
    result = data["result"]
    assert result["issuerTrusted"] is True
    assert result["finalPolicyResult"] == "ACCEPTED"
    assert result["details"]["trust"]["trusted"] is True
    assert result["details"]["trust"]["reason"] == "ISSUER_TRUST_VALID"


def test_suspending_issuer_causes_subsequent_verification_rejection() -> None:
    """Demonstrates dynamic authoritative revocation: suspending trust causes immediate rejection."""
    admin_token = _get_token("admin")
    verifier_token = _get_token("verifier")
    trusted_did = "did:web:issuer.example"

    # Fetch record id for pre-seeded issuer
    get_res = client.get(
        f"/api/v1/trust-registry/issuers/{trusted_did}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert get_res.status_code == 200
    record_id = get_res.json()["id"]

    try:
        # 1. Verification while ACTIVE -> ACCEPTED
        s1_id, s1_nonce, s1_client = _create_oid4vp_session(verifier_token)
        vc1 = _build_signed_vc_with_issuer(trusted_did)
        vp1 = build_signed_presentation(vc1, nonce=s1_nonce, domain=s1_client, holder_did=SYNTHETIC_HOLDER_DID)

        res1 = client.post("/api/v1/oid4vp/response", json={"sessionId": s1_id, "vpToken": vp1})
        assert res1.status_code == 200
        assert res1.json()["status"] == "PROCESSED"
        assert res1.json()["result"]["issuerTrusted"] is True
        assert res1.json()["result"]["finalPolicyResult"] == "ACCEPTED"

        # 2. Suspend the issuer in Trust Registry
        suspend_res = client.post(
            f"/api/v1/trust-registry/issuers/{record_id}/suspend",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"reason": "Emergency accreditation freeze"},
        )
        assert suspend_res.status_code == 200

        # 3. Verification after SUSPENSION -> REJECTED (fail-closed on trust despite valid signature)
        s2_id, s2_nonce, s2_client = _create_oid4vp_session(verifier_token)
        vc2 = _build_signed_vc_with_issuer(trusted_did)
        vp2 = build_signed_presentation(vc2, nonce=s2_nonce, domain=s2_client, holder_did=SYNTHETIC_HOLDER_DID)

        res2 = client.post("/api/v1/oid4vp/response", json={"sessionId": s2_id, "vpToken": vp2})
        assert res2.status_code == 200
        assert res2.json()["status"] == "PROCESSED"
        assert res2.json()["result"]["issuerTrusted"] is False
        assert res2.json()["result"]["finalPolicyResult"] == "REJECTED"
        assert res2.json()["result"]["details"]["trust"]["reason"] == "ISSUER_TRUST_SUSPENDED"

    finally:
        # Restore issuer status to active so subsequent tests are unaffected
        client.put(
            f"/api/v1/trust-registry/issuers/{record_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"trustStatus": "active"},
        )
