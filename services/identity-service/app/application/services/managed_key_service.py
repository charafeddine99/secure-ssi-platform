import asyncio
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from time import perf_counter

from app.application.ports.holder_wallet import HolderWalletRepository
from app.application.ports.key_management import (
    ExternalKeyProvider,
    KeyPolicyProvider,
    ManagedKeyRepository,
)
from app.application.services.audit_outbox_service import (
    AuditOutboxDeliveryService,
)
from app.application.services.internal_metrics import InternalMetrics
from app.config.key_management_settings import KeyManagementSettings
from app.domain.audit_outbox import AuditOutboxRecord, AuditOutboxSource
from app.domain.holder_wallet import (
    HolderKeyMetadata,
    HolderWallet,
    HolderWalletNotFoundError,
)
from app.domain.managed_key import (
    KeyAlgorithm,
    KeyDestructionNotReadyError,
    KeyPurpose,
    ManagedKey,
    ManagedKeyError,
    ManagedKeyConflictError,
    ManagedKeyNotFoundError,
    ManagedKeySigningRejectedError,
    ManagedKeyState,
    ProviderKeyMetadata,
    ProviderKeyNotFoundError,
    ProviderMetadataError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    idempotency_hash,
    validate_provider_metadata,
)
from app.domain.persistence import (
    AuditEvent,
    AuditEventType,
    RepositoryError,
)


Clock = Callable[[], datetime]
IdGenerator = Callable[[], str]


class _ManagedKeyAudit:
    def __init__(self, delivery: AuditOutboxDeliveryService) -> None:
        self._delivery = delivery

    def record(
        self,
        event_type: AuditEventType,
        *,
        key: ManagedKey,
        actor_id: str,
        correlation_id: str,
        occurred_at: datetime,
        old_state: ManagedKeyState | None = None,
        reason_code: str | None = None,
        discriminator: str = "",
    ) -> None:
        metadata = {
            "walletId": key.wallet_id,
            "ownerUserId": key.owner_user_id,
            "holderDid": key.holder_did,
            "provider": key.provider,
            "algorithm": key.algorithm.value,
            "purpose": key.purpose.value,
            "newState": key.state.value,
        }
        if old_state is not None:
            metadata["oldState"] = old_state.value
        if reason_code is not None:
            metadata["reasonCode"] = _reason_code(reason_code)
        event = AuditEvent(
            id=_audit_id(
                event_type,
                key.key_id,
                actor_id,
                f"{key.version}:{discriminator}",
            ),
            event_type=event_type,
            subject_id=key.key_id,
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
                    aggregate_type="managed_key",
                    aggregate_id=key.key_id,
                    source=AuditOutboxSource.COLLECTION,
                )
            )
            self._delivery.deliver_event(event.id)
        except RepositoryError:
            pass


