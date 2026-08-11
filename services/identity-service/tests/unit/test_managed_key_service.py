import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.application.services.audit_outbox_service import (
    AuditOutboxDeliveryService,
)
from app.application.services.internal_metrics import InternalMetrics
from app.application.services.managed_key_service import (
    ManagedKeyReconciliationBackgroundService,
    ManagedKeyService,
    ProviderAwareHolderSigner,
)
from app.config.audit_outbox_settings import AuditOutboxSettings
from app.config.key_management_settings import (
    ConfiguredKeyPolicy,
    KeyManagementSettings,
)
from app.domain.holder_wallet import (
    HolderWallet,
    WalletStatus,
)
from app.domain.managed_key import (
    InvalidKeyTransitionError,
    KeyAlgorithm,
    KeyPurpose,
    ManagedKeyConflictError,
    ManagedKeyNotFoundError,
    ManagedKeySigningRejectedError,
    ManagedKeyState,
    ProviderTimeoutError,
)
from app.domain.persistence import AuditEventType
from app.domain.persistence import PersistenceUnavailableError
from app.infrastructure.key_management.development_provider import (
    DevelopmentExternalKeyProvider,
    DevelopmentProviderFailure,
)
from app.infrastructure.persistence.audit_outbox_repository import (
    MongoAuditOutboxRepository,
)
from app.infrastructure.persistence.holder_wallet_repositories import (
    MongoHolderWalletRepository,
)
from app.infrastructure.persistence.managed_key_repository import (
    MongoManagedKeyRepository,
)
from app.infrastructure.persistence.repositories import (
    MongoAuditEventRepository,
)
from tests.support.fake_mongo import FakeCollection
from pymongo.errors import PyMongoError


NOW = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
OWNER = "usr_local_holder"
WALLET_ID = "wallet_abcdefghijklmnop"


class MutableClock:
    def __init__(self) -> None:
        self.value = NOW

    def __call__(self) -> datetime:
        return self.value


class Sequence:
    def __init__(self) -> None:
        self.value = 0

    def storage_id(self) -> str:
        self.value += 1
        return f"{self.value:024x}"

    def key_id(self) -> str:
        self.value += 1
        return f"key_{self.value:016d}"


class Runtime:
    def __init__(self, *, retry_limit: int = 3) -> None:
        self.clock = MutableClock()
        self.sequence = Sequence()
        self.wallet_collection = FakeCollection(
            unique_fields=("walletId", "holderDid", "keyReference"),
        )
        self.key_collection = FakeCollection(
            unique_fields=("keyId",),
            unique_compounds=(
                ("provider", "providerKeyReference"),
                ("verificationMethod",),
                ("walletId", "purpose", "keyVersion"),
                ("walletId", "purpose", "idempotencyKeyHash"),
            ),
        )
        self.credential_collection = FakeCollection()
        self.audit_outbox_collection = FakeCollection()
        self.audit_event_collection = FakeCollection()
        self.wallets = MongoHolderWalletRepository(
            cast(Any, self.wallet_collection)
        )
        self.keys = MongoManagedKeyRepository(
            cast(Any, self.key_collection)
        )
        self.audit = MongoAuditEventRepository(
            cast(Any, self.audit_event_collection)
        )
        delivery = AuditOutboxDeliveryService(
            outbox_repository=MongoAuditOutboxRepository(
                cast(Any, self.audit_outbox_collection),
                cast(Any, self.credential_collection),
            ),
            audit_repository=self.audit,
            settings=AuditOutboxSettings(),
            clock=self.clock,
        )
        self.provider = DevelopmentExternalKeyProvider()
        self.metrics = InternalMetrics()
        self.service = ManagedKeyService(
            repository=self.keys,
            wallet_repository=self.wallets,
            providers={"development": self.provider},
            policy=ConfiguredKeyPolicy(KeyManagementSettings()),
            audit_delivery_service=delivery,
            clock=self.clock,
            storage_id_generator=self.sequence.storage_id,
            key_id_generator=self.sequence.key_id,
            default_provider="development",
            metrics=self.metrics,
            reconciliation_retry_limit=retry_limit,
        )
        self.wallets.add(
            HolderWallet(
                id="74b64c0f0123456789abcdef",
                wallet_id=WALLET_ID,
                owner_user_id=OWNER,
                holder_did="did:key:zLegacyDevelopmentHolder",
                status=WalletStatus.ACTIVE,
                key_reference="local-dev:wallet:abcdefghijklmnop",
                created_at=NOW,
                updated_at=NOW,
            )
        )

    def create(self, *, request: str = "create-request-0001"):
        return self.service.create_for_wallet(
            wallet_id=WALLET_ID,
            owner_user_id=OWNER,
            purpose=KeyPurpose.PRESENTATION_SIGNING,
            algorithm=KeyAlgorithm.ED25519,
            provider_name=None,
            idempotency_key=request,
            correlation_id=request,
        )

    def signer(self) -> ProviderAwareHolderSigner:
        return ProviderAwareHolderSigner(
            repository=self.keys,
            providers={"development": self.provider},
            metrics=self.metrics,
        )


