import copy
from typing import Any

from app.infrastructure.crypto.ed25519_signer import (
    Ed25519CredentialSigner,
)
from app.infrastructure.crypto.jcs_canonicalizer import JcsCanonicalizer
from app.infrastructure.crypto.local_issuer_key_provider import (
    LocalIssuerKeyProvider,
    SYNTHETIC_ISSUER_DID,
)
from app.infrastructure.crypto.multibase import encode_base58_btc


def _copy(credential: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(credential)


def _sign_with_alternate_key(
    credential: dict[str, Any],
) -> dict[str, Any]:
    tampered = _copy(credential)
    proof = tampered["proof"]
    proof_configuration = _copy(proof)
    proof_configuration.pop("proofValue")
    unsecured = _copy(tampered)
    unsecured.pop("proof")

    alternate_provider = LocalIssuerKeyProvider.alternate_for_tests()
    alternate_key = alternate_provider.get_signing_key(SYNTHETIC_ISSUER_DID)
    signing_input = JcsCanonicalizer().create_signing_input(
        unsecured,
        proof_configuration,
    )
    signature = Ed25519CredentialSigner().sign(
        signing_input,
        alternate_key,
    )
    proof["proofValue"] = encode_base58_btc(signature)
    return tampered


def build_tampered_credentials(
    signed_credential: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    fixtures: dict[str, dict[str, Any]] = {}

    degree = _copy(signed_credential)
    degree["credentialSubject"]["degree"] = "Master of Science"
    fixtures["degree_claim_changed"] = degree

    subject = _copy(signed_credential)
    subject["credentialSubject"]["id"] = (
        "did:key:z6Mkf5rGMoatrSj1f4CyvuHBeXJELe9RPdzo2PKGNCKVtZxQ"
    )
    fixtures["subject_did_changed"] = subject

    issuer = _copy(signed_credential)
    issuer["issuer"] = "did:web:other-issuer.example"
    fixtures["issuer_did_changed"] = issuer

    graduation_year = _copy(signed_credential)
    graduation_year["credentialSubject"]["graduationYear"] = 2027
    fixtures["graduation_year_changed"] = graduation_year

    proof_value = _copy(signed_credential)
    original = proof_value["proof"]["proofValue"]
    proof_value["proof"]["proofValue"] = (
        f"{original[:-1]}{'1' if original[-1] != '1' else '2'}"
    )
    fixtures["proof_value_changed"] = proof_value

    verification_method = _copy(signed_credential)
    verification_method["proof"]["verificationMethod"] = (
        "did:web:issuer.example#unknown-key"
    )
    fixtures["verification_method_changed"] = verification_method

    cryptosuite = _copy(signed_credential)
    cryptosuite["proof"]["cryptosuite"] = "eddsa-rdfc-2022"
    fixtures["cryptosuite_changed"] = cryptosuite

    proof_purpose = _copy(signed_credential)
    proof_purpose["proof"]["proofPurpose"] = "authentication"
    fixtures["proof_purpose_changed"] = proof_purpose

    created = _copy(signed_credential)
    created["proof"]["created"] = "not-a-timestamp"
    fixtures["created_timestamp_malformed"] = created

    proof_removed = _copy(signed_credential)
    proof_removed.pop("proof")
    fixtures["proof_removed"] = proof_removed

    unknown_claim = _copy(signed_credential)
    unknown_claim["credentialSubject"]["fullName"] = "Synthetic Person"
    fixtures["unknown_claim_added"] = unknown_claim

    context = _copy(signed_credential)
    context["@context"] = list(reversed(context["@context"]))
    fixtures["context_order_changed"] = context

    fixtures["public_key_mismatch"] = _sign_with_alternate_key(
        signed_credential
    )

    malformed_proof = _copy(signed_credential)
    malformed_proof["proof"]["proofValue"] = "z0-not-base58"
    fixtures["malformed_proof_value"] = malformed_proof

    other_issuer_key = _copy(signed_credential)
    other_issuer_key["issuer"] = "did:web:other-issuer.example"
    other_issuer_key["proof"]["verificationMethod"] = (
        "did:web:other-issuer.example#key-1"
    )
    fixtures["other_issuer_key_signature"] = _sign_with_alternate_key(
        other_issuer_key
    )

    return fixtures
