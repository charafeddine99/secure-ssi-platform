import asyncio
import logging
from collections.abc import Callable
from datetime import datetime

from app.application.ports.repositories import AuditEventRepository
from app.application.ports.status_list_repositories import (
    AuditOutboxRepository,
)
from app.application.services.internal_metrics import InternalMetrics
from app.config.audit_outbox_settings import AuditOutboxSettings
from app.domain.audit_outbox import (
    AuditOutboxRecord,
    AuditOutboxStatus,
)
from app.domain.persistence import (
    DuplicateEntityError,
    PersistenceUnavailableError,
    RepositoryError,
)


Clock = Callable[[], datetime]
_LOGGER = logging.getLogger(__name__)
_PUBLICATION_ERROR = "AUDIT_PUBLICATION_FAILED"


class AuditOutboxDeliveryService:
    def __init__(
        self,
        *,
        outbox_repository: AuditOutboxRepository,
        audit_repository: AuditEventRepository,
        settings: AuditOutboxSettings,
        clock: Clock,
        metrics: InternalMetrics | None = None,
    ) -> None:
        self._outbox = outbox_repository
        self._audit = audit_repository
        self._settings = settings
        self._clock = clock
        self._metrics = metrics

    def enqueue(self, record: AuditOutboxRecord) -> AuditOutboxRecord:
        return self._outbox.enqueue(record)

    def ensure(self, record: AuditOutboxRecord) -> AuditOutboxRecord:
        existing = self._outbox.get(record.event.id)
        if existing is None:
            return self.enqueue(record)
        if existing.event != record.event:
            raise PersistenceUnavailableError(
                "Audit outbox idempotency conflict."
            )
        return existing

    def deliver_event(self, event_id: str) -> bool:
        record = self._outbox.get(event_id)
        if record is None:
            return False
        if record.status is AuditOutboxStatus.DELIVERED:
            return True
        claimed_at = self._clock()
        claimed = self._outbox.claim(
            event_id,
            source=record.source,
            claimed_at=claimed_at,
            lease_until=self._settings.retry_policy.lease_until(
                claimed_at=claimed_at
            ),
            expected_version=record.version,
        )
        if claimed is None:
            current = self._outbox.get(event_id)
            return (
                current is not None
                and current.status is AuditOutboxStatus.DELIVERED
            )
        try:
            self._publish_idempotently(claimed)
            delivered_at = self._clock()
            self._outbox.mark_delivered(
                event_id,
                source=claimed.source,
                delivered_at=delivered_at,
                expected_version=claimed.version,
            )
            return True
        except RepositoryError:
            failed_at = self._clock()
            self._outbox.reschedule(
                event_id,
                source=claimed.source,
                available_at=(
                    self._settings.retry_policy.next_available_at(
                        failed_at=failed_at,
                        attempts=claimed.attempts,
                    )
                ),
                failed_at=failed_at,
                error_code=_PUBLICATION_ERROR,
                expected_version=claimed.version,
            )
            return False

    def deliver_pending(self) -> int:
        started_at = self._clock()
        ready = self._outbox.list_ready(
            now=started_at,
            limit=self._settings.batch_size,
        )
        delivered = 0
        for record in ready:
            if self.deliver_event(record.event.id):
                delivered += 1
        if self._metrics is not None:
            lag = max(
                (
                    max(
                        0.0,
                        (started_at - record.created_at).total_seconds(),
                    )
                    for record in ready
                ),
                default=0.0,
            )
            self._metrics.record_audit_cycle(
                occurred_at=self._clock(),
                delivered=delivered,
                retried=len(ready) - delivered,
                outbox_lag_seconds=lag,
            )
        return delivered

    def _publish_idempotently(
        self,
        record: AuditOutboxRecord,
    ) -> None:
        existing = self._audit.get_by_id(record.event.id)
        if existing is not None:
            if existing != record.event:
                raise PersistenceUnavailableError(
                    "Audit event idempotency conflict."
                )
            return
        try:
            self._audit.append(record.event)
        except DuplicateEntityError:
            existing = self._audit.get_by_id(record.event.id)
            if existing != record.event:
                raise PersistenceUnavailableError(
                    "Audit event idempotency conflict."
                ) from None


class AuditOutboxBackgroundService:
    def __init__(
        self,
        delivery_service: AuditOutboxDeliveryService,
        *,
        settings: AuditOutboxSettings,
    ) -> None:
        self._delivery = delivery_service
        self._settings = settings

    async def run(self, stop_event: asyncio.Event) -> None:
        interval = self._settings.poll_interval_ms / 1_000
        while not stop_event.is_set():
            try:
                await asyncio.to_thread(self._delivery.deliver_pending)
            except RepositoryError:
                _LOGGER.exception("Audit outbox delivery cycle failed.")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
            except TimeoutError:
                continue
