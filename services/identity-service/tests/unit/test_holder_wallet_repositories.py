from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from app.domain.holder_wallet import HolderWallet, WalletStatus
from app.domain.presentation_challenge import (
    ChallengeStatus,
    PresentationChallenge,
)
from app.domain.persistence import OptimisticLockError
from app.infrastructure.crypto.local_holder_key_provider import (
    LocalHolderKeyProvider,
)
from app.infrastructure.persistence.holder_wallet_mappers import (
    HolderWalletDocumentMapper,
    PresentationChallengeDocumentMapper,
)
from app.infrastructure.persistence.holder_wallet_repositories import (
    MongoHolderWalletRepository,
    MongoPresentationChallengeRepository,
)
from tests.support.fake_mongo import FakeCollection


NOW = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)


def _wallet() -> HolderWallet:
    metadata = LocalHolderKeyProvider().provision(
        "local-dev:wallet:abcdefghijklmnop"
    )
    return HolderWallet(
        id="64b64c0f0123456789abcdef",
        wallet_id="wallet_abcdefghijklmnop",
        owner_user_id="usr_local_holder",
        holder_did=metadata.holder_did,
        status=WalletStatus.ACTIVE,
        key_reference=metadata.key_reference,
        created_at=NOW,
        updated_at=NOW,
    )


def _challenge(
    holder_did: str,
    *,
    challenge_id: str = "challenge_abcdefghijklmnop",
    value: str = "challenge_nonce_00000001",
) -> PresentationChallenge:
    return PresentationChallenge(
        id="74b64c0f0123456789abcdef",
        challenge_id=challenge_id,
        challenge=value,
        domain="verifier.example",
        audience="secure-ssi-verifier",
        requested_holder_did=holder_did,
        issued_by="usr_local_verifier",
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        consumed_at=None,
        status=ChallengeStatus.ISSUED,
    )


def test_wallet_mapper_repository_status_and_raw_key_exclusion() -> None:
    collection = FakeCollection(
        unique_fields=("walletId", "holderDid", "keyReference"),
    )
    repository = MongoHolderWalletRepository(cast(Any, collection))
    wallet = repository.add(_wallet())
    document = collection.documents[0]

    assert repository.get(wallet.wallet_id) == wallet
    assert repository.get_active_by_holder_did(wallet.holder_did) == wallet
    assert repository.list_by_owner(wallet.owner_user_id) == (wallet,)
    assert "keyReference" in document
    assert not any(
        "private" in key.casefold() or "seed" in key.casefold()
        for key in document
    )

    locked = repository.update_status(
        wallet.wallet_id,
        status=WalletStatus.LOCKED,
        updated_at=NOW + timedelta(seconds=1),
        expected_version=1,
    )
    assert locked.status is WalletStatus.LOCKED
    assert locked.version == 2
    assert repository.get_active_by_holder_did(wallet.holder_did) is None
    with pytest.raises(OptimisticLockError):
        repository.update_status(
            wallet.wallet_id,
            status=WalletStatus.DISABLED,
            updated_at=NOW + timedelta(seconds=2),
            expected_version=1,
        )
    assert HolderWalletDocumentMapper.from_document(
        HolderWalletDocumentMapper.to_document(locked)
    ) == locked
    repository.soft_delete(
        wallet.wallet_id,
        deleted_at=NOW + timedelta(seconds=2),
        expected_version=2,
    )
    assert repository.get(wallet.wallet_id) is None


def test_challenge_mapper_atomic_consumption_expiration_and_replay() -> None:
    collection = FakeCollection(
        unique_fields=("challengeId", "challenge"),
    )
    repository = MongoPresentationChallengeRepository(
        cast(Any, collection)
    )
    challenge = repository.add(_challenge(_wallet().holder_did))

    consumed = repository.consume(
        challenge.challenge_id,
        consumed_at=NOW + timedelta(seconds=1),
        expected_version=1,
        domain=challenge.domain,
        audience=challenge.audience,
        requested_holder_did=challenge.requested_holder_did,
    )

    assert consumed is not None
    assert consumed.status is ChallengeStatus.CONSUMED
    assert consumed.version == 2
    assert (
        repository.consume(
            challenge.challenge_id,
            consumed_at=NOW + timedelta(seconds=2),
            expected_version=2,
            domain=challenge.domain,
            audience=challenge.audience,
            requested_holder_did=challenge.requested_holder_did,
        )
        is None
    )
    assert PresentationChallengeDocumentMapper.from_document(
        PresentationChallengeDocumentMapper.to_document(consumed)
    ) == consumed

    expired = _challenge(
        _wallet().holder_did,
        challenge_id="challenge_qrstuvwxyzABCDEF",
        value="challenge_nonce_00000002",
    )
    expired = PresentationChallenge(
        **{
            **vars(expired),
            "id": "84b64c0f0123456789abcdef",
            "expires_at": NOW + timedelta(seconds=30),
        }
    )
    repository.add(expired)
    result = repository.expire(
        expired.challenge_id,
        expired_at=NOW + timedelta(seconds=31),
        expected_version=1,
    )
    assert result is not None
    assert result.status is ChallengeStatus.EXPIRED
