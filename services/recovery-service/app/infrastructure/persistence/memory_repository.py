from datetime import datetime
from threading import RLock

from app.domain.recovery import (
    Guardian,
    GuardianStatus,
    RecoveryApproval,
    RecoveryAuditEvent,
    RecoveryConflictError,
    RecoveryPolicy,
    RecoveryRequest,
    RecoverySecretShareMetadata,
    RecoveryState,
)


class MemoryRecoveryRepository:
    def __init__(self) -> None:
        self._lock = RLock()
        self.guardians: dict[str, Guardian] = {}
        self.policies: dict[str, RecoveryPolicy] = {}
        self.requests: dict[str, RecoveryRequest] = {}
        self.approvals: dict[tuple[str, str], RecoveryApproval] = {}
        self.shares: dict[tuple[str, int, int, str], RecoverySecretShareMetadata] = {}
        self.audit_events: dict[str, RecoveryAuditEvent] = {}

    def add_guardian(self, guardian: Guardian) -> Guardian:
        with self._lock:
            if guardian.guardian_id in self.guardians:
                raise RecoveryConflictError("Guardian already exists.")
            duplicate = self.find_guardian_assignment(
                wallet_id=guardian.wallet_id,
                guardian_user_id=guardian.guardian_user_id,
                statuses=(GuardianStatus.ACTIVE, GuardianStatus.SUSPENDED),
            )
            if duplicate is not None:
                raise RecoveryConflictError("Guardian assignment already exists.")
            self.guardians[guardian.guardian_id] = guardian
            return guardian

    def get_guardian(self, guardian_id: str) -> Guardian | None:
        with self._lock:
            return self.guardians.get(guardian_id)

    def find_guardian_assignment(
        self,
        *,
        wallet_id: str,
        guardian_user_id: str,
        statuses: tuple[GuardianStatus, ...],
    ) -> Guardian | None:
        with self._lock:
            return next(
                (
                    item
                    for item in self.guardians.values()
                    if item.wallet_id == wallet_id
                    and item.guardian_user_id == guardian_user_id
                    and item.status in statuses
                ),
                None,
            )

    def list_guardians(
        self,
        *,
        wallet_id: str | None = None,
        owner_user_id: str | None = None,
        guardian_user_id: str | None = None,
        include_removed: bool = False,
    ) -> tuple[Guardian, ...]:
        with self._lock:
            values = (
                item
                for item in self.guardians.values()
                if (wallet_id is None or item.wallet_id == wallet_id)
                and (owner_user_id is None or item.owner_user_id == owner_user_id)
                and (
                    guardian_user_id is None
                    or item.guardian_user_id == guardian_user_id
                )
                and (include_removed or item.status is not GuardianStatus.REMOVED)
            )
            return tuple(sorted(values, key=lambda item: item.created_at))

    def update_guardian(
        self, guardian: Guardian, *, expected_version: int
    ) -> Guardian:
        with self._lock:
            existing = self.guardians.get(guardian.guardian_id)
            if existing is None or existing.version != expected_version:
                raise RecoveryConflictError("Guardian update lost an optimistic race.")
            self.guardians[guardian.guardian_id] = guardian
            return guardian

    def get_policy(self, wallet_id: str) -> RecoveryPolicy | None:
        with self._lock:
            return self.policies.get(wallet_id)

    def upsert_policy(
        self, policy: RecoveryPolicy, *, expected_version: int | None
    ) -> RecoveryPolicy:
        with self._lock:
            existing = self.policies.get(policy.wallet_id)
            if expected_version is None:
                if existing is not None:
                    raise RecoveryConflictError("Recovery policy already exists.")
            elif existing is None or existing.version != expected_version:
                raise RecoveryConflictError("Recovery policy update lost an optimistic race.")
            self.policies[policy.wallet_id] = policy
            return policy

    def add_request(self, request: RecoveryRequest) -> RecoveryRequest:
        with self._lock:
            if request.request_id in self.requests or self.get_active_request(request.wallet_id):
                raise RecoveryConflictError("An active recovery request already exists.")
            self.requests[request.request_id] = request
            return request

    def get_request(self, request_id: str) -> RecoveryRequest | None:
        with self._lock:
            return self.requests.get(request_id)

    def get_active_request(self, wallet_id: str) -> RecoveryRequest | None:
        with self._lock:
            return next(
                (
                    item
                    for item in self.requests.values()
                    if item.wallet_id == wallet_id and not item.session.state.terminal
                ),
                None,
            )

    def list_requests(
        self,
        *,
        owner_user_id: str | None = None,
        guardian_user_id: str | None = None,
        states: tuple[RecoveryState, ...] | None = None,
        limit: int = 100,
    ) -> tuple[RecoveryRequest, ...]:
        with self._lock:
            assigned_ids = {
                guardian.guardian_id
                for guardian in self.guardians.values()
                if guardian.guardian_user_id == guardian_user_id
            }
            values = (
                item
                for item in self.requests.values()
                if (owner_user_id is None or item.owner_user_id == owner_user_id)
                and (
                    guardian_user_id is None
                    or bool(set(item.policy.guardian_ids) & assigned_ids)
                )
                and (states is None or item.session.state in states)
            )
            return tuple(
                sorted(values, key=lambda item: item.created_at, reverse=True)[:limit]
            )

    def update_request(
        self, request: RecoveryRequest, *, expected_version: int
    ) -> RecoveryRequest:
        with self._lock:
            existing = self.requests.get(request.request_id)
            if existing is None or existing.version != expected_version:
                raise RecoveryConflictError("Recovery update lost an optimistic race.")
            self.requests[request.request_id] = request
            return request

    def add_approval_idempotently(
        self, approval: RecoveryApproval
    ) -> tuple[RecoveryApproval, bool]:
        key = (approval.request_id, approval.guardian_id)
        with self._lock:
            existing = self.approvals.get(key)
            if existing is None:
                self.approvals[key] = approval
                return approval, True
            if (
                existing.decision is approval.decision
                and existing.challenge_digest == approval.challenge_digest
                and existing.proof_digest == approval.proof_digest
            ):
                return existing, False
            raise RecoveryConflictError("Guardian already submitted another decision.")

    def list_approvals(self, request_id: str) -> tuple[RecoveryApproval, ...]:
        with self._lock:
            return tuple(
                sorted(
                    (
                        item
                        for item in self.approvals.values()
                        if item.request_id == request_id
                    ),
                    key=lambda item: item.decided_at,
                )
            )

    def save_share_set(
        self, shares: tuple[RecoverySecretShareMetadata, ...]
    ) -> None:
        with self._lock:
            for share in shares:
                key = (
                    share.policy_id,
                    share.policy_version,
                    share.share_version,
                    share.guardian_id,
                )
                existing = self.shares.get(key)
                if existing is not None and existing != share:
                    raise RecoveryConflictError("Recovery share version already exists.")
                self.shares[key] = share

    def get_share(
        self,
        *,
        policy_id: str,
        policy_version: int,
        share_version: int,
        guardian_id: str,
    ) -> RecoverySecretShareMetadata | None:
        with self._lock:
            return self.shares.get(
                (policy_id, policy_version, share_version, guardian_id)
            )

    def append_audit_idempotently(self, event: RecoveryAuditEvent) -> None:
        with self._lock:
            existing = self.audit_events.get(event.event_id)
            if existing is not None and existing != event:
                raise RecoveryConflictError("Recovery audit idempotency conflict.")
            self.audit_events[event.event_id] = event

    def list_audit_events(self, aggregate_id: str) -> tuple[RecoveryAuditEvent, ...]:
        with self._lock:
            return tuple(
                sorted(
                    (
                        event
                        for event in self.audit_events.values()
                        if event.aggregate_id == aggregate_id
                    ),
                    key=lambda event: event.occurred_at,
                )
            )

    def list_reconciliation_candidates(
        self, *, now: datetime, stale_before: datetime, limit: int
    ) -> tuple[RecoveryRequest, ...]:
        with self._lock:
            candidates = (
                item
                for item in self.requests.values()
                if not item.session.state.terminal
                and (
                    item.session.expires_at <= now
                    or item.session.updated_at <= stale_before
                    or (
                        item.session.executable_after is not None
                        and item.session.executable_after <= now
                    )
                )
            )
            return tuple(sorted(candidates, key=lambda item: item.updated_at)[:limit])

    def count_active_guardians(self) -> int:
        with self._lock:
            return sum(
                guardian.status is GuardianStatus.ACTIVE
                for guardian in self.guardians.values()
            )
