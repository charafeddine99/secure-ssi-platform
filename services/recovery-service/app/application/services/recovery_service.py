import asyncio
import logging
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from hmac import compare_digest
from secrets import token_bytes, token_urlsafe
from time import perf_counter

from app.application.ports.managed_keys import ManagedKeyRecoveryGateway
from app.application.ports.repositories import RecoveryRepository
from app.application.ports.secret_sharing import (
    SecretSharingContext,
    SecretSharingProvider,
)
from app.application.services.metrics import RecoveryMetrics
from app.core.config import RecoverySettings
from app.domain.auth import Permission, RecoveryPrincipal
from app.domain.recovery import (
    Guardian,
    GuardianStatus,
    RecoveryApproval,
    RecoveryAuditEvent,
    RecoveryAuditEventType,
    RecoveryChallenge,
    RecoveryConflictError,
    RecoveryDecision,
    RecoveryFailure,
    RecoveryLease,
    RecoveryNonce,
    RecoveryNotFoundError,
    RecoveryOperation,
    RecoveryPolicy,
    RecoveryPolicySnapshot,
    RecoveryQuorum,
    RecoveryReason,
    RecoveryRequest,
    RecoveryResult,
    RecoverySecretShareMetadata,
    RecoverySession,
    RecoveryState,
    RecoveryValidationError,
    SecretShareError,
)


Clock = Callable[[], datetime]
IdGenerator = Callable[[str], str]
_LOGGER = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(UTC)


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
    ) -> None:
        self._repository = repository
        self._secret_sharing = secret_sharing
        self._managed_keys = managed_keys
        self._settings = settings
        self._metrics = metrics
        self._clock = clock
        self._ids = id_generator
        self._worker_id = worker_id or secure_id("worker")

    def create_guardian(
        self,
        principal: RecoveryPrincipal,
        *,
        wallet_id: str,
        guardian_user_id: str,
        guardian_did: str,
        display_name: str,
        verification_method: str,
    ) -> Guardian:
        principal.require(Permission.GUARDIAN_CREATE)
        self._managed_keys.verify_wallet_owner(
            wallet_id=wallet_id, owner_user_id=principal.user_id
        )
        if self._repository.get_active_request(wallet_id) is not None:
            raise RecoveryConflictError(
                "Guardian assignments cannot change during active recovery."
            )
        policy = self._repository.get_policy(wallet_id)
        if guardian_user_id == principal.user_id and (
            policy is None or not policy.allow_self_guardian
        ):
            raise RecoveryValidationError("Wallet owners cannot be their own Guardian.")
        guardians = self._repository.list_guardians(wallet_id=wallet_id)
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
            guardian_did=guardian_did,
            display_name=display_name.strip(),
            verification_method=verification_method,
            status=GuardianStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        stored = self._repository.add_guardian(guardian)
        self._audit(
            RecoveryAuditEventType.GUARDIAN_ADDED,
            aggregate_id=stored.guardian_id,
            actor_id=principal.user_id,
            at=now,
            discriminator=str(stored.version),
            metadata={"walletId": wallet_id, "status": stored.status.value},
        )
        self._refresh_guardian_metric()
        return stored

    def list_guardians(
        self,
        principal: RecoveryPrincipal,
        *,
        wallet_id: str | None = None,
    ) -> tuple[Guardian, ...]:
        principal.require(Permission.GUARDIAN_READ)
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
        verification_method: str | None = None,
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
        fields_changed = display_name is not None or verification_method is not None
        updated = guardian.transition(status, at=now) if status_changed else guardian
        if fields_changed:
            updated = replace(
                updated,
                display_name=(display_name or updated.display_name).strip(),
                verification_method=(
                    verification_method or updated.verification_method
                ),
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
        allow_self_guardian: bool = False,
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
        if not allow_self_guardian and any(
            item.guardian_user_id == principal.user_id for item in active
        ):
            raise RecoveryValidationError("Policy forbids an assigned self-Guardian.")
        existing = self._repository.get_policy(wallet_id)
        now = self._now()
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
            allow_self_guardian=allow_self_guardian,
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
        context = SecretSharingContext(
            recovery_request_id=request_id,
            policy_id=policy.policy_id,
            policy_version=policy.version,
            share_version=1,
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

    def approve(
        self,
        principal: RecoveryPrincipal,
        request_id: str,
        *,
        guardian_id: str,
        challenge: str,
        proof: str | None = None,
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
        proof: str | None = None,
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
        proof: str | None,
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
        ):
            self._audit_unauthorized(request_id, principal.user_id)
            raise RecoveryNotFoundError("Recovery request was not found.")
        proof_digest = None if proof is None else _digest(proof)
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
                existing.decision is decision
                and existing.challenge_digest == _digest(challenge)
                and existing.proof_digest == proof_digest
            ):
                return existing, request
            raise RecoveryConflictError("Guardian already submitted another decision.")
        now = self._now()
        if request.session.state is not RecoveryState.PENDING_APPROVALS:
            raise RecoveryConflictError("Recovery is not accepting Guardian decisions.")
        if now >= request.session.approval_expires_at or now >= request.session.expires_at:
            self._expire(request, actor_id=principal.user_id, at=now)
            raise RecoveryConflictError("Recovery approval window has expired.")
        if not guardian.can_approve:
            raise RecoveryConflictError("Guardian is not active.")
        supplied_digest = _digest(challenge)
        if not compare_digest(supplied_digest, request.challenge.digest):
            self._audit_unauthorized(request_id, principal.user_id)
            raise RecoveryConflictError("Recovery challenge does not match.")
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
