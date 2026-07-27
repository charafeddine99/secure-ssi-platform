import pytest

from app.domain.did import DidResolutionError, DidResolutionErrorCode
from app.services.did_document_validator import (
    DID_V1_CONTEXT,
    MULTIKEY_V1_CONTEXT,
)
from app.services.did_resolver import DidKeyResolver


ED25519_DID = "did:key:z6Mkf5rGMoatrSj1f4CyvuHBeXJELe9RPdzo2PKGNCKVtZxP"


def test_ed25519_did_key_resolution_is_deterministic() -> None:
    resolver = DidKeyResolver()

    first = resolver.resolve(ED25519_DID)
    second = resolver.resolve(ED25519_DID)

    assert first == second
    assert first.metadata.method == "key"
    assert first.metadata.source == "generated"
    assert first.did_document["@context"] == [
        DID_V1_CONTEXT,
        MULTIKEY_V1_CONTEXT,
    ]
    method = first.did_document["verificationMethod"][0]
    expected_method_id = f"{ED25519_DID}#{ED25519_DID.removeprefix('did:key:')}"
    assert method == {
        "id": expected_method_id,
        "type": "Multikey",
        "controller": ED25519_DID,
        "publicKeyMultibase": ED25519_DID.removeprefix("did:key:"),
    }
    assert first.did_document["assertionMethod"] == [expected_method_id]


@pytest.mark.parametrize(
    "did",
    [
        "did:key:",
        "did:key:not-multibase",
        "did:key:z0invalid",
        "did:key:u7QExample",
    ],
)
def test_malformed_did_key_is_rejected(did: str) -> None:
    with pytest.raises(DidResolutionError) as captured:
        DidKeyResolver().resolve(did)

    assert captured.value.code == DidResolutionErrorCode.INVALID_DID


def test_non_ed25519_did_key_is_rejected() -> None:
    p256_did = "did:key:zDnaerx9CtbPJ1q36T5Ln5wYt3MQYeGRG5ehnPAmxcf5mDZpv"

    with pytest.raises(DidResolutionError) as captured:
        DidKeyResolver().resolve(p256_did)

    assert captured.value.code == DidResolutionErrorCode.UNSUPPORTED_KEY_TYPE
