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

        # 2. Holder inspects verification session
        res_inspect = client.get(f"/api/v1/oid4vp/requests/{session_id}")
        assert res_inspect.status_code == 200
        inspect_data = res_inspect.json()
        assert inspect_data["sessionId"] == session_id
        assert inspect_data["purpose"] == "Verify security clearance claims"
        assert inspect_data["requestedFields"] == ["Sertifika Sahibi", "Unvan", "Yetki Kapsami"]

        # 3. Holder declines consent / rejects the presentation request
        reject_payload = {
            "rejectionReason": "Holder declined to share security clearance claims for this verification purpose",
            "holderDid": "did:key:z6MkuBesnaSecureHolder2026Ed25519",
        }
        res_reject = client.post(
            f"/api/v1/oid4vp/requests/{session_id}/reject",
            json=reject_payload,
        )
        assert res_reject.status_code == 200, f"Reject failed: {res_reject.text}"
        reject_data = res_reject.json()
        assert reject_data["sessionId"] == session_id
        assert reject_data["status"] == "REJECTED"
        assert reject_data["consentStatus"] == "REJECTED"
        assert "Holder declined to share" in reject_data["rejectionReason"]

        # 4. Verifier polls session and sees REJECTED status and reason
        res_poll = client.get(f"/api/v1/oid4vp/requests/{session_id}")
        assert res_poll.status_code == 200
        poll_data = res_poll.json()
        assert poll_data["status"] == "REJECTED"
        assert poll_data["consentStatus"] == "REJECTED"
        assert poll_data["rejectionReason"] == reject_payload["rejectionReason"]

        # 5. Direct Post cannot be submitted for a rejected session (returns 409 Conflict)
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

        # 6. Re-rejecting the already rejected session also returns 409 Conflict
        res_dup_reject = client.post(
            f"/api/v1/oid4vp/requests/{session_id}/reject",
            json=reject_payload,
        )
        assert res_dup_reject.status_code == 409


def test_holder_selective_disclosure_and_consent_granted_flow(auth_headers_fn):
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

        # 2. Holder submits presentation selectively disclosing only 2 of the 4 requested claims
        sample_vp = {
            "@context": ["https://www.w3.org/ns/credentials/v2"],
            "type": ["VerifiablePresentation"],
            "verifiableCredential": [{
                "@context": ["https://www.w3.org/ns/credentials/v2"],
                "id": "urn:uuid:test-affiliation-credential",
                "type": ["VerifiableCredential", "UniversityAffiliationCredential"],
                "issuer": "did:web:trust.eudi.europa.eu",
                "validFrom": "2026-01-01T00:00:00Z",
                "validUntil": "2028-01-01T00:00:00Z",
                "credentialSubject": {
                    "id": "did:key:z6MkuBesnaSecureHolder2026Ed25519",
                    "affiliation": "student",
                    "degree": "Bachelor of Science",
                    "programCode": "SYN-CS-001",
                    "graduationYear": 2026,
                },
                "proof": {
                    "type": "Ed25519Signature2020",
                    "proofValue": "zMockValidSignatureValue12345",
                },
            }],
            "proof": {
                "type": "Ed25519Signature2020",
                "nonce": nonce,
                "proofValue": "zMockHolderPresentationProof",
            },
        }

        # Selective disclosure: only affiliation and degree
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

        # Verify data minimization statistics
        details = dp_result.get("details", {})
        data_min = details.get("dataMinimization", {})
        assert data_min["status"] == "SELECTIVE_DISCLOSURE_APPLIED"
        assert set(data_min["disclosedFields"]) == {"affiliation", "degree"}
        assert set(data_min["hiddenFields"]) == {"programCode", "graduationYear"}
        assert data_min["disclosureRatio"] == 0.5

        # 3. Verifier checks session state: status is VERIFIED and consentStatus is GRANTED
        res_session = client.get(f"/api/v1/oid4vp/requests/{session_id}")
        assert res_session.status_code == 200
        session_body = res_session.json()
        assert session_body["status"] == "VERIFIED"
        assert session_body["consentStatus"] == "GRANTED"
        assert session_body["disclosedClaims"] == disclosed_claims
