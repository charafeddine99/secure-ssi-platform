import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.application.services.credential_proof_service import (
    CredentialProofService,
)
from app.domain.exceptions import ExistingProofError, UnknownIssuerError
from app.domain.vc import VerificationReasonCode
from app.infrastructure.crypto.ed25519_signer import (
    Ed25519CredentialSigner,
)
from app.infrastructure.crypto.jcs_canonicalizer import JcsCanonicalizer
from app.infrastructure.crypto.local_issuer_key_provider import (
    LocalIssuerKeyProvider,
    SYNTHETIC_ISSUER_DID,
)
from app.infrastructure.crypto.multibase import (
    decode_base58_btc,
    encode_base58_btc,
)
from app.infrastructure.fixtures.signed_credentials import (
    FIXED_PROOF_TIME,
    build_local_proof_service,
    build_signed_credential,
    load_unsigned_credential,
)
from app.infrastructure.fixtures.tampered_credentials import (
    build_tampered_credentials,
)
from app.main import app
from app.services.credential_validator import CredentialProfileValidator
from app.services.did_resolver import CompositeDidResolver, DidWebFixtureResolver


FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures"
VALID_SIGNED_FIXTURE = (
    FIXTURE_ROOT / "valid-signed-university-affiliation.vc.json"
)
PRIMARY_SEED_HEX = (
    "dbdd31e053d58e33fff0d0a842d9a510"
    "ee0b5c2b52662caa91e8e6d84821b419"
)


def load_signed_fixture() -> dict[str, Any]:
    return json.loads(VALID_SIGNED_FIXTURE.read_text(encoding="utf-8"))


def test_valid_unsigned_credential_is_signed_deterministically() -> None:
    generated = build_signed_credential()

    assert generated == load_signed_fixture()
    assert generated["proof"] == {
        "@context": generated["@context"],
        "type": "DataIntegrityProof",
        "cryptosuite": "eddsa-jcs-2022",
        "created": "2026-06-01T00:00:00Z",
        "verificationMethod": "did:web:issuer.example#key-1",
        "proofPurpose": "assertionMethod",
        "proofValue": (
            "z2DBDjSRR4iBwcgJBJ4FCnRphCVJULnHK19J7wwM9VfWoUpt5"
            "kgQBoMZNt91gV3ckUVrsJdDf22xpxo1PPXQ2JmYx"
        ),
    }
    assert len(decode_base58_btc(generated["proof"]["proofValue"])) == 64


def test_valid_signed_credential_returns_a_structured_success() -> None:
    result = build_local_proof_service().verify_credential(
        load_signed_fixture()
    )

    assert result.verified is True
    assert result.reason_codes == ()
    assert all(
        check["status"] in {"passed", "notApplicable"}
        for check in result.to_dict()["checks"].values()
    )


def test_same_key_and_timestamp_produce_the_same_signature() -> None:
    service = build_local_proof_service()
    unsigned = load_unsigned_credential()

    first = service.sign_credential(unsigned, created=FIXED_PROOF_TIME)
    second = service.sign_credential(unsigned, created=FIXED_PROOF_TIME)

    assert first["proof"]["proofValue"] == second["proof"]["proofValue"]


def test_different_created_timestamp_produces_a_different_signature() -> None:
    service = build_local_proof_service()
    unsigned = load_unsigned_credential()

    first = service.sign_credential(
        unsigned,
        created=datetime(2026, 6, 1, tzinfo=UTC),
    )
    second = service.sign_credential(
        unsigned,
        created=datetime(2026, 6, 2, tzinfo=UTC),
    )

    assert first["proof"]["proofValue"] != second["proof"]["proofValue"]


def test_unknown_issuer_cannot_be_signed() -> None:
    unsigned = load_unsigned_credential()
    unsigned["issuer"] = "did:web:unknown.example"

    with pytest.raises(UnknownIssuerError):
        build_local_proof_service().sign_credential(unsigned)


def test_existing_proof_is_not_silently_replaced() -> None:
    with pytest.raises(ExistingProofError):
        build_local_proof_service().sign_credential(load_signed_fixture())


def test_no_private_key_material_appears_in_outputs_logs_or_errors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = build_local_proof_service()
    signed = service.sign_credential(load_unsigned_credential())

    assert PRIMARY_SEED_HEX not in json.dumps(signed)
    assert "privateKey" not in json.dumps(signed)
    assert "secretKey" not in json.dumps(signed)
    assert PRIMARY_SEED_HEX not in caplog.text

    unknown = load_unsigned_credential()
    unknown["issuer"] = "did:web:unknown.example"
    with pytest.raises(UnknownIssuerError) as captured:
        service.sign_credential(unknown)
    assert PRIMARY_SEED_HEX not in str(captured.value)


