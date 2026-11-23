"""Hash chain over audit events.

Tamper-evident, not immutable. Anyone holding the key and write access can
rebuild the chain, and removing the newest events leaves no gap, so an outside
checkpoint is still needed to detect tail truncation.
"""

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.domain.persistence import PersistenceUnavailableError

GENESIS = "0" * 64
_ATTEMPTS = 12
_CHAIN_FIELDS = ("chainSeq", "chainPrev", "chainHash")
_CHAINED = {"chainSeq": {"$gte": 1}}


def derive_chain_key(root_key: bytes) -> bytes:
    return hmac.new(root_key, b"secure-ssi/audit-chain/v1", hashlib.sha256).digest()


def _normal(value: Any) -> Any:
    """Mongo stores milliseconds, so hash what a later read will return."""
    if isinstance(value, datetime):
        moment = value if value.tzinfo else value.replace(tzinfo=UTC)
        seconds = int(moment.replace(microsecond=0).timestamp())
        return seconds * 1000 + moment.microsecond // 1000
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _normal(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normal(item) for item in value]
    return value


@dataclass(frozen=True)
class AuditChainReport:
    status: str
    checked: int
    unchained: int
    first_broken_sequence: int | None = None


class AuditChain:
    def __init__(self, collection: Collection[dict[str, Any]], key: bytes) -> None:
        self._collection = collection
        self._key = key

    def _digest(self, document: dict[str, Any], sequence: int, previous: str) -> str:
        body = {k: v for k, v in document.items() if k not in _CHAIN_FIELDS}
        payload = json.dumps(
            [sequence, previous, _normal(body)],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hmac.new(self._key, payload.encode(), hashlib.sha256).hexdigest()

    def insert(self, document: dict[str, Any]) -> None:
        """Two writers can pick one sequence; the unique index makes one retry."""
        for _ in range(_ATTEMPTS):
            newest = self._collection.find(_CHAINED).sort("chainSeq", DESCENDING).limit(1)
            head = next(iter(newest), None)
            sequence = head["chainSeq"] + 1 if head else 1
            previous = head["chainHash"] if head else GENESIS
            sealed = {
                **document,
                "chainSeq": sequence,
                "chainPrev": previous,
                "chainHash": self._digest(document, sequence, previous),
            }
            try:
                self._collection.insert_one(sealed)
                return
            except DuplicateKeyError as error:
                if "chainSeq" not in str(error):
                    raise
        raise PersistenceUnavailableError("The audit chain is too busy to append to.")

    def verify(self) -> AuditChainReport:
        expected_sequence, previous, checked = 1, GENESIS, 0
        try:
            unchained = self._collection.count_documents({}) - self._collection.count_documents(_CHAINED)
            for document in self._collection.find(_CHAINED).sort("chainSeq", ASCENDING):
                sequence = document["chainSeq"]
                intact = (
                    sequence == expected_sequence
                    and document.get("chainPrev") == previous
                    and hmac.compare_digest(
                        str(document.get("chainHash")),
                        self._digest(document, sequence, previous),
                    )
                )
                if not intact:
                    return AuditChainReport("BROKEN", checked, unchained, expected_sequence)
                previous = document["chainHash"]
                expected_sequence += 1
                checked += 1
        except PyMongoError as error:
            raise PersistenceUnavailableError("The audit chain cannot be read.") from error
        return AuditChainReport("INTACT", checked, unchained)