def test_provisioning_activates_binds_audits_and_is_idempotent() -> None:
    runtime = Runtime()
    key = runtime.create()
    repeated = runtime.create()
    wallet = runtime.wallets.get(WALLET_ID)

    assert repeated == key
    assert key.state is ManagedKeyState.ACTIVE
    assert key.provider_key_reference
    assert wallet is not None
    assert wallet.holder_did == key.holder_did
    assert wallet.key_reference == key.provider_key_reference
    snapshot = runtime.metrics.snapshot()
    assert snapshot.active_keys_by_provider_purpose == {
        "development:PRESENTATION_SIGNING": 1
    }
    assert snapshot.managed_keys_by_state["ACTIVE"] == 1
    event_types = {
        event.event_type for event in runtime.audit.list_recent(limit=100)
    }
    assert {
        AuditEventType.MANAGED_KEY_REQUESTED,
        AuditEventType.PROVIDER_KEY_CREATED,
        AuditEventType.MANAGED_KEY_ACTIVATED,
    }.issubset(event_types)
    for event in runtime.audit.list_recent(limit=100):
        assert key.provider_key_reference not in event.metadata.values()
    snapshot = runtime.metrics.snapshot()
    assert snapshot.managed_key_creation_attempts == 1
    assert snapshot.managed_key_creation_succeeded == 1


def test_rotation_changes_did_and_signer_while_old_signature_verifies() -> None:
    runtime = Runtime()
    source = runtime.create()
    signer = runtime.signer()
    message = b"proof payload before rotation"
    old_signature = signer.sign(
        message,
        key_reference=source.provider_key_reference or "",
    )
    old_verification = signer.get_verification_key(
        source.verification_method or ""
    )

    successor = runtime.service.rotate(
        WALLET_ID,
        source.key_id,
        owner_user_id=OWNER,
        idempotency_key="rotation-request-0001",
        correlation_id="rotation-request-0001",
    )
    wallet = runtime.wallets.get(WALLET_ID)
    retired = runtime.keys.get(source.key_id)
    new_signature = signer.sign(
        message,
        key_reference=successor.provider_key_reference or "",
    )
    new_verification = signer.get_verification_key(
        successor.verification_method or ""
    )

    Ed25519PublicKey.from_public_bytes(
        old_verification.public_key_bytes
    ).verify(old_signature, message)
    Ed25519PublicKey.from_public_bytes(
        new_verification.public_key_bytes
    ).verify(new_signature, message)
    assert retired is not None
    assert retired.state is ManagedKeyState.SUSPENDED
    assert retired.successor_key_id == successor.key_id
    assert successor.predecessor_key_id == source.key_id
    assert successor.key_version == 2
    assert successor.holder_did != source.holder_did
    assert wallet is not None
    assert wallet.holder_did == successor.holder_did
    assert wallet.key_reference == successor.provider_key_reference
    with pytest.raises(ManagedKeySigningRejectedError):
        signer.sign(
            message,
            key_reference=source.provider_key_reference or "",
        )


