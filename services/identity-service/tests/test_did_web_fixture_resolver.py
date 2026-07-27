import json
from pathlib import Path
from typing import Any

import pytest

from app.domain.did import DidResolutionError, DidResolutionErrorCode
from app.services.did_document_validator import DidDocumentValidator
from app.services.did_resolver import DidWebFixtureResolver


ISSUER_DID = "did:web:issuer.example"
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "issuer.did.json"
PUBLIC_KEY = "z6MkuG4LGc3sEyCZTFbKGVNi7ehNi1PT3zK3KcrUhKvUi3wd"


def valid_document(did: str = ISSUER_DID) -> dict[str, Any]:
    method_id = f"{did}#key-1"
    return {
        "@context": [
            "https://www.w3.org/ns/did/v1",
            "https://w3id.org/security/multikey/v1",
        ],
        "id": did,
        "verificationMethod": [
            {
                "id": method_id,
                "type": "Multikey",
                "controller": did,
                "publicKeyMultibase": PUBLIC_KEY,
            }
        ],
        "assertionMethod": [method_id],
    }


def fixture_resolver(path: Path = FIXTURE_PATH) -> DidWebFixtureResolver:
    return DidWebFixtureResolver({ISSUER_DID: path})


def write_document(path: Path, document: dict[str, Any]) -> Path:
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_local_did_web_fixture_resolves_without_network() -> None:
    result = fixture_resolver().resolve(ISSUER_DID)

    assert result.did == ISSUER_DID
    assert result.metadata.method == "web"
    assert result.metadata.source == "local-fixture"
    assert result.did_document["id"] == ISSUER_DID
    assert result.did_document["assertionMethod"] == [
        "did:web:issuer.example#key-1"
    ]


def test_unregistered_did_web_is_not_fetched_from_network() -> None:
    with pytest.raises(DidResolutionError) as captured:
        fixture_resolver().resolve("did:web:unregistered.example")

    assert captured.value.code == DidResolutionErrorCode.NOT_FOUND


def test_mismatched_document_id_is_rejected(tmp_path: Path) -> None:
    path = write_document(tmp_path / "mismatch.json", valid_document("did:web:other.example"))

    with pytest.raises(DidResolutionError) as captured:
        fixture_resolver(path).resolve(ISSUER_DID)

    assert captured.value.code == DidResolutionErrorCode.INVALID_DID_DOCUMENT


def test_missing_assertion_method_is_rejected(tmp_path: Path) -> None:
    document = valid_document()
    document.pop("assertionMethod")
    path = write_document(tmp_path / "missing-assertion.json", document)

    with pytest.raises(DidResolutionError) as captured:
        fixture_resolver(path).resolve(ISSUER_DID)

    assert captured.value.code == DidResolutionErrorCode.INVALID_DID_DOCUMENT


def test_undeclared_assertion_method_is_rejected(tmp_path: Path) -> None:
    document = valid_document()
    document["assertionMethod"] = [f"{ISSUER_DID}#unknown"]
    path = write_document(tmp_path / "unknown-assertion.json", document)

    with pytest.raises(DidResolutionError) as captured:
        fixture_resolver(path).resolve(ISSUER_DID)

    assert captured.value.code == DidResolutionErrorCode.INVALID_DID_DOCUMENT


@pytest.mark.parametrize(
    "private_field",
    ["privateKeyJwk", "privateKeyMultibase", "secretKeyMultibase"],
)
def test_private_key_material_is_rejected(
    tmp_path: Path,
    private_field: str,
) -> None:
    document = valid_document()
    document["verificationMethod"][0][private_field] = "synthetic-secret"
    path = write_document(tmp_path / f"{private_field}.json", document)

    with pytest.raises(DidResolutionError) as captured:
        fixture_resolver(path).resolve(ISSUER_DID)

    assert captured.value.code == DidResolutionErrorCode.PRIVATE_KEY_MATERIAL


def test_oversized_document_is_rejected_before_parsing(tmp_path: Path) -> None:
    path = write_document(tmp_path / "oversized.json", valid_document())
    resolver = DidWebFixtureResolver(
        {ISSUER_DID: path},
        validator=DidDocumentValidator(max_document_bytes=64),
    )

    with pytest.raises(DidResolutionError) as captured:
        resolver.resolve(ISSUER_DID)

    assert captured.value.code == DidResolutionErrorCode.DOCUMENT_TOO_LARGE


def test_duplicate_json_properties_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text(
        '{"id":"did:web:issuer.example","id":"did:web:issuer.example"}',
        encoding="utf-8",
    )

    with pytest.raises(DidResolutionError) as captured:
        fixture_resolver(path).resolve(ISSUER_DID)

    assert captured.value.code == DidResolutionErrorCode.INVALID_DID_DOCUMENT


def test_unapproved_context_is_rejected(tmp_path: Path) -> None:
    document = valid_document()
    document["@context"].append("https://attacker.example/context")
    path = write_document(tmp_path / "context.json", document)

    with pytest.raises(DidResolutionError) as captured:
        fixture_resolver(path).resolve(ISSUER_DID)

    assert captured.value.code == DidResolutionErrorCode.INVALID_DID_DOCUMENT


def test_unsupported_verification_method_type_is_rejected(tmp_path: Path) -> None:
    document = valid_document()
    document["verificationMethod"][0]["type"] = "JsonWebKey"
    path = write_document(tmp_path / "key-type.json", document)

    with pytest.raises(DidResolutionError) as captured:
        fixture_resolver(path).resolve(ISSUER_DID)

    assert captured.value.code == DidResolutionErrorCode.UNSUPPORTED_KEY_TYPE
