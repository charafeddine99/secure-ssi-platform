import copy
from datetime import UTC, datetime, timedelta

import pytest

from app.application.services.presentation_proof_service import (
    PresentationBuilder,
    PresentationValidator,
)
from app.domain.presentation import (
    PersistedPresentation,
    PresentationVerificationState,
    normalize_domain,
    validate_challenge,
)
from app.infrastructure.crypto.ed25519_signer import Ed25519CredentialSigner
from app.infrastructure.crypto.jcs_canonicalizer import JcsCanonicalizer
from app.infrastructure.crypto.local_holder_key_provider import (
    LocalHolderKeyProvider,
)
from app.services.did_resolver import CompositeDidResolver, DidKeyResolver


NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
CHALLENGE = "challenge_nonce_00000001"
DOMAIN = "verifier.example"


def _services() -> tuple[PresentationBuilder, PresentationValidator]:
    canonicalizer = JcsCanonicalizer()
    signer = Ed25519CredentialSigner()
    keys = LocalHolderKeyProvider()
    return (
        PresentationBuilder(
            canonicalizer=canonicalizer,
            signer=signer,
            key_provider=keys,
        ),
        PresentationValidator(
            canonicalizer=canonicalizer,
            signer=signer,
            key_provider=keys,
            did_resolver=CompositeDidResolver({"key": DidKeyResolver()}),
        ),
    )


def _credentials(count: int = 1) -> list[dict[str, object]]:
    holder = LocalHolderKeyProvider().holder_did
    return [
        {
            "id": f"urn:uuid:00000000-0000-4000-8000-{index:012d}",
            "credentialSubject": {"id": holder},
        }
        for index in range(1, count + 1)
    ]


def test_builder_signs_and_validator_accepts_multiple_credentials() -> None:
    builder, validator = _services()
    holder = LocalHolderKeyProvider().holder_did

    document = builder.build(
        _credentials(2),
        holder_did=holder,
        challenge=CHALLENGE,
        domain=DOMAIN,
        created_at=NOW,
        lifetime_seconds=300,
    )
    result = validator.validate(
        document,
        expected_challenge=CHALLENGE,
        expected_domain=DOMAIN,
        verified_at=NOW,
    )

    assert result.valid is True
    assert result.holder_did == holder
    assert len(result.credential_ids) == 2
    assert document["proof"]["proofPurpose"] == "authentication"


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    [
        (
            lambda value: value["proof"].update(
                {"proofValue": "z" + "1" * 88}
            ),
            "INVALID_PRESENTATION_SIGNATURE",
        ),
        (
            lambda value: value["proof"].update(
                {"challenge": "different_nonce_000001"}
            ),
            "CHALLENGE_MISMATCH",
        ),
        (
            lambda value: value.update(
                {"holder": "did:key:zUnsupportedHolder"}
            ),
            "INVALID_HOLDER_VERIFICATION_METHOD",
        ),
    ],
)
def test_validator_rejects_tampering_and_binding_failures(
    mutation,
    expected_error: str,
) -> None:
    builder, validator = _services()
    document = builder.build(
        _credentials(),
        holder_did=LocalHolderKeyProvider().holder_did,
        challenge=CHALLENGE,
        domain=DOMAIN,
        created_at=NOW,
        lifetime_seconds=300,
    )
    tampered = copy.deepcopy(document)
    mutation(tampered)

    result = validator.validate(
        tampered,
        expected_challenge=CHALLENGE,
        expected_domain=DOMAIN,
        verified_at=NOW,
    )

    assert result.valid is False
    assert expected_error in result.errors


def test_validator_rejects_expiration_and_domain_mismatch() -> None:
    builder, validator = _services()
    document = builder.build(
        _credentials(),
        holder_did=LocalHolderKeyProvider().holder_did,
        challenge=CHALLENGE,
        domain=DOMAIN,
        created_at=NOW,
        lifetime_seconds=30,
    )

    result = validator.validate(
        document,
        expected_challenge=CHALLENGE,
        expected_domain="other.example",
        verified_at=NOW + timedelta(seconds=31),
    )

    assert "PRESENTATION_EXPIRED" in result.errors
    assert "DOMAIN_MISMATCH" in result.errors


def test_persisted_presentation_enforces_metadata_and_nonce_policy() -> None:
    builder, _ = _services()
    holder = LocalHolderKeyProvider().holder_did
    document = builder.build(
        _credentials(),
        holder_did=holder,
        challenge=CHALLENGE,
        domain="Verifier.Example.",
        created_at=NOW,
        lifetime_seconds=60,
    )

    persisted = PersistedPresentation(
        id="64b64c0f0123456789abcdef",
        presentation_id=document["id"],
        holder_did=holder,
        challenge=CHALLENGE,
        domain="Verifier.Example.",
        credential_ids=(document["verifiableCredential"][0]["id"],),
        document=document,
        verification_result=PresentationVerificationState.PENDING,
        created_at=NOW,
        expires_at=NOW + timedelta(seconds=60),
        updated_at=NOW,
    )

    assert persisted.domain == DOMAIN
    assert normalize_domain("Verifier.Example.") == DOMAIN
    assert validate_challenge(CHALLENGE) == CHALLENGE
