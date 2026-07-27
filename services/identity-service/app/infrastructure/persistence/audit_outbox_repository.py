from datetime import datetime
from typing import Any

from pymongo import ASCENDING
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.domain.audit_outbox import (
    AuditOutboxRecord,
    AuditOutboxSource,
    AuditOutboxStatus,
)
from app.domain.persistence import PersistenceUnavailableError
from app.infrastructure.persistence.mappers import to_object_id
from app.infrastructure.persistence.status_list_mappers import (
    AuditOutboxDocumentMapper,
)


class MongoAuditOutboxRepository:
    def __init__(
        self,
        collection: Collection[dict[str, Any]],
        credential_collection: Collection[dict[str, Any]],
    ) -> None:
        self._collection = collection
        self._credentials = credential_collection

    def enqueue(self, record: AuditOutboxRecord) -> AuditOutboxRecord:
        if record.source is not AuditOutboxSource.COLLECTION:
            raise ValueError(
                "Embedded credential outbox records are committed by "
                "revocation."
            )
        try:
            self._collection.insert_one(
                AuditOutboxDocumentMapper.to_document(record)
            )
        except DuplicateKeyError:
            existing = self.get(record.event.id)
            if existing != record:
                raise PersistenceUnavailableError(
                    "Audit outbox idempotency conflict."
                ) from None
            return existing
        except PyMongoError as error:
            raise _unavailable("audit outbox insertion") from error
        return record

    def get(self, event_id: str) -> AuditOutboxRecord | None:
        object_id = to_object_id(event_id)
        try:
            document = self._collection.find_one({"_id": object_id})
            if document is not None:
                return AuditOutboxDocumentMapper.from_document(document)
            credential = self._credentials.find_one(
                {"auditOutbox._id": object_id}
            )
        except PyMongoError as error:
            raise _unavailable("audit outbox lookup") from error
        if credential is None:
            return None
        embedded = credential.get("auditOutbox")
        if not isinstance(embedded, dict):
            raise PersistenceUnavailableError(
                "Embedded audit outbox record is invalid."
            )
        return AuditOutboxDocumentMapper.from_document(embedded)

    def list_ready(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> tuple[AuditOutboxRecord, ...]:
        if limit < 1:
            raise ValueError("Audit outbox batch limit must be positive.")
        ready_filter = _ready_filter(now=now)
        try:
            collection_records = [
                AuditOutboxDocumentMapper.from_document(document)
                for document in (
                    self._collection.find(ready_filter)
                    .sort("availableAt", ASCENDING)
                    .limit(limit)
                )
            ]
            remaining = max(0, limit - len(collection_records))
            credential_records = (
                [
                    AuditOutboxDocumentMapper.from_document(
                        document["auditOutbox"]
                    )
                    for document in (
                        self._credentials.find(
                            _prefixed_filter(
                                ready_filter,
                                prefix="auditOutbox.",
                            )
                        )
                        .sort("auditOutbox.availableAt", ASCENDING)
                        .limit(remaining)
                    )
                ]
                if remaining
                else []
            )
        except (KeyError, TypeError, ValueError) as error:
            raise PersistenceUnavailableError(
                "Stored audit outbox record is invalid."
            ) from error
        except PyMongoError as error:
            raise _unavailable("audit outbox listing") from error
        return tuple(
            sorted(
                [*collection_records, *credential_records],
                key=lambda record: (
                    record.available_at,
                    record.event.id,
                ),
            )
        )

    def claim(
        self,
        event_id: str,
        *,
        source: AuditOutboxSource,
        claimed_at: datetime,
        lease_until: datetime,
        expected_version: int,
    ) -> AuditOutboxRecord | None:
        filters = {
            "_id": to_object_id(event_id),
            "version": expected_version,
            "$or": [
                {
                    "status": AuditOutboxStatus.PENDING.value,
                    "availableAt": {"$lte": claimed_at},
                },
                {
                    "status": AuditOutboxStatus.PROCESSING.value,
                    "leaseUntil": {"$lte": claimed_at},
                },
            ],
        }
        update = {
            "$set": {
                "status": AuditOutboxStatus.PROCESSING.value,
                "leaseUntil": lease_until,
                "deliveredAt": None,
                "lastError": None,
                "updatedAt": claimed_at,
            },
            "$inc": {"attempts": 1, "version": 1},
        }
        matched = self._update(
            source=source,
            filters=filters,
            update=update,
            operation="audit outbox claim",
        )
        return None if not matched else self.get(event_id)

    def mark_delivered(
        self,
        event_id: str,
        *,
        source: AuditOutboxSource,
        delivered_at: datetime,
        expected_version: int,
    ) -> AuditOutboxRecord:
        matched = self._update(
            source=source,
            filters={
                "_id": to_object_id(event_id),
                "version": expected_version,
                "status": AuditOutboxStatus.PROCESSING.value,
            },
            update={
                "$set": {
                    "status": AuditOutboxStatus.DELIVERED.value,
                    "leaseUntil": None,
                    "deliveredAt": delivered_at,
                    "lastError": None,
                    "updatedAt": delivered_at,
                },
                "$inc": {"version": 1},
            },
            operation="audit outbox delivery acknowledgement",
        )
        if not matched:
            raise PersistenceUnavailableError(
                "Audit outbox delivery acknowledgement was stale."
            )
        record = self.get(event_id)
        if record is None:
            raise _unavailable("audit outbox delivery readback")
        return record

    def reschedule(
        self,
        event_id: str,
        *,
        source: AuditOutboxSource,
        available_at: datetime,
        failed_at: datetime,
        error_code: str,
        expected_version: int,
    ) -> AuditOutboxRecord:
        matched = self._update(
            source=source,
            filters={
                "_id": to_object_id(event_id),
                "version": expected_version,
                "status": AuditOutboxStatus.PROCESSING.value,
            },
            update={
                "$set": {
                    "status": AuditOutboxStatus.PENDING.value,
                    "availableAt": available_at,
                    "leaseUntil": None,
                    "deliveredAt": None,
                    "lastError": error_code,
                    "updatedAt": failed_at,
                },
                "$inc": {"version": 1},
            },
            operation="audit outbox retry scheduling",
        )
        if not matched:
            raise PersistenceUnavailableError(
                "Audit outbox retry scheduling was stale."
            )
        record = self.get(event_id)
        if record is None:
            raise _unavailable("audit outbox retry readback")
        return record

    def _update(
        self,
        *,
        source: AuditOutboxSource,
        filters: dict[str, Any],
        update: dict[str, Any],
        operation: str,
    ) -> bool:
        try:
            if source is AuditOutboxSource.COLLECTION:
                result = self._collection.update_one(filters, update)
            else:
                result = self._credentials.update_one(
                    _prefixed_filter(filters, prefix="auditOutbox."),
                    _prefixed_update(update, prefix="auditOutbox."),
                )
        except PyMongoError as error:
            raise _unavailable(operation) from error
        return result.matched_count == 1


def _ready_filter(*, now: datetime) -> dict[str, Any]:
    return {
        "$or": [
            {
                "status": AuditOutboxStatus.PENDING.value,
                "availableAt": {"$lte": now},
            },
            {
                "status": AuditOutboxStatus.PROCESSING.value,
                "leaseUntil": {"$lte": now},
            },
        ]
    }


def _prefixed_filter(
    filters: dict[str, Any],
    *,
    prefix: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in filters.items():
        if key == "$or":
            result[key] = [
                _prefixed_filter(item, prefix=prefix)
                for item in value
            ]
        else:
            result[f"{prefix}{key}"] = value
    return result


def _prefixed_update(
    update: dict[str, Any],
    *,
    prefix: str,
) -> dict[str, Any]:
    return {
        operator: {
            f"{prefix}{key}": value
            for key, value in values.items()
        }
        for operator, values in update.items()
    }


def _unavailable(operation: str) -> PersistenceUnavailableError:
    return PersistenceUnavailableError(
        f"MongoDB {operation} could not be completed."
    )
