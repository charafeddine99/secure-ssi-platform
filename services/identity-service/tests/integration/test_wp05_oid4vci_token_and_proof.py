from __future__ import annotations

import base64
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
import pytest
import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from app.main import app
from app.infrastructure.crypto.multibase import encode_base58_btc
from app.services.credential_validator import CredentialProfileValidator
from app.services.did_resolver import DidKeyResolver
from app.application.services.oid4vci_service import build_holder_jwt_proof

PASSWORDS = {
    "admin": "Admin-Prototype-2026!",
    "issuer": "Issuer-Prototype-2026!",
    "verifier": "Verifier-Prototype-2026!",
    "holder": "Holder-Prototype-2026!",
}

client = TestClient(app)

def _get_auth_headers(role: str = "issuer") -> dict[str, str]:
    res = client.post(
        "/api/v1/auth/token",
        json={"username": f"{role}@example.test", "password": PASSWORDS[role]},
    )
    assert res.status_code == 200, f"Auth failed for {role}: {res.text}"
    return {"Authorization": f"Bearer {res.json()['accessToken']}"}

def _create_holder_key() -> tuple[Ed25519PrivateKey, str]:
    priv = Ed25519PrivateKey.generate()
    pub_bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    # 0xed01 is the Ed25519 multicodec prefix
    multibase = encode_base58_btc(b"\xed\x01" + pub_bytes)
    holder_did = f"did:key:{multibase}"
    return priv, holder_did

def _create_test_offer(
    *,
    config_ids: list[str] | None = None,
    user_pin: str | None = None,
    ttl_seconds: int = 1800,
) -> dict[str, Any]:
    hdrs = _get_auth_headers("issuer")
    payload = {
        "credentialConfigurationIds": config_ids or ["UniversityAffiliationCredential"],
        "subjectData": {
            "degree": "Master of Science",
            "affiliation": "student",
            "programCode": "SYN-CS-2026",
            "graduationYear": 2026,
        },
        "ttlSeconds": ttl_seconds,
        "userPin": user_pin,
    }
    res = client.post("/api/v1/oid4vci/offers", json=payload, headers=hdrs)
    assert res.status_code == 201, f"Create offer failed: {res.text}"
    return res.json()


def _create_holder_wallet() -> tuple[dict[str, str], str, str]:
    holder_headers = _get_auth_headers("holder")
    response = client.post(
        "/api/v1/wallets",
        json={},
        headers=holder_headers,
    )
    assert response.status_code == 201, f"Create holder wallet failed: {response.text}"
    wallet = response.json()
    return holder_headers, wallet["walletId"], wallet["holderDid"]


def _create_wallet_proof(
    *,
    holder_headers: dict[str, str],
    wallet_id: str,
    nonce: str,
) -> tuple[str, str]:
    issuer = client.get(
        "/api/v1/oid4vci/.well-known/openid-credential-issuer"
    ).json()
    response = client.post(
        "/api/v1/oid4vci/holder-proof",
        json={
            "walletId": wallet_id,
            "audience": issuer["credential_issuer"],
            "nonce": nonce,
        },
        headers=holder_headers,
    )
    assert response.status_code == 200, f"Create holder proof failed: {response.text}"
    proof = response.json()
    return proof["holderDid"], proof["jwt"]


def test_server_no_longer_signs_guardian_recovery_proofs() -> None:
    """A proof signed with a platform-held key says nothing about the Guardian."""
    holder_headers, _wallet_id, holder_did = _create_holder_wallet()
    response = client.post(
        "/api/v1/wallets/guardian-recovery-proof",
        json={"guardianDid": holder_did},
        headers=holder_headers,
    )
    assert response.status_code in {404, 405, 422}
    assert "proof" not in response.text.casefold().replace("guardian-recovery-proof", "")


# ============================================================================
# 1. METADATA & NONCE ENDPOINTS
# ============================================================================

