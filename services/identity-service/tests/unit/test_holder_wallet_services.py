from datetime import UTC, datetime
from typing import Any, cast

import pytest

from app.application.services.audit_outbox_service import (
    AuditOutboxDeliveryService,
)
from app.application.services.holder_wallet_service import (
    HolderWalletService,
    PresentationChallengeService,
)
from app.application.services.internal_metrics import InternalMetrics
from app.config.audit_outbox_settings import AuditOutboxSettings
from app.domain.holder_wallet import (
    HolderWalletNotFoundError,
    HolderWalletUnavailableError,
)
from app.domain.persistence import AuditEventType
from app.domain.presentation_challenge import (
    PresentationChallengeExpiredError,
    PresentationChallengeNotFoundError,
    PresentationChallengeReplayError,
)
from app.infrastructure.crypto.local_holder_key_provider import (
    LocalHolderKeyProvider,
)
from app.infrastructure.persistence.audit_outbox_repository import (
    MongoAuditOutboxRepository,
)
from app.infrastructure.persistence.holder_wallet_repositories import (
    MongoHolderWalletRepository,
    MongoPresentationChallengeRepository,
)
from app.infrastructure.persistence.repositories import (
    MongoAuditEventRepository,
    MongoCredentialRepository,
)
from tests.support.fake_mongo import FakeCollection


NOW = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)


class MutableClock:
    def __init__(self) -> None:
        self.value = NOW

    def __call__(self) -> datetime:
        return self.value


def _services() -> tuple[
    HolderWalletService,
    PresentationChallengeService,
    MongoAuditEventRepository,
    InternalMetrics,
    MutableClock,
]:
    clock = MutableClock()
    wallets = FakeCollection(
        unique_fields=("walletId", "holderDid", "keyReference"),
    )
    challenges = FakeCollection(
        unique_fields=("challengeId", "challenge"),
    )
    credentials = FakeCollection(unique_fields=("credentialId",))
    audit_outbox = FakeCollection()
    audit_events = FakeCollection()
    wallet_repository = MongoHolderWalletRepository(
        cast(Any, wallets)
    )
    audit_repository = MongoAuditEventRepository(
        cast(Any, audit_events)
    )
    delivery = AuditOutboxDeliveryService(
        outbox_repository=MongoAuditOutboxRepository(
            cast(Any, audit_outbox),
            cast(Any, credentials),
        ),
        audit_repository=audit_repository,
        settings=AuditOutboxSettings(),
        clock=clock,
    )
    metrics = InternalMetrics()
    wallet_service = HolderWalletService(
        wallet_repository=wallet_repository,
        credential_repository=MongoCredentialRepository(
            cast(Any, credentials)
        ),
        key_provider=LocalHolderKeyProvider(),
        audit_delivery_service=delivery,
        clock=clock,
        storage_id_generator=lambda: "64b64c0f0123456789abcdef",
        wallet_id_generator=lambda: "wallet_abcdefghijklmnop",
        key_reference_generator=(
            lambda: "local-dev:wallet:abcdefghijklmnop"
        ),
        metrics=metrics,
    )
    challenge_service = PresentationChallengeService(
        challenge_repository=MongoPresentationChallengeRepository(
            cast(Any, challenges)
        ),
        wallet_repository=wallet_repository,
        audit_delivery_service=delivery,
        clock=clock,
        storage_id_generator=lambda: "74b64c0f0123456789abcdef",
        challenge_id_generator=(
            lambda: "challenge_abcdefghijklmnop"
        ),
        challenge_value_generator=(
            lambda: "challenge_nonce_00000001"
        ),
        metrics=metrics,
    )
    return (
        wallet_service,
        challenge_service,
        audit_repository,
        metrics,
        clock,
    )