EXPECTED_TAMPER_REASONS = {
    "degree_claim_changed": VerificationReasonCode.SIGNATURE_INVALID,
    "subject_did_changed": VerificationReasonCode.SIGNATURE_INVALID,
    "issuer_did_changed": VerificationReasonCode.INVALID_VERIFICATION_METHOD,
    "graduation_year_changed": VerificationReasonCode.SIGNATURE_INVALID,
    "proof_value_changed": VerificationReasonCode.SIGNATURE_INVALID,
    "verification_method_changed": (
        VerificationReasonCode.VERIFICATION_METHOD_NOT_AUTHORIZED
    ),
    "cryptosuite_changed": VerificationReasonCode.UNSUPPORTED_CRYPTOSUITE,
    "proof_purpose_changed": VerificationReasonCode.INVALID_PROOF_PURPOSE,
    "created_timestamp_malformed": (
        VerificationReasonCode.PROOF_TIMESTAMP_INVALID
    ),
    "proof_removed": VerificationReasonCode.MISSING_PROOF,
    "unknown_claim_added": VerificationReasonCode.UNSUPPORTED_CLAIM,
    "context_order_changed": VerificationReasonCode.UNSUPPORTED_CONTEXT,
    "public_key_mismatch": VerificationReasonCode.SIGNATURE_INVALID,
    "malformed_proof_value": VerificationReasonCode.INVALID_PROOF_VALUE,
    "other_issuer_key_signature": (
        VerificationReasonCode.ISSUER_RESOLUTION_FAILED
    ),
}


@pytest.mark.parametrize(
    ("fixture_name", "expected_reason"),
    EXPECTED_TAMPER_REASONS.items(),
)
def test_tampered_credentials_are_rejected_with_reason_codes(
    fixture_name: str,
    expected_reason: VerificationReasonCode,
) -> None:
    tampered = build_tampered_credentials(load_signed_fixture())

    assert set(tampered) == set(EXPECTED_TAMPER_REASONS)
    result = build_local_proof_service().verify_credential(
        tampered[fixture_name]
    )

    assert result.verified is False
    assert expected_reason in result.reason_codes


def test_valid_format_created_timestamp_tampering_breaks_signature() -> None:
    tampered = copy.deepcopy(load_signed_fixture())
    tampered["proof"]["created"] = "2026-06-02T00:00:00Z"

    result = build_local_proof_service().verify_credential(tampered)

    assert result.verified is False
    assert VerificationReasonCode.SIGNATURE_INVALID in result.reason_codes


def test_wrong_signature_length_is_controlled_failure() -> None:
    tampered = copy.deepcopy(load_signed_fixture())
    tampered["proof"]["proofValue"] = encode_base58_btc(b"\x01" * 65)

    result = build_local_proof_service().verify_credential(tampered)

    assert result.verified is False
    assert VerificationReasonCode.SIGNATURE_MALFORMED in result.reason_codes


def test_expired_credential_is_rejected_before_signature_acceptance() -> None:
    result = build_local_proof_service().verify_credential(
        load_signed_fixture(),
        verified_at=datetime(2027, 1, 1, tzinfo=UTC),
    )

    assert result.verified is False
    assert VerificationReasonCode.CREDENTIAL_EXPIRED in result.reason_codes


def test_key_substitution_via_did_document_is_rejected(
    tmp_path: Path,
) -> None:
    document = json.loads(
        (FIXTURE_ROOT / "issuer.did.json").read_text(encoding="utf-8")
    )
    document["verificationMethod"][0]["publicKeyMultibase"] = (
        LocalIssuerKeyProvider.alternate_for_tests().public_key_multibase
    )
    substituted_path = tmp_path / "substituted.did.json"
    substituted_path.write_text(json.dumps(document), encoding="utf-8")
    resolver = CompositeDidResolver(
        {
            "web": DidWebFixtureResolver(
                {SYNTHETIC_ISSUER_DID: substituted_path}
            )
        }
    )
    service = CredentialProofService(
        validator=CredentialProfileValidator(),
        canonicalizer=JcsCanonicalizer(),
        signer=Ed25519CredentialSigner(),
        key_provider=LocalIssuerKeyProvider(),
        did_resolver=resolver,
        clock=lambda: FIXED_PROOF_TIME,
    )

    result = service.verify_credential(load_signed_fixture())

    assert result.verified is False
    assert VerificationReasonCode.PUBLIC_KEY_MISMATCH in result.reason_codes


def test_non_ed25519_did_verification_method_is_rejected(
    tmp_path: Path,
) -> None:
    document = json.loads(
        (FIXTURE_ROOT / "issuer.did.json").read_text(encoding="utf-8")
    )
    document["verificationMethod"][0]["type"] = "JsonWebKey"
    invalid_path = tmp_path / "wrong-key-type.did.json"
    invalid_path.write_text(json.dumps(document), encoding="utf-8")
    resolver = CompositeDidResolver(
        {"web": DidWebFixtureResolver({SYNTHETIC_ISSUER_DID: invalid_path})}
    )
    service = CredentialProofService(
        validator=CredentialProfileValidator(),
        canonicalizer=JcsCanonicalizer(),
        signer=Ed25519CredentialSigner(),
        key_provider=LocalIssuerKeyProvider(),
        did_resolver=resolver,
        clock=lambda: FIXED_PROOF_TIME,
    )

    result = service.verify_credential(load_signed_fixture())

    assert result.verified is False
    assert (
        VerificationReasonCode.ISSUER_RESOLUTION_FAILED
        in result.reason_codes
    )


def test_only_bounded_credential_http_routes_are_exposed() -> None:
    paths = {route.path for route in app.routes}

    assert "/health" in paths
    assert {
        "/api/v1/credentials/validate",
        "/api/v1/credentials/sign",
        "/api/v1/credentials/verify",
        "/api/v1/credentials/capabilities",
    }.issubset(paths)
    assert "/api/v1/credentials/{credential_id}" not in paths
    assert "/api/v1/credentials" not in paths
