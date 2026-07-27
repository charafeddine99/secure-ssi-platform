from typing import Any

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.database import Database
from pymongo.errors import OperationFailure, PyMongoError

from app.domain.persistence import PersistenceUnavailableError


USERS_COLLECTION = "users"
CREDENTIALS_COLLECTION = "credentials"
AUDIT_EVENTS_COLLECTION = "audit_events"
STATUS_LIST_ENTRIES_COLLECTION = "credential_status_entries"
STATUS_LISTS_COLLECTION = "status_lists"
AUDIT_OUTBOX_COLLECTION = "audit_outbox"
PRESENTATIONS_COLLECTION = "presentations"
HOLDER_WALLETS_COLLECTION = "holder_wallets"
PRESENTATION_CHALLENGES_COLLECTION = "presentation_challenges"

USER_INDEXES = (
    IndexModel(
        [("username", ASCENDING)],
        unique=True,
        name="uq_users_username",
    ),
    IndexModel(
        [("createdAt", DESCENDING)],
        name="ix_users_created_at",
    ),
)

CREDENTIAL_INDEXES = (
    IndexModel(
        [("credentialId", ASCENDING)],
        unique=True,
        name="uq_credentials_credential_id",
    ),
    IndexModel(
        [("issuerDid", ASCENDING)],
        name="ix_credentials_issuer_did",
    ),
    IndexModel(
        [("holderDid", ASCENDING)],
        name="ix_credentials_holder_did",
    ),
    IndexModel(
        [("status", ASCENDING)],
        name="ix_credentials_status",
    ),
    IndexModel(
        [("createdAt", DESCENDING)],
        name="ix_credentials_created_at",
    ),
    IndexModel(
        [("statusListId", ASCENDING), ("status", ASCENDING)],
        name="ix_credentials_status_list_status",
    ),
    IndexModel(
        [("statusListId", ASCENDING), ("statusListIndex", ASCENDING)],
        unique=True,
        partialFilterExpression={
            "statusListId": {"$type": "string"},
            "statusListIndex": {"$type": "number"},
        },
        name="uq_credentials_status_list_index",
    ),
    IndexModel(
        [
            ("walletId", ASCENDING),
            ("ownerUserId", ASCENDING),
            ("createdAt", DESCENDING),
        ],
        name="ix_credentials_wallet_owner_created_at",
    ),
)

AUDIT_EVENT_INDEXES = (
    IndexModel(
        [("createdAt", DESCENDING)],
        name="ix_audit_events_created_at",
    ),
    IndexModel(
        [("eventType", ASCENDING), ("createdAt", DESCENDING)],
        name="ix_audit_events_type_created_at",
    ),
)

STATUS_LIST_ENTRY_INDEXES = (
    IndexModel(
        [("credentialId", ASCENDING)],
        unique=True,
        name="uq_status_entries_credential_id",
    ),
    IndexModel(
        [("statusListId", ASCENDING), ("statusListIndex", ASCENDING)],
        unique=True,
        name="uq_status_entries_list_index",
    ),
    IndexModel(
        [("issuerDid", ASCENDING), ("statusPurpose", ASCENDING)],
        name="ix_status_entries_issuer_purpose",
    ),
)

STATUS_LIST_INDEXES = (
    IndexModel(
        [("statusListId", ASCENDING)],
        unique=True,
        name="uq_status_lists_status_list_id",
    ),
    IndexModel(
        [("issuerDid", ASCENDING), ("statusPurpose", ASCENDING)],
        name="ix_status_lists_issuer_purpose",
    ),
    IndexModel(
        [("updatedAt", DESCENDING)],
        name="ix_status_lists_updated_at",
    ),
)

AUDIT_OUTBOX_INDEXES = (
    IndexModel(
        [("status", ASCENDING), ("availableAt", ASCENDING)],
        name="ix_audit_outbox_delivery",
    ),
    IndexModel(
        [("aggregateType", ASCENDING), ("aggregateId", ASCENDING)],
        name="ix_audit_outbox_aggregate",
    ),
)

