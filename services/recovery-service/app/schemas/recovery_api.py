from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.recovery import (
    Guardian,
    GuardianStatus,
    RecoveryApproval,
    RecoveryPolicy,
    RecoveryReason,
    RecoveryRequest,
    RecoveryState,
)


_WALLET_PATTERN = r"^wallet_[A-Za-z0-9_-]{16,80}$"
_GUARDIAN_PATTERN = r"^guardian_[A-Za-z0-9_-]{16,80}$"
_REQUEST_PATTERN = r"^recovery_[A-Za-z0-9_-]{16,80}$"


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", populate_by_name=True, str_strip_whitespace=True
    )


class GuardianCreateRequest(StrictModel):
    wallet_id: str = Field(alias="walletId", pattern=_WALLET_PATTERN)
    guardian_user_id: str = Field(alias="guardianUserId", min_length=1, max_length=128)
    guardian_did: str = Field(alias="guardianDid", pattern=r"^did:(key|web):.{8,1900}$")
    display_name: str = Field(alias="displayName", min_length=1, max_length=120)
    verification_method: str = Field(
        alias="verificationMethod", min_length=8, max_length=2048
    )


class GuardianUpdateRequest(StrictModel):
    display_name: str | None = Field(
        default=None, alias="displayName", min_length=1, max_length=120
    )
    verification_method: str | None = Field(
        default=None, alias="verificationMethod", min_length=8, max_length=2048
    )
    status: GuardianStatus | None = None


class GuardianResponse(StrictModel):
    guardian_id: str = Field(alias="guardianId")
    owner_user_id: str = Field(alias="ownerUserId")
    wallet_id: str = Field(alias="walletId")
    guardian_user_id: str = Field(alias="guardianUserId")
    guardian_did: str = Field(alias="guardianDid")
    display_name: str = Field(alias="displayName")
    verification_method: str = Field(alias="verificationMethod")
    status: GuardianStatus
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    suspended_at: datetime | None = Field(alias="suspendedAt")
    revoked_at: datetime | None = Field(alias="revokedAt")
    removed_at: datetime | None = Field(alias="removedAt")
    version: int

    @classmethod
    def from_domain(cls, value: Guardian) -> "GuardianResponse":
        return cls(**value.__dict__)


class GuardianListResponse(StrictModel):
    items: list[GuardianResponse]


class RecoveryPolicyUpsertRequest(StrictModel):
    wallet_id: str = Field(alias="walletId", pattern=_WALLET_PATTERN)
    minimum_approvals: int = Field(alias="minimumApprovals", ge=1, le=32)
    maximum_guardians: int = Field(alias="maximumGuardians", ge=1, le=32)
    approval_window_seconds: int = Field(
        alias="approvalWindowSeconds", ge=60, le=2592000
    )
    time_lock_seconds: int = Field(alias="timeLockSeconds", ge=0, le=2592000)
    recovery_expiration_seconds: int = Field(
        alias="recoveryExpirationSeconds", ge=60, le=5184000
    )
    maximum_attempts: int = Field(alias="maximumAttempts", ge=1, le=20)
    cooldown_seconds: int = Field(alias="cooldownSeconds", ge=0, le=2592000)
    allow_cancellation: bool = Field(alias="allowCancellation")
    allow_self_guardian: bool = Field(default=False, alias="allowSelfGuardian")


class RecoveryPolicyResponse(StrictModel):
    policy_id: str = Field(alias="policyId")
    wallet_id: str = Field(alias="walletId")
    owner_user_id: str = Field(alias="ownerUserId")
    minimum_approvals: int = Field(alias="minimumApprovals")
    maximum_guardians: int = Field(alias="maximumGuardians")
    approval_window_seconds: int = Field(alias="approvalWindowSeconds")
    time_lock_seconds: int = Field(alias="timeLockSeconds")
    recovery_expiration_seconds: int = Field(alias="recoveryExpirationSeconds")
    maximum_attempts: int = Field(alias="maximumAttempts")
    cooldown_seconds: int = Field(alias="cooldownSeconds")
    allow_cancellation: bool = Field(alias="allowCancellation")
    allow_self_guardian: bool = Field(alias="allowSelfGuardian")
    version: int
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    @classmethod
    def from_domain(cls, value: RecoveryPolicy) -> "RecoveryPolicyResponse":
        return cls(**value.__dict__)


