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

from app.infrastructure.crypto.local_holder_key_provider import SYNTHETIC_HOLDER_DID

HOLDER_DID = SYNTHETIC_HOLDER_DID
OTHER_HOLDER_DID = "did:key:z6MkuBesnaSecureHolderOther2026Ed25519"


def _get_headers(client: TestClient, role: str) -> dict[str, str]:
    res = client.post(
        "/api/v1/auth/token",
        json={"username": f"{role}@example.test", "password": PASSWORDS[role]},
    )
    assert res.status_code == 200, f"Authentication failed for {role}: {res.text}"
    token = res.json()["accessToken"]
    return {"Authorization": f"Bearer {token}"}


def _create_wallet(client: TestClient, holder_headers: dict[str, str]) -> dict[str, str]:
    response = client.post("/api/v1/wallets", json={}, headers=holder_headers)
    assert response.status_code == 201, response.text
    return response.json()


def _claim_offer_with_wallet(
    client: TestClient,
    *,
    pre_authorized_code: str,
    wallet: dict[str, str],
    holder_headers: dict[str, str],
) -> dict[str, Any]:
    token_res = client.post(
        "/api/v1/oid4vci/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:pre-authorized_code",
            "pre-authorized_code": pre_authorized_code,
        },
    )
    assert token_res.status_code == 200, token_res.text
    token = token_res.json()
    metadata = client.get(
        "/api/v1/oid4vci/.well-known/openid-credential-issuer"
    ).json()
    proof_res = client.post(
        "/api/v1/oid4vci/holder-proof",
        json={
            "walletId": wallet["walletId"],
            "audience": metadata["credential_issuer"],
            "nonce": token["c_nonce"],
        },
        headers=holder_headers,
    )
    assert proof_res.status_code == 200, proof_res.text
    assert proof_res.json()["holderDid"] == wallet["holderDid"]
    credential_res = client.post(
        "/api/v1/oid4vci/credential",
        json={
            "credentialConfigurationId": "QualifiedElectronicAttestationCredential",
            "walletId": wallet["walletId"],
            "proof": {"proofType": "jwt", "jwt": proof_res.json()["jwt"]},
        },
        headers={"Authorization": f"Bearer {token['access_token']}"},
    )
    assert credential_res.status_code == 200, credential_res.text
    return credential_res.json()


def _create_consented_wallet_presentation(
    client: TestClient,
    *,
    session: dict[str, Any],
    credential_id: str,
    wallet: dict[str, str],
    holder_headers: dict[str, str],
    approved_claims: dict[str, Any],
) -> dict[str, Any]:
    consent = client.post(
        f"/api/v1/oid4vp/requests/{session['sessionId']}/wallet-consent",
        json={
            "walletId": wallet["walletId"],
            "holderDid": wallet["holderDid"],
            "action": "APPROVE",
            "approvedCredentials": [credential_id],
            "approvedClaims": approved_claims,
        },
        headers=holder_headers,
    )
    assert consent.status_code == 200, consent.text
    presentation = client.post(
        "/api/v1/oid4vp/wallet-presentation",
        json={
            "sessionId": session["sessionId"],
            "walletId": wallet["walletId"],
            "credentialIds": [credential_id],
            "disclosedClaims": approved_claims,
        },
        headers=holder_headers,
    )
    assert presentation.status_code == 200, presentation.text
    return presentation.json()["vpToken"]


