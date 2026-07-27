import base64
import copy
import gzip
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.infrastructure.crypto.ed25519_signer import Ed25519CredentialSigner
from app.infrastructure.crypto.jcs_canonicalizer import JcsCanonicalizer
from app.infrastructure.crypto.local_issuer_key_provider import (
    LocalIssuerKeyProvider,
)
from app.infrastructure.crypto.multibase import decode_base58_btc
from app.infrastructure.fixtures.signed_credentials import (
    build_local_proof_service,
)
from app.schemas.status_list_api import (
    BitstringStatusListCredentialResponse,
)
from app.services.credential_validator import CredentialProfileValidator
from app.services.did_resolver import DidKeyResolver


FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures"


def _load(name: str) -> dict[str, Any]:
    return json.loads(
        (FIXTURE_ROOT / name).read_text(encoding="utf-8")
    )


def test_status_bound_fixture_is_vc_v2_data_integrity_compatible() -> None:
    credential = _load("status-bound-university-affiliation.vc.json")

    validated = CredentialProfileValidator().validate(
        credential,
        require_proof=True,
    )
    verification = build_local_proof_service().verify_credential(
        credential,
        verified_at=datetime(2026, 6, 1, tzinfo=UTC),
    )

    assert validated["@context"][0] == (
        "https://www.w3.org/ns/credentials/v2"
    )
    assert validated["credentialStatus"]["type"] == (
        "BitstringStatusListEntry"
    )
    assert validated["credentialStatus"]["statusPurpose"] == "revocation"
    assert validated["proof"]["cryptosuite"] == "eddsa-jcs-2022"
    assert validated["issuer"].startswith("did:web:")
    assert DidKeyResolver().resolve(
        validated["credentialSubject"]["id"]
    ).did_document["id"] == validated["credentialSubject"]["id"]
    assert verification.verified is True


def test_status_list_fixture_has_valid_shape_encoding_and_signature() -> None:
    document = _load("bitstring-status-list-v1.vc.json")
    parsed = BitstringStatusListCredentialResponse.model_validate(
        document
    )
    encoded = parsed.credentialSubject.encodedList[1:]
    encoded += "=" * (-len(encoded) % 4)
    bitstring = gzip.decompress(
        base64.urlsafe_b64decode(encoded.encode("ascii"))
    )

    unsecured = copy.deepcopy(document)
    proof = unsecured.pop("proof")
    proof_value = proof.pop("proofValue")
    canonicalizer = JcsCanonicalizer()
    signing_input = canonicalizer.create_signing_input(
        unsecured,
        proof,
    )
    keys = LocalIssuerKeyProvider()

    assert len(bitstring) == 131072 // 8
    assert not any(bitstring)
    assert Ed25519CredentialSigner().verify(
        signing_input,
        decode_base58_btc(proof_value),
        keys.get_verification_key(proof["verificationMethod"]),
    )