PRESENTATION_INDEXES = (
    IndexModel(
        [("presentationId", ASCENDING)],
        unique=True,
        name="uq_presentations_presentation_id",
    ),
    IndexModel(
        [("challenge", ASCENDING), ("domain", ASCENDING)],
        unique=True,
        name="uq_presentations_challenge_domain",
    ),
    IndexModel(
        [("holderDid", ASCENDING), ("createdAt", DESCENDING)],
        name="ix_presentations_holder_created_at",
    ),
    IndexModel(
        [("verificationResult", ASCENDING)],
        name="ix_presentations_verification_result",
    ),
    IndexModel(
        [("expiresAt", ASCENDING)],
        name="ix_presentations_expires_at",
    ),
    IndexModel(
        [("walletId", ASCENDING), ("ownerUserId", ASCENDING)],
        name="ix_presentations_wallet_owner",
    ),
    IndexModel(
        [
            ("verificationResult", ASCENDING),
            ("processingStartedAt", ASCENDING),
        ],
        name="ix_presentations_stale_processing",
    ),
)

HOLDER_WALLET_INDEXES = (
    IndexModel(
        [("walletId", ASCENDING)],
        unique=True,
        name="uq_holder_wallets_wallet_id",
    ),
    IndexModel(
        [("keyReference", ASCENDING)],
        unique=True,
        name="uq_holder_wallets_key_reference",
    ),
    IndexModel(
        [("holderDid", ASCENDING)],
        unique=True,
        partialFilterExpression={
            "status": "ACTIVE",
            "deletedAt": None,
        },
        name="uq_holder_wallets_active_holder_did",
    ),
    IndexModel(
        [
            ("ownerUserId", ASCENDING),
            ("status", ASCENDING),
            ("createdAt", DESCENDING),
        ],
        name="ix_holder_wallets_owner_status",
    ),
)

PRESENTATION_CHALLENGE_INDEXES = (
    IndexModel(
        [("challengeId", ASCENDING)],
        unique=True,
        name="uq_presentation_challenges_challenge_id",
    ),
    IndexModel(
        [("challenge", ASCENDING)],
        unique=True,
        name="uq_presentation_challenges_challenge",
    ),
    IndexModel(
        [("expiresAt", ASCENDING)],
        name="ix_presentation_challenges_expires_at",
    ),
    IndexModel(
        [("status", ASCENDING), ("expiresAt", ASCENDING)],
        name="ix_presentation_challenges_status_expires",
    ),
    IndexModel(
        [("issuedBy", ASCENDING), ("issuedAt", DESCENDING)],
        name="ix_presentation_challenges_issuer_created_at",
    ),
)


def ensure_mongo_indexes(database: Database[dict[str, Any]]) -> None:
    try:
        _drop_deprecated_index(
            database[STATUS_LISTS_COLLECTION],
            "uq_status_lists_issuer_purpose",
        )
        database[USERS_COLLECTION].create_indexes(list(USER_INDEXES))
        database[CREDENTIALS_COLLECTION].create_indexes(
            list(CREDENTIAL_INDEXES)
        )
        database[AUDIT_EVENTS_COLLECTION].create_indexes(
            list(AUDIT_EVENT_INDEXES)
        )
        database[STATUS_LIST_ENTRIES_COLLECTION].create_indexes(
            list(STATUS_LIST_ENTRY_INDEXES)
        )
        database[STATUS_LISTS_COLLECTION].create_indexes(
            list(STATUS_LIST_INDEXES)
        )
        database[AUDIT_OUTBOX_COLLECTION].create_indexes(
            list(AUDIT_OUTBOX_INDEXES)
        )
        database[PRESENTATIONS_COLLECTION].create_indexes(
            list(PRESENTATION_INDEXES)
        )
        database[HOLDER_WALLETS_COLLECTION].create_indexes(
            list(HOLDER_WALLET_INDEXES)
        )
        database[PRESENTATION_CHALLENGES_COLLECTION].create_indexes(
            list(PRESENTATION_CHALLENGE_INDEXES)
        )
    except PyMongoError as error:
        raise PersistenceUnavailableError(
            "MongoDB indexes could not be ensured."
        ) from error


def _drop_deprecated_index(
    collection: Any,
    index_name: str,
) -> None:
    drop_index = getattr(collection, "drop_index", None)
    if drop_index is None:
        return
    try:
        drop_index(index_name)
    except OperationFailure as error:
        if error.code != 27:
            raise