def test_wp05_metadata_advertises_token_and_nonce_endpoints():
    """Issuer metadata truthfully advertises token_endpoint, nonce_endpoint, and proof types."""
    res = client.get("/api/v1/oid4vci/.well-known/openid-credential-issuer")
    assert res.status_code == 200
    meta = res.json()
    assert "token_endpoint" in meta
    assert meta["token_endpoint"].endswith("/api/v1/oid4vci/token")
    assert "nonce_endpoint" in meta
    assert meta["nonce_endpoint"].endswith("/api/v1/oid4vci/nonce")
    configs = meta.get("credential_configurations_supported", {})
    assert set(configs) == {
        "QualifiedElectronicAttestationCredential",
        "UniversityAffiliationCredential",
    }
    assert "UniversityAffiliationCredential" in configs
    assert configs["UniversityAffiliationCredential"]["credential_definition"] == {
        "@context": [
            "https://www.w3.org/ns/credentials/v2",
            "https://secure-ssi.example/contexts/university-affiliation/v1",
        ],
        "type": ["VerifiableCredential", "UniversityAffiliationCredential"],
    }
    proof_types = configs["UniversityAffiliationCredential"].get("proof_types_supported", {})
    assert "jwt" in proof_types
    assert "EdDSA" in proof_types["jwt"]["proof_signing_alg_values_supported"]


@pytest.mark.parametrize(
    "credential_type",
    ["NationalIdCredential", "DriverLicenseCredential"],
)
def test_wp05_offer_rejects_unconfigured_credential_profiles(
    credential_type: str,
) -> None:
    response = client.post(
        "/api/v1/oid4vci/offers",
        json={
            "credentialConfigurationIds": [credential_type],
            "subjectData": {"sampleClaim": "synthetic"},
        },
        headers=_get_auth_headers("issuer"),
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "HTTP_422"
    assert "not supported by the active profile" in error["message"]


def test_wp05_nonce_endpoint_generates_fresh_server_nonce():
    """Nonce endpoint produces valid c_nonce with 600s lifetime semantics."""
    res = client.post("/api/v1/oid4vci/nonce")
    assert res.status_code == 200
    data = res.json()
    assert "c_nonce" in data or "cNonce" in data
    nonce = data.get("c_nonce") or data.get("cNonce")
    assert isinstance(nonce, str) and len(nonce) > 16
    assert data.get("c_nonce_expires_in") == 600 or data.get("cNonceExpiresIn") == 600


# ============================================================================
# 2. TOKEN ENDPOINT (PRE-AUTHORIZED CODE GRANT)
# ============================================================================

def test_wp05_token_endpoint_valid_grant_and_single_use_enforcement():
    """Valid pre-authorized code exchange produces access token + c_nonce; replay fails closed."""
    offer = _create_test_offer()
    code = offer["preAuthorizedCode"]

    # 1. First redemption via form-urlencoded -> SUCCESS
    token_payload = {
        "grant_type": "urn:ietf:params:oauth:grant-type:pre-authorized_code",
        "pre-authorized_code": code,
    }
    res = client.post("/api/v1/oid4vci/token", data=token_payload)
    assert res.status_code == 200, f"Token exchange failed: {res.text}"
    token_data = res.json()
    assert "access_token" in token_data
    assert token_data["token_type"].lower() == "bearer"
    assert "c_nonce" in token_data
    assert token_data["c_nonce_expires_in"] == 600

    # 2. Second redemption attempt with same code -> REJECTED (single use)
    res_replay = client.post("/api/v1/oid4vci/token", data=token_payload)
    assert res_replay.status_code == 400
    assert res_replay.json()["error"] == "invalid_grant"
    assert "redeemed" in res_replay.json()["error_description"]


def test_wp05_token_endpoint_unsupported_grant_type_rejected():
    """Unsupported grant type fails closed with unsupported_grant_type error."""
    offer = _create_test_offer()
    res = client.post(
        "/api/v1/oid4vci/token",
        data={
            "grant_type": "authorization_code",
            "pre-authorized_code": offer["preAuthorizedCode"],
        },
    )
    assert res.status_code == 400
    assert res.json()["error"] == "unsupported_grant_type"


def test_wp05_token_endpoint_missing_code_rejected():
    """Missing pre-authorized code fails closed with invalid_request error."""
    res = client.post(
        "/api/v1/oid4vci/token",
        data={"grant_type": "urn:ietf:params:oauth:grant-type:pre-authorized_code"},
    )
    assert res.status_code == 400
    assert res.json()["error"] == "invalid_request"


def test_wp05_token_endpoint_unknown_code_rejected():
    """Unknown pre-authorized code fails closed with invalid_grant."""
    res = client.post(
        "/api/v1/oid4vci/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:pre-authorized_code",
            "pre-authorized_code": "unknown_invalid_code_99999",
        },
    )
    assert res.status_code == 400
    assert res.json()["error"] == "invalid_grant"


