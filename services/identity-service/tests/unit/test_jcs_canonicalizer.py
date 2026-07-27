import json
import math
from pathlib import Path

import pytest

from app.domain.exceptions import CanonicalizationError
from app.domain.vc import CredentialValidationError, VerificationReasonCode
from app.infrastructure.crypto.jcs_canonicalizer import JcsCanonicalizer
from app.services.credential_validator import CredentialProfileValidator


FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "fixtures"
    / "unsigned-university-affiliation.vc.json"
)


def test_key_order_does_not_change_canonical_bytes() -> None:
    canonicalizer = JcsCanonicalizer()

    first = canonicalizer.canonicalize_document({"z": 1, "a": 2})
    second = canonicalizer.canonicalize_document({"a": 2, "z": 1})

    assert first == second == b'{"a":2,"z":1}'


def test_input_whitespace_does_not_change_canonical_bytes() -> None:
    canonicalizer = JcsCanonicalizer()
    compact = json.loads('{"a":1,"nested":{"b":2}}')
    spaced = json.loads(
        """
        {
          "nested": { "b": 2 },
          "a": 1
        }
        """
    )

    assert canonicalizer.canonicalize_document(compact) == (
        canonicalizer.canonicalize_document(spaced)
    )


def test_nested_objects_are_sorted_deterministically() -> None:
    canonical = JcsCanonicalizer().canonicalize_document(
        {"outer": {"z": 1, "a": {"y": 2, "b": 3}}}
    )

    assert canonical == b'{"outer":{"a":{"b":3,"y":2},"z":1}}'


def test_array_order_is_preserved() -> None:
    canonicalizer = JcsCanonicalizer()

    first = canonicalizer.canonicalize_document({"items": [3, 2, 1]})
    second = canonicalizer.canonicalize_document({"items": [1, 2, 3]})

    assert first == b'{"items":[3,2,1]}'
    assert first != second


def test_unicode_is_encoded_deterministically_as_utf8() -> None:
    canonicalizer = JcsCanonicalizer()
    document = {"city": "İstanbul", "symbol": "🔐"}

    first = canonicalizer.canonicalize_document(document)
    second = canonicalizer.canonicalize_document(
        {"symbol": "🔐", "city": "İstanbul"}
    )

    assert first == second
    assert first.decode("utf-8") == '{"city":"İstanbul","symbol":"🔐"}'


def test_proof_is_excluded_from_credential_signing_input() -> None:
    canonicalizer = JcsCanonicalizer()
    credential = {"id": "urn:example:1", "claim": "synthetic"}
    proof_config = {
        "type": "DataIntegrityProof",
        "cryptosuite": "eddsa-jcs-2022",
        "created": "2026-06-01T00:00:00Z",
    }
    with_proof = {
        **credential,
        "proof": {"proofValue": "zIgnored"},
    }

    assert canonicalizer.create_signing_input(
        credential,
        proof_config,
    ) == canonicalizer.create_signing_input(with_proof, proof_config)


def test_proof_configuration_is_bound_to_signing_input() -> None:
    canonicalizer = JcsCanonicalizer()
    credential = {"id": "urn:example:1"}
    first_proof = {
        "type": "DataIntegrityProof",
        "cryptosuite": "eddsa-jcs-2022",
        "created": "2026-06-01T00:00:00Z",
    }
    second_proof = {
        **first_proof,
        "created": "2026-06-02T00:00:00Z",
    }

    assert canonicalizer.create_signing_input(
        credential,
        first_proof,
    ) != canonicalizer.create_signing_input(credential, second_proof)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_non_finite_numbers_are_rejected(value: float) -> None:
    with pytest.raises(CanonicalizationError):
        JcsCanonicalizer().canonicalize_document({"invalid": value})


def test_invalid_unicode_scalar_is_rejected() -> None:
    with pytest.raises(CanonicalizationError):
        JcsCanonicalizer().canonicalize_document({"invalid": "\ud800"})


def test_duplicate_json_keys_are_rejected_by_the_parser_layer() -> None:
    raw = FIXTURE_PATH.read_text(encoding="utf-8").replace(
        '"issuer": "did:web:issuer.example",',
        (
            '"issuer": "did:web:issuer.example",'
            '"issuer": "did:web:issuer.example",'
        ),
    )

    with pytest.raises(CredentialValidationError) as captured:
        CredentialProfileValidator().load_and_validate(raw)

    assert (
        captured.value.code
        is VerificationReasonCode.DUPLICATE_JSON_PROPERTY
    )


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_json_constants_are_rejected_by_parser(
    constant: str,
) -> None:
    raw = FIXTURE_PATH.read_text(encoding="utf-8").replace(
        '"graduationYear": 2026',
        f'"graduationYear": {constant}',
    )

    with pytest.raises(CredentialValidationError) as captured:
        CredentialProfileValidator().load_and_validate(raw)

    assert captured.value.code is VerificationReasonCode.DOCUMENT_INVALID


def test_invalid_utf8_is_rejected_by_parser() -> None:
    with pytest.raises(CredentialValidationError) as captured:
        CredentialProfileValidator().load_and_validate(b'{"bad":"\xff"}')

    assert captured.value.code is VerificationReasonCode.DOCUMENT_INVALID
