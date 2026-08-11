from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from app.application.ports.holder_wallet import (
    HolderWalletRepository,
    PresentationChallengeRepository,
)
from app.application.ports.key_management import InitialWalletKeyProvisioner
from app.application.ports.presentation import HolderKeyProvider
from app.application.ports.repositories import CredentialRepository
from app.application.services.audit_outbox_service import (
    AuditOutboxDeliveryService,
)
from app.application.services.internal_metrics import InternalMetrics
from app.domain.audit_outbox import AuditOutboxRecord, AuditOutboxSource
from app.domain.holder_wallet import (
    HolderOwnershipError,
    HolderWallet,
    HolderWalletNotFoundError,
    WalletStatus,
)
from app.domain.persistence import (
    AuditEvent,
    AuditEventType,
    PersistedCredential,
    RepositoryError,
)
from app.domain.presentation_challenge import (
    ChallengeStatus,
    PresentationChallenge,
    PresentationChallengeExpiredError,
    PresentationChallengeNotFoundError,
    PresentationChallengeRejectedError,
    PresentationChallengeReplayError,
    normalize_audience,
)
from app.domain.presentation import normalize_domain


Clock = Callable[[], datetime]
IdGenerator = Callable[[], str]


class _DurableSecurityAudit:
    def __init__(
        self,
        delivery: AuditOutboxDeliveryService,
    ) -> None:
        self._delivery = delivery

    def record(
        self,
        event_type: AuditEventType,
        *,
        subject_id: str,
        actor_id: str,
        correlation_id: str,
        occurred_at: datetime,
        aggregate_type: str,
        metadata: dict[str, str],
        discriminator: str = "",
    ) -> None:
        event = AuditEvent(
            id=_audit_event_id(
                event_type,
                subject_id,
                actor_id,
                discriminator,
            ),
            event_type=event_type,
            subject_id=subject_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            metadata=metadata,
            created_at=occurred_at,
            updated_at=occurred_at,
        )
        try:
            self._delivery.ensure(
                AuditOutboxRecord.pending(
                    event=event,
                    aggregate_type=aggregate_type,
                    aggregate_id=subject_id,
                    source=AuditOutboxSource.COLLECTION,
                )
            )
            self._delivery.deliver_event(event.id)
        except RepositoryError:
            pass


