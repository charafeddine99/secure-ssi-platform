import asyncio
import logging
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from hmac import compare_digest
from secrets import token_bytes, token_urlsafe
from time import perf_counter
from typing import Any

from app.application.ports.managed_keys import ManagedKeyRecoveryGateway
from app.application.ports.repositories import RecoveryRepository
from app.application.ports.secret_sharing import (
    SecretSharingContext,
    SecretSharingProvider,
)
from app.application.services.metrics import RecoveryMetrics
from app.application.services.guardian_proof import (
    GuardianDecisionProofVerifier,
    GuardianProofError,
)
from app.core.config import RecoverySettings
from app.domain.auth import Permission, RecoveryPrincipal
from app.domain.recovery import (
    Guardian,
    GuardianStatus,
    RecoveryApproval,
    RecoveryAuditEvent,
    RecoveryAuditEventType,
    RecoveryAuthorizationError,
    RecoveryChallenge,
    RecoveryConflictError,
    RecoveryDecision,
    RecoveryFailure,
    RecoveryLease,
    RecoveryNonce,
    RecoveryNotFoundError,
    RecoveryNotification,
    RecoveryOperation,
    RecoveryPolicy,
    RecoveryPolicySnapshot,
    RecoveryQuorum,
    RecoveryReason,
    RecoveryRequest,
    RecoveryResult,
    RecoveryRisk,
    RecoverySecretShareMetadata,
    RecoverySession,
    RecoveryState,
    RecoveryValidationError,
    RiskHoldStatus,
    SecretShareError,
    policy_hash,
)


Clock = Callable[[], datetime]
IdGenerator = Callable[[str], str]
_LOGGER = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(UTC)


_NOTIFIED_EVENTS = frozenset(
    {
        RecoveryAuditEventType.GUARDIAN_INVITED,
        RecoveryAuditEventType.GUARDIAN_ACCEPTED,
        RecoveryAuditEventType.GUARDIAN_ACTIVATED,
        RecoveryAuditEventType.GUARDIAN_CHANGE_SCHEDULED,
        RecoveryAuditEventType.GUARDIAN_REBOUND,
        RecoveryAuditEventType.RECOVERY_POLICY_UPDATED,
        RecoveryAuditEventType.RECOVERY_POLICY_CHANGE_SCHEDULED,
        RecoveryAuditEventType.RECOVERY_REQUESTED,
        RecoveryAuditEventType.RECOVERY_QUORUM_REACHED,
        RecoveryAuditEventType.RECOVERY_REJECTED,
        RecoveryAuditEventType.RECOVERY_CANCELLED,
        RecoveryAuditEventType.RECOVERY_EXPIRED,
        RecoveryAuditEventType.RECOVERY_COMPLETED,
        RecoveryAuditEventType.RECOVERY_FAILED,
        RecoveryAuditEventType.RECOVERY_RISK_HOLD,
        RecoveryAuditEventType.RECOVERY_RISK_REVIEWED,
    }
)
_POLICY_FIELDS = {
    "minimumApprovals": "minimum_approvals",
    "maximumGuardians": "maximum_guardians",
    "approvalWindowSeconds": "approval_window_seconds",
    "timeLockSeconds": "time_lock_seconds",
    "recoveryExpirationSeconds": "recovery_expiration_seconds",
    "maximumAttempts": "maximum_attempts",
    "cooldownSeconds": "cooldown_seconds",
    "allowCancellation": "allow_cancellation",
}


def _policy_fields(change: Any) -> dict[str, Any]:
    return {_POLICY_FIELDS[key]: value for key, value in change.items()}


def _weakens(policy: RecoveryPolicy, requested: dict[str, Any]) -> bool:
    return (
        requested["minimumApprovals"] < policy.minimum_approvals
        or requested["timeLockSeconds"] < policy.time_lock_seconds
        or requested["maximumAttempts"] > policy.maximum_attempts
        or requested["cooldownSeconds"] < policy.cooldown_seconds
        or requested["approvalWindowSeconds"] > policy.approval_window_seconds
    )


def secure_id(prefix: str) -> str:
    return f"{prefix}_{token_urlsafe(18)}"


