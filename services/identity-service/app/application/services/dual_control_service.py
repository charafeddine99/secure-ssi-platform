"""Two people for irreversible operations, enforced here and not in the UI."""

import hashlib
import hmac
import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from app.domain.exceptions import PermissionDeniedError
from app.domain.persistence import PersistenceUnavailableError


DUAL_CONTROL_COLLECTION = "dual_control_operations"
KEY_COMPROMISE = "KEY_COMPROMISE"
KEY_DESTRUCTION = "KEY_DESTRUCTION"
PLATFORM_RESTORE = "PLATFORM_RESTORE"
BACKUP_KEY_ROTATION = "BACKUP_KEY_ROTATION"
OPERATION_TYPES = frozenset(
    {KEY_COMPROMISE, KEY_DESTRUCTION, PLATFORM_RESTORE, BACKUP_KEY_ROTATION}
)
_LIFETIME = timedelta(minutes=30)


class DualControlError(PermissionDeniedError):
    """The operation has no valid approval from a second person."""


@dataclass(frozen=True)
class DualControlOperation:
    operation_id: str
    operation_type: str
    target: str
    requested_by: str
    approved_by: str | None
    status: str
    expires_at: datetime

    @classmethod
    def from_document(
        cls,
        value: Mapping[str, Any],
    ) -> "DualControlOperation":
        expires_at = value["expiresAt"]
        return cls(
            operation_id=value["_id"],
            operation_type=value["operationType"],
            target=value["target"],
            requested_by=value["requestedBy"],
            approved_by=value.get("approvedBy"),
            status=value["status"],
            expires_at=(
                expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)
            ),
        )


class DualControlService:
    def __init__(
        self,
        *,
        operations: Collection[dict[str, Any]],
        clock: Callable[[], datetime],
    ) -> None:
        self._operations = operations
        self._clock = clock

    def request(
        self,
        *,
        operation_type: str,
        target: str,
        reason: str,
        requested_by: str,
    ) -> DualControlOperation:
        if operation_type not in OPERATION_TYPES:
            raise DualControlError("This operation type is not recognised.")
        if not target.strip() or len(reason.strip()) < 3:
            raise DualControlError("A target and a reason are required.")
        now = self._now()
        document = {
            "_id": "dco_" + secrets.token_urlsafe(18),
            "operationType": operation_type,
            "target": target,
            "reasonDigest": hashlib.sha256(reason.encode()).hexdigest(),
            "requestedBy": requested_by,
            "approvedBy": None,
            "status": "PENDING",
            "tokenDigest": None,
            "createdAt": now,
            "expiresAt": now + _LIFETIME,
        }
        try:
            self._operations.insert_one(document)
        except PyMongoError as error:
            raise _unavailable() from error
        return DualControlOperation.from_document(document)

    def approve(
        self,
        operation_id: str,
        *,
        approved_by: str,
    ) -> tuple[DualControlOperation, str]:
        """Returns the one-time execution token. Only its digest is stored."""
        current = self._require(operation_id)
        if current.requested_by == approved_by:
            raise DualControlError(
                "A second administrator must approve this operation."
            )
        if current.status != "PENDING":
            raise DualControlError("This operation is not awaiting approval.")
        if current.expires_at <= self._now():
            raise DualControlError("This operation has expired.")
        token = secrets.token_urlsafe(32)
        try:
            result = self._operations.update_one(
                {"_id": operation_id, "status": "PENDING"},
                {
                    "$set": {
                        "status": "APPROVED",
                        "approvedBy": approved_by,
                        "tokenDigest": _digest(token),
                    }
                },
            )
        except PyMongoError as error:
            raise _unavailable() from error
        if result.matched_count != 1:
            raise DualControlError("This operation is not awaiting approval.")
        return self._require(operation_id), token

    def consume(
        self,
        operation_id: str | None,
        token: str | None,
        *,
        operation_type: str,
        target: str,
    ) -> DualControlOperation:
        """Single use, and only for the exact operation that was approved."""
        if not operation_id or not token:
            raise DualControlError("Two-person approval is required.")
        current = self._require(operation_id)
        try:
            document = self._operations.find_one({"_id": operation_id})
        except PyMongoError as error:
            raise _unavailable() from error
        digest = (document or {}).get("tokenDigest") or ""
        if (
            current.status != "APPROVED"
            or current.operation_type != operation_type
            or current.target != target
            or current.expires_at <= self._now()
            or current.approved_by in {None, current.requested_by}
            or not hmac.compare_digest(digest, _digest(token))
        ):
            raise DualControlError("Two-person approval is not valid.")
        try:
            result = self._operations.update_one(
                {"_id": operation_id, "status": "APPROVED"},
                {"$set": {"status": "EXECUTED", "executedAt": self._now()}},
            )
        except PyMongoError as error:
            raise _unavailable() from error
        if result.matched_count != 1:
            raise DualControlError("Two-person approval is not valid.")
        return self._require(operation_id)

    def list_recent(self, *, limit: int = 50) -> tuple[DualControlOperation, ...]:
        try:
            documents = list(
                self._operations.find({}).sort("createdAt", -1).limit(limit)
            )
        except PyMongoError as error:
            raise _unavailable() from error
        return tuple(
            DualControlOperation.from_document(item) for item in documents
        )

    def _require(self, operation_id: str) -> DualControlOperation:
        try:
            document = self._operations.find_one({"_id": operation_id})
        except PyMongoError as error:
            raise _unavailable() from error
        if document is None:
            raise DualControlError("This operation does not exist.")
        return DualControlOperation.from_document(document)

    def _now(self) -> datetime:
        return self._clock().astimezone(UTC)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _unavailable() -> PersistenceUnavailableError:
    return PersistenceUnavailableError("Dual control data is unavailable.")