class HolderWalletService:
    def __init__(
        self,
        *,
        wallet_repository: HolderWalletRepository,
        credential_repository: CredentialRepository,
        key_provider: HolderKeyProvider,
        audit_delivery_service: AuditOutboxDeliveryService,
        clock: Clock,
        storage_id_generator: IdGenerator,
        wallet_id_generator: IdGenerator,
        key_reference_generator: IdGenerator,
        metrics: InternalMetrics | None = None,
        initial_key_provisioner: InitialWalletKeyProvisioner | None = None,
    ) -> None:
        self._wallets = wallet_repository
        self._credentials = credential_repository
        self._keys = key_provider
        self._audit = _DurableSecurityAudit(audit_delivery_service)
        self._clock = clock
        self._storage_id_generator = storage_id_generator
        self._wallet_id_generator = wallet_id_generator
        self._key_reference_generator = key_reference_generator
        self._metrics = metrics
        self._initial_key_provisioner = initial_key_provisioner

    def create(
        self,
        *,
        owner_user_id: str,
        correlation_id: str,
    ) -> HolderWallet:
        now = self._now()
        wallet_id = self._wallet_id_generator()
        if self._initial_key_provisioner is None:
            key_reference = self._key_reference_generator()
            metadata = self._keys.provision(key_reference)
            holder_did = metadata.holder_did
        else:
            managed_key = (
                self._initial_key_provisioner.provision_initial_wallet_key(
                    wallet_id=wallet_id,
                    owner_user_id=owner_user_id,
                    idempotency_key=f"wallet-create:{wallet_id}",
                    correlation_id=correlation_id,
                )
            )
            if managed_key.provider_key_reference is None:
                raise ValueError(
                    "Active managed key requires a provider reference."
                )
            key_reference = managed_key.provider_key_reference
            holder_did = managed_key.holder_did
        wallet = HolderWallet(
            id=self._storage_id_generator(),
            wallet_id=wallet_id,
            owner_user_id=owner_user_id,
            holder_did=holder_did,
            status=WalletStatus.ACTIVE,
            key_reference=key_reference,
            created_at=now,
            updated_at=now,
        )
        stored = self._wallets.add(wallet)
        self._audit.record(
            AuditEventType.WALLET_CREATED,
            subject_id=stored.wallet_id,
            actor_id=owner_user_id,
            correlation_id=correlation_id,
            occurred_at=now,
            aggregate_type="holder_wallet",
            metadata={"status": stored.status.value},
        )
        if self._metrics is not None:
            self._metrics.record_wallet_created()
        return stored

    def get_owned(
        self,
        wallet_id: str,
        *,
        owner_user_id: str,
    ) -> HolderWallet:
        wallet = self._wallets.get(wallet_id)
        if wallet is None or wallet.owner_user_id != owner_user_id:
            raise HolderWalletNotFoundError(
                "The requested holder wallet was not found."
            )
        return wallet

    def require_owned_active(
        self,
        wallet_id: str,
        *,
        owner_user_id: str,
        correlation_id: str,
    ) -> HolderWallet:
        try:
            wallet = self.get_owned(
                wallet_id,
                owner_user_id=owner_user_id,
            )
        except HolderWalletNotFoundError:
            self.record_ownership_rejection(
                wallet_id=wallet_id,
                actor_id=owner_user_id,
                correlation_id=correlation_id,
                reason="WALLET_NOT_OWNED",
            )
            raise
        wallet.require_usable_for_signing()
        return wallet

    def list_credentials(
        self,
        wallet_id: str,
        *,
        owner_user_id: str,
        limit: int = 100,
    ) -> tuple[PersistedCredential, ...]:
        self.get_owned(wallet_id, owner_user_id=owner_user_id)
        return self._credentials.list_by_wallet(
            wallet_id,
            owner_user_id=owner_user_id,
            limit=limit,
        )

    def lock(
        self,
        wallet_id: str,
        *,
        owner_user_id: str,
        correlation_id: str,
    ) -> HolderWallet:
        wallet = self.get_owned(wallet_id, owner_user_id=owner_user_id)
        if wallet.status is not WalletStatus.ACTIVE:
            return wallet
        now = self._now()
        updated = self._wallets.update_status(
            wallet_id,
            status=WalletStatus.LOCKED,
            updated_at=now,
            expected_version=wallet.version,
        )
        self._audit.record(
            AuditEventType.WALLET_LOCKED,
            subject_id=wallet_id,
            actor_id=owner_user_id,
            correlation_id=correlation_id,
            occurred_at=now,
            aggregate_type="holder_wallet",
            metadata={"status": updated.status.value},
        )
        if self._metrics is not None:
            self._metrics.record_wallet_locked()
        return updated

    def disable(
        self,
        wallet_id: str,
        *,
        owner_user_id: str,
        correlation_id: str,
    ) -> HolderWallet:
        wallet = self.get_owned(wallet_id, owner_user_id=owner_user_id)
        if wallet.status is WalletStatus.DISABLED:
            return wallet
        now = self._now()
        updated = self._wallets.update_status(
            wallet_id,
            status=WalletStatus.DISABLED,
            updated_at=now,
            expected_version=wallet.version,
        )
        self._audit.record(
            AuditEventType.WALLET_DISABLED,
            subject_id=wallet_id,
            actor_id=owner_user_id,
            correlation_id=correlation_id,
            occurred_at=now,
            aggregate_type="holder_wallet",
            metadata={"status": updated.status.value},
        )
        if self._metrics is not None:
            self._metrics.record_wallet_disabled(
                was_locked=wallet.status is WalletStatus.LOCKED
            )
        return updated

    def record_ownership_rejection(
        self,
        *,
        wallet_id: str,
        actor_id: str,
        correlation_id: str,
        reason: str,
    ) -> None:
        now = self._now()
        self._audit.record(
            AuditEventType.HOLDER_OWNERSHIP_REJECTED,
            subject_id=wallet_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            occurred_at=now,
            aggregate_type="holder_wallet",
            metadata={"reason": reason},
            discriminator=reason,
        )
        if self._metrics is not None:
            self._metrics.record_ownership_rejection()

    def _now(self) -> datetime:
        return self._clock().astimezone(UTC).replace(microsecond=0)


