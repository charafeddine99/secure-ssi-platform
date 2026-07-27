import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.dependencies import (
    build_audit_outbox_delivery_service,
    build_presentation_reconciliation_service,
    get_audit_outbox_settings,
    get_clock,
    get_mongo_connection_manager,
    get_mongo_settings,
    get_holder_wallet_settings,
)
from app.application.services.audit_outbox_service import (
    AuditOutboxBackgroundService,
)
from app.application.services.presentation_service import (
    PresentationReconciliationBackgroundService,
)
from app.infrastructure.persistence.indexes import ensure_mongo_indexes


@asynccontextmanager
async def application_lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_mongo_settings()
    manager = get_mongo_connection_manager()
    outbox_settings = get_audit_outbox_settings()
    wallet_settings = get_holder_wallet_settings()
    stop_event: asyncio.Event | None = None
    delivery_task: asyncio.Task[None] | None = None
    reconciliation_task: asyncio.Task[None] | None = None
    app.state.persistence_enabled = settings.enabled
    if settings.enabled:
        try:
            manager.connect()
            ensure_mongo_indexes(manager.database)
            if (
                outbox_settings.enabled
                or wallet_settings.reconciliation_enabled
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
        except Exception:
            manager.close()
            raise
    try:
        yield
    finally:
        if stop_event is not None:
            stop_event.set()
        if delivery_task is not None:
            await delivery_task
        if reconciliation_task is not None:
            await reconciliation_task
        manager.close()
