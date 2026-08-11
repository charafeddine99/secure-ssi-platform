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
    managed_key_creation_attempts: int
    managed_key_creation_succeeded: int
    managed_key_creation_failed: int
    provider_request_count: int
    provider_latency_seconds: float
    provider_timeout_count: int
    provider_error_count: int
    managed_signing_attempts: int
    managed_signing_succeeded: int
    managed_signing_failed: int
    managed_signing_lifecycle_rejections: int
    key_rotation_attempts: int
    key_rotation_succeeded: int
    key_rotation_failed: int
    stale_key_rotation_count: int
    key_compromise_count: int
    key_revocation_count: int
    key_destruction_scheduled: int
    key_destruction_completed: int
    key_destruction_failed: int
    key_reconciliation_attempts: int
    key_reconciliation_succeeded: int
    key_reconciliation_failed: int
    active_keys_by_provider_purpose: Mapping[str, int]
    managed_keys_by_state: Mapping[str, int]


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
        self._managed_key_creation_attempts = 0
        self._managed_key_creation_succeeded = 0
        self._managed_key_creation_failed = 0
        self._provider_request_count = 0
        self._provider_latency_seconds = 0.0
        self._provider_timeout_count = 0
        self._provider_error_count = 0
        self._managed_signing_attempts = 0
        self._managed_signing_succeeded = 0
        self._managed_signing_failed = 0
        self._managed_signing_lifecycle_rejections = 0
        self._key_rotation_attempts = 0
        self._key_rotation_succeeded = 0
        self._key_rotation_failed = 0
        self._stale_key_rotation_count = 0
        self._key_compromise_count = 0
        self._key_revocation_count = 0
        self._key_destruction_scheduled = 0
        self._key_destruction_completed = 0
        self._key_destruction_failed = 0
        self._key_reconciliation_attempts = 0
        self._key_reconciliation_succeeded = 0
        self._key_reconciliation_failed = 0
        self._active_keys_by_provider_purpose: dict[str, int] = {}
        self._managed_keys_by_state: dict[str, int] = {}

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

    def record_managed_key_creation(self, *, succeeded: bool) -> None:
        with self._lock:
            self._managed_key_creation_attempts += 1
            if succeeded:
                self._managed_key_creation_succeeded += 1
            else:
                self._managed_key_creation_failed += 1

    def observe_provider_request(
        self,
        *,
        latency_seconds: float,
        timed_out: bool = False,
        failed: bool = False,
    ) -> None:
        with self._lock:
            self._provider_request_count += 1
            self._provider_latency_seconds += max(0.0, latency_seconds)
            if timed_out:
                self._provider_timeout_count += 1
            if failed:
                self._provider_error_count += 1

    def record_managed_signing(
        self,
        *,
        succeeded: bool,
        lifecycle_rejected: bool = False,
    ) -> None:
        with self._lock:
            self._managed_signing_attempts += 1
            if succeeded:
                self._managed_signing_succeeded += 1
            else:
                self._managed_signing_failed += 1
            if lifecycle_rejected:
                self._managed_signing_lifecycle_rejections += 1

    def record_key_rotation(self, *, succeeded: bool) -> None:
        with self._lock:
            self._key_rotation_attempts += 1
            if succeeded:
                self._key_rotation_succeeded += 1
            else:
                self._key_rotation_failed += 1

    def observe_stale_key_rotations(self, *, count: int) -> None:
        with self._lock:
            self._stale_key_rotation_count = max(0, count)

    def record_key_compromise(self) -> None:
        with self._lock:
            self._key_compromise_count += 1

    def record_key_revocation(self) -> None:
        with self._lock:
            self._key_revocation_count += 1

    def record_key_destruction(self, *, stage: str) -> None:
        with self._lock:
            if stage == "scheduled":
                self._key_destruction_scheduled += 1
            elif stage == "completed":
                self._key_destruction_completed += 1
            elif stage == "failed":
                self._key_destruction_failed += 1
            else:
                raise ValueError("Unknown key destruction metric stage.")

    def record_key_reconciliation(self, *, succeeded: bool) -> None:
        with self._lock:
            self._key_reconciliation_attempts += 1
            if succeeded:
                self._key_reconciliation_succeeded += 1
            else:
                self._key_reconciliation_failed += 1

    def observe_managed_key_inventory(
        self,
        *,
        active_by_provider_purpose: Mapping[str, int],
        by_state: Mapping[str, int],
    ) -> None:
        with self._lock:
            self._active_keys_by_provider_purpose = dict(
                active_by_provider_purpose
            )
            self._managed_keys_by_state = dict(by_state)

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
                managed_key_creation_attempts=(
                    self._managed_key_creation_attempts
                ),
                managed_key_creation_succeeded=(
                    self._managed_key_creation_succeeded
                ),
                managed_key_creation_failed=(
                    self._managed_key_creation_failed
                ),
                provider_request_count=self._provider_request_count,
                provider_latency_seconds=self._provider_latency_seconds,
                provider_timeout_count=self._provider_timeout_count,
                provider_error_count=self._provider_error_count,
                managed_signing_attempts=self._managed_signing_attempts,
                managed_signing_succeeded=self._managed_signing_succeeded,
                managed_signing_failed=self._managed_signing_failed,
                managed_signing_lifecycle_rejections=(
                    self._managed_signing_lifecycle_rejections
                ),
                key_rotation_attempts=self._key_rotation_attempts,
                key_rotation_succeeded=self._key_rotation_succeeded,
                key_rotation_failed=self._key_rotation_failed,
                stale_key_rotation_count=self._stale_key_rotation_count,
                key_compromise_count=self._key_compromise_count,
                key_revocation_count=self._key_revocation_count,
                key_destruction_scheduled=(
                    self._key_destruction_scheduled
                ),
                key_destruction_completed=(
                    self._key_destruction_completed
                ),
                key_destruction_failed=self._key_destruction_failed,
                key_reconciliation_attempts=(
                    self._key_reconciliation_attempts
                ),
                key_reconciliation_succeeded=(
                    self._key_reconciliation_succeeded
                ),
                key_reconciliation_failed=(
                    self._key_reconciliation_failed
                ),
                active_keys_by_provider_purpose=MappingProxyType(
                    dict(self._active_keys_by_provider_purpose)
                ),
                managed_keys_by_state=MappingProxyType(
                    dict(self._managed_keys_by_state)
                ),
            )


INTERNAL_METRICS = InternalMetrics()
