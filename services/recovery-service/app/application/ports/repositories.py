from datetime import datetime
from typing import Protocol

from app.domain.recovery import (
    Guardian,
    GuardianStatus,
    RecoveryApproval,
    RecoveryAuditEvent,
    RecoveryPolicy,
    RecoveryRequest,
    RecoverySecretShareMetadata,
    RecoveryState,
)


class RecoveryRepository(Protocol):
    def add_guardian(self, guardian: Guardian) -> Guardian: ...

    def get_guardian(self, guardian_id: str) -> Guardian | None: ...

    def find_guardian_assignment(
        self,
        *,
        wallet_id: str,
        guardian_user_id: str,
        statuses: tuple[GuardianStatus, ...],
    ) -> Guardian | None: ...

    def list_guardians(
        self,
        *,
        wallet_id: str | None = None,
        owner_user_id: str | None = None,
        guardian_user_id: str | None = None,
        include_removed: bool = False,
    ) -> tuple[Guardian, ...]: ...

    def update_guardian(
        self,
        guardian: Guardian,
        *,
        expected_version: int,
    ) -> Guardian: ...

    def get_policy(self, wallet_id: str) -> RecoveryPolicy | None: ...

    def upsert_policy(
        self,
        policy: RecoveryPolicy,
        *,
        expected_version: int | None,
    ) -> RecoveryPolicy: ...

    def add_request(self, request: RecoveryRequest) -> RecoveryRequest: ...

    def get_request(self, request_id: str) -> RecoveryRequest | None: ...

    def get_active_request(self, wallet_id: str) -> RecoveryRequest | None: ...

    def list_requests(
        self,
        *,
        owner_user_id: str | None = None,
        guardian_user_id: str | None = None,
        states: tuple[RecoveryState, ...] | None = None,
        limit: int = 100,
    ) -> tuple[RecoveryRequest, ...]: ...

    def update_request(
        self,
        request: RecoveryRequest,
        *,
        expected_version: int,
    ) -> RecoveryRequest: ...

    def add_approval_idempotently(
        self,
        approval: RecoveryApproval,
    ) -> tuple[RecoveryApproval, bool]: ...

    def list_approvals(self, request_id: str) -> tuple[RecoveryApproval, ...]: ...

    def save_share_set(
        self,
        shares: tuple[RecoverySecretShareMetadata, ...],
    ) -> None: ...

    def get_share(
        self,
        *,
        policy_id: str,
        policy_version: int,
        share_version: int,
        guardian_id: str,
    ) -> RecoverySecretShareMetadata | None: ...

    def append_audit_idempotently(self, event: RecoveryAuditEvent) -> None: ...

    def list_audit_events(self, aggregate_id: str) -> tuple[RecoveryAuditEvent, ...]: ...

    def list_reconciliation_candidates(
        self,
        *,
        now: datetime,
        stale_before: datetime,
        limit: int,
    ) -> tuple[RecoveryRequest, ...]: ...

    def count_active_guardians(self) -> int: ...


class RecoveryConnectionManager(Protocol):
    @property
    def database(self): ...

    def connect(self) -> None: ...

    def close(self) -> None: ...
