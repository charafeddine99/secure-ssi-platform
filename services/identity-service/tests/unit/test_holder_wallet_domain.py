from datetime import UTC, datetime, timedelta

import pytest

from app.domain.holder_wallet import (
    HolderWallet,
    HolderWalletUnavailableError,
    WalletStatus,
)
from app.domain.presentation_challenge import (
    ChallengeStatus,
    PresentationChallenge,
    normalize_audience,
)
from app.infrastructure.crypto.local_holder_key_provider import (
    LocalDevelopmentHolderSigner,
    LocalHolderKeyProvider,
    SYNTHETIC_HOLDER_DID,
    SYNTHETIC_HOLDER_KEY_REFERENCE,
)


NOW = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)


def _wallet(
    *,
    status: WalletStatus = WalletStatus.ACTIVE,
    deleted_at: datetime | None = None,
) -> HolderWallet:
    return HolderWallet(
        id="64b64c0f0123456789abcdef",
        wallet_id="wallet_abcdefghijklmnop",
        owner_user_id="usr_local_holder",
        holder_did=SYNTHETIC_HOLDER_DID,
        status=status,
        key_reference=SYNTHETIC_HOLDER_KEY_REFERENCE,
        created_at=NOW,
        updated_at=NOW,
        deleted_at=deleted_at,
    )


def test_wallet_invariants_and_signing_availability() -> None:
    wallet = _wallet()

    assert wallet.usable_for_signing is True
    assert "synthetic" not in repr(wallet)

    with pytest.raises(HolderWalletUnavailableError):
        _wallet(status=WalletStatus.LOCKED).require_usable_for_signing()
    with pytest.raises(ValueError):
        _wallet(
            status=WalletStatus.ACTIVE,
            deleted_at=NOW + timedelta(seconds=1),
        )


def test_challenge_invariants_domain_and_audience_normalization() -> None:
    challenge = PresentationChallenge(
        id="74b64c0f0123456789abcdef",
        challenge_id="challenge_abcdefghijklmnop",
        challenge="challenge_nonce_00000001",
        domain="Verifier.Example.",
        audience="https://verifier.example/session",
        requested_holder_did=SYNTHETIC_HOLDER_DID,
        issued_by="usr_local_verifier",
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        consumed_at=None,
        status=ChallengeStatus.ISSUED,
    )

    assert challenge.domain == "verifier.example"
    assert normalize_audience(challenge.audience) == challenge.audience
    assert "challenge_nonce" not in repr(challenge)

    with pytest.raises(ValueError):
        PresentationChallenge(
            id=challenge.id,
            challenge_id=challenge.challenge_id,
            challenge=challenge.challenge,
            domain=challenge.domain,
            audience=challenge.audience,
            requested_holder_did=challenge.requested_holder_did,
            issued_by=challenge.issued_by,
            issued_at=challenge.issued_at,
            expires_at=challenge.expires_at,
            consumed_at=None,
            status=ChallengeStatus.CONSUMED,
        )


def test_development_key_adapter_uses_opaque_references() -> None:
    provider = LocalHolderKeyProvider()
    signer = LocalDevelopmentHolderSigner(provider)
    first = provider.provision("local-dev:wallet:abcdefghijklmnop")
    second = provider.provision("local-dev:wallet:qrstuvwxyzABCDEF")
    signature = signer.sign(
        b"wallet-bound-message",
        key_reference=first.key_reference,
    )

    assert first.holder_did != second.holder_did
    assert provider.get_metadata(first.key_reference) == first
    assert len(signature) == 64
    assert "<redacted>" in repr(provider)
    assert first.key_reference not in repr(provider)
    assert "<redacted>" in repr(signer)
