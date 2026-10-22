from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

PASSWORDS = {
    "admin": "Admin-Prototype-2026!",
    "issuer": "Issuer-Prototype-2026!",
    "verifier": "Verifier-Prototype-2026!",
    "holder": "Holder-Prototype-2026!",
}


@pytest.fixture
def auth_headers_fn():
    def _headers(client: TestClient, role: str) -> dict[str, str]:
        res = client.post(
            "/api/v1/auth/token",
            json={"username": f"{role}@example.test", "password": PASSWORDS[role]},
        )
        assert res.status_code == 200, f"Auth failed for {role}: {res.text}"
        return {"Authorization": f"Bearer {res.json()['accessToken']}"}

    return _headers


def test_holder_reject_verification_session_flow(auth_headers_fn):
    with TestClient(app) as client:
        verifier_hdrs = auth_headers_fn(client, "verifier")
        holder_hdrs = auth_headers_fn(client, "holder")

        # 1. Verifier creates OID4VP presentation request
        req_payload = {
            "purpose": "Verify security clearance claims",
            "requestedCredentialTypes": ["QualifiedElectronicAttestationCredential"],
            "requestedFields": ["Sertifika Sahibi", "Unvan", "Yetki Kapsami"],
            "ttlSeconds": 600,
        }
        res_create = client.post(
            "/api/v1/oid4vp/requests", json=req_payload, headers=verifier_hdrs
        )
        assert res_create.status_code == 201, f"Create failed: {res_create.text}"
        session_data = res_create.json()
        session_id = session_data["sessionId"]
        assert session_data["status"] == "PENDING"
        assert session_data["consentStatus"] == "PENDING"
        assert session_data["requestedFields"] == ["Sertifika Sahibi", "Unvan", "Yetki Kapsami"]

        # 2. The authenticated holder owns the wallet used to decide consent.
        wallet_response = client.post(
            "/api/v1/wallets", json={}, headers=holder_hdrs
        )
        assert wallet_response.status_code == 201, wallet_response.text
        wallet = wallet_response.json()

        # 3. Holder inspects verification session
        res_inspect = client.get(
            f"/api/v1/oid4vp/requests/{session_id}/holder-request",
            headers=holder_hdrs,
        )
        assert res_inspect.status_code == 200
        inspect_data = res_inspect.json()
        assert inspect_data["sessionId"] == session_id
        assert inspect_data["purpose"] == "Verify security clearance claims"
        assert inspect_data["requestedFields"] == ["Sertifika Sahibi", "Unvan", "Yetki Kapsami"]

        # 4. Holder declines consent through the wallet-bound route.
        reject_payload = {
            "rejectionReason": "Holder declined to share security clearance claims for this verification purpose",
            "holderDid": wallet["holderDid"],
            "walletId": wallet["walletId"],
            "action": "REJECT",
        }
        res_reject = client.post(
            f"/api/v1/oid4vp/requests/{session_id}/wallet-consent",
            json=reject_payload,
            headers=holder_hdrs,
        )
        assert res_reject.status_code == 200, f"Reject failed: {res_reject.text}"
        reject_data = res_reject.json()
        assert reject_data["sessionId"] == session_id
        assert reject_data["status"] == "REJECTED"
        assert reject_data["consentStatus"] == "REJECTED"
        assert "Holder declined to share" in reject_data["rejectionReason"]

        # 5. Verifier polls session and sees REJECTED status and reason
        res_poll = client.get(
            f"/api/v1/oid4vp/requests/{session_id}", headers=verifier_hdrs
        )
        assert res_poll.status_code == 200
        poll_data = res_poll.json()
        assert poll_data["status"] == "REJECTED"
        assert poll_data["consentStatus"] == "REJECTED"
        assert poll_data["rejectionReason"] == reject_payload["rejectionReason"]

        # 6. Direct Post cannot be submitted for a rejected session (returns 409 Conflict)
        sample_vp = {
            "@context": ["https://www.w3.org/ns/credentials/v2"],
            "type": ["VerifiablePresentation"],
            "verifiableCredential": [],
            "proof": {"type": "Ed25519Signature2020", "proofValue": "mock"},
        }
        dp_payload = {
            "sessionId": session_id,
            "vpToken": sample_vp,
            "disclosedClaims": {"Sertifika Sahibi": "Test User"},
            "aiRiskScore": 5,
        }
        res_dp = client.post("/api/v1/oid4vp/response", json=dp_payload)
        assert res_dp.status_code == 409

        # 7. Re-rejecting the already rejected session also returns 409 Conflict
        res_dup_reject = client.post(
            f"/api/v1/oid4vp/requests/{session_id}/wallet-consent",
            json=reject_payload,
            headers=holder_hdrs,
        )
        assert res_dup_reject.status_code == 409