def test_rotation_is_idempotent_and_concurrent_second_rotation_fails() -> None:
    runtime = Runtime()
    source = runtime.create()
    successor = runtime.service.rotate(
        WALLET_ID,
        source.key_id,
        owner_user_id=OWNER,
        idempotency_key="rotation-request-0001",
        correlation_id="rotation-request-0001",
    )

    assert (
        runtime.service.rotate(
            WALLET_ID,
            source.key_id,
            owner_user_id=OWNER,
            idempotency_key="rotation-request-0001",
            correlation_id="rotation-repeat-0001",
        )
        == successor
    )
    with pytest.raises(ManagedKeyConflictError):
        runtime.service.rotate(
            WALLET_ID,
            source.key_id,
            owner_user_id=OWNER,
            idempotency_key="rotation-request-0002",
            correlation_id="rotation-request-0002",
        )


def test_suspend_resume_compromise_and_revoke_enforce_signing_state() -> None:
    runtime = Runtime()
    key = runtime.create()
    signer = runtime.signer()

    suspended = runtime.service.suspend(
        WALLET_ID,
        key.key_id,
        owner_user_id=OWNER,
        correlation_id="suspend-0001",
    )
    with pytest.raises(ManagedKeySigningRejectedError):
        signer.sign(
            b"payload",
            key_reference=suspended.provider_key_reference or "",
        )
    resumed = runtime.service.resume(
        WALLET_ID,
        key.key_id,
        owner_user_id=OWNER,
        correlation_id="resume-0001",
    )
    assert resumed.state is ManagedKeyState.ACTIVE
    compromised = runtime.service.mark_compromised(
        WALLET_ID,
        key.key_id,
        actor_id="usr_local_admin",
        reason="confirmed operator compromise",
        correlation_id="compromise-0001",
        administrative=True,
    )
    assert compromised.state is ManagedKeyState.COMPROMISED
    with pytest.raises(ManagedKeySigningRejectedError):
        signer.sign(
            b"payload",
            key_reference=compromised.provider_key_reference or "",
        )
    revoked = runtime.service.revoke(
        WALLET_ID,
        key.key_id,
        owner_user_id=OWNER,
        reason="holder requested permanent revocation",
        correlation_id="revoke-0001",
    )
    assert revoked.state is ManagedKeyState.REVOKED
    with pytest.raises(InvalidKeyTransitionError):
        runtime.service.resume(
            WALLET_ID,
            key.key_id,
            owner_user_id=OWNER,
            correlation_id="invalid-resume-0001",
        )


def test_destruction_delay_cancel_and_provider_confirmation() -> None:
    runtime = Runtime()
    key = runtime.create()
    revoked = runtime.service.revoke(
        WALLET_ID,
        key.key_id,
        owner_user_id=OWNER,
        reason="retired key no longer required",
        correlation_id="revoke-0001",
    )
    pending = runtime.service.schedule_destruction(
        WALLET_ID,
        revoked.key_id,
        actor_id="usr_local_admin",
        reason="approved retention period completed",
        confirmation=revoked.key_id,
        correlation_id="destroy-schedule-0001",
        administrative=True,
    )
    cancelled = runtime.service.cancel_destruction(
        WALLET_ID,
        pending.key_id,
        actor_id="usr_local_admin",
        reason="legal hold was applied",
        correlation_id="destroy-cancel-0001",
        administrative=True,
    )
    assert cancelled.state is ManagedKeyState.REVOKED
    pending = runtime.service.schedule_destruction(
        WALLET_ID,
        cancelled.key_id,
        actor_id="usr_local_admin",
        reason="approved retention period completed",
        confirmation=cancelled.key_id,
        correlation_id="destroy-schedule-0002",
        administrative=True,
    )
    runtime.clock.value = NOW + timedelta(hours=25)
    destroyed = runtime.service.reconcile_authorized(
        WALLET_ID,
        pending.key_id,
        actor_id="usr_local_admin",
        correlation_id="destroy-confirm-0001",
        administrative=True,
    )

    assert destroyed.state is ManagedKeyState.DESTROYED
    assert runtime.provider.get_key_metadata(
        destroyed.provider_key_reference or ""
    ).destroyed
    snapshot = runtime.metrics.snapshot()
    assert snapshot.key_destruction_scheduled == 2
    assert snapshot.key_destruction_completed == 1