class RecoveryService:
    def __init__(
        self,
        *,
        repository: RecoveryRepository,
        secret_sharing: SecretSharingProvider,
        managed_keys: ManagedKeyRecoveryGateway,
        settings: RecoverySettings,
        metrics: RecoveryMetrics,
        clock: Clock = utc_now,
        id_generator: IdGenerator = secure_id,
        worker_id: str | None = None,
        risk: Any = None,
    ) -> None:
        self._risk = risk
        self._repository = repository
        self._secret_sharing = secret_sharing
        self._managed_keys = managed_keys
        self._settings = settings
        self._metrics = metrics
        self._guardian_proof_verifier = GuardianDecisionProofVerifier()
        self._clock = clock
        self._ids = id_generator
        self._worker_id = worker_id or secure_id("worker")

    def create_guardian(
        self,
        principal: RecoveryPrincipal,
        *,
        wallet_id: str,
        guardian_user_id: str,
        display_name: str,
    ) -> Guardian:
        """Invites an account. It holds no authority until that account accepts
        with a key of its own, so nobody can register a DID for someone else."""
        principal.require(Permission.GUARDIAN_CREATE)
        self._managed_keys.verify_wallet_owner(
            wallet_id=wallet_id, owner_user_id=principal.user_id
        )
        if self._repository.get_active_request(wallet_id) is not None:
            raise RecoveryConflictError(
                "Guardian assignments cannot change during active recovery."
            )
        if guardian_user_id == principal.user_id:
            raise RecoveryValidationError("Wallet owners cannot be their own Guardian.")
        policy = self._repository.get_policy(wallet_id)
        guardians = self._repository.list_guardians(wallet_id=wallet_id)
        if any(
            item.guardian_user_id == guardian_user_id
            and item.status is not GuardianStatus.REMOVED
            for item in guardians
        ):
            raise RecoveryConflictError("Guardian assignment already exists.")
        maximum = (
            policy.maximum_guardians
            if policy is not None
            else self._settings.default_maximum_guardians
        )
        if sum(item.status is not GuardianStatus.REMOVED for item in guardians) >= maximum:
            raise RecoveryConflictError("Recovery policy Guardian capacity is full.")
        now = self._now()
        guardian = Guardian(
            guardian_id=self._ids("guardian"),
            owner_user_id=principal.user_id,
            wallet_id=wallet_id,
            guardian_user_id=guardian_user_id,
            guardian_did="",
            display_name=display_name.strip(),
            verification_method="",
            status=GuardianStatus.INVITED,
            created_at=now,
            updated_at=now,
            invitation_challenge=token_urlsafe(32),
            invitation_expires_at=now
            + timedelta(seconds=self._settings.guardian_invitation_ttl_seconds),
        )
        stored = self._repository.add_guardian(guardian)
        self._audit(
            RecoveryAuditEventType.GUARDIAN_INVITED,
            aggregate_id=stored.guardian_id,
            actor_id=principal.user_id,
            at=now,
            discriminator=str(stored.version),
            metadata={"walletId": wallet_id, "status": stored.status.value},
        )
        return stored

    def list_invitations(
        self, principal: RecoveryPrincipal
    ) -> tuple[Guardian, ...]:
        principal.require(Permission.GUARDIAN_READ)
        now = self._now()
        return tuple(
            item
            for item in self._repository.list_guardians(
                guardian_user_id=principal.user_id
            )
            if item.invitation_challenge is not None
            and item.invitation_expires_at is not None
            and item.invitation_expires_at > now
        )

    def accept_invitation(
        self,
        principal: RecoveryPrincipal,
        guardian_id: str,
        *,
        guardian_did: str,
        verification_method: str,
        proof: str,
    ) -> Guardian:
        principal.require(Permission.RECOVERY_APPROVE)
        guardian = self._assigned_guardian(principal, guardian_id)
        if guardian.status is not GuardianStatus.INVITED:
            raise RecoveryConflictError("This Guardian invitation is not open.")
        now = self._now()
        self._require_key_binding(
            guardian,
            guardian_did=guardian_did,
            verification_method=verification_method,
            proof=proof,
            now=now,
        )
        if self._changes_are_delayed(guardian.wallet_id):
            status = GuardianStatus.PENDING_ACTIVATION
            pending_status = GuardianStatus.ACTIVE
            effective_at = now + timedelta(
                seconds=self._settings.guardian_change_delay_seconds
            )
        else:
            status, pending_status, effective_at = (
                GuardianStatus.ACTIVE,
                None,
                None,
            )
        accepted = replace(
            replace(
                guardian,
                guardian_did=guardian_did,
                verification_method=verification_method,
            ).transition(status, at=now),
            invitation_challenge=None,
            invitation_expires_at=None,
            pending_status=pending_status,
            pending_effective_at=effective_at,
        )
        stored = self._repository.update_guardian(
            accepted, expected_version=guardian.version
        )
        self._audit(
            RecoveryAuditEventType.GUARDIAN_ACCEPTED,
            aggregate_id=stored.guardian_id,
            actor_id=principal.user_id,
            at=now,
            discriminator=str(stored.version),
            metadata={"walletId": stored.wallet_id, "status": stored.status.value},
        )
        self._refresh_guardian_metric()
        return stored

    def start_rebind(
        self, principal: RecoveryPrincipal, guardian_id: str
    ) -> Guardian:
        """Opens a fresh challenge for a Guardian whose key changed or was lost."""
        principal.require(Permission.RECOVERY_APPROVE)
        guardian = self._assigned_guardian(principal, guardian_id)
        if guardian.status is not GuardianStatus.ACTIVE:
            raise RecoveryConflictError("Only an active Guardian can rebind a key.")
        now = self._now()
        return self._repository.update_guardian(
            replace(
                guardian,
                invitation_challenge=token_urlsafe(32),
                invitation_expires_at=now
                + timedelta(seconds=self._settings.guardian_invitation_ttl_seconds),
                updated_at=now,
                version=guardian.version + 1,
            ),
            expected_version=guardian.version,
        )

    def complete_rebind(
        self,
        principal: RecoveryPrincipal,
        guardian_id: str,
        *,
        guardian_did: str,
        verification_method: str,
        proof: str,
    ) -> Guardian:
        principal.require(Permission.RECOVERY_APPROVE)
        guardian = self._assigned_guardian(principal, guardian_id)
        if guardian.status is not GuardianStatus.ACTIVE:
            raise RecoveryConflictError("Only an active Guardian can rebind a key.")
        if self._repository.get_active_request(guardian.wallet_id) is not None:
            raise RecoveryConflictError(
                "Guardian keys cannot change during active recovery."
            )
        now = self._now()
        self._require_key_binding(
            guardian,
            guardian_did=guardian_did,
            verification_method=verification_method,
            proof=proof,
            now=now,
        )
        delay = self._settings.guardian_change_delay_seconds
        rebound = replace(
            guardian,
            invitation_challenge=None,
            invitation_expires_at=None,
            pending_did=guardian_did,
            pending_verification_method=verification_method,
            pending_effective_at=now + timedelta(seconds=delay),
            updated_at=now,
            version=guardian.version + 1,
        )
        stored = self._repository.update_guardian(
            rebound, expected_version=guardian.version
        )
        self._audit(
            RecoveryAuditEventType.GUARDIAN_CHANGE_SCHEDULED,
            aggregate_id=stored.guardian_id,
            actor_id=principal.user_id,
            at=now,
            discriminator=str(stored.version),
            metadata={"walletId": stored.wallet_id, "change": "KEY_REBIND"},
        )
        self._apply_due_changes(stored.wallet_id)
        return self._repository.get_guardian(guardian_id) or stored

    def _assigned_guardian(
        self, principal: RecoveryPrincipal, guardian_id: str
    ) -> Guardian:
        guardian = self._repository.get_guardian(guardian_id)
        if guardian is None or guardian.guardian_user_id != principal.user_id:
            raise RecoveryNotFoundError("Guardian was not found.")
        return guardian

    def _require_key_binding(
        self,
        guardian: Guardian,
        *,
        guardian_did: str,
        verification_method: str,
        proof: str,
        now: datetime,
    ) -> None:
        if (
            guardian.invitation_challenge is None
            or guardian.invitation_expires_at is None
            or guardian.invitation_expires_at <= now
        ):
            raise RecoveryConflictError("This Guardian challenge has expired.")
        try:
            self._guardian_proof_verifier.verify_binding(
                proof,
                guardian_did=guardian_did,
                verification_method=verification_method,
                guardian_id=guardian.guardian_id,
                wallet_id=guardian.wallet_id,
                challenge=guardian.invitation_challenge,
                now=now,
            )
        except GuardianProofError as error:
            raise RecoveryConflictError("Guardian key proof is invalid.") from error
        if any(
            item.guardian_id != guardian.guardian_id
            and guardian_did in {item.guardian_did, item.pending_did}
            and item.status is not GuardianStatus.REMOVED
            for item in self._repository.list_guardians(wallet_id=guardian.wallet_id)
        ):
            raise RecoveryConflictError(
                "Each Guardian must use a key of their own."
            )
        self._managed_keys.require_unmanaged_did(
            did=guardian_did, user_id=guardian.guardian_user_id
        )

    def _changes_are_delayed(self, wallet_id: str) -> bool:
        """The first Guardians can join at once, because nothing is protected
        yet. After recovery works, every change gives the owner time to react."""
        if self._settings.guardian_change_delay_seconds <= 0:
            return False
        policy = self._repository.get_policy(wallet_id)
        minimum = (
            self._settings.default_minimum_approvals
            if policy is None
            else policy.minimum_approvals
        )
        active = sum(
            item.status is GuardianStatus.ACTIVE
            for item in self._repository.list_guardians(wallet_id=wallet_id)
        )
        return active >= minimum

    def _apply_due_changes(self, wallet_id: str) -> None:
        if self._repository.get_active_request(wallet_id) is not None:
            return
        now = self._now()
        for guardian in self._repository.list_guardians(wallet_id=wallet_id):
            if (
                guardian.pending_effective_at is None
                or guardian.pending_effective_at > now
            ):
                continue
            updated = guardian
            if guardian.pending_status is not None:
                updated = guardian.transition(guardian.pending_status, at=now)
            if guardian.pending_did is not None:
                updated = replace(
                    updated,
                    guardian_did=guardian.pending_did,
                    verification_method=(
                        guardian.pending_verification_method or ""
                    ),
                )
            updated = replace(
                updated,
                pending_status=None,
                pending_did=None,
                pending_verification_method=None,
                pending_effective_at=None,
                updated_at=now,
                version=guardian.version + 1,
            )
            stored = self._repository.update_guardian(
                updated, expected_version=guardian.version
            )
            self._audit(
                (
                    RecoveryAuditEventType.GUARDIAN_REBOUND
                    if guardian.pending_did is not None
                    else RecoveryAuditEventType.GUARDIAN_ACTIVATED
                ),
                aggregate_id=stored.guardian_id,
                actor_id="system:scheduled-change",
                at=now,
                discriminator=str(stored.version),
                metadata={"walletId": wallet_id, "status": stored.status.value},
            )
        policy = self._repository.get_policy(wallet_id)
        if (
            policy is not None
            and policy.pending_change is not None
            and policy.pending_effective_at is not None
            and policy.pending_effective_at <= now
        ):
            stored_policy = self._repository.upsert_policy(
                replace(
                    policy,
                    **_policy_fields(policy.pending_change),
                    pending_change=None,
                    pending_effective_at=None,
                    version=policy.version + 1,
                    updated_at=now,
                ),
                expected_version=policy.version,
            )
            self._audit(
                RecoveryAuditEventType.RECOVERY_POLICY_UPDATED,
                aggregate_id=stored_policy.policy_id,
                actor_id="system:scheduled-change",
                at=now,
                discriminator=str(stored_policy.version),
                metadata={"walletId": wallet_id},
            )

    def list_guardians(
        self,
        principal: RecoveryPrincipal,
        *,
        wallet_id: str | None = None,
    ) -> tuple[Guardian, ...]:
        principal.require(Permission.GUARDIAN_READ)
        if wallet_id is not None:
            self._apply_due_changes(wallet_id)
        owned = self._repository.list_guardians(
            wallet_id=wallet_id, owner_user_id=principal.user_id
        )
        assigned = self._repository.list_guardians(
            wallet_id=wallet_id, guardian_user_id=principal.user_id
        )
        by_id = {item.guardian_id: item for item in (*owned, *assigned)}
        return tuple(sorted(by_id.values(), key=lambda item: item.created_at))

    def get_guardian(
        self, principal: RecoveryPrincipal, guardian_id: str
    ) -> Guardian:
        principal.require(Permission.GUARDIAN_READ)
        guardian = self._repository.get_guardian(guardian_id)
        if guardian is None or principal.user_id not in {
            guardian.owner_user_id,
            guardian.guardian_user_id,
        }:
            raise RecoveryNotFoundError("Guardian was not found.")
        return guardian

    def update_guardian(
        self,
        principal: RecoveryPrincipal,
        guardian_id: str,
        *,
        display_name: str | None = None,
        status: GuardianStatus | None = None,
    ) -> Guardian:
        principal.require(Permission.GUARDIAN_UPDATE)
        guardian = self._owned_guardian(principal, guardian_id)
        if self._repository.get_active_request(guardian.wallet_id) is not None:
            raise RecoveryConflictError(
                "Guardian assignments cannot change during active recovery."
            )
        now = self._now()
        status_changed = status is not None and status is not guardian.status
        if (
            status_changed
            and guardian.status is GuardianStatus.ACTIVE
            and self._changes_are_delayed(guardian.wallet_id)
        ):
            scheduled = self._repository.update_guardian(
                replace(
                    guardian,
                    pending_status=status,
                    pending_effective_at=now
                    + timedelta(
                        seconds=self._settings.guardian_change_delay_seconds
                    ),
                    updated_at=now,
                    version=guardian.version + 1,
                ),
                expected_version=guardian.version,
            )
            self._audit(
                RecoveryAuditEventType.GUARDIAN_CHANGE_SCHEDULED,
                aggregate_id=scheduled.guardian_id,
                actor_id=principal.user_id,
                at=now,
                discriminator=str(scheduled.version),
                metadata={
                    "walletId": scheduled.wallet_id,
                    "change": str(status),
                },
            )
            return scheduled
        fields_changed = display_name is not None
        updated = guardian.transition(status, at=now) if status_changed else guardian
        if fields_changed:
            updated = replace(
                updated,
                display_name=(display_name or updated.display_name).strip(),
                updated_at=now,
                version=(updated.version if status_changed else guardian.version + 1),
            )
        if updated is guardian:
            return guardian
        stored = self._repository.update_guardian(
            updated, expected_version=guardian.version
        )
        event_type = {
            GuardianStatus.SUSPENDED: RecoveryAuditEventType.GUARDIAN_SUSPENDED,
            GuardianStatus.ACTIVE: RecoveryAuditEventType.GUARDIAN_RESUMED,
            GuardianStatus.REMOVED: RecoveryAuditEventType.GUARDIAN_REMOVED,
            GuardianStatus.REVOKED: RecoveryAuditEventType.GUARDIAN_UPDATED,
        }.get(status, RecoveryAuditEventType.GUARDIAN_UPDATED)
        self._audit(
            event_type,
            aggregate_id=stored.guardian_id,
            actor_id=principal.user_id,
            at=now,
            discriminator=str(stored.version),
            metadata={"walletId": stored.wallet_id, "status": stored.status.value},
        )
        self._refresh_guardian_metric()
        return stored

    def remove_guardian(
        self, principal: RecoveryPrincipal, guardian_id: str
    ) -> Guardian:
        principal.require(Permission.GUARDIAN_REMOVE)
        guardian = self._owned_guardian(principal, guardian_id)
        if guardian.status is GuardianStatus.REMOVED:
            return guardian
        return self.update_guardian(
            principal, guardian_id, status=GuardianStatus.REMOVED
        )

    def get_policy(
        self, principal: RecoveryPrincipal, *, wallet_id: str
    ) -> RecoveryPolicy:
        principal.require(Permission.RECOVERY_POLICY_READ)
        self._apply_due_changes(wallet_id)
        policy = self._repository.get_policy(wallet_id)
        if policy is None or policy.owner_user_id != principal.user_id:
            raise RecoveryNotFoundError("Recovery policy was not found.")
        return policy

    def put_policy(
        self,
        principal: RecoveryPrincipal,
        *,
        wallet_id: str,
        minimum_approvals: int,
        maximum_guardians: int,
        approval_window_seconds: int,
        time_lock_seconds: int,
        recovery_expiration_seconds: int,
        maximum_attempts: int,
        cooldown_seconds: int,
        allow_cancellation: bool,
    ) -> RecoveryPolicy:
        principal.require(Permission.RECOVERY_POLICY_UPDATE)
        self._managed_keys.verify_wallet_owner(
            wallet_id=wallet_id, owner_user_id=principal.user_id
        )
        if self._repository.get_active_request(wallet_id) is not None:
            raise RecoveryConflictError("Policy cannot change during active recovery.")
        guardians = self._repository.list_guardians(wallet_id=wallet_id)
        active = [item for item in guardians if item.status is GuardianStatus.ACTIVE]
        if len(active) > maximum_guardians:
            raise RecoveryValidationError("Policy maximum is below active Guardian count.")
        if minimum_approvals < self._settings.minimum_approvals_floor:
            raise RecoveryValidationError(
                "Recovery needs more independent Guardian approvals."
            )
        if time_lock_seconds < self._settings.time_lock_floor_seconds:
            raise RecoveryValidationError("Recovery time-lock is too short.")
        self._apply_due_changes(wallet_id)
        existing = self._repository.get_policy(wallet_id)
        now = self._now()
        requested = {
            "minimumApprovals": minimum_approvals,
            "maximumGuardians": maximum_guardians,
            "approvalWindowSeconds": approval_window_seconds,
            "timeLockSeconds": time_lock_seconds,
            "recoveryExpirationSeconds": recovery_expiration_seconds,
            "maximumAttempts": maximum_attempts,
            "cooldownSeconds": cooldown_seconds,
            "allowCancellation": allow_cancellation,
        }
        if (
            existing is not None
            and _weakens(existing, requested)
            and self._changes_are_delayed(wallet_id)
        ):
            scheduled = self._repository.upsert_policy(
                replace(
                    existing,
                    pending_change=requested,
                    pending_effective_at=now
                    + timedelta(
                        seconds=self._settings.guardian_change_delay_seconds
                    ),
                    version=existing.version + 1,
                    updated_at=now,
                ),
                expected_version=existing.version,
            )
            self._audit(
                RecoveryAuditEventType.RECOVERY_POLICY_CHANGE_SCHEDULED,
                aggregate_id=scheduled.policy_id,
                actor_id=principal.user_id,
                at=now,
                discriminator=str(scheduled.version),
                metadata={"walletId": wallet_id},
            )
            return scheduled
        policy = RecoveryPolicy(
            policy_id=existing.policy_id if existing else self._ids("policy"),
            wallet_id=wallet_id,
            owner_user_id=principal.user_id,
            minimum_approvals=minimum_approvals,
            maximum_guardians=maximum_guardians,
            approval_window_seconds=approval_window_seconds,
            time_lock_seconds=time_lock_seconds,
            recovery_expiration_seconds=recovery_expiration_seconds,
            maximum_attempts=maximum_attempts,
            cooldown_seconds=cooldown_seconds,
            allow_cancellation=allow_cancellation,
            version=1 if existing is None else existing.version + 1,
            created_at=now if existing is None else existing.created_at,
            updated_at=now,
        )
        stored = self._repository.upsert_policy(
            policy,
            expected_version=None if existing is None else existing.version,
        )
        self._audit(
            RecoveryAuditEventType.RECOVERY_POLICY_UPDATED,
            aggregate_id=stored.policy_id,
            actor_id=principal.user_id,
            at=now,
            discriminator=str(stored.version),
            metadata={
                "walletId": wallet_id,
                "threshold": str(stored.minimum_approvals),
                "maximumGuardians": str(stored.maximum_guardians),
            },
        )
        return stored

    def create_request(
        self,
        principal: RecoveryPrincipal,
        *,
        wallet_id: str,
        reason: RecoveryReason,
    ) -> RecoveryRequest:
        started = perf_counter()
        principal.require(Permission.RECOVERY_REQUEST_CREATE)
        self._managed_keys.verify_wallet_owner(
            wallet_id=wallet_id, owner_user_id=principal.user_id
        )
        if self._repository.get_active_request(wallet_id) is not None:
            raise RecoveryConflictError("An active recovery request already exists.")
        self._apply_due_changes(wallet_id)
        policy = self._repository.get_policy(wallet_id)
        if policy is None:
            policy = self._create_default_policy(principal, wallet_id=wallet_id)
        if policy.owner_user_id != principal.user_id:
            raise RecoveryNotFoundError("Recovery policy was not found.")
        now = self._now()
        self._require_cooldown_elapsed(policy, now=now)
        guardians = tuple(
            sorted(
                (
                    item
                    for item in self._repository.list_guardians(wallet_id=wallet_id)
                    if item.status is GuardianStatus.ACTIVE
                ),
                key=lambda item: item.guardian_id,
            )
        )
        if not policy.minimum_approvals <= len(guardians) <= policy.maximum_guardians:
            raise RecoveryConflictError("Active Guardians cannot satisfy the recovery policy.")
        request_id = self._ids("recovery")
        session_id = self._ids("session")
        # Share sets are unique per (policy, policy version, share version); every
        # new request under an unchanged policy needs the next share version.
        share_version = 1 + max(
            (
                item.policy.share_version
                for item in self._repository.list_requests(
                    owner_user_id=principal.user_id, limit=100
                )
                if item.wallet_id == wallet_id
                and item.policy.policy_id == policy.policy_id
                and item.policy.policy_version == policy.version
            ),
            default=0,
        )
        context = SecretSharingContext(
            recovery_request_id=request_id,
            policy_id=policy.policy_id,
            policy_version=policy.version,
            share_version=share_version,
        )
        secret = bytearray(token_bytes(16))
        try:
            split = self._secret_sharing.split(
                bytes(secret),
                threshold=policy.minimum_approvals,
                guardian_ids=tuple(item.guardian_id for item in guardians),
                context=context,
                created_at=now,
            )
        finally:
            for index in range(len(secret)):
                secret[index] = 0
        challenge_value = token_urlsafe(32)
        nonce_value = token_urlsafe(32)
        approval_expires_at = now + timedelta(
            seconds=policy.approval_window_seconds
        )
        expires_at = now + timedelta(seconds=policy.recovery_expiration_seconds)
        snapshot = RecoveryPolicySnapshot(
            policy_id=policy.policy_id,
            policy_version=policy.version,
            minimum_approvals=policy.minimum_approvals,
            maximum_guardians=policy.maximum_guardians,
            approval_window_seconds=policy.approval_window_seconds,
            time_lock_seconds=policy.time_lock_seconds,
            recovery_expiration_seconds=policy.recovery_expiration_seconds,
            maximum_attempts=policy.maximum_attempts,
            allow_cancellation=policy.allow_cancellation,
            guardian_ids=tuple(item.guardian_id for item in guardians),
            share_version=context.share_version,
            secret_commitment=split.commitment,
        )
        request = RecoveryRequest(
            request_id=request_id,
            owner_user_id=principal.user_id,
            wallet_id=wallet_id,
            reason=reason,
            operation=RecoveryOperation.MANAGED_KEY_ROTATION,
            policy=snapshot,
            challenge=RecoveryChallenge(
                value=challenge_value, digest=_digest(challenge_value)
            ),
            nonce=RecoveryNonce(value=nonce_value, digest=_digest(nonce_value)),
            session=RecoverySession(
                session_id=session_id,
                state=RecoveryState.PENDING_APPROVALS,
                created_at=now,
                updated_at=now,
                approval_expires_at=approval_expires_at,
                expires_at=expires_at,
                quorum=RecoveryQuorum(
                    required=policy.minimum_approvals,
                    approvals=0,
                    rejections=0,
                ),
            ),
            created_at=now,
            updated_at=now,
            risk=self._assess_risk(wallet_id=wallet_id, reason=reason),
        )
        self._repository.save_share_set(split.shares)
        stored = self._repository.add_request(request)
        self._audit(
            RecoveryAuditEventType.RECOVERY_REQUESTED,
            aggregate_id=stored.request_id,
            actor_id=principal.user_id,
            at=now,
            discriminator=str(stored.version),
            metadata={
                "walletId": wallet_id,
                "reason": reason.value,
                "threshold": str(snapshot.minimum_approvals),
                "guardianCount": str(len(snapshot.guardian_ids)),
            },
        )
        if stored.risk.status is RiskHoldStatus.ON_HOLD:
            self._audit(
                RecoveryAuditEventType.RECOVERY_RISK_HOLD,
                aggregate_id=stored.request_id,
                actor_id="system:risk",
                at=now,
                discriminator="created",
                metadata={"walletId": wallet_id, "level": stored.risk.level},
            )
        self._metrics.increment("requests")
        self._metrics.observe("request_creation_seconds", perf_counter() - started)
        return stored

    def get_request(
        self, principal: RecoveryPrincipal, request_id: str
    ) -> RecoveryRequest:
        principal.require(Permission.RECOVERY_REQUEST_READ)
        request = self._repository.get_request(request_id)
        if request is None or not self._can_read(principal, request):
            raise RecoveryNotFoundError("Recovery request was not found.")
        return request

    def list_requests(
        self, principal: RecoveryPrincipal, *, limit: int = 100
    ) -> tuple[RecoveryRequest, ...]:
        principal.require(Permission.RECOVERY_REQUEST_READ)
        owned = self._repository.list_requests(
            owner_user_id=principal.user_id, limit=limit
        )
        assigned = self._repository.list_requests(
            guardian_user_id=principal.user_id, limit=limit
        )
        by_id = {item.request_id: item for item in (*owned, *assigned)}
        return tuple(
            sorted(by_id.values(), key=lambda item: item.created_at, reverse=True)[:limit]
        )

    def get_timeline(
        self, principal: RecoveryPrincipal, request_id: str
    ) -> tuple[RecoveryAuditEvent, ...]:
        """Audit timeline for the owner or an assigned Guardian of the request."""
        request = self.get_request(principal, request_id)
        return self._repository.list_audit_events(request.request_id)

    def list_oversight(
        self,
        principal: RecoveryPrincipal,
        *,
        states: tuple[RecoveryState, ...] | None = None,
        limit: int = 100,
    ) -> tuple[RecoveryRequest, ...]:
        """Admin read-only case list. Admins cannot vote, cancel or bypass."""
        principal.require(Permission.RECOVERY_OVERSIGHT_READ)
        return self._repository.list_requests(states=states, limit=limit)

    def get_oversight(
        self, principal: RecoveryPrincipal, request_id: str
    ) -> tuple[RecoveryRequest, tuple[RecoveryAuditEvent, ...]]:
        principal.require(Permission.RECOVERY_OVERSIGHT_READ)
        request = self._repository.get_request(request_id)
        if request is None:
            raise RecoveryNotFoundError("Recovery request was not found.")
        return request, self._repository.list_audit_events(request_id)

    def approve(
        self,
        principal: RecoveryPrincipal,
        request_id: str,
        *,
        guardian_id: str,
        challenge: str,
        proof: str,
    ) -> tuple[RecoveryApproval, RecoveryRequest]:
        principal.require(Permission.RECOVERY_APPROVE)
        return self._decide(
            principal,
            request_id,
            guardian_id=guardian_id,
            challenge=challenge,
            proof=proof,
            decision=RecoveryDecision.APPROVE,
        )

    def reject(
        self,
        principal: RecoveryPrincipal,
        request_id: str,
        *,
        guardian_id: str,
        challenge: str,
        proof: str,
    ) -> tuple[RecoveryApproval, RecoveryRequest]:
        principal.require(Permission.RECOVERY_REJECT)
        return self._decide(
            principal,
            request_id,
            guardian_id=guardian_id,
            challenge=challenge,
            proof=proof,
            decision=RecoveryDecision.REJECT,
        )

    def cancel(
        self, principal: RecoveryPrincipal, request_id: str
    ) -> RecoveryRequest:
        principal.require(Permission.RECOVERY_REQUEST_CANCEL)
        request = self._repository.get_request(request_id)
        if request is None or request.owner_user_id != principal.user_id:
            raise RecoveryNotFoundError("Recovery request was not found.")
        if request.session.state is RecoveryState.CANCELLED:
            return request
        if not request.policy.allow_cancellation:
            raise RecoveryConflictError("Recovery policy does not allow cancellation.")
        if request.session.state in {
            RecoveryState.EXECUTING,
            RecoveryState.RECONCILIATION_REQUIRED,
        } or request.session.state.terminal:
            raise RecoveryConflictError("Recovery can no longer be cancelled.")
        now = self._now()
        cancelled = request.transition(RecoveryState.CANCELLED, at=now)
        stored = self._repository.update_request(
            cancelled, expected_version=request.version
        )
        self._audit(
            RecoveryAuditEventType.RECOVERY_CANCELLED,
            aggregate_id=request_id,
            actor_id=principal.user_id,
            at=now,
            discriminator=str(stored.version),
            metadata={"walletId": stored.wallet_id},
        )
        self._metrics.increment("cancellations")
        return stored

    def reconcile_request(
        self, principal: RecoveryPrincipal, request_id: str
    ) -> RecoveryRequest:
        principal.require(Permission.RECOVERY_RECONCILE)
        return self._reconcile_one(request_id, actor_id=principal.user_id)

    def reconcile_due(self) -> tuple[int, int]:
        now = self._now()
        candidates = self._repository.list_reconciliation_candidates(
            now=now,
            stale_before=now
            - timedelta(seconds=self._settings.reconciliation_stale_seconds),
            limit=self._settings.reconciliation_batch_size,
        )
        succeeded = 0
        failed = 0
        for candidate in candidates:
            self._metrics.increment("reconciliation_attempts")
            try:
                self._reconcile_one(candidate.request_id, actor_id=self._worker_id)
                succeeded += 1
                self._metrics.increment("reconciliation_successes")
            except Exception:
                failed += 1
                self._metrics.increment("reconciliation_failures")
        return succeeded, failed

    def _decide(
        self,
        principal: RecoveryPrincipal,
        request_id: str,
        *,
        guardian_id: str,
        challenge: str,
        proof: str,
        decision: RecoveryDecision,
    ) -> tuple[RecoveryApproval, RecoveryRequest]:
        started = perf_counter()
        request = self._repository.get_request(request_id)
        guardian = self._repository.get_guardian(guardian_id)
        if (
            request is None
            or guardian is None
            or guardian.guardian_user_id != principal.user_id
            or guardian.wallet_id != request.wallet_id
            or guardian_id not in request.policy.guardian_ids
            or principal.user_id == request.owner_user_id
            or guardian.guardian_user_id == request.owner_user_id
        ):
            self._audit_unauthorized(request_id, principal.user_id)
            raise RecoveryNotFoundError("Recovery request was not found.")
        proof_digest = _digest(proof)
        existing = next(
            (
                item
                for item in self._repository.list_approvals(request_id)
                if item.guardian_id == guardian_id
            ),
            None,
        )
        if existing is not None:
            if (
                existing.decision is not decision
                or existing.challenge_digest != _digest(challenge)
            ):
                raise RecoveryConflictError("Guardian already submitted another decision.")
            if existing.proof_digest == proof_digest:
                return existing, request
        now = self._now()
        supplied_digest = _digest(challenge)
        if not compare_digest(supplied_digest, request.challenge.digest):
            self._audit_unauthorized(request_id, principal.user_id)
            raise RecoveryConflictError("Recovery challenge does not match.")
        try:
            self._guardian_proof_verifier.verify(
                proof,
                guardian_did=guardian.guardian_did,
                verification_method=guardian.verification_method,
                guardian_id=guardian.guardian_id,
                request_id=request.request_id,
                session_id=request.session.session_id,
                wallet_id=request.wallet_id,
                decision=decision.value,
                challenge=challenge,
                policy_hash=policy_hash(request),
                now=now,
            )
        except GuardianProofError as error:
            self._audit(
                RecoveryAuditEventType.GUARDIAN_PROOF_REJECTED,
                aggregate_id=request_id,
                actor_id=principal.user_id,
                at=now,
                discriminator=proof_digest,
                metadata={"guardianId": guardian_id},
            )
            raise RecoveryConflictError("Guardian DID proof is invalid.") from error
        if existing is not None:
            return existing, request
        if request.session.state is not RecoveryState.PENDING_APPROVALS:
            raise RecoveryConflictError("Recovery is not accepting Guardian decisions.")
        if now >= request.session.approval_expires_at or now >= request.session.expires_at:
            self._expire(request, actor_id=principal.user_id, at=now)
            raise RecoveryConflictError("Recovery approval window has expired.")
        if not guardian.can_approve:
            raise RecoveryConflictError("Guardian is not active.")
        context = self._sharing_context(request)
        share = self._share_for(request, guardian_id)
        try:
            self._secret_sharing.validate_share(share, context=context)
        except SecretShareError:
            self._metrics.increment("share_validation_failures")
            self._audit(
                RecoveryAuditEventType.SECRET_SHARE_VALIDATION_FAILED,
                aggregate_id=request_id,
                actor_id=principal.user_id,
                at=now,
                discriminator=guardian_id,
                metadata={"guardianId": guardian_id},
            )
            raise
        approval = RecoveryApproval(
            approval_id=(
                "approval_"
                + sha256(f"{request_id}:{guardian_id}".encode()).hexdigest()[:32]
            ),
            request_id=request_id,
            session_id=request.session.session_id,
            guardian_id=guardian_id,
            guardian_user_id=principal.user_id,
            wallet_id=request.wallet_id,
            decision=decision,
            challenge_digest=supplied_digest,
            proof_digest=proof_digest,
            decided_at=now,
            created_at=now,
        )
        stored_approval, created = self._repository.add_approval_idempotently(approval)
        if created:
            event_type = (
                RecoveryAuditEventType.RECOVERY_APPROVED
                if decision is RecoveryDecision.APPROVE
                else RecoveryAuditEventType.RECOVERY_REJECTED
            )
            self._audit(
                event_type,
                aggregate_id=request_id,
                actor_id=principal.user_id,
                at=now,
                discriminator=guardian_id,
                metadata={
                    "guardianId": guardian_id,
                    "decision": decision.value,
                },
            )
            self._metrics.increment(
                "approvals" if decision is RecoveryDecision.APPROVE else "rejections"
            )
        current = self._recalculate_quorum(request_id, now=now)
        self._metrics.observe("approval_processing_seconds", perf_counter() - started)
        return stored_approval, current

    def _recalculate_quorum(
        self, request_id: str, *, now: datetime
    ) -> RecoveryRequest:
        started = perf_counter()
        for _ in range(8):
            request = self._repository.get_request(request_id)
            if request is None:
                raise RecoveryNotFoundError("Recovery request was not found.")
            if request.session.state is not RecoveryState.PENDING_APPROVALS:
                return request
            approvals = self._repository.list_approvals(request_id)
            valid = []
            for approval in approvals:
                guardian = self._repository.get_guardian(approval.guardian_id)
                if (
                    guardian is not None
                    and guardian.status is GuardianStatus.ACTIVE
                    and guardian.guardian_id in request.policy.guardian_ids
                    and guardian.wallet_id == request.wallet_id
                ):
                    valid.append(approval)
            approval_count = sum(
                item.decision is RecoveryDecision.APPROVE for item in valid
            )
            rejection_count = sum(
                item.decision is RecoveryDecision.REJECT for item in valid
            )
            reached = approval_count >= request.policy.minimum_approvals
            quorum = RecoveryQuorum(
                required=request.policy.minimum_approvals,
                approvals=approval_count,
                rejections=rejection_count,
                reached_at=now if reached else None,
            )
            try:
                if reached:
                    quorum_state = request.transition(
                        RecoveryState.QUORUM_REACHED,
                        at=now,
                        session_changes={
                            "quorum": quorum,
                            "quorum_reached_at": now,
                        },
                    )
                    quorum_state = self._repository.update_request(
                        quorum_state, expected_version=request.version
                    )
                    self._audit(
                        RecoveryAuditEventType.RECOVERY_QUORUM_REACHED,
                        aggregate_id=request_id,
                        actor_id=self._worker_id,
                        at=now,
                        discriminator="quorum",
                        metadata={"approvalCount": str(approval_count)},
                    )
                    self._metrics.increment("quorum_reached")
                    executable_after = now + timedelta(
                        seconds=request.policy.time_lock_seconds
                    )
                    waiting = quorum_state.transition(
                        RecoveryState.WAITING_TIMELOCK,
                        at=now,
                        session_changes={
                            "time_lock_started_at": now,
                            "executable_after": executable_after,
                        },
                    )
                    stored = self._repository.update_request(
                        waiting, expected_version=quorum_state.version
                    )
                    self._audit(
                        RecoveryAuditEventType.RECOVERY_TIMELOCK_STARTED,
                        aggregate_id=request_id,
                        actor_id=self._worker_id,
                        at=now,
                        discriminator="timelock",
                        metadata={
                            "timeLockSeconds": str(request.policy.time_lock_seconds)
                        },
                    )
                    self._metrics.observe(
                        "quorum_calculation_seconds", perf_counter() - started
                    )
                    return stored
                if len(request.policy.guardian_ids) - rejection_count < (
                    request.policy.minimum_approvals
                ):
                    rejected = request.transition(
                        RecoveryState.REJECTED,
                        at=now,
                        session_changes={"quorum": quorum},
                    )
                    stored = self._repository.update_request(
                        rejected, expected_version=request.version
                    )
                    self._metrics.observe(
                        "quorum_calculation_seconds", perf_counter() - started
                    )
                    return stored
                updated = replace(
                    request,
                    session=replace(
                        request.session, quorum=quorum, updated_at=now
                    ),
                    updated_at=now,
                    version=request.version + 1,
                )
                stored = self._repository.update_request(
                    updated, expected_version=request.version
                )
                self._metrics.observe(
                    "quorum_calculation_seconds", perf_counter() - started
                )
                return stored
            except RecoveryConflictError:
                continue
        raise RecoveryConflictError("Concurrent quorum calculation did not converge.")

    def _reconcile_one(self, request_id: str, *, actor_id: str) -> RecoveryRequest:
        for _ in range(6):
            request = self._repository.get_request(request_id)
            if request is None:
                raise RecoveryNotFoundError("Recovery request was not found.")
            if request.session.state.terminal:
                return request
            now = self._now()
            try:
                if now >= request.session.expires_at or (
                    request.session.state is RecoveryState.PENDING_APPROVALS
                    and now >= request.session.approval_expires_at
                ):
                    return self._expire(request, actor_id=actor_id, at=now)
                if request.session.state is RecoveryState.QUORUM_REACHED:
                    time_lock_started_at = (
                        request.session.quorum_reached_at or request.updated_at
                    )
                    executable_after = time_lock_started_at + timedelta(
                        seconds=request.policy.time_lock_seconds
                    )
                    waiting = request.transition(
                        RecoveryState.WAITING_TIMELOCK,
                        at=now,
                        session_changes={
                            "time_lock_started_at": time_lock_started_at,
                            "executable_after": executable_after,
                        },
                    )
                    stored = self._repository.update_request(
                        waiting, expected_version=request.version
                    )
                    self._audit(
                        RecoveryAuditEventType.RECOVERY_TIMELOCK_STARTED,
                        aggregate_id=request_id,
                        actor_id=actor_id,
                        at=now,
                        discriminator="timelock",
                        metadata={
                            "timeLockSeconds": str(
                                request.policy.time_lock_seconds
                            )
                        },
                    )
                    return stored
                if (
                    request.session.state is RecoveryState.WAITING_TIMELOCK
                    and request.session.executable_after is not None
                    and now >= request.session.executable_after
                ):
                    started = perf_counter()
                    ready = request.transition(
                        RecoveryState.READY_FOR_EXECUTION, at=now
                    )
                    ready = self._repository.update_request(
                        ready, expected_version=request.version
                    )
                    self._audit(
                        RecoveryAuditEventType.RECOVERY_READY,
                        aggregate_id=request_id,
                        actor_id=actor_id,
                        at=now,
                        discriminator="ready",
                        metadata={},
                    )
                    self._metrics.observe(
                        "timelock_processing_seconds", perf_counter() - started
                    )
                    return self._execute(ready, actor_id=actor_id)
                if request.session.state is RecoveryState.READY_FOR_EXECUTION:
                    return self._execute(request, actor_id=actor_id)
                if request.session.state is RecoveryState.EXECUTING:
                    lease = request.session.lease
                    if lease is not None and lease.expires_at > now:
                        return request
                    failure = RecoveryFailure(
                        code="STALE_EXECUTION_LEASE",
                        retryable=True,
                        occurred_at=now,
                        attempt=max(1, request.session.attempt_count),
                    )
                    stale = request.transition(
                        RecoveryState.RECONCILIATION_REQUIRED,
                        at=now,
                        session_changes={"lease": None, "failure": failure},
                    )
                    return self._repository.update_request(
                        stale, expected_version=request.version
                    )
                if request.session.state is RecoveryState.RECONCILIATION_REQUIRED:
                    ready = request.transition(
                        RecoveryState.READY_FOR_EXECUTION,
                        at=now,
                        session_changes={"lease": None},
                    )
                    ready = self._repository.update_request(
                        ready, expected_version=request.version
                    )
                    self._audit(
                        RecoveryAuditEventType.RECOVERY_RECONCILED,
                        aggregate_id=request_id,
                        actor_id=actor_id,
                        at=now,
                        discriminator=str(ready.version),
                        metadata={},
                    )
                    return self._execute(ready, actor_id=actor_id)
                return request
            except RecoveryConflictError:
                continue
        raise RecoveryConflictError("Recovery reconciliation did not converge.")

    def _execute(
        self, request: RecoveryRequest, *, actor_id: str
    ) -> RecoveryRequest:
        if request.session.state is not RecoveryState.READY_FOR_EXECUTION:
            return request
        if request.risk.status is RiskHoldStatus.ON_HOLD:
            return request
        now = self._now()
        attempt = request.session.attempt_count + 1
        lease = RecoveryLease(
            worker_id=self._worker_id,
            acquired_at=now,
            expires_at=now
            + timedelta(seconds=self._settings.reconciliation_lease_seconds),
            attempt=attempt,
        )
        claimed = request.transition(
            RecoveryState.EXECUTING,
            at=now,
            session_changes={"lease": lease, "attempt_count": attempt},
        )
        claimed = self._repository.update_request(
            claimed, expected_version=request.version
        )
        self._audit(
            RecoveryAuditEventType.RECOVERY_EXECUTION_STARTED,
            aggregate_id=request.request_id,
            actor_id=actor_id,
            at=now,
            discriminator=str(attempt),
            metadata={"attempt": str(attempt)},
        )
        execution_started = perf_counter()
        try:
            approvals = tuple(
                item
                for item in self._repository.list_approvals(request.request_id)
                if item.decision is RecoveryDecision.APPROVE
                and self._guardian_still_active(item.guardian_id, request)
            )
            if len(approvals) < request.policy.minimum_approvals:
                raise SecretShareError("Active Guardian quorum is no longer valid.")
            shares = tuple(
                self._share_for(request, item.guardian_id) for item in approvals
            )
            recovered = bytearray(
                self._secret_sharing.combine(
                    shares,
                    threshold=request.policy.minimum_approvals,
                    context=self._sharing_context(request),
                    expected_commitment=request.policy.secret_commitment,
                )
            )
            try:
                if len(recovered) != 16:
                    raise SecretShareError("Recovery authorization secret is invalid.")
                rotation_started = perf_counter()
                outcome = self._managed_keys.rotate_for_recovery(
                    request_id=request.request_id,
                    wallet_id=request.wallet_id,
                    owner_user_id=request.owner_user_id,
                    reason=request.reason,
                )
                rotation_seconds = perf_counter() - rotation_started
            finally:
                for index in range(len(recovered)):
                    recovered[index] = 0
            completed_at = self._now()
            if outcome.predecessor_did.startswith("did:key:") and (
                outcome.predecessor_did == outcome.successor_did
            ):
                raise RecoveryConflictError("did:key recovery requires a successor DID.")
            result = RecoveryResult(
                predecessor_key_id=outcome.predecessor_key_id,
                successor_key_id=outcome.successor_key_id,
                predecessor_did=outcome.predecessor_did,
                successor_did=outcome.successor_did,
                provider=outcome.provider,
                completed_at=completed_at,
                key_rotation_duration_ms=rotation_seconds * 1000,
            )
            completed = claimed.transition(
                RecoveryState.COMPLETED,
                at=completed_at,
                session_changes={"lease": None, "result": result, "failure": None},
            )
            stored = self._repository.update_request(
                completed, expected_version=claimed.version
            )
            self._audit(
                RecoveryAuditEventType.RECOVERY_NEW_KEY_PROVISIONED,
                aggregate_id=request.request_id,
                actor_id=actor_id,
                at=completed_at,
                discriminator=outcome.successor_key_id,
                metadata={"provider": outcome.provider},
            )
            if outcome.predecessor_did != outcome.successor_did:
                self._audit(
                    RecoveryAuditEventType.RECOVERY_DID_CHANGED,
                    aggregate_id=request.request_id,
                    actor_id=actor_id,
                    at=completed_at,
                    discriminator=outcome.successor_did,
                    metadata={"method": outcome.successor_did.split(":", 2)[1]},
                )
            self._audit(
                RecoveryAuditEventType.RECOVERY_COMPLETED,
                aggregate_id=request.request_id,
                actor_id=actor_id,
                at=completed_at,
                discriminator="completed",
                metadata={"reason": request.reason.value},
            )
            self._metrics.increment("successes")
            self._metrics.observe("key_rotation_seconds", rotation_seconds)
            self._metrics.observe(
                "execution_seconds", perf_counter() - execution_started
            )
            return stored
        except SecretShareError:
            self._metrics.increment("share_validation_failures")
            return self._record_execution_failure(
                claimed,
                actor_id=actor_id,
                code="RECOVERY_AUTHORIZATION_INVALID",
                retryable=False,
            )
        except Exception:
            return self._record_execution_failure(
                claimed,
                actor_id=actor_id,
                code="RECOVERY_EXECUTION_FAILED",
                retryable=True,
            )

    def _record_execution_failure(
        self,
        request: RecoveryRequest,
        *,
        actor_id: str,
        code: str,
        retryable: bool,
    ) -> RecoveryRequest:
        now = self._now()
        attempt = request.session.attempt_count
        exhausted = attempt >= request.policy.maximum_attempts
        target = (
            RecoveryState.RECONCILIATION_REQUIRED
            if retryable and not exhausted
            else RecoveryState.FAILED
        )
        failed = request.transition(
            target,
            at=now,
            session_changes={
                "lease": None,
                "failure": RecoveryFailure(
                    code=code,
                    retryable=retryable and not exhausted,
                    occurred_at=now,
                    attempt=attempt,
                ),
            },
        )
        stored = self._repository.update_request(
            failed, expected_version=request.version
        )
        self._audit(
            RecoveryAuditEventType.RECOVERY_FAILED,
            aggregate_id=request.request_id,
            actor_id=actor_id,
            at=now,
            discriminator=f"{attempt}:{code}",
            metadata={"errorCode": code, "retryable": str(not exhausted).lower()},
        )
        self._metrics.increment("failures")
        return stored

    def _expire(
        self, request: RecoveryRequest, *, actor_id: str, at: datetime
    ) -> RecoveryRequest:
        if request.session.state is RecoveryState.EXPIRED:
            return request
        expired = request.transition(RecoveryState.EXPIRED, at=at)
        stored = self._repository.update_request(
            expired, expected_version=request.version
        )
        self._audit(
            RecoveryAuditEventType.RECOVERY_EXPIRED,
            aggregate_id=request.request_id,
            actor_id=actor_id,
            at=at,
            discriminator="expired",
            metadata={},
        )
        self._metrics.increment("expirations")
        return stored

    def _create_default_policy(
        self, principal: RecoveryPrincipal, *, wallet_id: str
    ) -> RecoveryPolicy:
        return self.put_policy(
            principal,
            wallet_id=wallet_id,
            minimum_approvals=self._settings.default_minimum_approvals,
            maximum_guardians=self._settings.default_maximum_guardians,
            approval_window_seconds=self._settings.default_approval_window_seconds,
            time_lock_seconds=self._settings.default_time_lock_seconds,
            recovery_expiration_seconds=self._settings.default_expiration_seconds,
            maximum_attempts=self._settings.default_maximum_attempts,
            cooldown_seconds=self._settings.default_cooldown_seconds,
            allow_cancellation=True,
        )

    def _require_cooldown_elapsed(
        self, policy: RecoveryPolicy, *, now: datetime
    ) -> None:
        previous = (
            item
            for item in self._repository.list_requests(
                owner_user_id=policy.owner_user_id, limit=100
            )
            if item.wallet_id == policy.wallet_id and item.session.state.terminal
        )
        latest = max((item.updated_at for item in previous), default=None)
        if latest is not None and now < latest + timedelta(seconds=policy.cooldown_seconds):
            raise RecoveryConflictError("Recovery cooldown has not elapsed.")

    def _owned_guardian(
        self, principal: RecoveryPrincipal, guardian_id: str
    ) -> Guardian:
        guardian = self._repository.get_guardian(guardian_id)
        if guardian is None or guardian.owner_user_id != principal.user_id:
            raise RecoveryNotFoundError("Guardian was not found.")
        return guardian

    def _can_read(
        self, principal: RecoveryPrincipal, request: RecoveryRequest
    ) -> bool:
        if request.owner_user_id == principal.user_id:
            return True
        return any(
            guardian.guardian_user_id == principal.user_id
            and guardian.guardian_id in request.policy.guardian_ids
            for guardian in self._repository.list_guardians(
                guardian_user_id=principal.user_id
            )
        )

    def _guardian_still_active(
        self, guardian_id: str, request: RecoveryRequest
    ) -> bool:
        guardian = self._repository.get_guardian(guardian_id)
        return (
            guardian is not None
            and guardian.status is GuardianStatus.ACTIVE
            and guardian.wallet_id == request.wallet_id
            and guardian_id in request.policy.guardian_ids
        )

    def _share_for(
        self, request: RecoveryRequest, guardian_id: str
    ) -> RecoverySecretShareMetadata:
        share = self._repository.get_share(
            policy_id=request.policy.policy_id,
            policy_version=request.policy.policy_version,
            share_version=request.policy.share_version,
            guardian_id=guardian_id,
        )
        if share is None or share.recovery_request_id != request.request_id:
            raise SecretShareError("Recovery share was not found.")
        return share

    @staticmethod
    def _sharing_context(request: RecoveryRequest) -> SecretSharingContext:
        return SecretSharingContext(
            recovery_request_id=request.request_id,
            policy_id=request.policy.policy_id,
            policy_version=request.policy.policy_version,
            share_version=request.policy.share_version,
        )

    def _refresh_guardian_metric(self) -> None:
        self._metrics.set_active_guardians(
            self._repository.count_active_guardians()
        )

    def _audit_unauthorized(self, request_id: str, actor_id: str) -> None:
        self._audit(
            RecoveryAuditEventType.UNAUTHORIZED_RECOVERY_ATTEMPT,
            aggregate_id=request_id,
            actor_id=actor_id,
            at=self._now(),
            discriminator=self._ids("attempt"),
            metadata={},
        )

    def _audit(
        self,
        event_type: RecoveryAuditEventType,
        *,
        aggregate_id: str,
        actor_id: str,
        at: datetime,
        discriminator: str,
        metadata: dict[str, str],
    ) -> None:
        event_id = "recovery_audit_" + sha256(
            f"{event_type.value}:{aggregate_id}:{discriminator}".encode()
        ).hexdigest()
        self._repository.append_audit_idempotently(
            RecoveryAuditEvent(
                event_id=event_id,
                event_type=event_type,
                aggregate_id=aggregate_id,
                actor_id=actor_id,
                occurred_at=at,
                metadata=metadata,
            )
        )
        if event_type in _NOTIFIED_EVENTS:
            self._notify(event_id, event_type, aggregate_id, at, metadata)

    def _notify(
        self,
        event_id: str,
        event_type: RecoveryAuditEventType,
        aggregate_id: str,
        at: datetime,
        metadata: dict[str, str],
    ) -> None:
        wallet_id = metadata.get("walletId", "")
        recipients: set[str] = set()
        request = self._repository.get_request(aggregate_id)
        guardian = self._repository.get_guardian(aggregate_id)
        if request is not None:
            wallet_id = request.wallet_id
            recipients.add(request.owner_user_id)
            for guardian_id in request.policy.guardian_ids:
                assigned = self._repository.get_guardian(guardian_id)
                if assigned is not None:
                    recipients.add(assigned.guardian_user_id)
        elif guardian is not None:
            wallet_id = guardian.wallet_id
            recipients.update({guardian.owner_user_id, guardian.guardian_user_id})
        elif wallet_id:
            policy = self._repository.get_policy(wallet_id)
            if policy is not None:
                recipients.add(policy.owner_user_id)
            recipients.update(
                item.guardian_user_id
                for item in self._repository.list_guardians(wallet_id=wallet_id)
                if item.status is GuardianStatus.ACTIVE
            )
        for user_id in recipients:
            self._repository.add_notification(
                RecoveryNotification(
                    notification_id="notice_"
                    + sha256(f"{event_id}:{user_id}".encode()).hexdigest()[:40],
                    recipient_user_id=user_id,
                    event_type=event_type.value,
                    aggregate_id=aggregate_id,
                    wallet_id=wallet_id,
                    created_at=at,
                )
            )

    def list_notifications(
        self, principal: RecoveryPrincipal, *, limit: int = 50
    ) -> tuple[RecoveryNotification, ...]:
        return self._repository.list_notifications(
            principal.user_id, limit=limit
        )

    def mark_notification_read(
        self, principal: RecoveryPrincipal, notification_id: str
    ) -> None:
        self._repository.mark_notification_read(
            notification_id,
            recipient_user_id=principal.user_id,
            read_at=self._now(),
        )

    def _assess_risk(
        self, *, wallet_id: str, reason: RecoveryReason
    ) -> RecoveryRisk:
        """Only an explicit LOW result passes. Anything else holds the rotation
        for a person to review; a Guardian quorum alone does not clear it."""
        try:
            level = (
                "UNAVAILABLE"
                if self._risk is None
                else self._risk.assess_recovery(
                    wallet_id=wallet_id, reason=reason.value
                )
            )
        except Exception:
            level = "UNAVAILABLE"
        return RecoveryRisk(
            level=level,
            status=(
                RiskHoldStatus.CLEAR if level == "LOW" else RiskHoldStatus.ON_HOLD
            ),
        )

    def review_risk(
        self,
        principal: RecoveryPrincipal,
        request_id: str,
        *,
        decision: str,
        reason: str,
    ) -> RecoveryRequest:
        principal.require(Permission.RECOVERY_RISK_REVIEW)
        request = self._repository.get_request(request_id)
        if request is None:
            raise RecoveryNotFoundError("Recovery request was not found.")
        if request.owner_user_id == principal.user_id:
            raise RecoveryAuthorizationError(
                "A requester cannot review their own risk hold."
            )
        if request.risk.status is not RiskHoldStatus.ON_HOLD:
            raise RecoveryConflictError("This recovery is not on risk hold.")
        now = self._now()
        if decision == "RELEASE":
            updated = replace(
                request,
                risk=replace(
                    request.risk,
                    status=RiskHoldStatus.RELEASED,
                    reviewed_by=principal.user_id,
                    reviewed_at=now,
                ),
                updated_at=now,
                version=request.version + 1,
            )
        else:
            updated = replace(
                request.transition(RecoveryState.CANCELLED, at=now),
                risk=replace(
                    request.risk, reviewed_by=principal.user_id, reviewed_at=now
                ),
            )
        stored = self._repository.update_request(
            updated, expected_version=request.version
        )
        self._audit(
            RecoveryAuditEventType.RECOVERY_RISK_REVIEWED,
            aggregate_id=request_id,
            actor_id=principal.user_id,
            at=now,
            discriminator=str(stored.version),
            metadata={
                "decision": decision,
                "reasonDigest": _digest(reason),
            },
        )
        return stored

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise RecoveryValidationError("Recovery clock must be timezone-aware.")
        return value.astimezone(UTC)


class RecoveryReconciliationBackgroundService:
    def __init__(
        self, service: RecoveryService, *, poll_interval_ms: int
    ) -> None:
        self._service = service
        self._poll_interval = poll_interval_ms / 1000

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                await asyncio.to_thread(self._service.reconcile_due)
            except Exception:
                _LOGGER.exception("Recovery reconciliation cycle failed")
            try:
                await asyncio.wait_for(
                    stop_event.wait(), timeout=self._poll_interval
                )
            except TimeoutError:
                continue


def _digest(value: str) -> str:
    return sha256(value.encode()).hexdigest()