def test_wallet_ownership_status_and_audit_metrics() -> None:
    wallet_service, _, audit, metrics, _ = _services()
    wallet = wallet_service.create(
        owner_user_id="usr_local_holder",
        correlation_id="wallet-create-1",
    )

    assert wallet_service.get_owned(
        wallet.wallet_id,
        owner_user_id="usr_local_holder",
    ) == wallet
    with pytest.raises(HolderWalletNotFoundError):
        wallet_service.get_owned(
            wallet.wallet_id,
            owner_user_id="usr_other",
        )

    locked = wallet_service.lock(
        wallet.wallet_id,
        owner_user_id="usr_local_holder",
        correlation_id="wallet-lock-1",
    )
    with pytest.raises(HolderWalletUnavailableError):
        wallet_service.require_owned_active(
            locked.wallet_id,
            owner_user_id="usr_local_holder",
            correlation_id="wallet-use-locked",
        )
    locked_snapshot = metrics.snapshot()
    disabled = wallet_service.disable(
        locked.wallet_id,
        owner_user_id="usr_local_holder",
        correlation_id="wallet-disable-1",
    )
    with pytest.raises(HolderWalletUnavailableError):
        wallet_service.require_owned_active(
            disabled.wallet_id,
            owner_user_id="usr_local_holder",
            correlation_id="wallet-use-disabled",
        )

    event_types = {event.event_type for event in audit.list_recent()}
    assert event_types == {
        AuditEventType.WALLET_CREATED,
        AuditEventType.WALLET_LOCKED,
        AuditEventType.WALLET_DISABLED,
    }
    snapshot = metrics.snapshot()
    assert locked_snapshot.locked_wallet_count == 1
    assert snapshot.active_wallet_count == 0
    assert snapshot.locked_wallet_count == 0


def test_challenge_single_use_binding_authorization_and_safe_audit() -> None:
    wallet_service, challenges, audit, metrics, _ = _services()
    wallet = wallet_service.create(
        owner_user_id="usr_local_holder",
        correlation_id="wallet-create-1",
    )
    challenge = challenges.issue(
        domain="Verifier.Example.",
        audience="secure-ssi-verifier",
        requested_holder_did=wallet.holder_did,
        issued_by="usr_local_verifier",
        lifetime_seconds=300,
        correlation_id="challenge-issue-1",
    )

    with pytest.raises(HolderWalletNotFoundError):
        wallet_service.get_owned(
            wallet.wallet_id,
            owner_user_id="usr_other",
        )
    with pytest.raises(PresentationChallengeNotFoundError):
        challenges.get_authorized(
            challenge.challenge_id,
            actor_id="usr_other",
        )

    consumed = challenges.consume_for_presentation(
        challenge.challenge_id,
        wallet=wallet,
        actor_id=wallet.owner_user_id,
        correlation_id="challenge-consume-1",
    )
    with pytest.raises(PresentationChallengeReplayError):
        challenges.consume_for_presentation(
            challenge.challenge_id,
            wallet=wallet,
            actor_id=wallet.owner_user_id,
            correlation_id="challenge-replay-1",
        )

    assert consumed.domain == "verifier.example"
    assert consumed.challenge == "challenge_nonce_00000001"
    events = audit.list_recent()
    assert {
        AuditEventType.CHALLENGE_ISSUED,
        AuditEventType.CHALLENGE_CONSUMED,
        AuditEventType.CHALLENGE_REJECTED,
        AuditEventType.WALLET_CREATED,
    } == {event.event_type for event in events}
    assert all(
        consumed.challenge not in event.metadata.values()
        for event in events
    )
    snapshot = metrics.snapshot()
    assert snapshot.challenge_issuance_count == 1
    assert snapshot.challenge_replay_count == 1
    assert snapshot.challenge_rejection_count == 1


def test_expired_challenge_is_atomically_rejected_and_measured() -> None:
    wallet_service, challenges, audit, metrics, clock = _services()
    wallet = wallet_service.create(
        owner_user_id="usr_local_holder",
        correlation_id="wallet-create-1",
    )
    challenge = challenges.issue(
        domain="verifier.example",
        audience="secure-ssi-verifier",
        requested_holder_did=wallet.holder_did,
        issued_by="usr_local_verifier",
        lifetime_seconds=30,
        correlation_id="challenge-issue-1",
    )
    clock.value = NOW.replace(second=31)

    with pytest.raises(PresentationChallengeExpiredError):
        challenges.consume_for_presentation(
            challenge.challenge_id,
            wallet=wallet,
            actor_id=wallet.owner_user_id,
            correlation_id="challenge-expired-1",
        )

    assert (
        metrics.snapshot().expired_challenge_count == 1
    )
    rejected = audit.list_recent(
        event_type=AuditEventType.CHALLENGE_REJECTED
    )
    assert len(rejected) == 1
    assert rejected[0].metadata == {"reason": "CHALLENGE_EXPIRED"}
