import os
import pytest
from app.config.request_object_settings import request_object_signer
from datetime import UTC, datetime, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.application.services.oid4vp_service import fraud_client


def _record_holder_consent(session_id: str, credential: dict) -> None:
    """Seed server-side consent for the direct-post lifecycle fixture."""
    from app.api.v1 import dependencies
    from app.domain.oid4vp import ConsentAction, ConsentDecision
    from app.infrastructure.crypto.local_holder_key_provider import SYNTHETIC_HOLDER_DID

    manager = dependencies.get_mongo_connection_manager()
    repository = dependencies.get_verification_session_repository(manager=manager)
    session = repository.get_by_session_id(session_id)
    assert session is not None
    subject = credential["credentialSubject"]
    repository.record_consent(
        session.session_id,
        consent_decision=ConsentDecision(
            session_id=session.session_id,
            verifier_did=session.verifier_did,
            client_id=session.client_id,
            purpose=session.purpose,
            nonce=session.nonce,
            holder_did=SYNTHETIC_HOLDER_DID,
            decision=ConsentAction.APPROVE,
            approved_credentials=(credential["id"],),
            requested_claims=session.requested_fields,
            approved_claims={key: value for key, value in subject.items() if key != "id"},
            expires_at=session.expires_at,
        ),
        expected_version=session.version,
    )


@pytest.fixture(autouse=True)
def isolate_optional_fraud_dependency(monkeypatch: pytest.MonkeyPatch):
    # Protocol lifecycle assertions must not depend on mutable host-level fraud
    # state; dedicated fraud integration tests cover the external adapter.
    monkeypatch.setattr(fraud_client, "base_url", "http://127.0.0.1:1")
    monkeypatch.setattr(fraud_client, "report_event", lambda **kwargs: None)

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
        holder_hdrs = auth_headers_fn(client, "holder")
        wallet_res = client.post("/api/v1/wallets", json={}, headers=holder_hdrs)
        assert wallet_res.status_code == 201, wallet_res.text
        wallet = wallet_res.json()

        # 1. Issuer creates offer
        offer_payload = {
            "credentialConfigurationIds": ["UniversityAffiliationCredential"],
            "subjectData": {
                "affiliation": "student",
                "programCode": "SYN-CS-001",
                "degree": "Bachelor of Science",
                "graduationYear": 2026,
                "holder_did": wallet["holderDid"],
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

        # Offer ids are random (not ObjectId counters) so neighbours cannot be derived.
        assert offer_id.startswith("offer_") and len(offer_id) >= len("offer_") + 32

        # 2. The addressed holder and the issuing authority may inspect the offer.
        res_inspect = client.get(f"/api/v1/oid4vci/offers/{offer_id}", headers=holder_hdrs)
        assert res_inspect.status_code == 200
        assert res_inspect.json()["offerId"] == offer_id
        assert client.get(f"/api/v1/oid4vci/offers/{offer_id}", headers=issuer_hdrs).status_code == 200

        # Nobody else learns the pre-authorized code or the subject data.
        assert client.get(f"/api/v1/oid4vci/offers/{offer_id}").status_code == 401
        res_other = client.get(
            f"/api/v1/oid4vci/offers/{offer_id}",
            headers=auth_headers_fn(client, "verifier"),
        )
        assert res_other.status_code == 404
        assert "preAuthorizedCode" not in res_other.text

        # 3. Holder uses the canonical token, wallet proof, and credential flow.
        token_res = client.post(
            "/api/v1/oid4vci/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:pre-authorized_code",
                "pre-authorized_code": pre_auth_code,
            },
        )
        assert token_res.status_code == 200, token_res.text
        token = token_res.json()
        issuer_meta = client.get(
            "/api/v1/oid4vci/.well-known/openid-credential-issuer"
        ).json()
        proof_res = client.post(
            "/api/v1/oid4vci/holder-proof",
            json={
                "walletId": wallet["walletId"],
                "audience": issuer_meta["credential_issuer"],
                "nonce": token["c_nonce"],
            },
            headers=holder_hdrs,
        )
        assert proof_res.status_code == 200, proof_res.text
        assert proof_res.json()["holderDid"] == wallet["holderDid"]
        res_claim = client.post(
            "/api/v1/oid4vci/credential",
            json={
                "credentialConfigurationId": "UniversityAffiliationCredential",
                "walletId": wallet["walletId"],
                "proof": {"proofType": "jwt", "jwt": proof_res.json()["jwt"]},
            },
            headers={"Authorization": f"Bearer {token['access_token']}"},
        )
        assert res_claim.status_code == 200, f"Claim failed: {res_claim.text}"
        claim_data = res_claim.json()
        assert claim_data["status"] == "ACTIVE"
        vc = claim_data["credential"]
        assert vc["issuer"] is not None
        assert vc["credentialSubject"]["id"] == wallet["holderDid"]
        assert vc["proof"]["type"] == "DataIntegrityProof"
        assert vc["proof"]["cryptosuite"] == "eddsa-jcs-2022"

        # 4. The pre-authorized code is single use and cannot mint another token.
        res_dup = client.post(
            "/api/v1/oid4vci/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:pre-authorized_code",
                "pre-authorized_code": pre_auth_code,
            },
        )
        assert res_dup.status_code == 400
        assert res_dup.json()["error"] == "invalid_grant"

