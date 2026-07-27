import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from app.domain.persistence import AuditEvent


_SAFE_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,99}$")


class AuditOutboxStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    DELIVERED = "DELIVERED"


class AuditOutboxSource(StrEnum):
    COLLECTION = "COLLECTION"
    CREDENTIAL = "CREDENTIAL"


@dataclass(frozen=True)
class AuditOutboxRecord:
    event: AuditEvent
    aggregate_type: str
    aggregate_id: str
    source: AuditOutboxSource
    status: AuditOutboxStatus
    attempts: int
    available_at: datetime
    created_at: datetime
    updated_at: datetime
    version: int = 1
    lease_until: datetime | None = None
    delivered_at: datetime | None = None
    last_error: str | None = None

    def __post_init__(self) -> None:
        if not self.aggregate_type.strip() or len(self.aggregate_type) > 100:
            raise ValueError("Outbox aggregate type is invalid.")
        if not self.aggregate_id.strip() or len(self.aggregate_id) > 2_048:
            raise ValueError("Outbox aggregate id is invalid.")
        if self.attempts < 0 or self.version < 1:
            raise ValueError("Outbox counters must not be negative.")
        for name, value in (
            ("availableAt", self.available_at),
            ("createdAt", self.created_at),
            ("updatedAt", self.updated_at),
        ):
            _require_aware(value, name=name)
        if self.updated_at < self.created_at:
            raise ValueError("Outbox updatedAt precedes createdAt.")
        if self.lease_until is not None:
            _require_aware(self.lease_until, name="leaseUntil")
        if self.delivered_at is not None:
            _require_aware(self.delivered_at, name="deliveredAt")
        if (
            self.last_error is not None
            and not _SAFE_ERROR_CODE.fullmatch(self.last_error)
        ):
            raise ValueError("Outbox error code is invalid.")
        if self.status is AuditOutboxStatus.PENDING:
            if self.lease_until is not None or self.delivered_at is not None:
                raise ValueError("Pending outbox state is inconsistent.")
        elif self.status is AuditOutboxStatus.PROCESSING:
            if self.lease_until is None or self.delivered_at is not None:
                raise ValueError("Processing outbox state is inconsistent.")
        elif (
            self.lease_until is not None
            or self.delivered_at is None
            or self.last_error is not None
        ):
            raise ValueError("Delivered outbox state is inconsistent.")

    @classmethod
    def pending(
        cls,
        *,
        event: AuditEvent,
        aggregate_type: str,
        aggregate_id: str,
        source: AuditOutboxSource,
    ) -> "AuditOutboxRecord":
        return cls(
            event=event,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            source=source,
            status=AuditOutboxStatus.PENDING,
            attempts=0,
            available_at=event.created_at,
            created_at=event.created_at,
            updated_at=event.created_at,
        )


@dataclass(frozen=True)
class AuditRetryPolicy:
    base_delay_seconds: int = 1
    max_delay_seconds: int = 300
    lease_seconds: int = 30

    def __post_init__(self) -> None:
        if not 1 <= self.base_delay_seconds <= self.max_delay_seconds:
            raise ValueError("Audit retry delay bounds are invalid.")
        if not 1 <= self.lease_seconds <= 3_600:
            raise ValueError("Audit delivery lease is invalid.")

    def next_available_at(
        self,
        *,
        failed_at: datetime,
        attempts: int,
    ) -> datetime:
        _require_aware(failed_at, name="failedAt")
        if attempts < 1:
            raise ValueError("Retry attempts must be positive.")
        delay = min(
            self.max_delay_seconds,
            self.base_delay_seconds * (2 ** min(attempts - 1, 20)),
        )
        return failed_at + timedelta(seconds=delay)

    def lease_until(self, *, claimed_at: datetime) -> datetime:
        _require_aware(claimed_at, name="claimedAt")
        return claimed_at + timedelta(seconds=self.lease_seconds)


def _require_aware(value: datetime, *, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware.")