class ManagedKeyService:
    def __init__(
        self,
        *,
        repository: ManagedKeyRepository,
        wallet_repository: HolderWalletRepository,
        providers: Mapping[str, ExternalKeyProvider],
        policy: KeyPolicyProvider,
        audit_delivery_service: AuditOutboxDeliveryService,
        clock: Clock,
        storage_id_generator: IdGenerator,
        key_id_generator: IdGenerator,
        default_provider: str,
        metrics: InternalMetrics | None = None,
        reconciliation_retry_limit: int = 5,
        reconciliation_lease_seconds: int = 30,
    ) -> None:
        self._keys = repository
        self._wallets = wallet_repository
        self._providers = {
            name.casefold(): provider for name, provider in providers.items()
        }
        self._policy = policy
        self._audit = _ManagedKeyAudit(audit_delivery_service)
        self._clock = clock
        self._storage_id_generator = storage_id_generator
        self._key_id_generator = key_id_generator
        self._default_provider = default_provider.casefold()
        self._metrics = metrics
        self._reconciliation_retry_limit = reconciliation_retry_limit
        self._reconciliation_lease_seconds = (
            reconciliation_lease_seconds
        )

    def provision_initial_wallet_key(
        self,
        *,
        wallet_id: str,
        owner_user_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> ManagedKey:
        return self._provision(
            wallet_id=wallet_id,
            owner_user_id=owner_user_id,
            holder_did="did:pending:managed-key",
            purpose=KeyPurpose.PRESENTATION_SIGNING,
            algorithm=KeyAlgorithm.ED25519,
            provider_name=self._default_provider,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            predecessor=None,
        )

    def create_for_wallet(
        self,
        *,
        wallet_id: str,
        owner_user_id: str,
        purpose: KeyPurpose,
        algorithm: KeyAlgorithm,
        provider_name: str | None,
        idempotency_key: str,
        correlation_id: str,
    ) -> ManagedKey:
        wallet = self._owned_wallet(
            wallet_id,
            owner_user_id=owner_user_id,
        )
        if self._keys.get_active(
            wallet_id=wallet_id,
            purpose=purpose,
        ) is not None:
            existing = self._keys.get_by_idempotency_hash(
                wallet_id=wallet_id,
                purpose=purpose,
                idempotency_key_hash=idempotency_hash(idempotency_key),
            )
            if existing is not None:
                self._bind_presentation_key(wallet, existing)
                return existing
            raise ManagedKeyConflictError(
                "An active key already exists for the wallet and purpose."
            )
        managed_key = self._provision(
            wallet_id=wallet_id,
            owner_user_id=owner_user_id,
            holder_did=wallet.holder_did,
            purpose=purpose,
            algorithm=algorithm,
            provider_name=provider_name or self._default_provider,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            predecessor=None,
        )
        self._bind_presentation_key(wallet, managed_key)
        return managed_key

    def list_owned(
        self,
        wallet_id: str,
        *,
        owner_user_id: str,
        limit: int,
        after_key_id: str | None,
    ) -> tuple[ManagedKey, ...]:
        self._owned_wallet(wallet_id, owner_user_id=owner_user_id)
        return self._keys.list_for_wallet(
            wallet_id,
            limit=limit,
            after_key_id=after_key_id,
        )

    def get_owned(
        self,
        wallet_id: str,
        key_id: str,
        *,
        owner_user_id: str,
        correlation_id: str = "managed-key-read",
    ) -> ManagedKey:
        wallet = self._wallets.get(wallet_id)
        key = self._keys.get(key_id)
        if (
            wallet is None
            or wallet.owner_user_id != owner_user_id
            or key is None
            or key.wallet_id != wallet_id
            or key.owner_user_id != owner_user_id
        ):
            if key is not None and key.wallet_id == wallet_id:
                self._audit.record(
                    AuditEventType.UNAUTHORIZED_KEY_ACCESS,
                    key=key,
                    actor_id=owner_user_id,
                    correlation_id=correlation_id,
                    occurred_at=self._now(),
                    reason_code="OBJECT_OWNERSHIP_REJECTED",
                )
            raise ManagedKeyNotFoundError(
                "The requested managed key was not found."
            )
        wallet.require_usable_for_signing()
        return key

    def rotate(
        self,
        wallet_id: str,
        key_id: str,
        *,
        owner_user_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> ManagedKey:
        source = self.get_owned(
            wallet_id,
            key_id,
            owner_user_id=owner_user_id,
            correlation_id=correlation_id,
        )
        digest = idempotency_hash(idempotency_key)
        existing = self._keys.get_by_idempotency_hash(
            wallet_id=wallet_id,
            purpose=source.purpose,
            idempotency_key_hash=digest,
        )
        if existing is not None:
            if existing.predecessor_key_id != source.key_id:
                raise ManagedKeyConflictError(
                    "Idempotency key belongs to another operation."
                )
            return existing
        if source.state is not ManagedKeyState.ACTIVE:
            raise ManagedKeyConflictError(
                "Only an active managed key can be rotated."
            )
        if source.holder_did.startswith("did:web:"):
            raise ManagedKeyConflictError(
                "did:web rotation requires a controlled mutable DID document."
            )
        now = self._now()
        self._audit.record(
            AuditEventType.KEY_ROTATION_REQUESTED,
            key=source,
            actor_id=owner_user_id,
            correlation_id=correlation_id,
            occurred_at=now,
        )
        claimed = self._keys.claim_rotation(
            source.key_id,
            rotated_at=now,
            expected_version=source.version,
        )
        try:
            successor = self._provision(
                wallet_id=wallet_id,
                owner_user_id=owner_user_id,
                holder_did=source.holder_did,
                purpose=source.purpose,
                algorithm=source.algorithm,
                provider_name=source.provider,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
                predecessor=source,
            )
            self._audit.record(
                AuditEventType.SUCCESSOR_KEY_CREATED,
                key=successor,
                actor_id=owner_user_id,
                correlation_id=correlation_id,
                occurred_at=now,
            )
            linked = self._keys.link_successor(
                claimed.key_id,
                successor_key_id=successor.key_id,
                updated_at=now,
                expected_version=claimed.version,
            )
            wallet = self._owned_wallet(
                wallet_id,
                owner_user_id=owner_user_id,
            )
            self._wallets.update_key_binding(
                wallet_id,
                holder_did=successor.holder_did,
                key_reference=_provider_reference(successor),
                updated_at=now,
                expected_version=wallet.version,
            )
            if self._policy.rotation_grace_seconds == 0:
                provider = self._provider(linked.provider)
                self._call_provider(
                    lambda: provider.suspend_key(
                        _provider_reference(linked)
                    )
                )
                retired = linked.transition(
                    ManagedKeyState.SUSPENDED,
                    at=now,
                )
                self._keys.update(
                    retired,
                    expected_version=linked.version,
                )
            self._audit.record(
                AuditEventType.KEY_ROTATION_COMPLETED,
                key=successor,
                actor_id=owner_user_id,
                correlation_id=correlation_id,
                occurred_at=now,
                old_state=source.state,
            )
            if self._metrics is not None:
                self._metrics.record_key_rotation(succeeded=True)
            self._observe_inventory()
            return successor
        except Exception:
            self._audit.record(
                AuditEventType.KEY_ROTATION_FAILED,
                key=claimed,
                actor_id=owner_user_id,
                correlation_id=correlation_id,
                occurred_at=now,
                reason_code="PARTIAL_ROTATION_FAILURE",
            )
            if self._metrics is not None:
                self._metrics.record_key_rotation(succeeded=False)
            raise

    def suspend(
        self,
        wallet_id: str,
        key_id: str,
        *,
        owner_user_id: str,
        correlation_id: str,
    ) -> ManagedKey:
        return self._provider_transition(
            self.get_owned(
                wallet_id,
                key_id,
                owner_user_id=owner_user_id,
                correlation_id=correlation_id,
            ),
            new_state=ManagedKeyState.SUSPENDED,
            event_type=AuditEventType.MANAGED_KEY_SUSPENDED,
            actor_id=owner_user_id,
            correlation_id=correlation_id,
            provider_action="suspend",
        )

    def resume(
        self,
        wallet_id: str,
        key_id: str,
        *,
        owner_user_id: str,
        correlation_id: str,
    ) -> ManagedKey:
        key = self.get_owned(
            wallet_id,
            key_id,
            owner_user_id=owner_user_id,
            correlation_id=correlation_id,
        )
        self._policy.require_resume_allowed(key)
        return self._provider_transition(
            key,
            new_state=ManagedKeyState.ACTIVE,
            event_type=AuditEventType.MANAGED_KEY_RESUMED,
            actor_id=owner_user_id,
            correlation_id=correlation_id,
            provider_action="enable",
        )

    def mark_compromised(
        self,
        wallet_id: str,
        key_id: str,
        *,
        actor_id: str,
        reason: str,
        correlation_id: str,
        administrative: bool,
    ) -> ManagedKey:
        key = self._authorized_key(
            wallet_id,
            key_id,
            actor_id=actor_id,
            administrative=administrative,
        )
        now = self._now()
        changed = key.transition(
            ManagedKeyState.COMPROMISED,
            at=now,
            reason=reason,
        )
        stored = self._keys.update(
            changed,
            expected_version=key.version,
        )
        try:
            provider = self._provider(stored.provider)
            self._call_provider(
                lambda: provider.suspend_key(
                    _provider_reference(stored)
                )
            )
        finally:
            self._audit.record(
                AuditEventType.MANAGED_KEY_COMPROMISED,
                key=stored,
                actor_id=actor_id,
                correlation_id=correlation_id,
                occurred_at=now,
                old_state=key.state,
                reason_code="REPORTED_COMPROMISE",
            )
            if self._metrics is not None:
                self._metrics.record_key_compromise()
            self._observe_inventory()
        return stored

    def revoke(
        self,
        wallet_id: str,
        key_id: str,
        *,
        owner_user_id: str,
        reason: str,
        correlation_id: str,
    ) -> ManagedKey:
        key = self.get_owned(
            wallet_id,
            key_id,
            owner_user_id=owner_user_id,
            correlation_id=correlation_id,
        )
        stored = self._provider_transition(
            key,
            new_state=ManagedKeyState.REVOKED,
            event_type=AuditEventType.MANAGED_KEY_REVOKED,
            actor_id=owner_user_id,
            correlation_id=correlation_id,
            provider_action="revoke",
            reason=reason,
        )
        if self._metrics is not None:
            self._metrics.record_key_revocation()
        return stored

    def schedule_destruction(
        self,
        wallet_id: str,
        key_id: str,
        *,
        actor_id: str,
        reason: str,
        confirmation: str,
        correlation_id: str,
        administrative: bool,
    ) -> ManagedKey:
        if confirmation != key_id:
            raise ManagedKeyConflictError(
                "Destruction confirmation does not match the key id."
            )
        if len(reason.strip()) < 8:
            raise ValueError("A destruction reason is required.")
        key = self._authorized_key(
            wallet_id,
            key_id,
            actor_id=actor_id,
            administrative=administrative,
        )
        now = self._now()
        delete_at = self._policy.destruction_time(now=now)
        provider = self._provider(key.provider)
        self._call_provider(
            lambda: provider.schedule_deletion(
                _provider_reference(key),
                delete_at=delete_at,
            )
        )
        changed = key.transition(
            ManagedKeyState.DESTROY_PENDING,
            at=now,
            reason=reason,
            destruction_scheduled_at=delete_at,
        )
        stored = self._keys.update(
            changed,
            expected_version=key.version,
        )
        self._audit.record(
            AuditEventType.KEY_DESTRUCTION_SCHEDULED,
            key=stored,
            actor_id=actor_id,
            correlation_id=correlation_id,
            occurred_at=now,
            old_state=key.state,
            reason_code="ADMINISTRATIVE_DESTRUCTION",
        )
        if self._metrics is not None:
            self._metrics.record_key_destruction(stage="scheduled")
        self._observe_inventory()
        return stored

    def cancel_destruction(
        self,
        wallet_id: str,
        key_id: str,
        *,
        actor_id: str,
        reason: str,
        correlation_id: str,
        administrative: bool,
    ) -> ManagedKey:
        del reason
        key = self._authorized_key(
            wallet_id,
            key_id,
            actor_id=actor_id,
            administrative=administrative,
        )
        provider = self._provider(key.provider)
        self._call_provider(
            lambda: provider.cancel_scheduled_deletion(
                _provider_reference(key)
            )
        )
        now = self._now()
        changed = key.transition(ManagedKeyState.REVOKED, at=now)
        stored = self._keys.update(
            changed,
            expected_version=key.version,
        )
        self._audit.record(
            AuditEventType.KEY_DESTRUCTION_CANCELLED,
            key=stored,
            actor_id=actor_id,
            correlation_id=correlation_id,
            occurred_at=now,
            old_state=key.state,
        )
        self._observe_inventory()
        return stored

    def reconcile_authorized(
        self,
        wallet_id: str,
        key_id: str,
        *,
        actor_id: str,
        correlation_id: str,
        administrative: bool,
    ) -> ManagedKey:
        key = self._authorized_key(
            wallet_id,
            key_id,
            actor_id=actor_id,
            administrative=administrative,
        )
        return self.reconcile(
            key,
            actor_id=actor_id,
            correlation_id=correlation_id,
        )

    def reconcile(
        self,
        key: ManagedKey,
        *,
        actor_id: str = "managed-key-reconciliation",
        correlation_id: str = "managed-key-reconciliation",
    ) -> ManagedKey:
        now = self._now()
        claimed = self._keys.claim_reconciliation(
            key.key_id,
            now=now,
            lease_until=now
            + timedelta(seconds=self._reconciliation_lease_seconds),
            expected_version=key.version,
        )
        if claimed is None:
            return self._keys.get(key.key_id) or key
        self._audit.record(
            AuditEventType.KEY_RECONCILIATION_CLAIMED,
            key=claimed,
            actor_id=actor_id,
            correlation_id=correlation_id,
            occurred_at=now,
        )
        try:
            reconciled = self._reconcile_claimed(claimed, now=now)
            self._audit.record(
                AuditEventType.KEY_RECONCILIATION_COMPLETED,
                key=reconciled,
                actor_id=actor_id,
                correlation_id=correlation_id,
                occurred_at=now,
            )
            if (
                claimed.state is not ManagedKeyState.DESTROYED
                and reconciled.state is ManagedKeyState.DESTROYED
            ):
                self._audit.record(
                    AuditEventType.MANAGED_KEY_DESTROYED,
                    key=reconciled,
                    actor_id=actor_id,
                    correlation_id=correlation_id,
                    occurred_at=now,
                    old_state=claimed.state,
                )
            if self._metrics is not None:
                self._metrics.record_key_reconciliation(succeeded=True)
            self._observe_inventory()
            return reconciled
        except Exception as error:
            if isinstance(error, ProviderMetadataError):
                self._audit.record(
                    AuditEventType.KEY_PROVIDER_MISMATCH,
                    key=claimed,
                    actor_id=actor_id,
                    correlation_id=correlation_id,
                    occurred_at=now,
                    reason_code="PROVIDER_METADATA_MISMATCH",
                )
            self._audit.record(
                AuditEventType.KEY_RECONCILIATION_FAILED,
                key=claimed,
                actor_id=actor_id,
                correlation_id=correlation_id,
                occurred_at=now,
                reason_code="RECONCILIATION_FAILED",
            )
            if self._metrics is not None:
                self._metrics.record_key_reconciliation(succeeded=False)
                if claimed.state is ManagedKeyState.DESTROY_PENDING:
                    self._metrics.record_key_destruction(stage="failed")
            if (
                claimed.reconciliation_attempts
                >= self._reconciliation_retry_limit
                and claimed.state is not ManagedKeyState.FAILED
            ):
                failed = claimed.transition(
                    ManagedKeyState.FAILED,
                    at=now,
                    reason="RETRY_LIMIT_REACHED",
                )
                self._keys.update(
                    failed,
                    expected_version=claimed.version,
                )
            raise

    def reconcile_batch(
        self,
        *,
        stale_seconds: int,
        batch_size: int,
    ) -> tuple[int, int]:
        now = self._now()
        candidates = self._keys.list_reconciliation_candidates(
            stale_before=now - timedelta(seconds=stale_seconds),
            due_before=now,
            limit=batch_size,
        )
        if self._metrics is not None:
            self._metrics.observe_stale_key_rotations(
                count=sum(
                    key.state is ManagedKeyState.ROTATING
                    for key in candidates
                )
            )
        succeeded = 0
        failed = 0
        for key in candidates:
            try:
                self.reconcile(key)
                succeeded += 1
            except (RepositoryError, ManagedKeyError):
                failed += 1
        return succeeded, failed

    def _provision(
        self,
        *,
        wallet_id: str,
        owner_user_id: str,
        holder_did: str,
        purpose: KeyPurpose,
        algorithm: KeyAlgorithm,
        provider_name: str,
        idempotency_key: str,
        correlation_id: str,
        predecessor: ManagedKey | None,
    ) -> ManagedKey:
        provider_name = provider_name.casefold()
        self._policy.require_provision_allowed(
            provider=provider_name,
            algorithm=algorithm,
            purpose=purpose,
        )
        digest = idempotency_hash(idempotency_key)
        existing = self._keys.get_by_idempotency_hash(
            wallet_id=wallet_id,
            purpose=purpose,
            idempotency_key_hash=digest,
        )
        if existing is not None:
            return existing
        now = self._now()
        versions = self._keys.list_versions(
            wallet_id=wallet_id,
            purpose=purpose,
        )
        next_version = (
            max((key.key_version for key in versions), default=0) + 1
        )
        pending = ManagedKey(
            id=self._storage_id_generator(),
            key_id=self._key_id_generator(),
            wallet_id=wallet_id,
            owner_user_id=owner_user_id,
            holder_did=holder_did,
            provider=provider_name,
            algorithm=algorithm,
            purpose=purpose,
            key_version=next_version,
            state=ManagedKeyState.PENDING,
            created_at=now,
            updated_at=now,
            predecessor_key_id=(
                None if predecessor is None else predecessor.key_id
            ),
            idempotency_key_hash=digest,
        )
        stored_pending = self._keys.add(pending)
        self._audit.record(
            AuditEventType.MANAGED_KEY_REQUESTED,
            key=stored_pending,
            actor_id=owner_user_id,
            correlation_id=correlation_id,
            occurred_at=now,
        )
        try:
            provider = self._provider(provider_name)
            metadata = self._call_provider(
                lambda: provider.create_key(
                    key_id=pending.key_id,
                    algorithm=algorithm,
                    purpose=purpose,
                    idempotency_key=digest,
                )
            )
            validate_provider_metadata(
                metadata,
                provider=provider_name,
                algorithm=algorithm,
            )
            provisioned = replace(
                stored_pending,
                holder_did=metadata.holder_did,
                provider_key_reference=(
                    metadata.provider_key_reference
                ),
                public_key_multibase=metadata.public_key_multibase,
                fingerprint=metadata.fingerprint,
                verification_method=metadata.verification_method,
                last_provider_sync_at=now,
            )
            active = provisioned.transition(
                ManagedKeyState.ACTIVE,
                at=now,
            )
            stored = self._keys.update(
                active,
                expected_version=stored_pending.version,
            )
            self._audit.record(
                AuditEventType.PROVIDER_KEY_CREATED,
                key=stored,
                actor_id=owner_user_id,
                correlation_id=correlation_id,
                occurred_at=now,
            )
            self._audit.record(
                AuditEventType.MANAGED_KEY_ACTIVATED,
                key=stored,
                actor_id=owner_user_id,
                correlation_id=correlation_id,
                occurred_at=now,
                old_state=ManagedKeyState.PENDING,
            )
            if self._metrics is not None:
                self._metrics.record_managed_key_creation(succeeded=True)
            self._observe_inventory()
            return stored
        except Exception as error:
            if isinstance(error, ProviderMetadataError):
                self._audit.record(
                    AuditEventType.KEY_PROVIDER_MISMATCH,
                    key=stored_pending,
                    actor_id=owner_user_id,
                    correlation_id=correlation_id,
                    occurred_at=now,
                    reason_code="PROVIDER_METADATA_MISMATCH",
                )
            self._audit.record(
                AuditEventType.MANAGED_KEY_CREATION_FAILED,
                key=stored_pending,
                actor_id=owner_user_id,
                correlation_id=correlation_id,
                occurred_at=now,
                reason_code="PROVISIONING_FAILED",
            )
            if self._metrics is not None:
                self._metrics.record_managed_key_creation(succeeded=False)
            raise

    def _provider_transition(
        self,
        key: ManagedKey,
        *,
        new_state: ManagedKeyState,
        event_type: AuditEventType,
        actor_id: str,
        correlation_id: str,
        provider_action: str,
        reason: str | None = None,
    ) -> ManagedKey:
        now = self._now()
        if new_state is key.state:
            return key
        changed = key.transition(new_state, at=now, reason=reason)
        provider = self._provider(key.provider)
        action = {
            "enable": provider.enable_key,
            "suspend": provider.suspend_key,
            "revoke": provider.revoke_key,
        }[provider_action]
        self._call_provider(lambda: action(_provider_reference(key)))
        stored = self._keys.update(
            changed,
            expected_version=key.version,
        )
        self._audit.record(
            event_type,
            key=stored,
            actor_id=actor_id,
            correlation_id=correlation_id,
            occurred_at=now,
            old_state=key.state,
            reason_code=reason,
        )
        self._observe_inventory()
        return stored

    def _observe_inventory(self) -> None:
        if self._metrics is None:
            return
        try:
            self._metrics.observe_managed_key_inventory(
                active_by_provider_purpose=(
                    self._keys.count_active_by_provider_purpose()
                ),
                by_state={
                    state.value: count
                    for state, count in self._keys.count_by_state().items()
                },
            )
        except RepositoryError:
            return

    def _reconcile_claimed(
        self,
        key: ManagedKey,
        *,
        now: datetime,
    ) -> ManagedKey:
        provider = self._provider(key.provider)
        if key.state is ManagedKeyState.DESTROY_PENDING:
            scheduled_at = key.destruction_scheduled_at
            if scheduled_at is None or scheduled_at > now:
                raise KeyDestructionNotReadyError(
                    "The destruction delay has not elapsed."
                )
            try:
                self._call_provider(
                    lambda: provider.destroy_key(
                        _provider_reference(key)
                    )
                )
            except ProviderKeyNotFoundError:
                pass
            destroyed = key.transition(
                ManagedKeyState.DESTROYED,
                at=now,
            )
            result = self._keys.update(
                destroyed,
                expected_version=key.version,
            )
            if self._metrics is not None:
                self._metrics.record_key_destruction(stage="completed")
            return result
        if (
            key.state is ManagedKeyState.PENDING
            and key.provider_key_reference is None
        ):
            if key.idempotency_key_hash is None:
                raise ProviderMetadataError(
                    "Pending key lacks a recoverable idempotency identity."
                )
            created = self._call_provider(
                lambda: provider.create_key(
                    key_id=key.key_id,
                    algorithm=key.algorithm,
                    purpose=key.purpose,
                    idempotency_key=key.idempotency_key_hash,
                )
            )
            validate_provider_metadata(
                created,
                provider=key.provider,
                algorithm=key.algorithm,
            )
            hydrated = _with_provider_metadata(key, created, now=now)
            activated = hydrated.transition(
                ManagedKeyState.ACTIVE,
                at=now,
            )
            stored = self._keys.update(
                activated,
                expected_version=key.version,
            )
            wallet = self._wallets.get(stored.wallet_id)
            if (
                wallet is not None
                and wallet.owner_user_id == stored.owner_user_id
            ):
                self._bind_presentation_key(wallet, stored)
            return stored
        try:
            metadata = self._call_provider(
                lambda: provider.get_key_metadata(
                    _provider_reference(key)
                )
            )
        except ProviderKeyNotFoundError:
            if key.state is ManagedKeyState.ACTIVE:
                failed = key.transition(
                    ManagedKeyState.FAILED,
                    at=now,
                    reason="PROVIDER_KEY_MISSING",
                )
                return self._keys.update(
                    failed,
                    expected_version=key.version,
                )
            raise
        validate_provider_metadata(
            metadata,
            provider=key.provider,
            algorithm=key.algorithm,
            provider_key_reference=key.provider_key_reference,
        )
        if key.state is ManagedKeyState.PENDING:
            hydrated = _with_provider_metadata(key, metadata, now=now)
            activated = hydrated.transition(
                ManagedKeyState.ACTIVE,
                at=now,
            )
            stored = self._keys.update(
                activated,
                expected_version=key.version,
            )
            wallet = self._wallets.get(stored.wallet_id)
            if (
                wallet is not None
                and wallet.owner_user_id == stored.owner_user_id
            ):
                self._bind_presentation_key(wallet, stored)
            return stored
        if key.state is ManagedKeyState.ROTATING:
            grace_ends_at = (
                key.rotated_at or key.updated_at or now
            ) + timedelta(seconds=self._policy.rotation_grace_seconds)
            if now < grace_ends_at:
                waiting = replace(
                    key,
                    reconciliation_lease_until=None,
                    last_provider_sync_at=now,
                    updated_at=now,
                    version=key.version + 1,
                )
                return self._keys.update(
                    waiting,
                    expected_version=key.version,
                )
            if key.successor_key_id is None:
                restored = key.transition(
                    ManagedKeyState.ACTIVE,
                    at=now,
                )
                return self._keys.update(
                    restored,
                    expected_version=key.version,
                )
            successor = self._keys.get(key.successor_key_id)
            if (
                successor is None
                or successor.state is not ManagedKeyState.ACTIVE
            ):
                raise ManagedKeyConflictError(
                    "Rotation successor is not active."
                )
            wallet = self._wallets.get(key.wallet_id)
            if wallet is None or wallet.owner_user_id != key.owner_user_id:
                raise ManagedKeyConflictError(
                    "Rotation wallet binding is unavailable."
                )
            if (
                wallet.key_reference
                != successor.provider_key_reference
                or wallet.holder_did != successor.holder_did
            ):
                self._wallets.update_key_binding(
                    wallet.wallet_id,
                    holder_did=successor.holder_did,
                    key_reference=_provider_reference(successor),
                    updated_at=now,
                    expected_version=wallet.version,
                )
            self._call_provider(
                lambda: provider.suspend_key(
                    _provider_reference(key)
                )
            )
            retired = key.transition(
                ManagedKeyState.SUSPENDED,
                at=now,
            )
            return self._keys.update(
                retired,
                expected_version=key.version,
            )
        if key.state is ManagedKeyState.ACTIVE and not metadata.enabled:
            suspended = key.transition(
                ManagedKeyState.SUSPENDED,
                at=now,
            )
            return self._keys.update(
                suspended,
                expected_version=key.version,
            )
        if key.state is ManagedKeyState.ACTIVE:
            wallet = self._wallets.get(key.wallet_id)
            if wallet is None or wallet.owner_user_id != key.owner_user_id:
                self._call_provider(
                    lambda: provider.suspend_key(
                        _provider_reference(key)
                    )
                )
                failed = key.transition(
                    ManagedKeyState.FAILED,
                    at=now,
                    reason="WALLET_BINDING_MISSING",
                )
                return self._keys.update(
                    failed,
                    expected_version=key.version,
                )
        synced = replace(
            key,
            last_provider_sync_at=now,
            reconciliation_lease_until=None,
            updated_at=now,
            version=key.version + 1,
        )
        return self._keys.update(
            synced,
            expected_version=key.version,
        )

    def _owned_wallet(
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
        wallet.require_usable_for_signing()
        return wallet

    def _bind_presentation_key(
        self,
        wallet: HolderWallet,
        key: ManagedKey,
    ) -> None:
        if key.purpose is not KeyPurpose.PRESENTATION_SIGNING:
            return
        if (
            wallet.key_reference == key.provider_key_reference
            and wallet.holder_did == key.holder_did
        ):
            return
        self._wallets.update_key_binding(
            wallet.wallet_id,
            holder_did=key.holder_did,
            key_reference=_provider_reference(key),
            updated_at=self._now(),
            expected_version=wallet.version,
        )

    def _authorized_key(
        self,
        wallet_id: str,
        key_id: str,
        *,
        actor_id: str,
        administrative: bool,
    ) -> ManagedKey:
        key = self._keys.get(key_id)
        if key is None or key.wallet_id != wallet_id:
            raise ManagedKeyNotFoundError(
                "The requested managed key was not found."
            )
        if key.owner_user_id != actor_id and not administrative:
            raise ManagedKeyNotFoundError(
                "The requested managed key was not found."
            )
        return key

    def _provider(self, name: str) -> ExternalKeyProvider:
        provider = self._providers.get(name.casefold())
        if provider is None:
            raise ProviderUnavailableError(
                "The configured key provider is unavailable."
            )
        return provider

    def _call_provider(self, operation: Callable[[], object]):
        started = perf_counter()
        try:
            result = operation()
        except ProviderTimeoutError:
            if self._metrics is not None:
                self._metrics.observe_provider_request(
                    latency_seconds=perf_counter() - started,
                    timed_out=True,
                    failed=True,
                )
            raise
        except Exception:
            if self._metrics is not None:
                self._metrics.observe_provider_request(
                    latency_seconds=perf_counter() - started,
                    failed=True,
                )
            raise
        if self._metrics is not None:
            self._metrics.observe_provider_request(
                latency_seconds=perf_counter() - started,
            )
        return result

    def _now(self) -> datetime:
        return self._clock().astimezone(UTC).replace(microsecond=0)


class ManagedKeyReconciliationBackgroundService:
    def __init__(
        self,
        service: ManagedKeyService,
        *,
        settings: KeyManagementSettings,
    ) -> None:
        self._service = service
        self._settings = settings

    async def run(self, stop_event: asyncio.Event) -> None:
        interval = self._settings.reconciliation_interval_ms / 1_000
        while not stop_event.is_set():
            try:
                await asyncio.to_thread(
                    self._service.reconcile_batch,
                    stale_seconds=self._settings.stale_operation_seconds,
                    batch_size=self._settings.reconciliation_batch_size,
                )
            except RepositoryError:
                pass
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=interval,
                )
            except TimeoutError:
                continue


class ProviderAwareHolderSigner:
    def __init__(
        self,
        *,
        repository: ManagedKeyRepository,
        providers: Mapping[str, ExternalKeyProvider],
        legacy_provider: object | None = None,
        legacy_signer: object | None = None,
        allow_legacy_fallback: bool = False,
        metrics: InternalMetrics | None = None,
        audit_delivery_service: AuditOutboxDeliveryService | None = None,
    ) -> None:
        self._keys = repository
        self._providers = {
            name.casefold(): provider for name, provider in providers.items()
        }
        self._legacy_provider = legacy_provider
        self._legacy_signer = legacy_signer
        self._allow_legacy_fallback = allow_legacy_fallback
        self._metrics = metrics
        self._audit = (
            None
            if audit_delivery_service is None
            else _ManagedKeyAudit(audit_delivery_service)
        )

    def sign(
        self,
        message: bytes,
        *,
        key_reference: str,
    ) -> bytes:
        key = self._managed_by_reference(key_reference)
        if key is None:
            return self._legacy_sign(message, key_reference=key_reference)
        try:
            key.require_signing(
                purpose=KeyPurpose.PRESENTATION_SIGNING,
                algorithm=KeyAlgorithm.ED25519,
            )
        except ManagedKeySigningRejectedError:
            if self._metrics is not None:
                self._metrics.record_managed_signing(
                    succeeded=False,
                    lifecycle_rejected=True,
                )
            self._record_signing_rejection(
                key,
                reason_code="INVALID_LIFECYCLE_STATE",
            )
            raise
        provider = self._providers.get(key.provider.casefold())
        if provider is None:
            raise ProviderUnavailableError(
                "The managed key provider is disabled."
            )
        metadata = provider.get_key_metadata(
            _provider_reference(key)
        )
        validate_provider_metadata(
            metadata,
            provider=key.provider,
            algorithm=key.algorithm,
            provider_key_reference=key.provider_key_reference,
        )
        if not metadata.enabled:
            if self._metrics is not None:
                self._metrics.record_managed_signing(
                    succeeded=False,
                    lifecycle_rejected=True,
                )
            self._record_signing_rejection(
                key,
                reason_code="PROVIDER_KEY_DISABLED",
            )
            raise ManagedKeySigningRejectedError(
                "The provider has disabled this managed key."
            )
        try:
            signature = provider.sign(
                message,
                provider_key_reference=_provider_reference(key),
                algorithm=key.algorithm,
            )
        except Exception:
            if self._metrics is not None:
                self._metrics.record_managed_signing(succeeded=False)
            raise
        if self._metrics is not None:
            self._metrics.record_managed_signing(succeeded=True)
        return signature

    def _record_signing_rejection(
        self,
        key: ManagedKey,
        *,
        reason_code: str,
    ) -> None:
        if self._audit is None:
            return
        self._audit.record(
            AuditEventType.MANAGED_KEY_SIGNING_REJECTED,
            key=key,
            actor_id=key.owner_user_id,
            correlation_id="managed-key-signing",
            occurred_at=datetime.now(UTC).replace(microsecond=0),
            reason_code=reason_code,
        )

    def get_metadata(self, key_reference: str) -> HolderKeyMetadata:
        key = self._managed_by_reference(key_reference)
        if key is None:
            provider = self._require_legacy_provider()
            return provider.get_metadata(key_reference)
        key.require_signing(
            purpose=KeyPurpose.PRESENTATION_SIGNING,
            algorithm=KeyAlgorithm.ED25519,
        )
        if key.verification_method is None:
            raise ProviderMetadataError(
                "Managed key public metadata is incomplete."
            )
        return HolderKeyMetadata(
            key_reference=key_reference,
            holder_did=key.holder_did,
            verification_method=key.verification_method,
            algorithm=key.algorithm.value,
        )

    def get_verification_key(self, verification_method: str):
        from app.domain.crypto import VerificationKey
        from app.infrastructure.crypto.local_holder_key_provider import (
            ED25519_MULTICODEC_PREFIX,
        )
        from app.infrastructure.crypto.multibase import decode_base58_btc

        key = self._keys.get_by_verification_method(verification_method)
        if key is None:
            provider = self._require_legacy_provider()
            return provider.get_verification_key(verification_method)
        if key.public_key_multibase is None:
            raise ProviderMetadataError(
                "Managed key public metadata is incomplete."
            )
        encoded = decode_base58_btc(key.public_key_multibase)
        if not encoded.startswith(ED25519_MULTICODEC_PREFIX):
            raise ProviderMetadataError(
                "Managed key multicodec is unsupported."
            )
        return VerificationKey(
            verification_method=verification_method,
            controller=key.holder_did,
            key_type="Multikey",
            public_key_bytes=encoded[len(ED25519_MULTICODEC_PREFIX) :],
        )

    def _managed_by_reference(
        self,
        key_reference: str,
    ) -> ManagedKey | None:
        for provider_name in self._providers:
            key = self._keys.get_by_provider_reference(
                provider=provider_name,
                provider_key_reference=key_reference,
            )
            if key is not None:
                return key
        return None

    def _legacy_sign(
        self,
        message: bytes,
        *,
        key_reference: str,
    ) -> bytes:
        if not self._allow_legacy_fallback or self._legacy_signer is None:
            raise ManagedKeyNotFoundError(
                "The managed signing key was not found."
            )
        return self._legacy_signer.sign(
            message,
            key_reference=key_reference,
        )

    def _require_legacy_provider(self):
        if not self._allow_legacy_fallback or self._legacy_provider is None:
            raise ManagedKeyNotFoundError(
                "The managed verification key was not found."
            )
        return self._legacy_provider

    def __repr__(self) -> str:
        return (
            "ProviderAwareHolderSigner("
            f"providers={tuple(self._providers)}, "
            "private_material=<provider-boundary>)"
        )


def _with_provider_metadata(
    key: ManagedKey,
    metadata: ProviderKeyMetadata,
    *,
    now: datetime,
) -> ManagedKey:
    return replace(
        key,
        holder_did=metadata.holder_did,
        provider_key_reference=metadata.provider_key_reference,
        public_key_multibase=metadata.public_key_multibase,
        fingerprint=metadata.fingerprint,
        verification_method=metadata.verification_method,
        last_provider_sync_at=now,
    )


def _provider_reference(key: ManagedKey) -> str:
    if key.provider_key_reference is None:
        raise ProviderMetadataError(
            "Managed key provider reference is unavailable."
        )
    return key.provider_key_reference


def _audit_id(
    event_type: AuditEventType,
    key_id: str,
    actor_id: str,
    discriminator: str,
) -> str:
    payload = (
        f"{event_type.value}\0{key_id}\0{actor_id}\0{discriminator}"
    ).encode("utf-8")
    return sha256(payload).hexdigest()[:24]


def _reason_code(value: str) -> str:
    normalized = "".join(
        character if character.isalnum() else "_"
        for character in value.strip().upper()
    )
    return normalized[:64] or "UNSPECIFIED"
