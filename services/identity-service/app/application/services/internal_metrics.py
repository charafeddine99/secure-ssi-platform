from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class InternalMetricsSnapshot:
    issuance_succeeded: int
    issuance_failed: int
    rollover_count: int
    publications_created: int
    audit_worker_cycles: int
    audit_events_delivered: int
    audit_events_retried: int
    outbox_lag_seconds: float
    last_issuance_at: datetime | None
    last_publication_at: datetime | None
    last_audit_worker_at: datetime | None
    status_list_utilization: Mapping[str, float]
    active_wallet_count: int
    locked_wallet_count: int
    challenge_issuance_count: int
    challenge_rejection_count: int
    challenge_replay_count: int
    expired_challenge_count: int
    presentation_reconciliation_count: int
    stale_processing_count: int
    reconciliation_success_count: int
    reconciliation_failure_count: int
    ownership_rejection_count: int


class InternalMetrics:
    """Process-local operational signals with no public API surface."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._issuance_succeeded = 0
        self._issuance_failed = 0
        self._rollover_count = 0
        self._publications_created = 0
        self._audit_worker_cycles = 0
        self._audit_events_delivered = 0
        self._audit_events_retried = 0
        self._outbox_lag_seconds = 0.0
        self._last_issuance_at: datetime | None = None
        self._last_publication_at: datetime | None = None
        self._last_audit_worker_at: datetime | None = None
        self._status_list_utilization: dict[str, float] = {}
        self._active_wallet_count = 0
        self._locked_wallet_count = 0
        self._challenge_issuance_count = 0
        self._challenge_rejection_count = 0
        self._challenge_replay_count = 0
        self._expired_challenge_count = 0
        self._presentation_reconciliation_count = 0
        self._stale_processing_count = 0
        self._reconciliation_success_count = 0
        self._reconciliation_failure_count = 0
        self._ownership_rejection_count = 0

    def record_issuance_success(self, *, occurred_at: datetime) -> None:
        with self._lock:
            self._issuance_succeeded += 1
            self._last_issuance_at = occurred_at

    def record_issuance_failure(self) -> None:
        with self._lock:
            self._issuance_failed += 1

    def record_rollover(self) -> None:
        with self._lock:
            self._rollover_count += 1

    def record_publication(
        self,
        *,
        status_list_id: str,
        assigned_entries: int,
        capacity: int,
        published_at: datetime,
    ) -> None:
        with self._lock:
            self._publications_created += 1
            self._last_publication_at = published_at
            self._status_list_utilization[status_list_id] = (
                assigned_entries / capacity
            )

    def observe_utilization(
        self,
        *,
        status_list_id: str,
        assigned_entries: int,
        capacity: int,
    ) -> None:
        with self._lock:
            self._status_list_utilization[status_list_id] = (
                assigned_entries / capacity
            )

    def record_audit_cycle(
        self,
        *,
        occurred_at: datetime,
        delivered: int,
        retried: int,
        outbox_lag_seconds: float,
    ) -> None:
        with self._lock:
            self._audit_worker_cycles += 1
            self._audit_events_delivered += delivered
            self._audit_events_retried += retried
            self._outbox_lag_seconds = max(0.0, outbox_lag_seconds)
            self._last_audit_worker_at = occurred_at

    def record_wallet_created(self) -> None:
        with self._lock:
            self._active_wallet_count += 1

    def record_wallet_locked(self) -> None:
        with self._lock:
            self._active_wallet_count = max(
                0,
                self._active_wallet_count - 1,
            )
            self._locked_wallet_count += 1

    def record_wallet_disabled(self, *, was_locked: bool) -> None:
        with self._lock:
            if was_locked:
                self._locked_wallet_count = max(
                    0,
                    self._locked_wallet_count - 1,
                )
            else:
                self._active_wallet_count = max(
                    0,
                    self._active_wallet_count - 1,
                )

    def record_challenge_issued(self) -> None:
        with self._lock:
            self._challenge_issuance_count += 1

    def record_challenge_rejected(
        self,
        *,
        replay: bool = False,
        expired: bool = False,
    ) -> None:
        with self._lock:
            self._challenge_rejection_count += 1
            if replay:
                self._challenge_replay_count += 1
            if expired:
                self._expired_challenge_count += 1

    def record_ownership_rejection(self) -> None:
        with self._lock:
            self._ownership_rejection_count += 1

    def record_reconciliation_cycle(
        self,
        *,
        stale_count: int,
        succeeded: int,
        failed: int,
    ) -> None:
        with self._lock:
            self._presentation_reconciliation_count += (
                succeeded + failed
            )
            self._stale_processing_count = max(0, stale_count)
            self._reconciliation_success_count += succeeded
            self._reconciliation_failure_count += failed

    def record_reconciliation_result(self, *, succeeded: bool) -> None:
        with self._lock:
            self._presentation_reconciliation_count += 1
            if succeeded:
                self._reconciliation_success_count += 1
            else:
                self._reconciliation_failure_count += 1

    def observe_stale_processing(self, *, count: int) -> None:
        with self._lock:
            self._stale_processing_count = max(0, count)

    def snapshot(self) -> InternalMetricsSnapshot:
        with self._lock:
            return InternalMetricsSnapshot(
                issuance_succeeded=self._issuance_succeeded,
                issuance_failed=self._issuance_failed,
                rollover_count=self._rollover_count,
                publications_created=self._publications_created,
                audit_worker_cycles=self._audit_worker_cycles,
                audit_events_delivered=self._audit_events_delivered,
                audit_events_retried=self._audit_events_retried,
                outbox_lag_seconds=self._outbox_lag_seconds,
                last_issuance_at=self._last_issuance_at,
                last_publication_at=self._last_publication_at,
                last_audit_worker_at=self._last_audit_worker_at,
                status_list_utilization=MappingProxyType(
                    dict(self._status_list_utilization)
                ),
                active_wallet_count=self._active_wallet_count,
                locked_wallet_count=self._locked_wallet_count,
                challenge_issuance_count=self._challenge_issuance_count,
                challenge_rejection_count=self._challenge_rejection_count,
                challenge_replay_count=self._challenge_replay_count,
                expired_challenge_count=self._expired_challenge_count,
                presentation_reconciliation_count=(
                    self._presentation_reconciliation_count
                ),
                stale_processing_count=self._stale_processing_count,
                reconciliation_success_count=(
                    self._reconciliation_success_count
                ),
                reconciliation_failure_count=(
                    self._reconciliation_failure_count
                ),
                ownership_rejection_count=(
                    self._ownership_rejection_count
                ),
            )


INTERNAL_METRICS = InternalMetrics()
