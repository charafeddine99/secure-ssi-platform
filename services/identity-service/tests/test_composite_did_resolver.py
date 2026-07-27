from pathlib import Path

import pytest

from app.domain.did import DidResolutionError, DidResolutionErrorCode
from app.services.did_resolver import (
    CompositeDidResolver,
    DidKeyResolver,
    DidWebFixtureResolver,
)


ISSUER_DID = "did:web:issuer.example"
HOLDER_DID = "did:key:z6Mkf5rGMoatrSj1f4CyvuHBeXJELe9RPdzo2PKGNCKVtZxP"
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "issuer.did.json"


def resolver() -> CompositeDidResolver:
    return CompositeDidResolver(
        {
            "key": DidKeyResolver(),
            "web": DidWebFixtureResolver({ISSUER_DID: FIXTURE_PATH}),
        }
    )


def test_composite_resolver_dispatches_only_allowlisted_methods() -> None:
    composite = resolver()

    assert composite.resolve(ISSUER_DID).metadata.method == "web"
    assert composite.resolve(HOLDER_DID).metadata.method == "key"


def test_unsupported_method_is_rejected() -> None:
    with pytest.raises(DidResolutionError) as captured:
        resolver().resolve("did:ethr:0x1234")

    assert captured.value.code == DidResolutionErrorCode.METHOD_NOT_SUPPORTED


@pytest.mark.parametrize("value", ["not-a-did", "did:", "did:WEB:issuer.example"])
def test_invalid_did_syntax_is_rejected(value: str) -> None:
    with pytest.raises(DidResolutionError) as captured:
        resolver().resolve(value)

    assert captured.value.code == DidResolutionErrorCode.INVALID_DID