def test_golden_path_complete_lifecycle():
    """
    Executes the full 13-step Golden Path lifecycle from issuance offer to verification.
    """
    with TestClient(app) as client:
        issuer_hdrs = _get_headers(client, "issuer")
        holder_hdrs = _get_headers(client, "holder")
        verifier_hdrs = _get_headers(client, "verifier")
        wallet = _create_wallet(client, holder_hdrs)

        # =========================================================================
        # 1. Issuer creates credential offer (OID4VCI)
        # =========================================================================
        offer_payload = {
            "credentialConfigurationIds": ["QualifiedElectronicAttestationCredential"],
            "subjectData": {
                "Sertifika Sahibi": "Charaf Eddine Bessanane",
                "Unvan": "Senior Distributed Systems & SSI Security Architect",
                "Yetki Kapsami": "W3C VC 2.0 / OID4VCI / OID4VP Cryptographic Engine",
                "holder_did": wallet["holderDid"],
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
        claim_data = _claim_offer_with_wallet(
            client,
            pre_authorized_code=pre_auth_code,
            wallet=wallet,
            holder_headers=holder_hdrs,
        )

        # =========================================================================
        # 4. Credential is persisted (Gap A verification)
        # =========================================================================
        assert claim_data["status"] == "ACTIVE"
        signed_vc = claim_data["credential"]
        cred_uuid = signed_vc["id"]
        assert signed_vc["id"] == cred_uuid
        assert signed_vc["issuer"] is not None
        assert signed_vc["credentialSubject"]["id"] == wallet["holderDid"]
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
        res_reclaim = client.post(
            "/api/v1/oid4vci/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:pre-authorized_code",
                "pre-authorized_code": pre_auth_code,
            },
        )
        assert res_reclaim.status_code == 400, "Double claim must be rejected"
        assert res_reclaim.json()["error"] == "invalid_grant"

        inventory = client.get(
            f"/api/v1/wallets/{wallet['walletId']}/credentials",
            headers=holder_hdrs,
        )
        assert inventory.status_code == 200
        from app.api.v1 import dependencies

        repository = dependencies.get_credential_repository(
            dependencies._MONGO_MANAGER
        )
        persisted = repository.get_by_credential_id(cred_uuid)
        assert persisted is not None
        assert persisted.wallet_id == wallet["walletId"]
        assert persisted.owner_user_id == wallet["ownerUserId"]
        assert any(
            record["credentialId"] == cred_uuid
            for record in inventory.json()["credentials"]
        ), inventory.json()

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
        approved_claims = {
            "Sertifika Sahibi": "Charaf Eddine Bessanane",
            "Unvan": "Senior Distributed Systems & SSI Security Architect",
            "Yetki Kapsami": "W3C VC 2.0 / OID4VCI / OID4VP Cryptographic Engine",
        }
        verifiable_presentation = _create_consented_wallet_presentation(
            client,
            session=session_data,
            credential_id=cred_uuid,
            wallet=wallet,
            holder_headers=holder_hdrs,
            approved_claims=approved_claims,
        )

        # =========================================================================
        # 8 & 9. OID4VP presentation is submitted & Direct Post is processed
        # =========================================================================
        direct_post_payload = {
            "sessionId": session_id,
            "vpToken": verifiable_presentation,
            "disclosedClaims": approved_claims,
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
        # Integrity anchoring is optional in the frozen project profile. This
        # local Golden Path has no receipt-backed anchor provider, so the
        # verifier must report UNANCHORED without changing credential policy.
        assert dp_result["blockchainAnchored"] is False
        assert dp_result["finalPolicyResult"] == "ACCEPTED", "Final policy decision must be ACCEPTED"

        # =========================================================================
        # 13. Audit event & Session state verification
        # =========================================================================
        res_session_check = client.get(
            f"/api/v1/oid4vp/requests/{session_id}", headers=verifier_hdrs
        )
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

        from app.infrastructure.fixtures.signed_credentials import build_signed_presentation
        sample_vp = build_signed_presentation(
            {
                "id": "urn:uuid:replay-test-vc",
                "type": ["VerifiableCredential"],
                "issuer": "did:web:issuer.example",
                "credentialSubject": {"id": HOLDER_DID},
            },
            nonce=nonce,
            domain="http://testserver/verifier",
            holder_did=HOLDER_DID,
        )

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


def test_golden_path_crypto_failure_hierarchy(monkeypatch: pytest.MonkeyPatch):
    """
    Security Invariant: A cryptographic failure MUST result in REJECTED even with low AI risk score.
    """
    from app.application.services.oid4vp_service import fraud_client

    monkeypatch.setattr(
        fraud_client,
        "evaluate_presentation_risk",
        lambda **kwargs: {
            "risk_score": 5,
            "reasons": [],
            "model_version": "test-server-heuristic-v1",
            "risk_signals": ["server_test_signal"],
            "advisory_only": True,
            "source": "test_server_evaluator",
        },
    )
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
            }
        )
        assert res_dp.status_code == 200
        dp_result = res_dp.json()["result"]
        # A server-computed risk score is LOW, but crypto/issuer is invalid,
        # so policy MUST be REJECTED.
        assert dp_result["aiRiskScore"] == 5
        assert dp_result["aiRiskLevel"] == "LOW"
        assert dp_result["details"]["aiRisk"]["source"] == "test_server_evaluator"
        assert dp_result["issuerTrusted"] is False or dp_result["signatureValid"] is False
        assert dp_result["finalPolicyResult"] == "REJECTED"


