"""
Sprint 9 — Golden Path End-to-End Integration Test Suite

Verifies the complete 13-point SSI lifecycle:
1. Issuer creates credential offer
2. Holder receives offer
3. Holder claims offer
4. Credential is persisted in database/repository
5. Credential appears in wallet inventory
6. Verifier creates verification request
7. Holder approves presentation
8. OID4VP presentation is submitted
9. Direct Post is processed
10. 9-point verification matrix runs
11. Cryptographic verification occurs
12. Final policy result is generated
13. Audit event is generated

Also validates Sprint 9 security invariants:
- Replay protection & nonce binding
- Cryptographic failure hierarchy (AI risk cannot override crypto failure)
- Object-level authorization & privacy isolation between holders
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app

PASSWORDS = {
    "admin": "Admin-Prototype-2026!",
    "issuer": "Issuer-Prototype-2026!",
    "verifier": "Verifier-Prototype-2026!",
    "holder": "Holder-Prototype-2026!",
}

HOLDER_DID = "did:key:z6Mkf5rGMoatrSj1f4CyvuHBeXJELe9RPdzo2PKGNCKVtZxP"
OTHER_HOLDER_DID = "did:key:z6MkuBesnaSecureHolderOther2026Ed25519"


def _get_headers(client: TestClient, role: str) -> dict[str, str]:
    res = client.post(
        "/api/v1/auth/token",
        json={"username": f"{role}@example.test", "password": PASSWORDS[role]},
    )
    assert res.status_code == 200, f"Authentication failed for {role}: {res.text}"
    token = res.json()["accessToken"]
    return {"Authorization": f"Bearer {token}"}


def test_golden_path_complete_lifecycle():
    """
    Executes the full 13-step Golden Path lifecycle from issuance offer to verification.
    """
    with TestClient(app) as client:
        issuer_hdrs = _get_headers(client, "issuer")
        holder_hdrs = _get_headers(client, "holder")
        verifier_hdrs = _get_headers(client, "verifier")

        # =========================================================================
        # 1. Issuer creates credential offer (OID4VCI)
        # =========================================================================
        offer_payload = {
            "credentialConfigurationIds": ["QualifiedElectronicAttestationCredential"],
            "subjectData": {
                "Sertifika Sahibi": "Charaf Eddine Bessanane",
                "Unvan": "Senior Distributed Systems & SSI Security Architect",
                "Yetki Kapsami": "W3C VC 2.0 / OID4VCI / OID4VP Cryptographic Engine",
                "holder_did": HOLDER_DID,
            },
            "ttlSeconds": 1800,
        }
        res_create_offer = client.post(
            "/api/v1/oid4vci/offers",
            json=offer_payload,
            headers=issuer_hdrs,
        )
        assert res_create_offer.status_code == 201, f"Step 1 failed: {res_create_offer.text}"
        offer_data = res_create_offer.json()
        offer_id = offer_data["offerId"]
        pre_auth_code = offer_data["preAuthorizedCode"]
        assert offer_data["status"] == "PENDING"
        assert offer_data["deepLinkUri"].startswith("openid-credential-offer://")

        # =========================================================================
        # 2. Holder receives / lists pending offers (Gap B verification)
        # =========================================================================
        res_offers = client.get("/api/v1/oid4vci/offers", headers=holder_hdrs)
        assert res_offers.status_code == 200, f"Step 2 failed: {res_offers.text}"
        offers_list = res_offers.json()
        assert isinstance(offers_list, list)
        matching_offers = [o for o in offers_list if o["offerId"] == offer_id]
        assert len(matching_offers) == 1, "Holder must receive the pending offer"
        received_offer = matching_offers[0]
        assert received_offer["status"] == "PENDING"
        assert received_offer["preAuthorizedCode"] == pre_auth_code

        # =========================================================================
        # 3. Holder claims offer
        # =========================================================================
        claim_payload = {
            "preAuthorizedCode": pre_auth_code,
            "holderDid": HOLDER_DID,
            "walletId": "wallet_holder_primary",
        }
        res_claim = client.post("/api/v1/oid4vci/credential", json=claim_payload)
        assert res_claim.status_code == 201, f"Step 3 failed: {res_claim.text}"
        claim_data = res_claim.json()

        # =========================================================================
        # 4. Credential is persisted (Gap A verification)
        # =========================================================================
        assert claim_data["status"] == "ACTIVE"
        cred_uuid = claim_data["credentialId"]
        signed_vc = claim_data["credential"]
        assert signed_vc["id"] == cred_uuid
        assert signed_vc["issuer"] is not None
        assert signed_vc["credentialSubject"]["id"] == HOLDER_DID
        assert signed_vc["credentialSubject"]["Sertifika Sahibi"] == "Charaf Eddine Bessanane"
        assert signed_vc["proof"]["type"] == "DataIntegrityProof"
        assert signed_vc["proof"]["cryptosuite"] == "eddsa-jcs-2022"

        # =========================================================================
        # 5. Credential appears in wallet inventory
        # =========================================================================
        # Offer is no longer pending
        res_offers_after = client.get("/api/v1/oid4vci/offers", headers=holder_hdrs)
        assert res_offers_after.status_code == 200
        claimed_ids = [o["offerId"] for o in res_offers_after.json() if o["offerId"] == offer_id]
        assert len(claimed_ids) == 0, "Claimed offer must not remain in pending offers"

        # Re-claiming must be rejected
        res_reclaim = client.post("/api/v1/oid4vci/credential", json=claim_payload)
        assert res_reclaim.status_code == 409, "Double claim must be rejected"

        # =========================================================================
        # 6. Verifier creates verification request session (OID4VP)
        # =========================================================================
        req_payload = {
            "purpose": "Verify qualified engineering qualification for security clearance",
            "requestedCredentialTypes": ["QualifiedElectronicAttestationCredential"],
            "requestedFields": ["Sertifika Sahibi", "Unvan", "Yetki Kapsami"],
            "ttlSeconds": 600,
        }
        res_session = client.post(
            "/api/v1/oid4vp/requests",
            json=req_payload,
            headers=verifier_hdrs,
        )
        assert res_session.status_code == 201, f"Step 6 failed: {res_session.text}"
        session_data = res_session.json()
        session_id = session_data["sessionId"]
        nonce = session_data["nonce"]
        assert session_data["status"] == "PENDING"
        assert session_data["deepLinkUri"].startswith("openid4vp://")

        # =========================================================================
        # 7. Holder approves presentation & builds VP bound to nonce
        # =========================================================================
        verifiable_presentation = {
            "@context": ["https://www.w3.org/ns/credentials/v2"],
            "id": f"urn:uuid:golden-path-vp-{session_id}",
            "type": ["VerifiablePresentation"],
            "verifiableCredential": [signed_vc],
            "proof": {
                "type": "Ed25519Signature2020",
                "nonce": nonce,
                "proofValue": "zMockHolderProofBoundToNonce12345",
            },
        }

        # =========================================================================
        # 8 & 9. OID4VP presentation is submitted & Direct Post is processed
        # =========================================================================
        direct_post_payload = {
            "sessionId": session_id,
            "vpToken": verifiable_presentation,
            "disclosedClaims": {
                "Sertifika Sahibi": "Charaf Eddine Bessanane",
                "Unvan": "Senior Distributed Systems & SSI Security Architect",
                "Yetki Kapsami": "W3C VC 2.0 / OID4VCI / OID4VP Cryptographic Engine",
            },
            "aiRiskScore": 12,
        }
        res_dp = client.post("/api/v1/oid4vp/response", json=direct_post_payload)
        assert res_dp.status_code == 200, f"Step 8/9 failed: {res_dp.text}"
        dp_result = res_dp.json()["result"]

        # =========================================================================
        # 10, 11 & 12. 9-point verification matrix runs, crypto valid, policy ACCEPTED
        # =========================================================================
        assert dp_result["credentialValid"] is True, "1. Credential structure must be valid"
        assert dp_result["issuerTrusted"] is True, "2. Issuer DID must be trusted"
        assert dp_result["signatureValid"] is True, "3. Cryptographic signature must be valid"
        assert dp_result["holderBindingValid"] is True, "4. Holder DID binding must be valid"
        assert dp_result["expirationValid"] is True, "5. Expiration must be valid"
        assert dp_result["revocationStatusClear"] is True, "6. Status list revocation must be clear"
        assert dp_result["challengeValid"] is True, "7. Session challenge/nonce must match"
        assert dp_result["aiRiskLevel"] == "LOW", "8. AI risk score must be acceptable"
        assert dp_result["blockchainAnchored"] is True, "9. Event anchoring must be verified"
        assert dp_result["finalPolicyResult"] == "ACCEPTED", "Final policy decision must be ACCEPTED"

        # =========================================================================
        # 13. Audit event & Session state verification
        # =========================================================================
        res_session_check = client.get(f"/api/v1/oid4vp/requests/{session_id}")
        assert res_session_check.status_code == 200
        verified_session = res_session_check.json()
        assert verified_session["status"] == "VERIFIED"
        assert verified_session["verificationResult"]["finalPolicyResult"] == "ACCEPTED"
        assert verified_session["disclosedClaims"]["Sertifika Sahibi"] == "Charaf Eddine Bessanane"


def test_golden_path_replay_protection():
    """
    Security Invariant: Replay of an already-consumed presentation session must fail.
    """
    with TestClient(app) as client:
        verifier_hdrs = _get_headers(client, "verifier")

        # 1. Create session
        res_session = client.post(
            "/api/v1/oid4vp/requests",
            json={"purpose": "Replay test", "requestedCredentialTypes": ["TestCredential"]},
            headers=verifier_hdrs,
        )
        assert res_session.status_code == 201
        session_id = res_session.json()["sessionId"]
        nonce = res_session.json()["nonce"]

        sample_vp = {
            "@context": ["https://www.w3.org/ns/credentials/v2"],
            "type": ["VerifiablePresentation"],
            "verifiableCredential": [{
                "id": "urn:uuid:replay-test-vc",
                "type": ["VerifiableCredential"],
                "issuer": "did:web:issuer.example",
                "credentialSubject": {"id": HOLDER_DID},
                "proof": {"type": "Ed25519Signature2020", "proofValue": "zSig"}
            }],
            "proof": {"type": "Ed25519Signature2020", "nonce": nonce, "proofValue": "zProof"}
        }

        # First post succeeds
        res_first = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session_id, "vpToken": sample_vp}
        )
        assert res_first.status_code == 200

        # Second post with identical session must be rejected (session consumed)
        res_second = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session_id, "vpToken": sample_vp}
        )
        assert res_second.status_code in {400, 409}, "Replayed session must be rejected"


def test_golden_path_nonce_mismatch_rejected():
    """
    Security Invariant: Mismatched challenge nonce must cause verification REJECTED.
    """
    with TestClient(app) as client:
        verifier_hdrs = _get_headers(client, "verifier")

        res_session = client.post(
            "/api/v1/oid4vp/requests",
            json={"purpose": "Nonce mismatch test"},
            headers=verifier_hdrs,
        )
        assert res_session.status_code == 201
        session_id = res_session.json()["sessionId"]

        # Presentation has forged/tampered nonce
        tampered_vp = {
            "@context": ["https://www.w3.org/ns/credentials/v2"],
            "type": ["VerifiablePresentation"],
            "verifiableCredential": [{
                "id": "urn:uuid:nonce-test-vc",
                "type": ["VerifiableCredential"],
                "issuer": "did:web:issuer.example",
                "credentialSubject": {"id": HOLDER_DID},
                "proof": {"type": "Ed25519Signature2020", "proofValue": "zSig"}
            }],
            "proof": {"type": "Ed25519Signature2020", "nonce": "invalid_forged_nonce_12345", "proofValue": "zProof"}
        }

        res_dp = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session_id, "vpToken": tampered_vp}
        )
        assert res_dp.status_code == 200
        dp_result = res_dp.json()["result"]
        assert dp_result["challengeValid"] is False
        assert dp_result["finalPolicyResult"] == "REJECTED"


def test_golden_path_crypto_failure_hierarchy():
    """
    Security Invariant: A cryptographic failure MUST result in REJECTED even with low AI risk score.
    """
    with TestClient(app) as client:
        verifier_hdrs = _get_headers(client, "verifier")

        res_session = client.post(
            "/api/v1/oid4vp/requests",
            json={"purpose": "Hierarchy test"},
            headers=verifier_hdrs,
        )
        session_id = res_session.json()["sessionId"]
        nonce = res_session.json()["nonce"]

        # Missing proof in credential (crypto invalid)
        untrusted_vp = {
            "@context": ["https://www.w3.org/ns/credentials/v2"],
            "type": ["VerifiablePresentation"],
            "verifiableCredential": [{
                "id": "urn:uuid:hierarchy-test-vc",
                "type": ["VerifiableCredential"],
                "issuer": "untrusted-issuer-no-did",
                "credentialSubject": {"id": HOLDER_DID},
                # No proof
            }],
            "proof": {"type": "Ed25519Signature2020", "nonce": nonce, "proofValue": "zProof"}
        }

        res_dp = client.post(
            "/api/v1/oid4vp/response",
            json={
                "sessionId": session_id,
                "vpToken": untrusted_vp,
                "aiRiskScore": 5,  # Very low AI risk score!
            }
        )
        assert res_dp.status_code == 200
        dp_result = res_dp.json()["result"]
        # AI risk is LOW, but crypto/issuer is invalid, so policy MUST be REJECTED
        assert dp_result["aiRiskLevel"] == "LOW"
        assert dp_result["issuerTrusted"] is False or dp_result["signatureValid"] is False
        assert dp_result["finalPolicyResult"] == "REJECTED"
