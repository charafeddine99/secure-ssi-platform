import os
import pytest
from datetime import UTC, datetime, timedelta
from fastapi.testclient import TestClient

from app.main import app

PASSWORDS = {
    "admin": "Admin-Prototype-2026!",
    "issuer": "Issuer-Prototype-2026!",
    "verifier": "Verifier-Prototype-2026!",
    "holder": "Holder-Prototype-2026!"
}

@pytest.fixture
def auth_headers_fn():
    def _headers(client: TestClient, role: str) -> dict[str, str]:
        res = client.post(
            "/api/v1/auth/token",
            json={"username": f"{role}@example.test", "password": PASSWORDS[role]}
        )
        assert res.status_code == 200, f"Auth failed for {role}: {res.text}"
        return {"Authorization": f"Bearer {res.json()['accessToken']}"}
    return _headers

def test_oid4vci_issuer_metadata():
    with TestClient(app) as client:
        res = client.get("/api/v1/oid4vci/.well-known/openid-credential-issuer")
        assert res.status_code == 200
        data = res.json()
        assert "credential_issuer" in data
        assert "credential_endpoint" in data
        assert "credential_configurations_supported" in data
        assert "QualifiedElectronicAttestationCredential" in data["credential_configurations_supported"]

def test_oid4vci_full_offer_lifecycle(auth_headers_fn):
    with TestClient(app) as client:
        issuer_hdrs = auth_headers_fn(client, "issuer")

        # 1. Issuer creates offer
        offer_payload = {
            "credentialConfigurationIds": ["UniversityAffiliationCredential"],
            "subjectData": {
                "affiliation": "student",
                "programCode": "SYN-CS-001",
                "degree": "Bachelor of Science",
                "graduationYear": 2026
            },
            "ttlSeconds": 1800
        }
        res_create = client.post("/api/v1/oid4vci/offers", json=offer_payload, headers=issuer_hdrs)
        assert res_create.status_code == 201, f"Create offer failed: {res_create.text}"
        offer_data = res_create.json()
        offer_id = offer_data["offerId"]
        pre_auth_code = offer_data["preAuthorizedCode"]
        assert offer_data["status"] == "PENDING"
        assert offer_data["deepLinkUri"].startswith("openid-credential-offer://")

        # 2. Holder inspects offer
        res_inspect = client.get(f"/api/v1/oid4vci/offers/{offer_id}")
        assert res_inspect.status_code == 200
        assert res_inspect.json()["offerId"] == offer_id

        # 3. Holder claims offer
        claim_payload = {
            "preAuthorizedCode": pre_auth_code,
            "holderDid": "did:key:z6Mkf5rGMoatrSj1f4CyvuHBeXJELe9RPdzo2PKGNCKVtZxP",
            "walletId": "wallet_holder_primary"
        }
        res_claim = client.post("/api/v1/oid4vci/credential", json=claim_payload)
        assert res_claim.status_code == 201, f"Claim failed: {res_claim.text}"
        claim_data = res_claim.json()
        assert claim_data["status"] == "ACTIVE"
        vc = claim_data["credential"]
        assert vc["issuer"] is not None
        assert vc["credentialSubject"]["id"] == "did:key:z6Mkf5rGMoatrSj1f4CyvuHBeXJELe9RPdzo2PKGNCKVtZxP"
        assert vc["proof"]["type"] == "DataIntegrityProof"
        assert vc["proof"]["cryptosuite"] == "eddsa-jcs-2022"

        # 4. Duplicate claim rejected
        res_dup = client.post("/api/v1/oid4vci/credential", json=claim_payload)
        assert res_dup.status_code == 409

def test_oid4vp_full_verification_lifecycle(auth_headers_fn):
    with TestClient(app) as client:
        verifier_hdrs = auth_headers_fn(client, "verifier")

        # 1. Verifier creates session
        req_payload = {
            "purpose": "Verify holder qualification for security clearance",
            "requestedCredentialTypes": ["QualifiedElectronicAttestationCredential"],
            "requestedFields": ["Sertifika Sahibi", "Unvan", "Yetki Kapsami"],
            "ttlSeconds": 600
        }
        res_create = client.post("/api/v1/oid4vp/requests", json=req_payload, headers=verifier_hdrs)
        assert res_create.status_code == 201, f"Create session failed: {res_create.text}"
        session_data = res_create.json()
        session_id = session_data["sessionId"]
        nonce = session_data["nonce"]
        assert session_data["status"] == "PENDING"
        assert session_data["deepLinkUri"].startswith("openid4vp://")

        # 2. Verifier checks initial pending status
        res_poll = client.get(f"/api/v1/oid4vp/requests/{session_id}")
        assert res_poll.status_code == 200
        assert res_poll.json()["status"] == "PENDING"

        # 3. Holder submits presentation via Direct Post
        sample_vp = {
            "@context": ["https://www.w3.org/ns/credentials/v2"],
            "type": ["VerifiablePresentation"],
            "verifiableCredential": [{
                "@context": ["https://www.w3.org/ns/credentials/v2"],
                "id": "urn:uuid:test-qeaa-presentation",
                "type": ["VerifiableCredential", "QualifiedElectronicAttestationCredential"],
                "issuer": "did:web:trust.eudi.europa.eu",
                "validFrom": "2026-01-01T00:00:00Z",
                "validUntil": "2028-01-01T00:00:00Z",
                "credentialSubject": {
                    "id": "did:key:z6MkuBesnaSecureHolder2026Ed25519",
                    "Sertifika Sahibi": "Charaf Eddine Bessanane",
                    "Unvan": "Senior Distributed Systems & SSI Security Architect",
                    "Yetki Kapsami": "W3C VC 2.0 / OID4VCI / OID4VP Cryptographic Engine"
                },
                "proof": {
                    "type": "Ed25519Signature2020",
                    "proofValue": "zMockValidSignatureValue12345"
                }
            }],
            "proof": {
                "type": "Ed25519Signature2020",
                "nonce": nonce,
                "proofValue": "zMockHolderPresentationProof"
            }
        }
        dp_payload = {
            "sessionId": session_id,
            "vpToken": sample_vp,
            "disclosedClaims": {
                "Sertifika Sahibi": "Charaf Eddine Bessanane",
                "Unvan": "Senior Distributed Systems & SSI Security Architect"
            },
            "aiRiskScore": 12
        }
        res_dp = client.post("/api/v1/oid4vp/response", json=dp_payload)
        assert res_dp.status_code == 200, f"Direct post failed: {res_dp.text}"
        dp_res = res_dp.json()["result"]
        
        # Verify 9-point checklist
        assert dp_res["credentialValid"] is True
        assert dp_res["issuerTrusted"] is True
        assert dp_res["signatureValid"] is True
        assert dp_res["holderBindingValid"] is True
        assert dp_res["expirationValid"] is True
        assert dp_res["revocationStatusClear"] is True
        assert dp_res["challengeValid"] is True
        assert dp_res["aiRiskLevel"] == "LOW"
        assert dp_res["blockchainAnchored"] is True
        assert dp_res["finalPolicyResult"] == "ACCEPTED"

        # 4. Verifier polls session and sees VERIFIED status + result
        res_poll_after = client.get(f"/api/v1/oid4vp/requests/{session_id}")
        assert res_poll_after.status_code == 200
        poll_data = res_poll_after.json()
        assert poll_data["status"] == "VERIFIED"
        assert poll_data["verificationResult"]["finalPolicyResult"] == "ACCEPTED"
        assert poll_data["disclosedClaims"]["Sertifika Sahibi"] == "Charaf Eddine Bessanane"