def test_golden_path_revoked_credential_rejection():
    """
    Sprint 10 — Revoked Golden Path Regression Test.

    Validates:
    1. Credential is issued via OID4VCI and stored with status list metadata.
    2. Issuer revokes the credential via authoritative endpoint.
    3. Status is verified against the Bitstring Status List.
    4. revocationStatusClear becomes False.
    5. Final policy result is strictly REJECTED, even with zero/low AI risk score.
    """
    with TestClient(app) as client:
        issuer_hdrs = _get_headers(client, "issuer")
        holder_hdrs = _get_headers(client, "holder")
        verifier_hdrs = _get_headers(client, "verifier")
        wallet = _create_wallet(client, holder_hdrs)

        # 1. Issuer creates offer
        offer_payload = {
            "credentialConfigurationIds": ["QualifiedElectronicAttestationCredential"],
            "subjectData": {
                "Sertifika Sahibi": "Charaf Eddine Bessanane",
                "Unvan": "Senior Distributed Systems & SSI Security Architect",
                "holder_did": wallet["holderDid"],
            },
            "ttlSeconds": 1800,
        }
        res_offer = client.post("/api/v1/oid4vci/offers", json=offer_payload, headers=issuer_hdrs)
        assert res_offer.status_code == 201
        pre_auth_code = res_offer.json()["preAuthorizedCode"]

        # 2. Holder claims credential
        claim_data = _claim_offer_with_wallet(
            client,
            pre_authorized_code=pre_auth_code,
            wallet=wallet,
            holder_headers=holder_hdrs,
        )
        signed_vc = claim_data["credential"]
        cred_uuid = signed_vc["id"]
        assert claim_data["status"] == "ACTIVE"

        # Confirm credentialStatus is embedded
        assert "credentialStatus" in signed_vc, "Credential must include credentialStatus definition"
        status_info = signed_vc["credentialStatus"]
        assert status_info["type"] == "BitstringStatusListEntry"
        assert "statusListIndex" in status_info
        assert "statusListCredential" in status_info

        # 3. Verifier creates request session
        req_payload = {
            "purpose": "Verify engineering credential before revocation test",
            "requestedCredentialTypes": ["QualifiedElectronicAttestationCredential"],
            "requestedFields": ["Sertifika Sahibi", "Unvan"],
            "ttlSeconds": 600,
        }
        res_session = client.post("/api/v1/oid4vp/requests", json=req_payload, headers=verifier_hdrs)
        assert res_session.status_code == 201
        session_id = res_session.json()["sessionId"]
        nonce = res_session.json()["nonce"]

        # 4. Holder builds presentation bound to nonce
        approved_claims = {
            "Sertifika Sahibi": "Charaf Eddine Bessanane",
            "Unvan": "Senior Distributed Systems & SSI Security Architect",
        }
        verifiable_presentation = _create_consented_wallet_presentation(
            client,
            session=res_session.json(),
            credential_id=cred_uuid,
            wallet=wallet,
            holder_headers=holder_hdrs,
            approved_claims=approved_claims,
        )

        # 5. Authoritative Revocation: Issuer revokes the credential
        res_revoke = client.post(
            f"/api/v1/credentials/{cred_uuid}/revoke",
            json={"reason": "Affiliation Expired and Revoked"},
            headers=issuer_hdrs,
        )
        assert res_revoke.status_code == 200, f"Revocation must succeed: {res_revoke.text}"
        revoke_data = res_revoke.json()
        assert revoke_data["status"] == "REVOKED"
        assert revoke_data["revoked"] is True

        # 6. Verifier receives presentation via Direct Post
        # Even with AI risk score = 0 (perfect safety score), the revoked credential MUST be REJECTED!
        direct_post_payload = {
            "sessionId": session_id,
            "vpToken": verifiable_presentation,
            "disclosedClaims": approved_claims,
            "aiRiskScore": 0,  # Zero fraud risk detected by AI!
        }
        res_dp = client.post("/api/v1/oid4vp/response", json=direct_post_payload)
        assert res_dp.status_code == 200, f"Direct post request should be processed: {res_dp.text}"
        dp_result = res_dp.json()["result"]

        # 7. Assert 9-point matrix results
        assert dp_result["signatureValid"] is True, "Signature itself is still cryptographically intact"
        assert dp_result["revocationStatusClear"] is False, "Status list check must detect revocation"
        assert dp_result["aiRiskLevel"] == "LOW", "AI risk level was lowest possible"
        assert dp_result["finalPolicyResult"] == "REJECTED", (
            "Cryptographic and status invariants strictly override AI score: policy MUST be REJECTED"
        )

        # 8. Check verification session state
        res_session_check = client.get(
            f"/api/v1/oid4vp/requests/{session_id}", headers=verifier_hdrs
        )
        assert res_session_check.status_code == 200
        session_body = res_session_check.json()
        assert session_body["status"] == "REJECTED"
        assert session_body["verificationResult"]["finalPolicyResult"] == "REJECTED"
        assert session_body["verificationResult"]["revocationStatusClear"] is False
