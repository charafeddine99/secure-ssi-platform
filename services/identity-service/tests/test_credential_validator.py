import copy
import json
from pathlib import Path
from typing import Any

import pytest

from app.domain.vc import CredentialValidationError, VerificationReasonCode
from app.services.credential_validator import CredentialProfileValidator
from app.services.did_resolver import DidKeyResolver


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "unsigned-university-affiliation.vc.json"
)


def unsigned_credential() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def proof() -> dict[str, Any]:
    return {
        "@context": [
            "https://www.w3.org/ns/credentials/v2",
            "https://secure-ssi.example/contexts/university-affiliation/v1",
        ],
        "type": "DataIntegrityProof",
        "cryptosuite": "eddsa-jcs-2022",
        "created": "2026-01-01T00:00:00Z",
        "verificationMethod": "did:web:issuer.example#key-1",
        "proofPurpose": "assertionMethod",
        "proofValue": f"z{'1' * 79}",
    }


def assert_rejected(
    credential: dict[str, Any],
    expected_code: VerificationReasonCode,
    *,
    require_proof: bool = False,
) -> None:
    with pytest.raises(CredentialValidationError) as captured:
        CredentialProfileValidator().validate(
            credential,
            require_proof=require_proof,
        )
    assert captured.value.code == expected_code


def test_unsigned_synthetic_fixture_matches_the_pinned_profile() -> None:
    raw = FIXTURE_PATH.read_bytes()

    credential = CredentialProfileValidator().load_and_validate(raw)

    assert credential["issuer"] == "did:web:issuer.example"
    assert credential["credentialSubject"]["affiliation"] == "student"
    assert "proof" not in credential
    DidKeyResolver().resolve(credential["credentialSubject"]["id"])


def test_unsigned_fixture_contains_no_private_or_secret_material() -> None:
    raw = FIXTURE_PATH.read_text(encoding="utf-8").lower()

    assert "privatekey" not in raw
    assert "secretkey" not in raw
    assert "proofvalue" not in raw


def test_secured_validation_requires_a_proof() -> None:
    assert_rejected(
        unsigned_credential(),
        VerificationReasonCode.MISSING_PROOF,
        require_proof=True,
    )


def test_valid_proof_shape_is_accepted_without_claiming_signature_validity() -> None:
    credential = unsigned_credential()
    credential["proof"] = proof()

    result = CredentialProfileValidator().validate(
        credential,
        require_proof=True,
    )

    assert result["proof"]["cryptosuite"] == "eddsa-jcs-2022"


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        (
            "@context",
            [
                "https://www.w3.org/ns/credentials/v2",
                "https://attacker.example/context",
            ],
            VerificationReasonCode.UNSUPPORTED_CONTEXT,
        ),
        (
            "type",
            ["VerifiableCredential", "UnknownCredential"],
            VerificationReasonCode.UNSUPPORTED_TYPE,
        ),
        (
            "issuer",
            "did:key:z6Mkf5rGMoatrSj1f4CyvuHBeXJELe9RPdzo2PKGNCKVtZxP",
            VerificationReasonCode.INVALID_IDENTIFIER,
        ),
    ],
)
def test_unsupported_profile_values_are_rejected(
    field: str,
    value: object,
    code: VerificationReasonCode,
) -> None:
    credential = unsigned_credential()
    credential[field] = value

    assert_rejected(credential, code)


def test_unknown_top_level_field_is_rejected() -> None:
    credential = unsigned_credential()
    credential["unexpected"] = True

    assert_rejected(credential, VerificationReasonCode.DOCUMENT_INVALID)


def test_unapproved_claim_is_rejected() -> None:
    credential = unsigned_credential()
    credential["credentialSubject"]["fullName"] = "Synthetic Person"

    assert_rejected(credential, VerificationReasonCode.UNSUPPORTED_CLAIM)


def test_non_did_key_subject_is_rejected() -> None:
    credential = unsigned_credential()
    credential["credentialSubject"]["id"] = "did:web:holder.example"

    assert_rejected(credential, VerificationReasonCode.INVALID_IDENTIFIER)


@pytest.mark.parametrize(
    ("valid_from", "valid_until", "code"),
    [
        (
            "2026-12-31T23:59:59Z",
            "2026-01-01T00:00:00Z",
            VerificationReasonCode.INVALID_VALIDITY_WINDOW,
        ),
        (
            "2026-01-01 00:00:00",
            "2026-12-31T23:59:59Z",
            VerificationReasonCode.INVALID_TIMESTAMP,
        ),
        (
            "2026-02-30T00:00:00Z",
            "2026-12-31T23:59:59Z",
            VerificationReasonCode.INVALID_TIMESTAMP,
        ),
    ],
)
def test_invalid_timestamps_and_windows_are_rejected(
    valid_from: str,
    valid_until: str,
    code: VerificationReasonCode,
) -> None:
    credential = unsigned_credential()
    credential["validFrom"] = valid_from
    credential["validUntil"] = valid_until

    assert_rejected(credential, code)


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        (
            "type",
            "Ed25519Signature2020",
            VerificationReasonCode.UNSUPPORTED_PROOF_TYPE,
        ),
        (
            "cryptosuite",
            "eddsa-rdfc-2022",
            VerificationReasonCode.UNSUPPORTED_CRYPTOSUITE,
        ),
        (
            "proofPurpose",
            "authentication",
            VerificationReasonCode.INVALID_PROOF_PURPOSE,
        ),
        (
            "verificationMethod",
            "did:web:attacker.example#key-1",
            VerificationReasonCode.INVALID_VERIFICATION_METHOD,
        ),
        (
            "proofValue",
            "not-a-multibase-signature",
            VerificationReasonCode.INVALID_PROOF_VALUE,
        ),
    ],
)
def test_unsupported_proof_shape_is_rejected(
    field: str,
    value: str,
    code: VerificationReasonCode,
) -> None:
    credential = unsigned_credential()
    credential["proof"] = proof()
    credential["proof"][field] = value

    assert_rejected(credential, code, require_proof=True)


def test_private_key_material_is_rejected_recursively() -> None:
    credential = unsigned_credential()
    credential["credentialSubject"]["privateKeyMultibase"] = "synthetic-secret"

    assert_rejected(credential, VerificationReasonCode.PRIVATE_KEY_MATERIAL)


def test_duplicate_json_properties_are_rejected() -> None:
    raw = FIXTURE_PATH.read_text(encoding="utf-8")
    duplicate = raw.replace(
        '"issuer": "did:web:issuer.example",',
        (
            '"issuer": "did:web:issuer.example",'
            '"issuer": "did:web:issuer.example",'
        ),
    )

    with pytest.raises(CredentialValidationError) as captured:
        CredentialProfileValidator().load_and_validate(duplicate)

    assert (
        captured.value.code
        == VerificationReasonCode.DUPLICATE_JSON_PROPERTY
    )


def test_oversized_credential_is_rejected_before_parsing() -> None:
    validator = CredentialProfileValidator(max_credential_bytes=64)

    with pytest.raises(CredentialValidationError) as captured:
        validator.load_and_validate(FIXTURE_PATH.read_bytes())

    assert (
        captured.value.code
        == VerificationReasonCode.CREDENTIAL_TOO_LARGE
    )


def test_fixture_helper_returns_independent_documents() -> None:
    first = unsigned_credential()
    second = copy.deepcopy(first)
    second["credentialSubject"]["affiliation"] = "staff"

    assert first["credentialSubject"]["affiliation"] == "student"