def test_wp05_token_endpoint_user_pin_enforcement():
    """Offer requiring user PIN rejects incorrect PIN and accepts correct PIN."""
    offer = _create_test_offer(user_pin="7492")
    code = offer["preAuthorizedCode"]

    # Wrong PIN fails
    res_bad = client.post(
        "/api/v1/oid4vci/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:pre-authorized_code",
            "pre-authorized_code": code,
            "user_pin": "0000",
        },
    )
    assert res_bad.status_code == 400
    assert res_bad.json()["error"] == "invalid_grant"
    assert "PIN" in res_bad.json()["error_description"]

    # Correct PIN succeeds
    res_good = client.post(
        "/api/v1/oid4vci/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:pre-authorized_code",
            "pre-authorized_code": code,
            "user_pin": "7492",
        },
    )
    assert res_good.status_code == 200
    assert "access_token" in res_good.json()


# ============================================================================
# 3. CREDENTIAL ENDPOINT & PROOF-OF-POSSESSION
# ============================================================================

def test_wp05_canonical_golden_path_issuance_with_bearer_and_proof():
    """Canonical Golden Path: Token exchange -> JWT Holder Proof -> Credential -> Wallet persistence."""
    offer = _create_test_offer()
    code = offer["preAuthorizedCode"]

    # 1. Exchange code for token
    token_res = client.post(
        "/api/v1/oid4vci/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:pre-authorized_code",
            "pre-authorized_code": code,
        },
    )
    assert token_res.status_code == 200
    token_data = token_res.json()
    access_token = token_data["access_token"]
    c_nonce = token_data["c_nonce"]

    # 2. Holder obtains an issuer-nonce proof through the authenticated wallet.
    holder_headers, wallet_id, holder_did = _create_holder_wallet()
    proof_holder_did, proof_jwt = _create_wallet_proof(
        holder_headers=holder_headers,
        wallet_id=wallet_id,
        nonce=c_nonce,
    )
    assert proof_holder_did == holder_did

    # 3. Call Credential Endpoint with Bearer token and proof
    cred_req = {
        "credential_configuration_id": "UniversityAffiliationCredential",
        "proof": {
            "proof_type": "jwt",
            "jwt": proof_jwt,
        },
        "wallet_id": wallet_id,
    }
    cred_res = client.post(
        "/api/v1/oid4vci/credential",
        json=cred_req,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert cred_res.status_code == 200, f"Credential issuance failed: {cred_res.text}"
    cred_data = cred_res.json()

    assert "credential" in cred_data
    vc = cred_data["credential"]
    assert vc["credentialSubject"]["id"] == holder_did
    assert vc["credentialSubject"]["degree"] == "Master of Science"
    assert vc["proof"]["type"] == "DataIntegrityProof"
    assert vc["proof"]["cryptosuite"] == "eddsa-jcs-2022"
    assert "c_nonce" in cred_data  # Next fresh nonce returned

    # 4. Verify the issued credential is valid and persisted
    verifier_hdrs = _get_auth_headers("verifier")
    verify_res = client.post(
        "/api/v1/credentials/verify",
        json={"credential": vc},
        headers=verifier_hdrs,
    )
    assert verify_res.json()["valid"] is True

    status_res = client.get(f"/api/v1/credentials/{vc['id']}/status")
    assert status_res.status_code == 200
    assert status_res.json()["status"].lower() == "active"


def test_wp05_qeaa_issuance_uses_the_validator_pinned_context() -> None:
    offer = _create_test_offer(
        config_ids=["QualifiedElectronicAttestationCredential"]
    )
    token_response = client.post(
        "/api/v1/oid4vci/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:pre-authorized_code",
            "pre-authorized_code": offer["preAuthorizedCode"],
        },
    )
    assert token_response.status_code == 200
    token = token_response.json()["access_token"]

    holder_headers, wallet_id, holder_did = _create_holder_wallet()
    proof_holder_did, proof_jwt = _create_wallet_proof(
        holder_headers=holder_headers,
        wallet_id=wallet_id,
        nonce=token_response.json()["c_nonce"],
    )
    assert proof_holder_did == holder_did

    issued = client.post(
        "/api/v1/oid4vci/credential",
        json={
            "credential_configuration_id": "QualifiedElectronicAttestationCredential",
            "proof": {"proof_type": "jwt", "jwt": proof_jwt},
            "wallet_id": wallet_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert issued.status_code == 200, issued.text
    credential = issued.json()["credential"]
    assert credential["@context"] == [
        "https://www.w3.org/ns/credentials/v2",
        "https://secure-ssi.example/contexts/qeaa/v1",
    ]
    assert credential["type"] == [
        "VerifiableCredential",
        "QualifiedElectronicAttestationCredential",
    ]
    assert CredentialProfileValidator().validate(
        credential,
        require_proof=True,
    )["credentialSubject"]["id"] == holder_did


def test_wp05_credential_endpoint_unauthorized_without_bearer():
    """Missing Bearer token and missing legacy code fails with 401 Unauthorized."""
    res = client.post(
        "/api/v1/oid4vci/credential",
        json={"credential_configuration_id": "UniversityAffiliationCredential"},
    )
    assert res.status_code == 401
    assert "invalid_token" in res.text


def test_wp05_credential_endpoint_invalid_bearer_token_rejected():
    """Invalid or fabricated Bearer token fails with 401 Unauthorized."""
    res = client.post(
        "/api/v1/oid4vci/credential",
        json={"credential_configuration_id": "UniversityAffiliationCredential"},
        headers={"Authorization": "Bearer fabricated_invalid_token_xyz"},
    )
    assert res.status_code == 401
    assert "invalid_token" in res.text


def test_wp05_credential_endpoint_missing_proof_rejected():
    """Bearer token present but missing proof object fails with 400 invalid_proof."""
    offer = _create_test_offer()
    token_res = client.post(
        "/api/v1/oid4vci/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:pre-authorized_code",
            "pre-authorized_code": offer["preAuthorizedCode"],
        },
    )
    token = token_res.json()["access_token"]

    res = client.post(
        "/api/v1/oid4vci/credential",
        json={"credential_configuration_id": "UniversityAffiliationCredential"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert res.json()["error"] == "invalid_proof"


def test_wp05_credential_endpoint_tampered_proof_signature_rejected():
    """JWT proof with tampered signature fails closed mathematically."""
    offer = _create_test_offer()
    token_res = client.post(
        "/api/v1/oid4vci/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:pre-authorized_code",
            "pre-authorized_code": offer["preAuthorizedCode"],
        },
    )
    token = token_res.json()["access_token"]
    nonce = token_res.json()["c_nonce"]

    priv, holder_did = _create_holder_key()
    valid_jwt = build_holder_jwt_proof(
        holder_did=holder_did,
        private_key=priv,
        audience="http://localhost:8001",
        nonce=nonce,
    )
    parts = valid_jwt.split(".")
    # Mutate the signature bytes
    tampered_sig = base64.urlsafe_b64encode(b"invalid_signature_bytes_32_bytes_len!!").decode()
    tampered_jwt = f"{parts[0]}.{parts[1]}.{tampered_sig}"

    res = client.post(
        "/api/v1/oid4vci/credential",
        json={
            "credential_configuration_id": "UniversityAffiliationCredential",
            "proof": {"proof_type": "jwt", "jwt": tampered_jwt},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert res.json()["error"] == "invalid_proof"
    assert "signature is mathematically invalid" in res.json()["error_description"]


def test_wp05_credential_endpoint_wrong_audience_rejected():
    """JWT proof specifying wrong audience fails closed."""
    offer = _create_test_offer()
    token_res = client.post(
        "/api/v1/oid4vci/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:pre-authorized_code",
            "pre-authorized_code": offer["preAuthorizedCode"],
        },
    )
    token = token_res.json()["access_token"]
    nonce = token_res.json()["c_nonce"]

    priv, holder_did = _create_holder_key()
    bad_aud_jwt = build_holder_jwt_proof(
        holder_did=holder_did,
        private_key=priv,
        audience="https://malicious-adversary.com",
        nonce=nonce,
    )

    res = client.post(
        "/api/v1/oid4vci/credential",
        json={
            "credential_configuration_id": "UniversityAffiliationCredential",
            "proof": {"proof_type": "jwt", "jwt": bad_aud_jwt},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert res.json()["error"] == "invalid_proof"
    assert "audience" in res.json()["error_description"]


def test_wp05_credential_endpoint_stale_proof_timestamp_rejected():
    """Proof created outside freshness window (> 300s old) fails closed."""
    offer = _create_test_offer()
    token_res = client.post(
        "/api/v1/oid4vci/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:pre-authorized_code",
            "pre-authorized_code": offer["preAuthorizedCode"],
        },
    )
    token = token_res.json()["access_token"]
    nonce = token_res.json()["c_nonce"]

    priv, holder_did = _create_holder_key()
    stale_time = datetime.now(UTC) - timedelta(seconds=600)  # 10 minutes ago
    stale_jwt = build_holder_jwt_proof(
        holder_did=holder_did,
        private_key=priv,
        audience="http://localhost:8001",
        nonce=nonce,
        issued_at=stale_time,
    )

    res = client.post(
        "/api/v1/oid4vci/credential",
        json={
            "credential_configuration_id": "UniversityAffiliationCredential",
            "proof": {"proof_type": "jwt", "jwt": stale_jwt},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert res.json()["error"] == "invalid_proof"
    assert "freshness window" in res.json()["error_description"]


def test_wp05_credential_endpoint_replayed_c_nonce_rejected():
    """Replaying the same c_nonce fails closed with invalid_nonce (replay detected)."""
    offer1 = _create_test_offer()
    token_res1 = client.post(
        "/api/v1/oid4vci/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:pre-authorized_code",
            "pre-authorized_code": offer1["preAuthorizedCode"],
        },
    )
    token1 = token_res1.json()["access_token"]
    nonce = token_res1.json()["c_nonce"]

    holder_headers, wallet_id, holder_did = _create_holder_wallet()
    proof_holder_did, proof_jwt = _create_wallet_proof(
        holder_headers=holder_headers,
        wallet_id=wallet_id,
        nonce=nonce,
    )
    assert proof_holder_did == holder_did

    # 1. First presentation consumes the nonce -> SUCCESS
    res1 = client.post(
        "/api/v1/oid4vci/credential",
        json={
            "credential_configuration_id": "UniversityAffiliationCredential",
            "proof": {"proof_type": "jwt", "jwt": proof_jwt},
            "wallet_id": wallet_id,
        },
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert res1.status_code == 200

    # 2. Offer 2 token request: attempt to reuse the old nonce in proof -> REJECTED
    offer2 = _create_test_offer()
    token_res2 = client.post(
        "/api/v1/oid4vci/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:pre-authorized_code",
            "pre-authorized_code": offer2["preAuthorizedCode"],
        },
    )
    token2 = token_res2.json()["access_token"]

    res2 = client.post(
        "/api/v1/oid4vci/credential",
        json={
            "credential_configuration_id": "UniversityAffiliationCredential",
            "proof": {"proof_type": "jwt", "jwt": proof_jwt},  # contains already-consumed nonce
            "wallet_id": wallet_id,
        },
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert res2.status_code == 400
    assert res2.json()["error"] == "invalid_nonce"
    assert "nonce mismatch" in res2.json()["error_description"]


def test_wp05_credential_endpoint_unsupported_credential_config_rejected():
    """Requesting an unoffered credential configuration ID fails closed."""
    offer = _create_test_offer(config_ids=["UniversityAffiliationCredential"])
    token_res = client.post(
        "/api/v1/oid4vci/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:pre-authorized_code",
            "pre-authorized_code": offer["preAuthorizedCode"],
        },
    )
    token = token_res.json()["access_token"]
    nonce = token_res.json()["c_nonce"]

    priv, holder_did = _create_holder_key()
    proof_jwt = build_holder_jwt_proof(
        holder_did=holder_did,
        private_key=priv,
        audience="http://localhost:8001",
        nonce=nonce,
    )

    res = client.post(
        "/api/v1/oid4vci/credential",
        json={
            "credential_configuration_id": "NonExistentSpecialClearanceCredential",
            "proof": {"proof_type": "jwt", "jwt": proof_jwt},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert res.json()["error"] == "unsupported_credential_configuration_id"


# ============================================================================
# 4. LEGACY DIRECT ISSUANCE MIGRATION & ISOLATION
# ============================================================================

def test_wp05_legacy_direct_issuance_isolated_with_warning_headers():
    """Legacy preAuthorizedCode direct post returns X-Legacy-Issuance and Warning header."""
    offer = _create_test_offer()
    code = offer["preAuthorizedCode"]
    holder_headers, wallet_id, holder_did = _create_holder_wallet()

    # Legacy direct call to /credential
    res_direct = client.post(
        "/api/v1/oid4vci/credential",
        json={
            "preAuthorizedCode": code,
            "holderDid": holder_did,
            "walletId": wallet_id,
        },
        headers=holder_headers,
    )
    assert res_direct.status_code == 201, f"res_direct failed: {res_direct.text}"
    assert res_direct.headers.get("X-Legacy-Issuance") == "true"
    assert "Deprecated direct" in res_direct.headers.get("Warning", "")

    # Legacy isolated endpoint /legacy/claim
    offer2 = _create_test_offer()
    res_legacy = client.post(
        "/api/v1/oid4vci/legacy/claim",
        json={
            "preAuthorizedCode": offer2["preAuthorizedCode"],
            "holderDid": holder_did,
            "walletId": wallet_id,
        },
        headers=holder_headers,
    )
    assert res_legacy.status_code == 201
    assert res_legacy.headers.get("X-Legacy-Issuance") == "true"


# ============================================================================
# 5. CROSS-WORK-PACKAGE REGRESSION (WP-01 to WP-04)
# ============================================================================

def test_wp05_issued_credential_participates_in_wp04_oid4vp_dcql_presentation():
    """Credential issued via OID4VCI 1.0 canonical flow is successfully presented and verified in WP-04 DCQL."""
    # 1. Issue credential via OID4VCI 1.0
    offer = _create_test_offer()
    token_res = client.post(
        "/api/v1/oid4vci/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:pre-authorized_code",
            "pre-authorized_code": offer["preAuthorizedCode"],
        },
    )
    token = token_res.json()["access_token"]
    nonce = token_res.json()["c_nonce"]

    holder_headers, wallet_id, holder_did = _create_holder_wallet()
    proof_holder_did, proof_jwt = _create_wallet_proof(
        holder_headers=holder_headers,
        wallet_id=wallet_id,
        nonce=nonce,
    )
    assert proof_holder_did == holder_did
    cred_res = client.post(
        "/api/v1/oid4vci/credential",
        json={
            "credential_configuration_id": "UniversityAffiliationCredential",
            "proof": {"proof_type": "jwt", "jwt": proof_jwt},
            "wallet_id": wallet_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert cred_res.status_code == 200
    issued_vc = cred_res.json()["credential"]

    # 2. Verifier initializes WP-04 session with DCQL
    verif_hdrs = _get_auth_headers("verifier")
    dcql_query = {
        "credentials": [
            {
                "id": "q_degree",
                "format": "w3c_vc",
                "meta": {"type_values": ["UniversityAffiliationCredential"]},
                "claims": [{"id": "c1", "path": ["credentialSubject", "degree"]}],
            }
        ]
    }
    vp_session_res = client.post(
        "/api/v1/oid4vp/requests",
        json={
            "purpose": "Verify issued degree",
            "requestedFields": ["degree"],
            "dcqlQuery": dcql_query,
        },
        headers=verif_hdrs,
    )
    assert vp_session_res.status_code == 201
    vp_session = vp_session_res.json()
    session_id = vp_session["sessionId"]
    credential_id = issued_vc["id"]
    credential_subject = issued_vc.get("credentialSubject")
    assert isinstance(credential_subject, dict)
    disclosed_claims = {
        key: value
        for key, value in credential_subject.items()
        if key != "id"
    }
    assert disclosed_claims["degree"] == "Master of Science"
    consent_res = client.post(
        f"/api/v1/oid4vp/requests/{session_id}/wallet-consent",
        json={
            "walletId": wallet_id,
            "holderDid": holder_did,
            "action": "APPROVE",
            "approvedCredentials": [credential_id],
            "approvedClaims": disclosed_claims,
        },
        headers=holder_headers,
    )
    assert consent_res.status_code == 200, consent_res.text

    # 3. Holder creates a wallet-key-signed W3C VP from persisted credentials.
    presentation_res = client.post(
        "/api/v1/oid4vp/wallet-presentation",
        json={
            "sessionId": session_id,
            "walletId": wallet_id,
            "credentialIds": [credential_id],
            "disclosedClaims": disclosed_claims,
        },
        headers=holder_headers,
    )
    assert presentation_res.status_code == 200, presentation_res.text
    vp = presentation_res.json()["vpToken"]

    # 4. Submit to Direct Post
    dp_res = client.post(
        "/api/v1/oid4vp/response",
        json={
            "sessionId": session_id,
            "vpToken": vp,
            "disclosedClaims": disclosed_claims,
        },
    )
    assert dp_res.status_code == 200
    result = dp_res.json()["result"]
    assert result["finalPolicyResult"] == "ACCEPTED"
    assert result["holderBindingValid"] is True
    assert result["details"]["dcql"]["satisfied"] is True