def test_provider_timeout_leaves_recoverable_pending_key() -> None:
    runtime = Runtime()
    runtime.provider.inject_failure(DevelopmentProviderFailure.TIMEOUT)

    with pytest.raises(ProviderTimeoutError):
        runtime.create()
    pending = runtime.keys.list_for_wallet(
        WALLET_ID,
        after_key_id=None,
    )[0]
    assert pending.state is ManagedKeyState.PENDING
    runtime.provider.inject_failure(DevelopmentProviderFailure.NONE)
    runtime.clock.value = NOW + timedelta(seconds=61)

    assert runtime.service.reconcile_batch(
        stale_seconds=60,
        batch_size=10,
    ) == (1, 0)
    active = runtime.keys.get(pending.key_id)
    wallet = runtime.wallets.get(WALLET_ID)
    assert active is not None
    assert active.state is ManagedKeyState.ACTIVE
    assert wallet is not None
    assert wallet.key_reference == active.provider_key_reference


def test_reconciliation_retry_limit_dead_letters_failed_operation() -> None:
    runtime = Runtime(retry_limit=2)
    runtime.provider.inject_failure(DevelopmentProviderFailure.TIMEOUT)
    with pytest.raises(ProviderTimeoutError):
        runtime.create()
    key = runtime.keys.list_for_wallet(
        WALLET_ID,
        after_key_id=None,
    )[0]
    runtime.clock.value = NOW + timedelta(seconds=61)

    for _ in range(2):
        current = runtime.keys.get(key.key_id)
        assert current is not None
        with pytest.raises(ProviderTimeoutError):
            runtime.service.reconcile(current)
        runtime.clock.value += timedelta(seconds=31)
    failed = runtime.keys.get(key.key_id)
    assert failed is not None
    assert failed.state is ManagedKeyState.FAILED
    assert failed.failure_code == "RETRY_LIMIT_REACHED"


def test_foreign_owner_is_hidden_and_did_web_rotation_is_not_faked() -> None:
    runtime = Runtime()
    key = runtime.create()
    with pytest.raises(ManagedKeyNotFoundError):
        runtime.service.get_owned(
            WALLET_ID,
            key.key_id,
            owner_user_id="usr_foreign",
            correlation_id="foreign-access-0001",
        )
    assert AuditEventType.UNAUTHORIZED_KEY_ACCESS in {
        event.event_type for event in runtime.audit.list_recent(limit=100)
    }

    did_web_key = replace(
        key,
        holder_did="did:web:holder.example.test",
        verification_method=(
            "did:web:holder.example.test#managed-presentation-key"
        ),
    )
    runtime.keys.update(
        replace(
            did_web_key,
            version=key.version + 1,
            updated_at=NOW + timedelta(seconds=1),
        ),
        expected_version=key.version,
    )
    wallet = runtime.wallets.get(WALLET_ID)
    assert wallet is not None
    runtime.wallets.update_key_binding(
        WALLET_ID,
        holder_did=did_web_key.holder_did,
        key_reference=did_web_key.provider_key_reference or "",
        updated_at=NOW + timedelta(seconds=1),
        expected_version=wallet.version,
    )

    with pytest.raises(ManagedKeyConflictError):
        runtime.service.rotate(
            WALLET_ID,
            key.key_id,
            owner_user_id=OWNER,
            idempotency_key="did-web-rotation-0001",
            correlation_id="did-web-rotation-0001",
        )