def test_oid4vp_full_verification_lifecycle(auth_headers_fn):
    with TestClient(app) as client:
        verifier_hdrs = auth_headers_fn(client, "verifier")

        # 1. Verifier creates session
        req_payload = {
            "purpose": "Verify holder qualification for security clearance",
            "requestedCredentialTypes": ["UniversityAffiliationCredential"],
            "requestedFields": ["affiliation", "degree", "programCode"],
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
        res_poll = client.get(
            f"/api/v1/oid4vp/requests/{session_id}", headers=verifier_hdrs
        )
        assert res_poll.status_code == 200
        assert res_poll.json()["status"] == "PENDING"

        import uuid
        from app.infrastructure.fixtures.signed_credentials import build_local_proof_service
        now = datetime.now(UTC)
        proof_service = build_local_proof_service(clock=lambda: now)
        from app.infrastructure.crypto.local_holder_key_provider import SYNTHETIC_HOLDER_DID
        raw_vc = {
            "@context": [
                "https://www.w3.org/ns/credentials/v2",
                "https://secure-ssi.example/contexts/university-affiliation/v1"
            ],
            "id": f"urn:uuid:{uuid.uuid4()}",
            "type": ["VerifiableCredential", "UniversityAffiliationCredential"],
            "issuer": "did:web:issuer.example",
            "validFrom": (now - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
            "validUntil": (now + timedelta(days=365)).isoformat().replace("+00:00", "Z"),
            "credentialSubject": {
                "id": SYNTHETIC_HOLDER_DID,
                "affiliation": "student",
                "programCode": "SYN-CS-001",
                "degree": "Bachelor of Science",
                "graduationYear": 2026,
            }
        }
        signed_vc = proof_service.sign_credential(raw_vc)
        _record_holder_consent(session_id, signed_vc)

        # 3. Holder submits presentation via Direct Post
        from app.infrastructure.fixtures.signed_credentials import build_signed_presentation
        sample_vp = build_signed_presentation(
            signed_vc,
            nonce=nonce,
            domain=request_object_signer().client_id,
        )


        dp_payload = {
            "sessionId": session_id,
            "vpToken": sample_vp,
            "disclosedClaims": {
                "affiliation": "student",
                "degree": "Bachelor of Science",
            },
            "aiRiskScore": 12
        }
        res_dp = client.post("/api/v1/oid4vp/response", json=dp_payload)
        assert res_dp.status_code == 200, f"Direct post failed: {res_dp.text}"
        dp_res = res_dp.json()["result"]
        print("DP RESULT DETAILS:", dp_res.get("details"))
        
        # Verify 9-point checklist
        assert dp_res["credentialValid"] is True
        assert dp_res["issuerTrusted"] is True
        assert dp_res["signatureValid"] is True
        assert dp_res["holderBindingValid"] is True
        assert dp_res["expirationValid"] is True
        assert dp_res["revocationStatusClear"] is True
        assert dp_res["challengeValid"] is True
        assert dp_res["aiRiskLevel"] == "LOW"
        # Anchoring is optional, and this local lifecycle has no verified
        # receipt provider. An absent anchor must not invalidate VC policy or
        # be reported as a successful anchor.
        assert dp_res["blockchainAnchored"] is False
        assert dp_res["finalPolicyResult"] == "ACCEPTED"

        # 4. Verifier polls session and sees VERIFIED status + result
        res_poll_after = client.get(
            f"/api/v1/oid4vp/requests/{session_id}", headers=verifier_hdrs
        )
        assert res_poll_after.status_code == 200
        poll_data = res_poll_after.json()
        assert poll_data["status"] == "VERIFIED"
        assert poll_data["verificationResult"]["finalPolicyResult"] == "ACCEPTED"
        assert poll_data["disclosedClaims"]["degree"] == "Bachelor of Science"


def test_oid4vci_tx_code_attempts_are_limited_per_offer(auth_headers_fn):
    """SEC-04: a short transaction code cannot be brute-forced at the token endpoint."""
    from app.application.services.oid4vci_service import MAX_TX_CODE_ATTEMPTS

    subject = {"affiliation": "student", "programCode": "SYN-CS-009", "degree": "Bachelor of Science", "graduationYear": 2027}
    grant = "urn:ietf:params:oauth:grant-type:pre-authorized_code"
    with TestClient(app) as client:
        issuer_hdrs = auth_headers_fn(client, "issuer")

        def offer_code() -> str:
            res = client.post(
                "/api/v1/oid4vci/offers",
                json={"credentialConfigurationIds": ["UniversityAffiliationCredential"], "subjectData": subject, "ttlSeconds": 600, "userPin": "4821"},
                headers=issuer_hdrs,
            )
            assert res.status_code == 201, res.text
            return res.json()["preAuthorizedCode"]

        def token(code: str, pin: str):
            return client.post("/api/v1/oid4vci/token", data={"grant_type": grant, "pre-authorized_code": code, "tx_code": pin})

        # The right code still works after a few mistakes.
        code = offer_code()
        assert token(code, "0000").status_code == 400
        assert token(code, "4821").status_code == 200

        # Reaching the limit revokes the offer; even the right code is then refused.
        code = offer_code()
        for _ in range(MAX_TX_CODE_ATTEMPTS):
            assert token(code, "0000").status_code == 400
        assert token(code, "4821").status_code == 400
