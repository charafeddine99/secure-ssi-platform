from datetime import datetime
from typing import Any

from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.domain.recovery import (
    Guardian,
    GuardianStatus,
    RecoveryApproval,
    RecoveryAuditEvent,
    RecoveryConflictError,
    RecoveryPersistenceError,
    RecoveryPolicy,
    RecoveryRequest,
    RecoverySecretShareMetadata,
    RecoveryState,
)
from app.infrastructure.persistence.indexes import (
    APPROVALS,
    AUDIT,
    GUARDIANS,
    POLICIES,
    REQUESTS,
    SHARES,
)
from app.infrastructure.persistence.mappers import (
    approval_from_document,
    approval_to_document,
    audit_from_document,
    audit_to_document,
    guardian_from_document,
    guardian_to_document,
    policy_from_document,
    policy_to_document,
    request_from_document,
    request_to_document,
    share_from_document,
    share_to_document,
)


_TERMINAL = tuple(state.value for state in RecoveryState if state.terminal)


class MongoRecoveryRepository:
    def __init__(self, database: Database[dict[str, Any]]) -> None:
        self._db = database

    def add_guardian(self, guardian: Guardian) -> Guardian:
        try:
            self._db[GUARDIANS].insert_one(guardian_to_document(guardian))
            return guardian
        except DuplicateKeyError as error:
            raise RecoveryConflictError("Guardian assignment already exists.") from error
        except PyMongoError as error:
            raise RecoveryPersistenceError("Guardian could not be stored.") from error

    def get_guardian(self, guardian_id: str) -> Guardian | None:
        value = self._find_one(GUARDIANS, {"guardianId": guardian_id})
        return None if value is None else guardian_from_document(value)

    def find_guardian_assignment(
        self,
        *,
        wallet_id: str,
        guardian_user_id: str,
        statuses: tuple[GuardianStatus, ...],
    ) -> Guardian | None:
        value = self._find_one(
            GUARDIANS,
            {
                "walletId": wallet_id,
                "guardianUserId": guardian_user_id,
                "status": {"$in": [status.value for status in statuses]},
            },
        )
        return None if value is None else guardian_from_document(value)

    def list_guardians(
        self,
        *,
        wallet_id: str | None = None,
        owner_user_id: str | None = None,
        guardian_user_id: str | None = None,
        include_removed: bool = False,
    ) -> tuple[Guardian, ...]:
        query: dict[str, Any] = {}
        if wallet_id is not None:
            query["walletId"] = wallet_id
        if owner_user_id is not None:
            query["ownerUserId"] = owner_user_id
        if guardian_user_id is not None:
            query["guardianUserId"] = guardian_user_id
        if not include_removed:
            query["status"] = {"$ne": GuardianStatus.REMOVED.value}
        return tuple(
            guardian_from_document(value)
            for value in self._find(GUARDIANS, query, sort=("createdAt", ASCENDING))
        )

    def update_guardian(
        self, guardian: Guardian, *, expected_version: int
    ) -> Guardian:
        return self._replace_cas(
            GUARDIANS,
            {"guardianId": guardian.guardian_id, "version": expected_version},
            guardian_to_document(guardian),
            guardian,
            "Guardian update lost an optimistic race.",
        )

    def get_policy(self, wallet_id: str) -> RecoveryPolicy | None:
        value = self._find_one(POLICIES, {"walletId": wallet_id})
        return None if value is None else policy_from_document(value)

    def upsert_policy(
        self, policy: RecoveryPolicy, *, expected_version: int | None
    ) -> RecoveryPolicy:
        try:
            if expected_version is None:
                self._db[POLICIES].insert_one(policy_to_document(policy))
                return policy
            return self._replace_cas(
                POLICIES,
                {"walletId": policy.wallet_id, "version": expected_version},
                policy_to_document(policy),
                policy,
                "Recovery policy update lost an optimistic race.",
            )
        except DuplicateKeyError as error:
            raise RecoveryConflictError("Recovery policy already exists.") from error
        except PyMongoError as error:
            raise RecoveryPersistenceError("Recovery policy could not be stored.") from error

    def add_request(self, request: RecoveryRequest) -> RecoveryRequest:
        try:
            self._db[REQUESTS].insert_one(request_to_document(request))
            return request
        except DuplicateKeyError as error:
            raise RecoveryConflictError("An active recovery request already exists.") from error
        except PyMongoError as error:
            raise RecoveryPersistenceError("Recovery request could not be stored.") from error

    def get_request(self, request_id: str) -> RecoveryRequest | None:
        value = self._find_one(REQUESTS, {"requestId": request_id})
        return None if value is None else request_from_document(value)

    def get_active_request(self, wallet_id: str) -> RecoveryRequest | None:
        value = self._find_one(
            REQUESTS, {"walletId": wallet_id, "state": {"$nin": list(_TERMINAL)}}
        )
        return None if value is None else request_from_document(value)

    def list_requests(
        self,
        *,
        owner_user_id: str | None = None,
        guardian_user_id: str | None = None,
        states: tuple[RecoveryState, ...] | None = None,
        limit: int = 100,
    ) -> tuple[RecoveryRequest, ...]:
        query: dict[str, Any] = {}
        if owner_user_id is not None:
            query["ownerUserId"] = owner_user_id
        if guardian_user_id is not None:
            guardian_ids = [
                guardian.guardian_id
                for guardian in self.list_guardians(guardian_user_id=guardian_user_id)
            ]
            query["policy.guardianIds"] = {"$in": guardian_ids}
        if states is not None:
            query["state"] = {"$in": [state.value for state in states]}
        return tuple(
            request_from_document(value)
            for value in self._find(
                REQUESTS, query, sort=("createdAt", DESCENDING), limit=limit
            )
        )

    def update_request(
        self, request: RecoveryRequest, *, expected_version: int
    ) -> RecoveryRequest:
        return self._replace_cas(
            REQUESTS,
            {"requestId": request.request_id, "version": expected_version},
            request_to_document(request),
            request,
            "Recovery update lost an optimistic race.",
        )

    def add_approval_idempotently(
        self, approval: RecoveryApproval
    ) -> tuple[RecoveryApproval, bool]:
        try:
            self._db[APPROVALS].insert_one(approval_to_document(approval))
            return approval, True
        except DuplicateKeyError:
            value = self._find_one(
                APPROVALS,
                {"requestId": approval.request_id, "guardianId": approval.guardian_id},
            )
            if value is None:
                raise RecoveryConflictError("Approval idempotency race was lost.") from None
            existing = approval_from_document(value)
            if (
                existing.decision is approval.decision
                and existing.challenge_digest == approval.challenge_digest
                and existing.proof_digest == approval.proof_digest
            ):
                return existing, False
            raise RecoveryConflictError("Guardian already submitted another decision.") from None
        except PyMongoError as error:
            raise RecoveryPersistenceError("Recovery approval could not be stored.") from error

    def list_approvals(self, request_id: str) -> tuple[RecoveryApproval, ...]:
        return tuple(
            approval_from_document(value)
            for value in self._find(
                APPROVALS,
                {"requestId": request_id},
                sort=("decidedAt", ASCENDING),
            )
        )

    def save_share_set(
        self, shares: tuple[RecoverySecretShareMetadata, ...]
    ) -> None:
        try:
            for share in shares:
                query = {
                    "policyId": share.policy_id,
                    "policyVersion": share.policy_version,
                    "shareVersion": share.share_version,
                    "guardianId": share.guardian_id,
                }
                existing = self._db[SHARES].find_one(query)
                if existing is not None:
                    if share_from_document(existing) != share:
                        raise RecoveryConflictError("Recovery share version already exists.")
                    continue
                self._db[SHARES].insert_one(share_to_document(share))
        except DuplicateKeyError as error:
            raise RecoveryConflictError("Recovery share version already exists.") from error
        except PyMongoError as error:
            raise RecoveryPersistenceError("Recovery shares could not be stored.") from error

    def get_share(
        self,
        *,
        policy_id: str,
        policy_version: int,
        share_version: int,
        guardian_id: str,
    ) -> RecoverySecretShareMetadata | None:
        value = self._find_one(
            SHARES,
            {
                "policyId": policy_id,
                "policyVersion": policy_version,
                "shareVersion": share_version,
                "guardianId": guardian_id,
            },
        )
        return None if value is None else share_from_document(value)

    def append_audit_idempotently(self, event: RecoveryAuditEvent) -> None:
        try:
            self._db[AUDIT].insert_one(audit_to_document(event))
        except DuplicateKeyError:
            value = self._find_one(AUDIT, {"eventId": event.event_id})
            if value is None or audit_from_document(value) != event:
                raise RecoveryConflictError("Recovery audit idempotency conflict.") from None
        except PyMongoError as error:
            raise RecoveryPersistenceError("Recovery audit event could not be stored.") from error

    def list_audit_events(self, aggregate_id: str) -> tuple[RecoveryAuditEvent, ...]:
        return tuple(
            audit_from_document(value)
            for value in self._find(
                AUDIT,
                {"aggregateId": aggregate_id},
                sort=("occurredAt", ASCENDING),
            )
        )

    def list_reconciliation_candidates(
        self, *, now: datetime, stale_before: datetime, limit: int
    ) -> tuple[RecoveryRequest, ...]:
        query = {
            "state": {"$nin": list(_TERMINAL)},
            "$or": [
                {"expiresAt": {"$lte": now}},
                {"executableAfter": {"$lte": now}},
                {"updatedAt": {"$lte": stale_before}},
            ],
        }
        return tuple(
            request_from_document(value)
            for value in self._find(
                REQUESTS, query, sort=("updatedAt", ASCENDING), limit=limit
            )
        )

    def count_active_guardians(self) -> int:
        try:
            return self._db[GUARDIANS].count_documents(
                {"status": GuardianStatus.ACTIVE.value}
            )
        except PyMongoError as error:
            raise RecoveryPersistenceError("Guardian count failed.") from error

    def _find_one(self, collection: str, query: dict[str, Any]) -> dict[str, Any] | None:
        try:
            return self._db[collection].find_one(query)
        except PyMongoError as error:
            raise RecoveryPersistenceError("Recovery read failed.") from error

    def _find(
        self,
        collection: str,
        query: dict[str, Any],
        *,
        sort: tuple[str, int],
        limit: int | None = None,
    ):
        try:
            cursor = self._db[collection].find(query).sort(*sort)
            return cursor if limit is None else cursor.limit(limit)
        except PyMongoError as error:
            raise RecoveryPersistenceError("Recovery query failed.") from error

    def _replace_cas(
        self,
        collection: str,
        query: dict[str, Any],
        document: dict[str, Any],
        result: Any,
        message: str,
    ) -> Any:
        try:
            outcome = self._db[collection].replace_one(query, document)
            if outcome.matched_count != 1:
                raise RecoveryConflictError(message)
            return result
        except DuplicateKeyError as error:
            raise RecoveryConflictError(message) from error
        except PyMongoError as error:
            raise RecoveryPersistenceError("Recovery update failed.") from error
