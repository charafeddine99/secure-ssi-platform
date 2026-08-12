from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


class RecoveryError(Exception):
    """Base class for controlled recovery failures."""


class RecoveryValidationError(RecoveryError, ValueError):
    pass


class RecoveryNotFoundError(RecoveryError):
    pass


class RecoveryConflictError(RecoveryError):
    pass


class RecoveryAuthorizationError(RecoveryError):
    pass


class RecoveryStateError(RecoveryConflictError):
    pass


class RecoveryPersistenceError(RecoveryError):
    pass


class SecretShareError(RecoveryError):
    pass


class GuardianStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"
    REMOVED = "REMOVED"


class RecoveryState(StrEnum):
    PENDING_APPROVALS = "PENDING_APPROVALS"
    QUORUM_REACHED = "QUORUM_REACHED"
    WAITING_TIMELOCK = "WAITING_TIMELOCK"
    READY_FOR_EXECUTION = "READY_FOR_EXECUTION"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"

    @property
    def terminal(self) -> bool:
        return self in {
            RecoveryState.COMPLETED,
            RecoveryState.REJECTED,
            RecoveryState.CANCELLED,
            RecoveryState.EXPIRED,
            RecoveryState.FAILED,
        }


class RecoveryReason(StrEnum):
    ACCOUNT_COMPROMISE = "ACCOUNT_COMPROMISE"
    LOST_ACCESS = "LOST_ACCESS"
    DEVICE_LOSS = "DEVICE_LOSS"
    KEY_LOSS = "KEY_LOSS"


class RecoveryOperation(StrEnum):
    MANAGED_KEY_ROTATION = "MANAGED_KEY_ROTATION"