class PresentationChallengeService:
    def __init__(
        self,
        *,
        challenge_repository: PresentationChallengeRepository,
        wallet_repository: HolderWalletRepository,
        audit_delivery_service: AuditOutboxDeliveryService,
        clock: Clock,
        storage_id_generator: IdGenerator,
        challenge_id_generator: IdGenerator,
        challenge_value_generator: IdGenerator,
        metrics: InternalMetrics | None = None,
    ) -> None:
        self._challenges = challenge_repository
        self._wallets = wallet_repository
        self._audit = _DurableSecurityAudit(audit_delivery_service)
        self._clock = clock
        self._storage_id_generator = storage_id_generator
        self._challenge_id_generator = challenge_id_generator
        self._challenge_value_generator = challenge_value_generator
        self._metrics = metrics

    def issue(
        self,
        *,
        domain: str,
        audience: str,
        requested_holder_did: str | None,
        issued_by: str,
        lifetime_seconds: int,
        correlation_id: str,
    ) -> PresentationChallenge:
        now = self._now()
        challenge = PresentationChallenge(
            id=self._storage_id_generator(),
            challenge_id=self._challenge_id_generator(),
            challenge=self._challenge_value_generator(),
            domain=normalize_domain(domain),
            audience=normalize_audience(audience),
            requested_holder_did=requested_holder_did,
            issued_by=issued_by,
            issued_at=now,
            expires_at=now + timedelta(seconds=lifetime_seconds),
            consumed_at=None,
            status=ChallengeStatus.ISSUED,
        )
        stored = self._challenges.add(challenge)
        self._audit.record(
            AuditEventType.CHALLENGE_ISSUED,
            subject_id=stored.challenge_id,
            actor_id=issued_by,
            correlation_id=correlation_id,
            occurred_at=now,
            aggregate_type="presentation_challenge",
            metadata={
                "domain": stored.domain,
                "audience": stored.audience,
                "status": stored.status.value,
            },
        )
        if self._metrics is not None:
            self._metrics.record_challenge_issued()
        return stored

    def get_authorized(
        self,
        challenge_id: str,
        *,
        actor_id: str,
    ) -> PresentationChallenge:
        challenge = self._challenges.get(challenge_id)
        if challenge is None:
            raise PresentationChallengeNotFoundError(
                "The requested challenge was not found."
            )
        allowed = challenge.issued_by == actor_id
        if not allowed and challenge.requested_holder_did is not None:
            wallet = self._wallets.get_active_by_holder_did(
                challenge.requested_holder_did
            )
            allowed = (
                wallet is not None
                and wallet.owner_user_id == actor_id
            )
        if not allowed:
            raise PresentationChallengeNotFoundError(
                "The requested challenge was not found."
            )
        return self._expire_if_needed(challenge)

    def consume_for_presentation(
        self,
        challenge_id: str,
        *,
        wallet: HolderWallet,
        actor_id: str,
        correlation_id: str,
    ) -> PresentationChallenge:
        if wallet.owner_user_id != actor_id:
            raise HolderOwnershipError(
                "The actor does not own the holder wallet."
            )
        challenge = self._challenges.get(challenge_id)
        if challenge is None:
            raise PresentationChallengeNotFoundError(
                "The requested challenge was not found."
            )
        now = self._now()
        if (
            challenge.requested_holder_did is not None
            and challenge.requested_holder_did != wallet.holder_did
        ):
            self._reject(
                challenge,
                actor_id=actor_id,
                correlation_id=correlation_id,
                reason="HOLDER_DID_MISMATCH",
            )
            raise PresentationChallengeRejectedError(
                "The challenge is restricted to a different holder."
            )
        if challenge.status is ChallengeStatus.CONSUMED:
            self._reject(
                challenge,
                actor_id=actor_id,
                correlation_id=correlation_id,
                reason="CHALLENGE_REPLAY",
                replay=True,
            )
            raise PresentationChallengeReplayError(
                "The challenge was already consumed."
            )
        if now > challenge.expires_at:
            self._challenges.expire(
                challenge_id,
                expired_at=now,
                expected_version=challenge.version,
            )
            self._reject(
                challenge,
                actor_id=actor_id,
                correlation_id=correlation_id,
                reason="CHALLENGE_EXPIRED",
                expired=True,
            )
            raise PresentationChallengeExpiredError(
                "The challenge has expired."
            )
        if challenge.status is not ChallengeStatus.ISSUED:
            self._reject(
                challenge,
                actor_id=actor_id,
                correlation_id=correlation_id,
                reason="CHALLENGE_UNAVAILABLE",
            )
            raise PresentationChallengeRejectedError(
                "The challenge cannot be consumed."
            )
        consumed = self._challenges.consume(
            challenge_id,
            consumed_at=now,
            expected_version=challenge.version,
            domain=challenge.domain,
            audience=challenge.audience,
            requested_holder_did=challenge.requested_holder_did,
        )
        if consumed is None:
            current = self._challenges.get(challenge_id)
            replay = (
                current is not None
                and current.status is ChallengeStatus.CONSUMED
            )
            self._reject(
                challenge,
                actor_id=actor_id,
                correlation_id=correlation_id,
                reason=(
                    "CHALLENGE_REPLAY"
                    if replay
                    else "CHALLENGE_CONFLICT"
                ),
                replay=replay,
            )
            if replay:
                raise PresentationChallengeReplayError(
                    "The challenge was already consumed."
                )
            raise PresentationChallengeRejectedError(
                "The challenge changed during consumption."
            )
        self._audit.record(
            AuditEventType.CHALLENGE_CONSUMED,
            subject_id=consumed.challenge_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            occurred_at=now,
            aggregate_type="presentation_challenge",
            metadata={
                "domain": consumed.domain,
                "audience": consumed.audience,
                "status": consumed.status.value,
            },
        )
        return consumed

    def require_for_verification(
        self,
        challenge_id: str,
        *,
        issued_by: str,
        holder_did: str,
    ) -> PresentationChallenge:
        challenge = self._challenges.get(challenge_id)
        if (
            challenge is None
            or challenge.issued_by != issued_by
            or challenge.status is not ChallengeStatus.CONSUMED
            or (
                challenge.requested_holder_did is not None
                and challenge.requested_holder_did != holder_did
            )
        ):
            raise PresentationChallengeNotFoundError(
                "The requested challenge was not found."
            )
        if self._now() > challenge.expires_at:
            raise PresentationChallengeExpiredError(
                "The challenge has expired."
            )
        return challenge

    def reject_binding(
        self,
        challenge: PresentationChallenge,
        *,
        actor_id: str,
        correlation_id: str,
        reason: str,
    ) -> None:
        self._reject(
            challenge,
            actor_id=actor_id,
            correlation_id=correlation_id,
            reason=reason,
        )
        raise PresentationChallengeRejectedError(
            "Client challenge binding conflicts with server state."
        )

    def get_for_reconciliation(
        self,
        challenge_id: str,
        *,
        holder_did: str,
    ) -> PresentationChallenge:
        challenge = self._challenges.get(challenge_id)
        if (
            challenge is None
            or challenge.status is not ChallengeStatus.CONSUMED
            or (
                challenge.requested_holder_did is not None
                and challenge.requested_holder_did != holder_did
            )
        ):
            raise PresentationChallengeRejectedError(
                "Challenge evidence is incomplete."
            )
        return challenge

    def _expire_if_needed(
        self,
        challenge: PresentationChallenge,
    ) -> PresentationChallenge:
        now = self._now()
        if (
            challenge.status is ChallengeStatus.ISSUED
            and now > challenge.expires_at
        ):
            return (
                self._challenges.expire(
                    challenge.challenge_id,
                    expired_at=now,
                    expected_version=challenge.version,
                )
                or challenge
            )
        return challenge

    def _reject(
        self,
        challenge: PresentationChallenge,
        *,
        actor_id: str,
        correlation_id: str,
        reason: str,
        replay: bool = False,
        expired: bool = False,
    ) -> None:
        now = self._now()
        self._audit.record(
            AuditEventType.CHALLENGE_REJECTED,
            subject_id=challenge.challenge_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            occurred_at=now,
            aggregate_type="presentation_challenge",
            metadata={"reason": reason},
            discriminator=reason,
        )
        if self._metrics is not None:
            self._metrics.record_challenge_rejected(
                replay=replay,
                expired=expired,
            )

    def _now(self) -> datetime:
        return self._clock().astimezone(UTC).replace(microsecond=0)


def _audit_event_id(
    event_type: AuditEventType,
    subject_id: str,
    actor_id: str,
    discriminator: str,
) -> str:
    value = (
        f"{event_type.value}\0{subject_id}\0{actor_id}\0{discriminator}"
    ).encode("utf-8")
    return sha256(value).hexdigest()[:24]
