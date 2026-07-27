from datetime import UTC, datetime, timedelta
from typing import Any, cast

from bson import ObjectId

from app.application.services.audit_outbox_service import (
    AuditOutboxDeliveryService,
)
from app.application.services.internal_metrics import InternalMetrics
from app.config.audit_outbox_settings import AuditOutboxSettings
from app.domain.audit_outbox import (
    AuditOutboxRecord,
    AuditOutboxSource,
    AuditOutboxStatus,
)
from app.domain.persistence import (
    AuditEvent,
    AuditEventType,
    DuplicateEntityError,
    PersistenceUnavailableError,
)
from app.infrastructure.persistence.audit_outbox_repository import (
    MongoAuditOutboxRepository,
)
from app.infrastructure.persistence.status_list_mappers import (
    AuditOutboxDocumentMapper,
)
from tests.support.fake_mongo import FakeCollection


NOW = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)


class MutableClock:
    def __init__(self) -> None:
        self.value = NOW

    def __call__(self) -> datetime:
        return self.value


class FailingAuditRepository:
    def __init__(self) -> None:
        self.events: dict[str, AuditEvent] = {}
        self.failures = 0

    def append(self, event: AuditEvent) -> AuditEvent:
        if self.failures:
            self.failures -= 1
            raise PersistenceUnavailableError("Temporary failure.")
        if event.id in self.events:
            raise DuplicateEntityError("Duplicate audit id.")
        self.events[event.id] = event
        return event

    def get_by_id(self, event_id: str) -> AuditEvent | None:
        return self.events.get(event_id)

    def list_recent(
        self,
        *,
        event_type: AuditEventType | None = None,
        limit: int = 100,
    ) -> tuple[AuditEvent, ...]:
        events = [
            event
            for event in self.events.values()
            if event_type is None or event.event_type is event_type
        ]
        return tuple(events[-limit:])


def _record(
    *,
    source: AuditOutboxSource = AuditOutboxSource.COLLECTION,
) -> AuditOutboxRecord:
    event = AuditEvent(
        id="64b64c0f0123456789abcdef",
        event_type=AuditEventType.STATUS_CHECKED,
        subject_id="urn:uuid:credential-1",
        actor_id=None,
        correlation_id="request-1",
        metadata={"status": "ACTIVE"},
        created_at=NOW,
        updated_at=NOW,
    )
    return AuditOutboxRecord.pending(
        event=event,
        aggregate_type="credential",
        aggregate_id=event.subject_id or "unknown",
        source=source,
    )


def test_failed_audit_delivery_is_preserved_retried_and_not_duplicated() -> None:
    outbox = FakeCollection()
    credentials = FakeCollection()
    repository = MongoAuditOutboxRepository(
        cast(Any, outbox),
        cast(Any, credentials),
    )
    audit = FailingAuditRepository()
    audit.failures = 1
    clock = MutableClock()
    metrics = InternalMetrics()
    delivery = AuditOutboxDeliveryService(
        outbox_repository=repository,
        audit_repository=audit,
        settings=AuditOutboxSettings(
            base_retry_seconds=1,
            max_retry_seconds=4,
        ),
        clock=clock,
        metrics=metrics,
    )
    record = delivery.enqueue(_record())

    assert delivery.deliver_event(record.event.id) is False
    pending = repository.get(record.event.id)
    assert pending is not None
    assert pending.status is AuditOutboxStatus.PENDING
    assert pending.attempts == 1
    assert pending.last_error == "AUDIT_PUBLICATION_FAILED"
    assert audit.events == {}

    clock.value = NOW + timedelta(seconds=1)
    assert delivery.deliver_pending() == 1
    metric_snapshot = metrics.snapshot()
    assert metric_snapshot.audit_worker_cycles == 1
    assert metric_snapshot.audit_events_delivered == 1
    assert metric_snapshot.audit_events_retried == 0
    assert metric_snapshot.outbox_lag_seconds == 1
    delivered = repository.get(record.event.id)
    assert delivered is not None
    assert delivered.status is AuditOutboxStatus.DELIVERED
    assert len(audit.events) == 1
    assert delivery.deliver_event(record.event.id) is True
    assert len(audit.events) == 1


def test_embedded_revocation_outbox_is_claimed_and_acknowledged() -> None:
    outbox = FakeCollection()
    credentials = FakeCollection()
    record = _record(source=AuditOutboxSource.CREDENTIAL)
    credentials.documents.append(
        {
            "_id": ObjectId("74b64c0f0123456789abcdef"),
            "credentialId": record.aggregate_id,
            "auditOutbox": AuditOutboxDocumentMapper.to_document(record),
        }
    )
    repository = MongoAuditOutboxRepository(
        cast(Any, outbox),
        cast(Any, credentials),
    )
    audit = FailingAuditRepository()
    delivery = AuditOutboxDeliveryService(
        outbox_repository=repository,
        audit_repository=audit,
        settings=AuditOutboxSettings(),
        clock=lambda: NOW,
    )

    assert delivery.deliver_event(record.event.id) is True
    stored = repository.get(record.event.id)
    assert stored is not None
    assert stored.source is AuditOutboxSource.CREDENTIAL
    assert stored.status is AuditOutboxStatus.DELIVERED
    assert stored.attempts == 1
    assert len(outbox.documents) == 0
    assert len(audit.events) == 1


def test_existing_destination_event_closes_crash_window_idempotently() -> None:
    outbox = FakeCollection()
    credentials = FakeCollection()
    repository = MongoAuditOutboxRepository(
        cast(Any, outbox),
        cast(Any, credentials),
    )
    record = repository.enqueue(_record())
    audit = FailingAuditRepository()
    audit.events[record.event.id] = record.event
    delivery = AuditOutboxDeliveryService(
        outbox_repository=repository,
        audit_repository=audit,
        settings=AuditOutboxSettings(),
        clock=lambda: NOW,
    )

    assert delivery.deliver_event(record.event.id) is True
    assert len(audit.events) == 1
    stored = repository.get(record.event.id)
    assert stored is not None
    assert stored.status is AuditOutboxStatus.DELIVERED
