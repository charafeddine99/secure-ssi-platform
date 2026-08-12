from typing import Any

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.domain.recovery import RecoveryPersistenceError


GUARDIANS = "guardians"
POLICIES = "recovery_policies"
REQUESTS = "recovery_requests"
APPROVALS = "recovery_approvals"
SHARES = "recovery_secret_shares"
AUDIT = "recovery_audit_events"

GUARDIAN_INDEXES = (
    IndexModel([("guardianId", ASCENDING)], unique=True, name="uq_guardians_id"),
    IndexModel(
        [("walletId", ASCENDING), ("guardianUserId", ASCENDING)],
        unique=True,
        partialFilterExpression={"status": {"$in": ["ACTIVE", "SUSPENDED"]}},
        name="uq_guardians_wallet_user_active",
    ),
    IndexModel([("walletId", ASCENDING), ("status", ASCENDING)], name="ix_guardians_wallet"),
    IndexModel([("ownerUserId", ASCENDING), ("createdAt", DESCENDING)], name="ix_guardians_owner"),
    IndexModel([("guardianUserId", ASCENDING), ("status", ASCENDING)], name="ix_guardians_assignee"),
)

POLICY_INDEXES = (
    IndexModel([("policyId", ASCENDING)], unique=True, name="uq_recovery_policy_id"),
    IndexModel([("walletId", ASCENDING)], unique=True, name="uq_recovery_policy_wallet"),
)

REQUEST_INDEXES = (
    IndexModel([("requestId", ASCENDING)], unique=True, name="uq_recovery_request_id"),
    IndexModel([("session.sessionId", ASCENDING)], unique=True, name="uq_recovery_session_id"),
    IndexModel([("state", ASCENDING), ("expiresAt", ASCENDING)], name="ix_recovery_state_expiry"),
    IndexModel([("walletId", ASCENDING), ("createdAt", DESCENDING)], name="ix_recovery_wallet_created"),
    IndexModel([("ownerUserId", ASCENDING), ("createdAt", DESCENDING)], name="ix_recovery_owner_created"),
    IndexModel([("state", ASCENDING), ("executableAfter", ASCENDING)], name="ix_recovery_timelock_due"),
    IndexModel([("state", ASCENDING), ("updatedAt", ASCENDING)], name="ix_recovery_stale_execution"),
    IndexModel(
        [("walletId", ASCENDING)],
        unique=True,
        partialFilterExpression={
            "state": {
                "$in": [
                    "PENDING_APPROVALS",
                    "QUORUM_REACHED",
                    "WAITING_TIMELOCK",
                    "READY_FOR_EXECUTION",
                    "EXECUTING",
                    "RECONCILIATION_REQUIRED",
                ]
            }
        },
        name="uq_recovery_active_wallet",
    ),
)

APPROVAL_INDEXES = (
    IndexModel([("approvalId", ASCENDING)], unique=True, name="uq_recovery_approval_id"),
    IndexModel(
        [("requestId", ASCENDING), ("guardianId", ASCENDING)],
        unique=True,
        name="uq_recovery_approval_guardian",
    ),
    IndexModel([("requestId", ASCENDING), ("decision", ASCENDING)], name="ix_recovery_approval_decision"),
)

SHARE_INDEXES = (
    IndexModel([("shareId", ASCENDING)], unique=True, name="uq_recovery_share_id"),
    IndexModel(
        [("recoveryRequestId", ASCENDING), ("guardianId", ASCENDING)],
        unique=True,
        name="uq_recovery_share_request_guardian",
    ),
    IndexModel(
        [
            ("policyId", ASCENDING),
            ("policyVersion", ASCENDING),
            ("shareVersion", ASCENDING),
            ("guardianId", ASCENDING),
        ],
        unique=True,
        name="uq_recovery_share_guardian_version",
    ),
)

AUDIT_INDEXES = (
    IndexModel([("eventId", ASCENDING)], unique=True, name="uq_recovery_audit_event"),
    IndexModel([("aggregateId", ASCENDING), ("occurredAt", ASCENDING)], name="ix_recovery_audit_aggregate"),
    IndexModel([("eventType", ASCENDING), ("occurredAt", DESCENDING)], name="ix_recovery_audit_type"),
)


def ensure_recovery_indexes(database: Database[dict[str, Any]]) -> None:
    try:
        database[GUARDIANS].create_indexes(list(GUARDIAN_INDEXES))
        database[POLICIES].create_indexes(list(POLICY_INDEXES))
        database[REQUESTS].create_indexes(list(REQUEST_INDEXES))
        database[APPROVALS].create_indexes(list(APPROVAL_INDEXES))
        database[SHARES].create_indexes(list(SHARE_INDEXES))
        database[AUDIT].create_indexes(list(AUDIT_INDEXES))
    except PyMongoError as error:
        raise RecoveryPersistenceError("Recovery indexes could not be ensured.") from error