class RecoveryCreateRequest(StrictModel):
    wallet_id: str = Field(alias="walletId", pattern=_WALLET_PATTERN)
    reason: RecoveryReason


class GuardianDecisionRequest(StrictModel):
    guardian_id: str = Field(alias="guardianId", pattern=_GUARDIAN_PATTERN)
    challenge: str = Field(min_length=32, max_length=256)
    proof: str | None = Field(default=None, min_length=16, max_length=4096)


class RecoveryResultResponse(StrictModel):
    predecessor_key_id: str = Field(alias="predecessorKeyId")
    successor_key_id: str = Field(alias="successorKeyId")
    predecessor_did: str = Field(alias="predecessorDid")
    successor_did: str = Field(alias="successorDid")
    provider: str
    completed_at: datetime = Field(alias="completedAt")
    key_rotation_duration_ms: float = Field(alias="keyRotationDurationMs")


class RecoveryRequestResponse(StrictModel):
    request_id: str = Field(alias="requestId")
    session_id: str = Field(alias="sessionId")
    owner_user_id: str = Field(alias="ownerUserId")
    wallet_id: str = Field(alias="walletId")
    reason: RecoveryReason
    operation: str
    state: RecoveryState
    challenge: str
    nonce: str
    minimum_approvals: int = Field(alias="minimumApprovals")
    guardian_count: int = Field(alias="guardianCount")
    approval_count: int = Field(alias="approvalCount")
    rejection_count: int = Field(alias="rejectionCount")
    policy_version: int = Field(alias="policyVersion")
    share_version: int = Field(alias="shareVersion")
    approval_expires_at: datetime = Field(alias="approvalExpiresAt")
    expires_at: datetime = Field(alias="expiresAt")
    executable_after: datetime | None = Field(alias="executableAfter")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    version: int
    result: RecoveryResultResponse | None = None
    failure_code: str | None = Field(alias="failureCode")

    @classmethod
    def from_domain(cls, value: RecoveryRequest) -> "RecoveryRequestResponse":
        result = value.session.result
        return cls(
            request_id=value.request_id,
            session_id=value.session.session_id,
            owner_user_id=value.owner_user_id,
            wallet_id=value.wallet_id,
            reason=value.reason,
            operation=value.operation.value,
            state=value.session.state,
            challenge=value.challenge.value,
            nonce=value.nonce.value,
            minimum_approvals=value.policy.minimum_approvals,
            guardian_count=len(value.policy.guardian_ids),
            approval_count=value.session.quorum.approvals,
            rejection_count=value.session.quorum.rejections,
            policy_version=value.policy.policy_version,
            share_version=value.policy.share_version,
            approval_expires_at=value.session.approval_expires_at,
            expires_at=value.session.expires_at,
            executable_after=value.session.executable_after,
            created_at=value.created_at,
            updated_at=value.updated_at,
            version=value.version,
            result=None if result is None else RecoveryResultResponse(**result.__dict__),
            failure_code=(
                None if value.session.failure is None else value.session.failure.code
            ),
        )


class RecoveryRequestListResponse(StrictModel):
    items: list[RecoveryRequestResponse]


class RecoveryApprovalResponse(StrictModel):
    approval_id: str = Field(alias="approvalId")
    request_id: str = Field(alias="requestId")
    guardian_id: str = Field(alias="guardianId")
    decision: str
    decided_at: datetime = Field(alias="decidedAt")

    @classmethod
    def from_domain(cls, value: RecoveryApproval) -> "RecoveryApprovalResponse":
        return cls(
            approval_id=value.approval_id,
            request_id=value.request_id,
            guardian_id=value.guardian_id,
            decision=value.decision.value,
            decided_at=value.decided_at,
        )


class RecoveryDecisionResponse(StrictModel):
    approval: RecoveryApprovalResponse
    recovery: RecoveryRequestResponse


class ApiError(StrictModel):
    code: str
    message: str
    request_id: str | None = Field(default=None, alias="requestId")


class HealthResponse(StrictModel):
    service: Literal["recovery-service"] = "recovery-service"
    status: Literal["healthy"] = "healthy"
    version: str