def test_holder_consent_and_full_credential_disclosure_flow(auth_headers_fn):
    with TestClient(app) as client:
        verifier_hdrs = auth_headers_fn(client, "verifier")

        # 1. Verifier creates request asking for 4 fields
        req_payload = {
            "purpose": "Academic credential verification with selective disclosure",
            "requestedCredentialTypes": ["UniversityAffiliationCredential"],
            "requestedFields": ["affiliation", "degree", "programCode", "graduationYear"],
            "ttlSeconds": 600,
        }
        res_create = client.post(
            "/api/v1/oid4vp/requests", json=req_payload, headers=verifier_hdrs
        )
        assert res_create.status_code == 201
        session_id = res_create.json()["sessionId"]
        nonce = res_create.json()["nonce"]

        # 2. The holder approves a credential, but this profile sends the full
        # signed credential; the client selection cannot hide signed claims.
        import uuid
        from datetime import UTC, datetime, timedelta
        from app.infrastructure.crypto.local_holder_key_provider import SYNTHETIC_HOLDER_DID
        from app.infrastructure.fixtures.signed_credentials import (
            build_local_proof_service,
            build_signed_presentation,
        )
        now = datetime.now(UTC)
        proof_service = build_local_proof_service(clock=lambda: now)
        raw_vc = {
            "@context": [
                "https://www.w3.org/ns/credentials/v2",
                "https://secure-ssi.example/contexts/university-affiliation/v1",
            ],
            "id": f"urn:uuid:{uuid.uuid4()}",
            "type": ["VerifiableCredential", "UniversityAffiliationCredential"],
            "issuer": "did:web:issuer.example",
            "validFrom": (now - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
            "validUntil": (now + timedelta(days=365)).isoformat().replace("+00:00", "Z"),
            "credentialSubject": {
                "id": SYNTHETIC_HOLDER_DID,
                "affiliation": "student",
                "degree": "Bachelor of Science",
                "programCode": "SYN-CS-001",
                "graduationYear": 2026,
            },
        }
        signed_vc = proof_service.sign_credential(raw_vc)

        sample_vp = build_signed_presentation(
            signed_vc,
            nonce=nonce,
            domain="http://testserver/verifier",
        )


        # Legacy selection metadata does not alter the signed credential.
        disclosed_claims = {
            "affiliation": "student",
            "degree": "Bachelor of Science",
        }

        dp_payload = {
            "sessionId": session_id,
            "vpToken": sample_vp,
            "disclosedClaims": disclosed_claims,
            "aiRiskScore": 10,
        }
        res_dp = client.post("/api/v1/oid4vp/response", json=dp_payload)
        assert res_dp.status_code == 200, f"Direct post failed: {res_dp.text}"
        dp_result = res_dp.json()["result"]

        # Verify 9-point checklist accepted
        assert dp_result["finalPolicyResult"] == "ACCEPTED"

        # Verify the result describes the complete credential actually sent.
        details = dp_result.get("details", {})
        data_min = details.get("dataMinimization", {})
        assert data_min["status"] == "FULL_CREDENTIAL_DISCLOSED"
        assert set(data_min["disclosedFields"]) == {
            "affiliation", "degree", "programCode", "graduationYear"
        }
        assert data_min["hiddenFields"] == []
        assert data_min["cryptographicSelectiveDisclosure"] is False

        # 3. Verifier checks session state: status is VERIFIED and consentStatus is GRANTED
        res_session = client.get(
            f"/api/v1/oid4vp/requests/{session_id}", headers=verifier_hdrs
        )
        assert res_session.status_code == 200
        session_body = res_session.json()
        assert session_body["status"] == "VERIFIED"
        assert session_body["consentStatus"] == "GRANTED"
        assert session_body["disclosedClaims"] == disclosed_claims