class RecoveryDecision(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class RecoveryAuditEventType(StrEnum):
    GUARDIAN_ADDED = "GUARDIAN_ADDED"
    GUARDIAN_UPDATED = "GUARDIAN_UPDATED"
    GUARDIAN_SUSPENDED = "GUARDIAN_SUSPENDED"
    GUARDIAN_RESUMED = "GUARDIAN_RESUMED"
    GUARDIAN_REMOVED = "GUARDIAN_REMOVED"
    RECOVERY_POLICY_UPDATED = "RECOVERY_POLICY_UPDATED"
    RECOVERY_REQUESTED = "RECOVERY_REQUESTED"
    RECOVERY_APPROVED = "RECOVERY_APPROVED"
    RECOVERY_REJECTED = "RECOVERY_REJECTED"
    RECOVERY_QUORUM_REACHED = "RECOVERY_QUORUM_REACHED"
    RECOVERY_TIMELOCK_STARTED = "RECOVERY_TIMELOCK_STARTED"
    RECOVERY_READY = "RECOVERY_READY"
    RECOVERY_EXECUTION_STARTED = "RECOVERY_EXECUTION_STARTED"
    RECOVERY_NEW_KEY_PROVISIONED = "RECOVERY_NEW_KEY_PROVISIONED"
    RECOVERY_DID_CHANGED = "RECOVERY_DID_CHANGED"
    RECOVERY_COMPLETED = "RECOVERY_COMPLETED"
    RECOVERY_CANCELLED = "RECOVERY_CANCELLED"
    RECOVERY_EXPIRED = "RECOVERY_EXPIRED"
    RECOVERY_FAILED = "RECOVERY_FAILED"
    RECOVERY_RECONCILED = "RECOVERY_RECONCILED"
    UNAUTHORIZED_RECOVERY_ATTEMPT = "UNAUTHORIZED_RECOVERY_ATTEMPT"
    SECRET_SHARE_VALIDATION_FAILED = "SECRET_SHARE_VALIDATION_FAILED"


_TRANSITIONS: Mapping[RecoveryState, frozenset[RecoveryState]] = MappingProxyType(
    {
        RecoveryState.PENDING_APPROVALS: frozenset(
            {
                RecoveryState.QUORUM_REACHED,
                RecoveryState.REJECTED,
                RecoveryState.CANCELLED,
                RecoveryState.EXPIRED,
                RecoveryState.FAILED,
            }
        ),
        RecoveryState.QUORUM_REACHED: frozenset(
            {
                RecoveryState.WAITING_TIMELOCK,
                RecoveryState.CANCELLED,
                RecoveryState.EXPIRED,
                RecoveryState.FAILED,
            }
        ),
        RecoveryState.WAITING_TIMELOCK: frozenset(
            {
                RecoveryState.READY_FOR_EXECUTION,
                RecoveryState.CANCELLED,
                RecoveryState.EXPIRED,
                RecoveryState.FAILED,
            }
        ),
        RecoveryState.READY_FOR_EXECUTION: frozenset(
            {
                RecoveryState.EXECUTING,
                RecoveryState.CANCELLED,
                RecoveryState.EXPIRED,
                RecoveryState.FAILED,
            }
        ),
        RecoveryState.EXECUTING: frozenset(
            {
                RecoveryState.COMPLETED,
                RecoveryState.RECONCILIATION_REQUIRED,
                RecoveryState.EXPIRED,
                RecoveryState.FAILED,
            }
        ),
        RecoveryState.RECONCILIATION_REQUIRED: frozenset(
            {
                RecoveryState.READY_FOR_EXECUTION,
                RecoveryState.EXECUTING,
                RecoveryState.COMPLETED,
                RecoveryState.EXPIRED,
                RecoveryState.FAILED,
            }
        ),
        RecoveryState.COMPLETED: frozenset(),
        RecoveryState.REJECTED: frozenset(),
        RecoveryState.CANCELLED: frozenset(),
        RecoveryState.EXPIRED: frozenset(),
        RecoveryState.FAILED: frozenset(),
    }
)


def require_transition(current: RecoveryState, target: RecoveryState) -> None:
    if target not in _TRANSITIONS[current]:
        raise RecoveryStateError(
            f"Recovery transition {current.value} -> {target.value} is invalid."
        )


@dataclass(frozen=True)
class Guardian:
    guardian_id: str
    owner_user_id: str
    wallet_id: str
    guardian_user_id: str
    guardian_did: str
    display_name: str
    verification_method: str
    status: GuardianStatus
    created_at: datetime
    updated_at: datetime
    version: int = 1
    suspended_at: datetime | None = None
    revoked_at: datetime | None = None
    removed_at: datetime | None = None

    def __post_init__(self) -> None:
        for value in (
            self.guardian_id,
            self.owner_user_id,
            self.wallet_id,
            self.guardian_user_id,
            self.guardian_did,
            self.display_name,
            self.verification_method,
        ):
            if not value.strip():
                raise RecoveryValidationError("Guardian fields must not be empty.")
        _aware(self.created_at, "createdAt")
        _aware(self.updated_at, "updatedAt")
        if self.version < 1 or self.updated_at < self.created_at:
            raise RecoveryValidationError("Guardian version or timestamps are invalid.")

    @property
    def can_approve(self) -> bool:
        return self.status is GuardianStatus.ACTIVE

    def transition(self, status: GuardianStatus, *, at: datetime) -> Guardian:
        _aware(at, "updatedAt")
        allowed = {
            GuardianStatus.ACTIVE: {
                GuardianStatus.SUSPENDED,
                GuardianStatus.REVOKED,
                GuardianStatus.REMOVED,
            },
            GuardianStatus.SUSPENDED: {
                GuardianStatus.ACTIVE,
                GuardianStatus.REVOKED,
                GuardianStatus.REMOVED,
            },
            GuardianStatus.REVOKED: {GuardianStatus.REMOVED},
            GuardianStatus.REMOVED: set(),
        }
        if status is self.status:
            return self
        if status not in allowed[self.status]:
            raise RecoveryStateError("Guardian state transition is invalid.")
        return replace(
            self,
            status=status,
            updated_at=at,
            suspended_at=at if status is GuardianStatus.SUSPENDED else self.suspended_at,
            revoked_at=at if status is GuardianStatus.REVOKED else self.revoked_at,
            removed_at=at if status is GuardianStatus.REMOVED else self.removed_at,
            version=self.version + 1,
        )


@dataclass(frozen=True)
class RecoveryPolicy:
    policy_id: str
    wallet_id: str
    owner_user_id: str
    minimum_approvals: int
    maximum_guardians: int
    approval_window_seconds: int
    time_lock_seconds: int
    recovery_expiration_seconds: int
    maximum_attempts: int
    cooldown_seconds: int
    allow_cancellation: bool
    allow_self_guardian: bool
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.policy_id or not self.wallet_id or not self.owner_user_id:
            raise RecoveryValidationError("Recovery policy identity is invalid.")
        if not 1 <= self.minimum_approvals <= self.maximum_guardians <= 32:
            raise RecoveryValidationError("Recovery policy must satisfy 1 <= M <= N <= 32.")
        if not 60 <= self.approval_window_seconds <= 30 * 24 * 3600:
            raise RecoveryValidationError("Approval window is outside safety bounds.")
        if not 0 <= self.time_lock_seconds <= 30 * 24 * 3600:
            raise RecoveryValidationError("Time-lock is outside safety bounds.")
        if self.recovery_expiration_seconds < (
            self.approval_window_seconds + self.time_lock_seconds
        ):
            raise RecoveryValidationError(
                "Recovery expiration must cover approval and time-lock windows."
            )
        if not 1 <= self.maximum_attempts <= 20:
            raise RecoveryValidationError("Recovery attempt limit is invalid.")
        if not 0 <= self.cooldown_seconds <= 30 * 24 * 3600:
            raise RecoveryValidationError("Recovery cooldown is invalid.")
        if self.version < 1:
            raise RecoveryValidationError("Recovery policy version is invalid.")
        _aware(self.created_at, "createdAt")
        _aware(self.updated_at, "updatedAt")


@dataclass(frozen=True)
class RecoveryPolicySnapshot:
    policy_id: str
    policy_version: int
    minimum_approvals: int
    maximum_guardians: int
    approval_window_seconds: int
    time_lock_seconds: int
    recovery_expiration_seconds: int
    maximum_attempts: int
    allow_cancellation: bool
    guardian_ids: tuple[str, ...]
    share_version: int
    secret_commitment: str = field(repr=False)

    def __post_init__(self) -> None:
        if not 1 <= self.minimum_approvals <= len(self.guardian_ids):
            raise RecoveryValidationError("Policy snapshot cannot reach quorum.")
        if len(set(self.guardian_ids)) != len(self.guardian_ids):
            raise RecoveryValidationError("Policy snapshot guardians are duplicated.")
        if self.share_version < 1 or not self.secret_commitment:
            raise RecoveryValidationError("Policy snapshot share metadata is invalid.")


@dataclass(frozen=True)
class RecoveryChallenge:
    value: str = field(repr=False)
    digest: str

    def __post_init__(self) -> None:
        if len(self.value) < 32 or len(self.digest) != 64:
            raise RecoveryValidationError("Recovery challenge is invalid.")


@dataclass(frozen=True)
class RecoveryNonce:
    value: str = field(repr=False)
    digest: str

    def __post_init__(self) -> None:
        if len(self.value) < 32 or len(self.digest) != 64:
            raise RecoveryValidationError("Recovery nonce is invalid.")


@dataclass(frozen=True)
class RecoveryQuorum:
    required: int
    approvals: int
    rejections: int
    reached_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.required < 1 or self.approvals < 0 or self.rejections < 0:
            raise RecoveryValidationError("Recovery quorum counters are invalid.")
        if self.reached_at is not None:
            _aware(self.reached_at, "quorumReachedAt")
            if self.approvals < self.required:
                raise RecoveryValidationError("Reached quorum lacks approvals.")

    @property
    def reached(self) -> bool:
        return self.approvals >= self.required


@dataclass(frozen=True)
class RecoveryLease:
    worker_id: str
    acquired_at: datetime
    expires_at: datetime
    attempt: int

    def __post_init__(self) -> None:
        if not self.worker_id or self.attempt < 1:
            raise RecoveryValidationError("Recovery lease is invalid.")
        _aware(self.acquired_at, "leaseAcquiredAt")
        _aware(self.expires_at, "leaseExpiresAt")
        if self.expires_at <= self.acquired_at:
            raise RecoveryValidationError("Recovery lease must expire later.")


@dataclass(frozen=True)
class RecoveryResult:
    predecessor_key_id: str
    successor_key_id: str
    predecessor_did: str
    successor_did: str
    provider: str
    completed_at: datetime
    key_rotation_duration_ms: float

    def __post_init__(self) -> None:
        for value in (
            self.predecessor_key_id,
            self.successor_key_id,
            self.predecessor_did,
            self.successor_did,
            self.provider,
        ):
            if not value:
                raise RecoveryValidationError("Recovery result is incomplete.")
        _aware(self.completed_at, "completedAt")
        if self.key_rotation_duration_ms < 0:
            raise RecoveryValidationError("Recovery duration is invalid.")


@dataclass(frozen=True)
class RecoveryFailure:
    code: str
    retryable: bool
    occurred_at: datetime
    attempt: int

    def __post_init__(self) -> None:
        if not self.code or self.attempt < 1:
            raise RecoveryValidationError("Recovery failure is invalid.")
        _aware(self.occurred_at, "failureOccurredAt")


@dataclass(frozen=True)
class RecoverySession:
    session_id: str
    state: RecoveryState
    created_at: datetime
    updated_at: datetime
    approval_expires_at: datetime
    expires_at: datetime
    quorum: RecoveryQuorum
    attempt_count: int = 0
    quorum_reached_at: datetime | None = None
    time_lock_started_at: datetime | None = None
    executable_after: datetime | None = None
    lease: RecoveryLease | None = None
    result: RecoveryResult | None = None
    failure: RecoveryFailure | None = None

    def __post_init__(self) -> None:
        if not self.session_id or self.attempt_count < 0:
            raise RecoveryValidationError("Recovery session is invalid.")
        for name, value in (
            ("createdAt", self.created_at),
            ("updatedAt", self.updated_at),
            ("approvalExpiresAt", self.approval_expires_at),
            ("expiresAt", self.expires_at),
        ):
            _aware(value, name)
        if not self.created_at < self.approval_expires_at <= self.expires_at:
            raise RecoveryValidationError("Recovery session windows are invalid.")


@dataclass(frozen=True)
class RecoveryRequest:
    request_id: str
    owner_user_id: str
    wallet_id: str
    reason: RecoveryReason
    operation: RecoveryOperation
    policy: RecoveryPolicySnapshot
    challenge: RecoveryChallenge
    nonce: RecoveryNonce
    session: RecoverySession
    created_at: datetime
    updated_at: datetime
    version: int = 1

    def __post_init__(self) -> None:
        if not self.request_id or not self.owner_user_id or not self.wallet_id:
            raise RecoveryValidationError("Recovery request identity is invalid.")
        _aware(self.created_at, "createdAt")
        _aware(self.updated_at, "updatedAt")
        if self.version < 1 or self.session.created_at != self.created_at:
            raise RecoveryValidationError("Recovery request version is invalid.")

    def transition(
        self,
        state: RecoveryState,
        *,
        at: datetime,
        session_changes: Mapping[str, Any] | None = None,
    ) -> RecoveryRequest:
        require_transition(self.session.state, state)
        _aware(at, "updatedAt")
        changes = dict(session_changes or {})
        changes.update(state=state, updated_at=at)
        return replace(
            self,
            session=replace(self.session, **changes),
            updated_at=at,
            version=self.version + 1,
        )


@dataclass(frozen=True)
class RecoveryApproval:
    approval_id: str
    request_id: str
    session_id: str
    guardian_id: str
    guardian_user_id: str
    wallet_id: str
    decision: RecoveryDecision
    challenge_digest: str
    proof_digest: str | None
    decided_at: datetime
    created_at: datetime
    version: int = 1

    def __post_init__(self) -> None:
        for value in (
            self.approval_id,
            self.request_id,
            self.session_id,
            self.guardian_id,
            self.guardian_user_id,
            self.wallet_id,
            self.challenge_digest,
        ):
            if not value:
                raise RecoveryValidationError("Recovery approval is incomplete.")
        _aware(self.decided_at, "decidedAt")
        _aware(self.created_at, "createdAt")


@dataclass(frozen=True)
class RecoverySecretShareMetadata:
    share_id: str
    recovery_request_id: str
    policy_id: str
    policy_version: int
    share_version: int
    guardian_id: str
    share_index: int
    threshold: int
    share_count: int
    envelope_version: int
    integrity_digest: str = field(repr=False)
    encrypted_envelope: str = field(repr=False)
    created_at: datetime = field(repr=False)

    def __post_init__(self) -> None:
        if not all(
            (
                self.share_id,
                self.recovery_request_id,
                self.policy_id,
                self.guardian_id,
                self.integrity_digest,
                self.encrypted_envelope,
            )
        ):
            raise RecoveryValidationError("Recovery share metadata is incomplete.")
        if not 1 <= self.threshold <= self.share_count <= 32:
            raise RecoveryValidationError("Recovery share threshold is invalid.")
        if not 1 <= self.share_index <= self.share_count:
            raise RecoveryValidationError("Recovery share index is invalid.")
        if min(self.policy_version, self.share_version, self.envelope_version) < 1:
            raise RecoveryValidationError("Recovery share version is invalid.")
        _aware(self.created_at, "createdAt")


@dataclass(frozen=True)
class RecoveryAuditEvent:
    event_id: str
    event_type: RecoveryAuditEventType
    aggregate_id: str
    actor_id: str
    occurred_at: datetime
    metadata: Mapping[str, str]

    def __post_init__(self) -> None:
        if not self.event_id or not self.aggregate_id or not self.actor_id:
            raise RecoveryValidationError("Recovery audit event identity is invalid.")
        _aware(self.occurred_at, "occurredAt")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


def _aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RecoveryValidationError(f"{name} must be timezone-aware.")