def test_provider_success_then_persistence_failure_is_reconciled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime()
    original = runtime.key_collection.replace_one
    failures = 1

    def fail_once(*args: object, **kwargs: object):
        nonlocal failures
        if failures:
            failures -= 1
            raise PyMongoError("injected persistence outage")
        return original(*args, **kwargs)

    monkeypatch.setattr(runtime.key_collection, "replace_one", fail_once)
    with pytest.raises(PersistenceUnavailableError):
        runtime.create()
    pending = runtime.keys.list_for_wallet(
        WALLET_ID,
        after_key_id=None,
    )[0]
    assert pending.state is ManagedKeyState.PENDING

    recovered = runtime.service.reconcile(pending)
    wallet = runtime.wallets.get(WALLET_ID)
    assert recovered.state is ManagedKeyState.ACTIVE
    assert wallet is not None
    assert wallet.key_reference == recovered.provider_key_reference


def test_stale_partial_rotation_reconciliation_repairs_wallet_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime()
    source = runtime.create()
    original = runtime.wallet_collection.update_one
    failures = 1

    def fail_once(*args: object, **kwargs: object):
        nonlocal failures
        if failures:
            failures -= 1
            raise PyMongoError("injected wallet binding outage")
        return original(*args, **kwargs)

    monkeypatch.setattr(runtime.wallet_collection, "update_one", fail_once)
    with pytest.raises(PersistenceUnavailableError):
        runtime.service.rotate(
            WALLET_ID,
            source.key_id,
            owner_user_id=OWNER,
            idempotency_key="partial-rotation-0001",
            correlation_id="partial-rotation-0001",
        )
    rotating = runtime.keys.get(source.key_id)
    assert rotating is not None
    assert rotating.state is ManagedKeyState.ROTATING
    assert rotating.successor_key_id is not None

    repaired = runtime.service.reconcile(rotating)
    successor = runtime.keys.get(rotating.successor_key_id)
    wallet = runtime.wallets.get(WALLET_ID)
    assert repaired.state is ManagedKeyState.SUSPENDED
    assert successor is not None
    assert wallet is not None
    assert wallet.key_reference == successor.provider_key_reference


def test_reconciliation_worker_starts_runs_and_stops_gracefully() -> None:
    calls: list[tuple[int, int]] = []

    class StubService:
        def reconcile_batch(
            self,
            *,
            stale_seconds: int,
            batch_size: int,
        ) -> tuple[int, int]:
            calls.append((stale_seconds, batch_size))
            return (0, 0)

    async def exercise() -> None:
        stop_event = asyncio.Event()
        background = ManagedKeyReconciliationBackgroundService(
            cast(Any, StubService()),
            settings=KeyManagementSettings(
                reconciliation_interval_ms=100,
                stale_operation_seconds=60,
                reconciliation_batch_size=7,
            ),
        )

        async def stop_soon() -> None:
            await asyncio.sleep(0.02)
            stop_event.set()

        await asyncio.gather(
            background.run(stop_event),
            stop_soon(),
        )

    asyncio.run(exercise())
    assert calls == [(60, 7)]


def test_reconciliation_worker_survives_repository_outage() -> None:
    calls = 0

    async def exercise() -> None:
        nonlocal calls
        stop_event = asyncio.Event()

        class FlakyService:
            def reconcile_batch(
                self,
                *,
                stale_seconds: int,
                batch_size: int,
            ) -> tuple[int, int]:
                nonlocal calls
                del stale_seconds, batch_size
                calls += 1
                if calls == 1:
                    raise PersistenceUnavailableError(
                        "temporary repository outage"
                    )
                stop_event.set()
                return (0, 0)

        background = ManagedKeyReconciliationBackgroundService(
            cast(Any, FlakyService()),
            settings=KeyManagementSettings(
                reconciliation_interval_ms=100,
            ),
        )
        await background.run(stop_event)

    asyncio.run(exercise())

    assert calls == 2
