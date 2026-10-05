from datetime import UTC, datetime, timedelta
from typing import Any
import copy
import uuid
import pytest
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from app.main import app
from app.infrastructure.crypto.local_holder_key_provider import (
    SYNTHETIC_HOLDER_DID,
    ED25519_MULTICODEC_PREFIX,
)
from app.infrastructure.crypto.multibase import encode_base58_btc
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


def _create_oid4vp_session(token: str, *, client_id: str | None = None) -> tuple[str, str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    req_payload = {
        "purpose": "WP-02 Holder Binding Verification Test",
        "requestedCredentialTypes": ["UniversityAffiliationCredential"],
        "requestedFields": ["degree", "gpa"],
        "ttlSeconds": 600,
    }
    if client_id:
        req_payload["clientId"] = client_id
    res = client.post("/api/v1/oid4vp/requests", json=req_payload, headers=headers)
    assert res.status_code == 201, f"Create session failed: {res.text}"
    data = res.json()
    return data["sessionId"], data["nonce"], data.get("clientId", "http://testserver/verifier")


def _build_valid_signed_vc(*, holder_did: str = SYNTHETIC_HOLDER_DID) -> dict[str, Any]:
    now = datetime.now(UTC)
    raw_vc = {
        "@context": [
            "https://www.w3.org/ns/credentials/v2",
            "https://secure-ssi.example/contexts/university-affiliation/v1",
        ],
        "id": f"urn:uuid:{uuid.uuid4()}",
        "type": ["VerifiableCredential", "UniversityAffiliationCredential"],
        "issuer": "did:web:issuer.example",
        "validFrom": (now - timedelta(days=30)).isoformat().replace("+00:00", "Z"),
        "validUntil": (now + timedelta(days=365)).isoformat().replace("+00:00", "Z"),
        "credentialSubject": {
            "id": holder_did,
            "degree": "MSc Computer Science",
            "gpa": "3.95",
        },
    }
    proof_service = build_local_proof_service(clock=lambda: now)
    return proof_service.sign_credential(raw_vc)


# ==============================================================================
# POSITIVE TESTS
# ==============================================================================


def test_wp02_positive_valid_holder_binding_succeeds():
    """A valid VP signed with holder's private key bound to session nonce/audience must succeed."""
    token = _get_verifier_token()
    session_id, nonce, client_id = _create_oid4vp_session(token)
    vc = _build_valid_signed_vc()

    vp = build_signed_presentation(
        vc,
        nonce=nonce,
        domain=client_id,
        holder_did=SYNTHETIC_HOLDER_DID,
    )

    res = client.post(
        "/api/v1/oid4vp/response",
        json={
            "sessionId": session_id,
            "vpToken": vp,
            "disclosedClaims": {"degree": "MSc Computer Science"},
            "aiRiskScore": 10,
        },
    )
    assert res.status_code == 200
    result = res.json()["result"]
    assert result["holderBindingValid"] is True
    assert result["details"]["holderBindingReason"] == "VALID"
    assert result["signatureValid"] is True
    assert result["challengeValid"] is True
    assert result["finalPolicyResult"] == "ACCEPTED"


def test_wp02_positive_presentation_endpoint_lifecycle():
    """Holder uses POST /api/v1/oid4vp/presentation to generate signed VP and submits to verifier."""
    token = _get_verifier_token()
    session_id, nonce, client_id = _create_oid4vp_session(token)
    vc = _build_valid_signed_vc()

    # Call presentation generator endpoint
    res_pres = client.post(
        "/api/v1/oid4vp/presentation",
        json={
            "sessionId": session_id,
            "verifiableCredentials": [vc],
            "disclosedClaims": {"degree": "MSc Computer Science"},
            "holderDid": SYNTHETIC_HOLDER_DID,
        },
    )
    assert res_pres.status_code == 200
    vp_data = res_pres.json()["vpToken"]
    assert vp_data["holder"] == SYNTHETIC_HOLDER_DID
    assert vp_data["proof"]["type"] == "DataIntegrityProof"
    assert vp_data["proof"]["cryptosuite"] == "eddsa-jcs-2022"
    assert vp_data["proof"]["challenge"] == nonce

    # Submit to verifier
    res_post = client.post(
        "/api/v1/oid4vp/response",
        json={
            "sessionId": session_id,
            "vpToken": vp_data,
            "disclosedClaims": {"degree": "MSc Computer Science"},
            "aiRiskScore": 10,
        },
    )
    assert res_post.status_code == 200
    res = res_post.json()["result"]
    assert res["holderBindingValid"] is True
    assert res["details"]["holderBindingReason"] == "VALID"
    assert res["finalPolicyResult"] == "ACCEPTED"


def test_wp02_positive_ephemeral_keypair_holder():
    """Holder with an arbitrary, newly generated did:key signs presentation and succeeds."""
    priv = Ed25519PrivateKey.generate()
    pub_bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    multibase = encode_base58_btc(ED25519_MULTICODEC_PREFIX + pub_bytes)
    holder_did = f"did:key:{multibase}"

    token = _get_verifier_token()
    session_id, nonce, client_id = _create_oid4vp_session(token)
    vc = _build_valid_signed_vc(holder_did=holder_did)

    vp = build_signed_presentation(
        vc,
        nonce=nonce,
        domain=client_id,
        holder_did=holder_did,
        private_key=priv,
    )

    res = client.post(
        "/api/v1/oid4vp/response",
        json={
            "sessionId": session_id,
            "vpToken": vp,
            "disclosedClaims": {"degree": "MSc Computer Science"},
            "aiRiskScore": 10,
        },
    )
    assert res.status_code == 200
    result = res.json()["result"]
    assert result["holderBindingValid"] is True
    assert result["finalPolicyResult"] == "ACCEPTED"


# ==============================================================================
# NEGATIVE / FAIL-CLOSED TESTS
# ==============================================================================


def test_wp02_negative_missing_presentation_proof_fails():
    """Presentation lacking a proof object must fail holder binding closed."""
    token = _get_verifier_token()
    session_id, nonce, client_id = _create_oid4vp_session(token)
    vc = _build_valid_signed_vc()

    vp = {
        "@context": ["https://www.w3.org/ns/credentials/v2"],
        "type": ["VerifiablePresentation"],
        "holder": SYNTHETIC_HOLDER_DID,
        "verifiableCredential": [vc],
        # No proof!
    }

    res = client.post("/api/v1/oid4vp/response", json={"sessionId": session_id, "vpToken": vp})
    assert res.status_code == 200
    result = res.json()["result"]
    assert result["holderBindingValid"] is False
    assert result["details"]["holderBindingReason"] in {"HOLDER_BINDING_MISSING", "HOLDER_BINDING_MISSING_PROOF"}
    assert result["finalPolicyResult"] == "REJECTED"


def test_wp02_negative_unsupported_cryptosuite_fails():
    """Unsupported cryptosuite (e.g. Ed25519Signature2020 or rsa-jcs-2022) must fail."""
    token = _get_verifier_token()
    session_id, nonce, client_id = _create_oid4vp_session(token)
    vc = _build_valid_signed_vc()

    vp = build_signed_presentation(vc, nonce=nonce, domain=client_id)
    vp["proof"]["cryptosuite"] = "rsa-jcs-2022"

    res = client.post("/api/v1/oid4vp/response", json={"sessionId": session_id, "vpToken": vp})
    assert res.status_code == 200
    result = res.json()["result"]
    assert result["holderBindingValid"] is False
    assert result["details"]["holderBindingReason"] == "HOLDER_BINDING_INVALID_PROOF_STRUCTURE"
    assert result["finalPolicyResult"] == "REJECTED"


def test_wp02_negative_invalid_proof_purpose_fails():
    """Proof purpose other than 'authentication' (e.g. 'assertionMethod') must fail."""
    token = _get_verifier_token()
    session_id, nonce, client_id = _create_oid4vp_session(token)
    vc = _build_valid_signed_vc()

    vp = build_signed_presentation(vc, nonce=nonce, domain=client_id, proof_purpose="assertionMethod")

    res = client.post("/api/v1/oid4vp/response", json={"sessionId": session_id, "vpToken": vp})
    assert res.status_code == 200
    result = res.json()["result"]
    assert result["holderBindingValid"] is False
    assert result["details"]["holderBindingReason"] == "HOLDER_BINDING_INVALID_PROOF_PURPOSE"
    assert result["finalPolicyResult"] == "REJECTED"


def test_wp02_negative_missing_nonce_fails():
    """Proof without challenge/nonce must fail holder binding."""
    token = _get_verifier_token()
    session_id, nonce, client_id = _create_oid4vp_session(token)
    vc = _build_valid_signed_vc()

    vp = build_signed_presentation(vc, nonce=nonce, domain=client_id)
    vp["proof"].pop("challenge", None)
    vp["proof"].pop("nonce", None)

    res = client.post("/api/v1/oid4vp/response", json={"sessionId": session_id, "vpToken": vp})
    assert res.status_code == 200
    result = res.json()["result"]
    assert result["holderBindingValid"] is False
    assert result["details"]["holderBindingReason"] == "HOLDER_BINDING_MISSING_NONCE"
    assert result["finalPolicyResult"] == "REJECTED"


def test_wp02_negative_mismatched_nonce_fails():
    """Proof bound to a wrong/foreign challenge must fail holder binding."""
    token = _get_verifier_token()
    session_id, nonce, client_id = _create_oid4vp_session(token)
    vc = _build_valid_signed_vc()

    vp = build_signed_presentation(vc, nonce="wrong-forged-nonce-9999", domain=client_id)

    res = client.post("/api/v1/oid4vp/response", json={"sessionId": session_id, "vpToken": vp})
    assert res.status_code == 200
    result = res.json()["result"]
    assert result["holderBindingValid"] is False
    assert result["details"]["holderBindingReason"] == "HOLDER_BINDING_WRONG_NONCE"
    assert result["finalPolicyResult"] == "REJECTED"


def test_wp02_negative_missing_audience_and_domain_fails():
    """Proof with neither audience nor domain must fail holder binding."""
    token = _get_verifier_token()
    session_id, nonce, client_id = _create_oid4vp_session(token)
    vc = _build_valid_signed_vc()

    vp = build_signed_presentation(vc, nonce=nonce, domain=client_id)
    vp["proof"].pop("domain", None)
    vp["proof"].pop("audience", None)

    res = client.post("/api/v1/oid4vp/response", json={"sessionId": session_id, "vpToken": vp})
    assert res.status_code == 200
    result = res.json()["result"]
    assert result["holderBindingValid"] is False
    assert result["details"]["holderBindingReason"] == "HOLDER_BINDING_MISSING_AUDIENCE"
    assert result["finalPolicyResult"] == "REJECTED"


def test_wp02_negative_mismatched_audience_domain_fails():
    """Proof bound to a different verifier/attacker domain must fail holder binding."""
    token = _get_verifier_token()
    session_id, nonce, client_id = _create_oid4vp_session(token)
    vc = _build_valid_signed_vc()

    vp = build_signed_presentation(vc, nonce=nonce, domain="https://evil-phishing-verifier.example")

    res = client.post("/api/v1/oid4vp/response", json={"sessionId": session_id, "vpToken": vp})
    assert res.status_code == 200
    result = res.json()["result"]
    assert result["holderBindingValid"] is False
    assert result["details"]["holderBindingReason"] == "HOLDER_BINDING_WRONG_AUDIENCE"
    assert result["finalPolicyResult"] == "REJECTED"


def test_wp02_negative_holder_did_mismatch_fails():
    """If VP holder or VM controller does not match VC credentialSubject.id, verification must fail."""
    token = _get_verifier_token()
    session_id, nonce, client_id = _create_oid4vp_session(token)

    # VC issued to SYNTHETIC_HOLDER_DID
    vc = _build_valid_signed_vc(holder_did=SYNTHETIC_HOLDER_DID)

    # Presentation signed by a different entity (attacker)
    attacker_priv = Ed25519PrivateKey.generate()
    attacker_pub = attacker_priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    attacker_did = f"did:key:{encode_base58_btc(ED25519_MULTICODEC_PREFIX + attacker_pub)}"

    vp = build_signed_presentation(
        vc,
        nonce=nonce,
        domain=client_id,
        holder_did=attacker_did,
        private_key=attacker_priv,
    )

    res = client.post("/api/v1/oid4vp/response", json={"sessionId": session_id, "vpToken": vp})
    assert res.status_code == 200
    result = res.json()["result"]
    assert result["holderBindingValid"] is False
    assert result["details"]["holderBindingReason"] == "HOLDER_BINDING_HOLDER_MISMATCH"
    assert result["finalPolicyResult"] == "REJECTED"


def test_wp02_negative_unauthorized_verification_relationship_fails():
    """If verification method is not in did_doc['authentication'], proof must fail."""
    token = _get_verifier_token()
    session_id, nonce, client_id = _create_oid4vp_session(token)
    vc = _build_valid_signed_vc()

    vp = build_signed_presentation(vc, nonce=nonce, domain=client_id)
    # Point verificationMethod to a key fragment not listed in authentication
    vp["proof"]["verificationMethod"] = f"{SYNTHETIC_HOLDER_DID}#unauthorized-key-fragment"

    res = client.post("/api/v1/oid4vp/response", json={"sessionId": session_id, "vpToken": vp})
    assert res.status_code == 200
    result = res.json()["result"]
    assert result["holderBindingValid"] is False
    assert result["details"]["holderBindingReason"] == "HOLDER_NOT_AUTHORIZED_FOR_AUTHENTICATION"
    assert result["finalPolicyResult"] == "REJECTED"


def test_wp02_negative_malformed_proof_value_fails():
    """Non-base58 or truncated proof value must fail closed."""
    token = _get_verifier_token()
    session_id, nonce, client_id = _create_oid4vp_session(token)
    vc = _build_valid_signed_vc()

    vp = build_signed_presentation(vc, nonce=nonce, domain=client_id)
    vp["proof"]["proofValue"] = "not_a_valid_base58_btc_string_000!!!"

    res = client.post("/api/v1/oid4vp/response", json={"sessionId": session_id, "vpToken": vp})
    assert res.status_code == 200
    result = res.json()["result"]
    assert result["holderBindingValid"] is False
    assert result["details"]["holderBindingReason"] == "HOLDER_BINDING_MALFORMED_PROOF_VALUE"
    assert result["finalPolicyResult"] == "REJECTED"


def test_wp02_negative_invalid_cryptographic_signature_fails():
    """Proof signed with wrong private key or corrupted signature bytes must fail."""
    token = _get_verifier_token()
    session_id, nonce, client_id = _create_oid4vp_session(token)
    vc = _build_valid_signed_vc()

    vp = build_signed_presentation(vc, nonce=nonce, domain=client_id)
    # Corrupt valid signature bytes by flipping bits in base58 proofValue
    from app.infrastructure.crypto.multibase import decode_base58_btc, encode_base58_btc
    raw_sig = bytearray(decode_base58_btc(vp["proof"]["proofValue"]))
    raw_sig[0] ^= 0xFF
    vp["proof"]["proofValue"] = encode_base58_btc(bytes(raw_sig))

    res = client.post("/api/v1/oid4vp/response", json={"sessionId": session_id, "vpToken": vp})
    assert res.status_code == 200
    result = res.json()["result"]
    assert result["holderBindingValid"] is False
    assert result["details"]["holderBindingReason"] == "HOLDER_BINDING_INVALID_SIGNATURE"
    assert result["finalPolicyResult"] == "REJECTED"


def test_wp02_negative_tampered_payload_after_signing_fails():
    """Tampering with VP fields (e.g. injecting claims or modifying validUntil) breaks signature."""
    token = _get_verifier_token()
    session_id, nonce, client_id = _create_oid4vp_session(token)
    vc = _build_valid_signed_vc()

    vp = build_signed_presentation(vc, nonce=nonce, domain=client_id)
    # Attacker alters validUntil or adds unauthorized claim
    vp["validUntil"] = "2099-12-31T23:59:59Z"

    res = client.post("/api/v1/oid4vp/response", json={"sessionId": session_id, "vpToken": vp})
    assert res.status_code == 200
    result = res.json()["result"]
    assert result["holderBindingValid"] is False
    assert result["details"]["holderBindingReason"] == "HOLDER_BINDING_INVALID_SIGNATURE"
    assert result["finalPolicyResult"] == "REJECTED"


def test_wp02_negative_unresolvable_did_fails():
    """An unresolvable or malformed holder DID must fail closed."""
    token = _get_verifier_token()
    session_id, nonce, client_id = _create_oid4vp_session(token)
    vc = _build_valid_signed_vc()
    unresolvable_did = "did:web:unresolvable-nonexistent-domain.xyz"
    vc["credentialSubject"]["id"] = unresolvable_did

    vp = build_signed_presentation(vc, nonce=nonce, domain=client_id, holder_did=unresolvable_did)
    vp["proof"]["verificationMethod"] = f"{unresolvable_did}#key-1"

    res = client.post("/api/v1/oid4vp/response", json={"sessionId": session_id, "vpToken": vp})
    assert res.status_code == 200
    result = res.json()["result"]
    assert result["holderBindingValid"] is False
    assert result["details"]["holderBindingReason"] == "HOLDER_BINDING_UNKNOWN_KEY"
    assert result["finalPolicyResult"] == "REJECTED"
