import json
from pathlib import Path

import pytest

from app.domain.exceptions import (
    UnknownIssuerError,
    UnknownVerificationMethodError,
)
from app.infrastructure.crypto.ed25519_signer import (
    Ed25519CredentialSigner,
)
from app.infrastructure.crypto.local_issuer_key_provider import (
    LocalIssuerKeyProvider,
    SYNTHETIC_ISSUER_DID,
    SYNTHETIC_VERIFICATION_METHOD,
)
from app.infrastructure.crypto.multibase import (
    decode_base58_btc,
    encode_base58_btc,
)


ISSUER_DID_PATH = Path(__file__).parents[1] / "fixtures" / "issuer.did.json"
PRIMARY_SEED_HEX = (
    "dbdd31e053d58e33fff0d0a842d9a510"
    "ee0b5c2b52662caa91e8e6d84821b419"
)


def test_base58_btc_round_trip_preserves_leading_zeroes() -> None:
    payload = b"\x00\x00synthetic-signature"

    assert decode_base58_btc(encode_base58_btc(payload)) == payload


def test_local_public_key_matches_the_issuer_did_document() -> None:
    provider = LocalIssuerKeyProvider()
    document = json.loads(ISSUER_DID_PATH.read_text(encoding="utf-8"))

    assert (
        document["verificationMethod"][0]["publicKeyMultibase"]
        == provider.public_key_multibase
    )
    assert (
        document["verificationMethod"][0]["id"]
        == SYNTHETIC_VERIFICATION_METHOD
    )


def test_signer_uses_library_verification_and_exact_signature_size() -> None:
    provider = LocalIssuerKeyProvider()
    signer = Ed25519CredentialSigner()
    handle = provider.get_signing_key(SYNTHETIC_ISSUER_DID)
    public_key = provider.get_verification_key(
        SYNTHETIC_VERIFICATION_METHOD
    )
    message = b"synthetic canonical signing input"

    signature = signer.sign(message, handle)

    assert len(signature) == 64
    assert signer.verify(message, signature, public_key) is True
    assert signer.verify(message + b"!", signature, public_key) is False
    assert signer.verify(message, signature[:-1], public_key) is False


def test_alternate_key_cannot_verify_a_primary_signature() -> None:
    primary = LocalIssuerKeyProvider()
    alternate = LocalIssuerKeyProvider.alternate_for_tests()
    signer = Ed25519CredentialSigner()
    message = b"key-substitution-test"
    signature = signer.sign(
        message,
        primary.get_signing_key(SYNTHETIC_ISSUER_DID),
    )

    assert signer.verify(
        message,
        signature,
        alternate.get_verification_key(SYNTHETIC_VERIFICATION_METHOD),
    ) is False


def test_unknown_issuer_and_key_id_raise_typed_exceptions() -> None:
    provider = LocalIssuerKeyProvider()

    with pytest.raises(UnknownIssuerError):
        provider.get_signing_key("did:web:unknown.example")
    with pytest.raises(UnknownVerificationMethodError):
        provider.get_verification_key("did:web:issuer.example#unknown")


def test_private_key_material_is_redacted_from_repr_and_exceptions() -> None:
    provider = LocalIssuerKeyProvider()
    handle = provider.get_signing_key(SYNTHETIC_ISSUER_DID)

    assert PRIMARY_SEED_HEX not in repr(provider)
    assert PRIMARY_SEED_HEX not in repr(handle)
    assert "redacted" in repr(provider)
    assert "redacted" in repr(handle)

    with pytest.raises(UnknownIssuerError) as captured:
        provider.get_signing_key("did:web:unknown.example")
    assert PRIMARY_SEED_HEX not in str(captured.value)
