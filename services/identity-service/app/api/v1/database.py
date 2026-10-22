"""Read-only, aggregate persistence telemetry for the Admin Console."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pymongo.errors import PyMongoError

from app.api.v1.dependencies import get_mongo_connection_manager, require_permission
from app.domain.auth import AuthenticatedPrincipal
from app.domain.permissions import Permission
from app.domain.persistence import PersistenceUnavailableError
from app.infrastructure.persistence.connection import MongoConnectionManager
from app.infrastructure.persistence.indexes import (
    AUDIT_EVENTS_COLLECTION,
    CREDENTIALS_COLLECTION,
    PRESENTATIONS_COLLECTION,
    STATUS_LIST_ENTRIES_COLLECTION,
    STATUS_LISTS_COLLECTION,
    USERS_COLLECTION,
)


router = APIRouter(prefix="/database", tags=["database telemetry"])

_COUNTED_COLLECTIONS = {
    "users": USERS_COLLECTION,
    "credentials": CREDENTIALS_COLLECTION,
    "audit_logs": AUDIT_EVENTS_COLLECTION,
    "presentations": PRESENTATIONS_COLLECTION,
    "status_lists": STATUS_LISTS_COLLECTION,
    "status_list_entries": STATUS_LIST_ENTRIES_COLLECTION,
}


@router.get(
    "/stats",
    summary="Read aggregate persistence telemetry",
    description=(
        "Returns counts for selected MongoDB collections only. No records, "
        "identifiers, credentials, or connection details are returned. "
        "When authoritative persistence is unavailable, returns 503 rather "
        "than presenting legacy or fabricated counts."
    ),
    responses={503: {"description": "Authoritative MongoDB is unavailable."}},
)
def get_database_stats(
    _principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.ADMIN_OPERATIONS_READ))],
    manager: Annotated[
        MongoConnectionManager,
        Depends(get_mongo_connection_manager),
    ],
) -> dict[str, Any]:
    if not manager.is_connected:
        raise PersistenceUnavailableError(
            "Authoritative persistence is unavailable."
        )

    try:
        database = manager.database
        counts = {
            label: database[collection].count_documents({})
            for label, collection in _COUNTED_COLLECTIONS.items()
        }
    except PyMongoError as error:
        raise PersistenceUnavailableError(
            "Authoritative persistence telemetry is unavailable."
        ) from error

    return {
        "status": "SUCCESS",
        "authoritative_persistence": "MongoDB",
        "active_runtime": "MongoDB",
        "mongo_connected": True,
        "stats": counts,
        "mongo_collections": counts,
    }
