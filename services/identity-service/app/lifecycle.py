import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.dependencies import (
    build_audit_outbox_delivery_service,
    build_revocation_reconciliation,
    prepare_revocation_ledger,
    build_presentation_reconciliation_service,
    get_audit_outbox_settings,
    get_auth_settings,
    get_clock,
    get_mongo_connection_manager,
    get_mongo_settings,
    get_holder_wallet_settings,
    get_key_management_settings,
    build_managed_key_service,
)
from app.application.services.audit_outbox_service import (
    AuditOutboxBackgroundService,
)
from app.application.services.presentation_service import (
    PresentationReconciliationBackgroundService,
)
from app.application.services.managed_key_service import (
    ManagedKeyReconciliationBackgroundService,
)
from app.api.v1.platform_backups import (
    build_platform_backup_service,
    get_platform_backup_settings,
)
from app.application.services.security_event_forwarder import build_forwarder
from app.application.services.platform_backup_scheduler import (
    PLATFORM_BACKUP_LEASES_COLLECTION,
    PlatformBackupBackgroundService,
    PlatformBackupScheduler,
)
from app.config.environment_policy import is_production_like
from app.domain.persistence import PersistenceUnavailableError
from app.infrastructure.persistence.indexes import ensure_mongo_indexes
from app.infrastructure.persistence.demo_seeder import seed_offline_demo_fixtures
from app.infrastructure.persistence.local_user_seed import seed_on_startup

_logger = logging.getLogger(__name__)


def settings_environment() -> str:
    return get_key_management_settings().environment


@asynccontextmanager
async def application_lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_mongo_settings()
    manager = get_mongo_connection_manager()
    outbox_settings = get_audit_outbox_settings()
    wallet_settings = get_holder_wallet_settings()
    key_settings = get_key_management_settings()
    # Fail at startup, not on the first verifier request, if a production-like
    # environment has no request-signing key.
    from app.config.request_object_settings import request_object_signer

    request_object_signer()
    stop_event: asyncio.Event | None = None
    delivery_task: asyncio.Task[None] | None = None
    reconciliation_task: asyncio.Task[None] | None = None
    key_reconciliation_task: asyncio.Task[None] | None = None
    backup_task: asyncio.Task[None] | None = None
    forwarder_task: asyncio.Task[None] | None = None
    app.state.persistence_enabled = settings.enabled
    if settings.enabled:
        try:
            manager.connect()
            ensure_mongo_indexes(manager.database)
            prepare_revocation_ledger(manager)
            # Before serving: old records may never outvote the ledger. A ledger
            # that cannot prove its history raises here and stops startup in
            # production-like mode; development continues and status stays
            # unavailable, because every status read repeats the same check.
            try:
                reconciled = build_revocation_reconciliation(
                    manager,
                    clock=get_clock(),
                ).reconcile()
                app.state.revocation_reconciliation = reconciled
                _logger.info(
                    "Revocation ledger reconciled: %d backfilled, %d repaired",
                    reconciled.backfilled,
                    reconciled.records_repaired,
                )
            except PersistenceUnavailableError as error:
                _logger.error(
                    "Revocation ledger reconciliation failed: %s",
                    getattr(error, "code", type(error).__name__),
                )
                if is_production_like(settings_environment()):
                    raise
            seeded = seed_on_startup(manager.database, get_auth_settings())
            if seeded:
                _logger.info("Seeded development accounts: %s", ", ".join(seeded))
            if (
                outbox_settings.enabled
                or wallet_settings.reconciliation_enabled
                or key_settings.reconciliation_enabled
            ):
                stop_event = asyncio.Event()
            if outbox_settings.enabled:
                delivery = build_audit_outbox_delivery_service(
                    manager,
                    settings=outbox_settings,
                    clock=get_clock(),
                )
                background = AuditOutboxBackgroundService(
                    delivery,
                    settings=outbox_settings,
                )
                delivery_task = asyncio.create_task(
                    background.run(stop_event),
                    name="audit-outbox-delivery",
                )
            if wallet_settings.reconciliation_enabled:
                reconciliation = (
                    build_presentation_reconciliation_service(
                        manager,
                        settings=wallet_settings,
                        audit_settings=outbox_settings,
                        clock=get_clock(),
                    )
                )
                reconciliation_background = (
                    PresentationReconciliationBackgroundService(
                        reconciliation,
                        settings=wallet_settings,
                    )
                )
                reconciliation_task = asyncio.create_task(
                    reconciliation_background.run(stop_event),
                    name="presentation-reconciliation",
                )
            backup_settings = get_platform_backup_settings()
            if backup_settings.enabled and backup_settings.interval_seconds > 0:
                stop_event = stop_event or asyncio.Event()
                backup_task = asyncio.create_task(
                    PlatformBackupBackgroundService(
                        PlatformBackupScheduler(
                            build_platform_backup_service(
                                manager,
                                settings=backup_settings,
                            ),
                            leases=manager.database[
                                PLATFORM_BACKUP_LEASES_COLLECTION
                            ],
                            interval_seconds=backup_settings.interval_seconds,
                            owner=uuid.uuid4().hex,
                        )
                    ).run(stop_event),
                    name="platform-backup-scheduler",
                )
            forwarder = build_forwarder(manager.database, settings_environment())
            if forwarder is not None:
                if stop_event is None:
                    stop_event = asyncio.Event()
                forwarder_task = asyncio.create_task(
                    forwarder.run(stop_event),
                    name="security-event-forwarder",
                )
            if key_settings.reconciliation_enabled:
                key_service = build_managed_key_service(
                    manager,
                    settings=key_settings,
                    audit_settings=outbox_settings,
                    clock=get_clock(),
                )
                key_background = (
                    ManagedKeyReconciliationBackgroundService(
                        key_service,
                        settings=key_settings,
                    )
                )
                key_reconciliation_task = asyncio.create_task(
                    key_background.run(stop_event),
                    name="managed-key-reconciliation",
                )
        except Exception:
            manager.close()
            raise
    else:
        # Offline / host-dev mode: seed deterministic demo fixtures so the
        # web app sees real-looking data without a MongoDB daemon.
        try:
            seed_offline_demo_fixtures(manager.database)
        except Exception as exc:  # pragma: no cover
            _logger.warning("Offline demo seeder failed (non-fatal): %s", exc)
    try:
        yield
    finally:
        if stop_event is not None:
            stop_event.set()
        if delivery_task is not None:
            await delivery_task
        if reconciliation_task is not None:
            await reconciliation_task
        if key_reconciliation_task is not None:
            await key_reconciliation_task
        if backup_task is not None:
            await backup_task
        if forwarder_task is not None:
            await forwarder_task
        manager.close()
