from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pymongo.collection import Collection
from pymongo.errors import PyMongoError


SESSION_REVOCATIONS_COLLECTION = "session_revocations"


class MongoTokenRevocationStore:
    """Revocation that survives restarts and is shared by every instance.

    Fails closed: if the store cannot be read, the token counts as revoked.
    A subject revocation is a not-before time, so the owner can sign in again
    while every token issued earlier stays dead.
    """

    def __init__(
        self,
        collection: Collection[dict[str, Any]],
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._collection = collection
        self._clock = clock or (lambda: datetime.now(UTC))

    def revoke_token(
        self,
        jti: str,
        expires_at: datetime | None = None,
        reason: str = "logout",
    ) -> None:
        if not jti:
            return
        self._collection.update_one(
            {"_id": f"jti:{jti}"},
            {
                "$set": {
                    "kind": "jti",
                    "reason": reason,
                    "revokedAt": self._clock(),
                    "expiresAt": expires_at,
                }
            },
            upsert=True,
        )

    def revoke_subject(
        self,
        subject: str,
        reason: str = "security_quarantine",
    ) -> None:
        if not subject:
            return
        self._collection.update_one(
            {"_id": f"subject:{subject}"},
            {
                "$set": {
                    "kind": "subject",
                    "reason": reason,
                    "notBefore": self._clock(),
                }
            },
            upsert=True,
        )

    def reinstate_subject(self, subject: str) -> None:
        del subject  # A not-before time needs no reinstatement.

    def is_revoked(
        self,
        jti: str,
        subject: str | None = None,
        issued_at: datetime | None = None,
    ) -> bool:
        try:
            if self._collection.find_one({"_id": f"jti:{jti}"}) is not None:
                return True
            # "global" is written by a platform restore: no session survives it.
            entries = [self._collection.find_one({"_id": "global"})]
            if subject is not None:
                entries.append(
                    self._collection.find_one({"_id": f"subject:{subject}"})
                )
        except PyMongoError:
            return True
        return any(
            entry is not None and self._predates(entry, issued_at)
            for entry in entries
        )

    @staticmethod
    def _predates(entry: dict[str, Any], issued_at: datetime | None) -> bool:
        if issued_at is None:
            return True
        not_before = entry["notBefore"]
        if not_before.tzinfo is None:
            not_before = not_before.replace(tzinfo=UTC)
        # Tokens carry whole seconds: one from the same second counts as older.
        return int(issued_at.timestamp()) <= int(not_before.timestamp())
