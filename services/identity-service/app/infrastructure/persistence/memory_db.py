"""
In-memory database adapter for offline / development mode.

Used when IDENTITY_MONGO_ENABLED=false (no Docker / MongoDB daemon).
Intentionally mirrors the test-support FakeDatabase so the same
collection-access patterns work in both production and test contexts.

This module is NOT a substitute for MongoDB in production. It provides
deterministic synthetic fixtures for local development and screenshot
capture only.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pymongo.errors import DuplicateKeyError


@dataclass(frozen=True)
class _WriteResult:
    matched_count: int


class _Cursor:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self._documents = documents

    def sort(self, key: str, direction: int) -> "_Cursor":
        self._documents.sort(
            key=lambda doc: _sort_value(_get_path(doc, key)),
            reverse=direction < 0,
        )
        return self

    def limit(self, value: int) -> "_Cursor":
        self._documents = self._documents[:value]
        return self

    def __iter__(self):
        return iter(deepcopy(self._documents))


def _sort_value(value: Any) -> tuple[int, Any]:
    if value is None:
        return (0, 0)
    if isinstance(value, datetime):
        normalized = (
            value.replace(tzinfo=timezone.utc)
            if value.tzinfo is None
            else value
        )
        return (1, normalized.timestamp())
    if isinstance(value, str):
        try:
            normalized = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        except ValueError:
            return (2, value.casefold())
        if normalized.tzinfo is None:
            normalized = normalized.replace(tzinfo=timezone.utc)
        return (1, normalized.timestamp())
    if isinstance(value, (int, float)):
        return (3, float(value))
    return (4, str(value).casefold())


class MemoryCollection:
    """Drop-in substitute for a pymongo Collection in offline mode."""

    def __init__(
        self,
        *,
        unique_fields: tuple[str, ...] = (),
        unique_compounds: tuple[tuple[str, ...], ...] = (),
    ) -> None:
        self.documents: list[dict[str, Any]] = []
        self.unique_fields = unique_fields
        self.unique_compounds = unique_compounds
        self.indexes: list[Any] = []

    def insert_one(self, document: dict[str, Any]) -> object:
        for existing in self.documents:
            if existing.get("_id") == document.get("_id"):
                raise DuplicateKeyError("duplicate _id")
            for field in self.unique_fields:
                val = _get_path(document, field)
                if val is not None and _get_path(existing, field) == val:
                    raise DuplicateKeyError(f"duplicate {field}")
            for fields in self.unique_compounds:
                doc_vals = tuple(_get_path(document, f) for f in fields)
                if any(v is None for v in doc_vals):
                    continue
                if all(_get_path(existing, f) == v for f, v in zip(fields, doc_vals)):
                    raise DuplicateKeyError(f"duplicate compound {fields}")
        self.documents.append(deepcopy(document))
        return object()

    def find_one(self, filters: dict[str, Any]) -> dict[str, Any] | None:
        for document in self.documents:
            if _matches(document, filters):
                return deepcopy(document)
        return None

    def find(self, filters: dict[str, Any]) -> _Cursor:
        return _Cursor(
            [deepcopy(doc) for doc in self.documents if _matches(doc, filters)]
        )

    def count_documents(self, filters: dict[str, Any]) -> int:
        return sum(1 for doc in self.documents if _matches(doc, filters))

    def replace_one(
        self, filters: dict[str, Any], replacement: dict[str, Any]
    ) -> _WriteResult:
        for idx, document in enumerate(self.documents):
            if _matches(document, filters):
                for other_idx, existing in enumerate(self.documents):
                    if idx == other_idx:
                        continue
                    for field in self.unique_fields:
                        if _get_path(existing, field) == _get_path(replacement, field):
                            raise DuplicateKeyError(f"duplicate {field}")
                self.documents[idx] = deepcopy(replacement)
                return _WriteResult(matched_count=1)
        return _WriteResult(matched_count=0)

    def update_one(
        self, filters: dict[str, Any], update: dict[str, Any], upsert: bool = False
    ) -> _WriteResult:
        for document in self.documents:
            if _matches(document, filters):
                for field, value in update.get("$set", {}).items():
                    _set_path(document, field, deepcopy(value))
                for field, increment in update.get("$inc", {}).items():
                    _set_path(document, field, _get_path(document, field) + increment)
                return _WriteResult(matched_count=1)
        if upsert:
            new_doc = deepcopy(update.get("$set", {}))
            for k, v in filters.items():
                if k not in new_doc:
                    new_doc[k] = deepcopy(v)
            if "_id" not in new_doc:
                new_doc["_id"] = str(len(self.documents) + 1)
            self.documents.append(new_doc)
            return _WriteResult(matched_count=1)
        return _WriteResult(matched_count=0)

    def create_indexes(self, indexes: list[Any]) -> list[str]:
        self.indexes.extend(indexes)
        return [
            idx.document["name"] if hasattr(idx, "document") else str(idx)
            for idx in indexes
        ]


class MemoryDatabase:
    """
    Process-wide in-memory database for offline development mode.

    All collections that the identity service uses are pre-created with
    the correct uniqueness constraints. Dynamic collection access
    auto-creates a plain MemoryCollection.
    """

    def __init__(self) -> None:
        self.collections: dict[str, MemoryCollection] = {
            "users": MemoryCollection(unique_fields=("username",)),
            "credentials": MemoryCollection(
                unique_fields=("credentialId",),
                unique_compounds=(("statusListId", "statusListIndex"),),
            ),
            "audit_events": MemoryCollection(),
            "credential_status_entries": MemoryCollection(
                unique_fields=("credentialId",),
                unique_compounds=(("statusListId", "statusListIndex"),),
            ),
            "status_lists": MemoryCollection(unique_fields=("statusListId",)),
            "audit_outbox": MemoryCollection(),
            "presentations": MemoryCollection(
                unique_fields=("presentationId",),
                unique_compounds=(("challenge", "domain"),),
            ),
            "holder_wallets": MemoryCollection(
                unique_fields=("walletId", "keyReference", "holderDid"),
            ),
            "presentation_challenges": MemoryCollection(
                unique_fields=("challengeId", "challenge"),
            ),
            "managed_keys": MemoryCollection(
                unique_fields=("keyId",),
                unique_compounds=(
                    ("provider", "providerKeyReference"),
                    ("verificationMethod",),
                    ("walletId", "purpose", "keyVersion"),
                    ("walletId", "purpose", "idempotencyKeyHash"),
                ),
            ),
            "credential_offers": MemoryCollection(unique_fields=("offerId",)),
            "verification_sessions": MemoryCollection(unique_fields=("sessionId",)),
            "blockchain_anchors": MemoryCollection(unique_fields=("anchorId",)),
            "trust_registry": MemoryCollection(unique_fields=("issuerDid",)),
        }

    def __getitem__(self, name: str) -> MemoryCollection:
        if name not in self.collections:
            self.collections[name] = MemoryCollection()
        return self.collections[name]


class MemoryConnectionManager:
    """
    Drop-in substitute for MongoConnectionManager in offline / dev mode.

    ``is_connected`` is always True; ``database`` always returns the
    shared MemoryDatabase instance. ``connect()`` and ``close()`` are
    no-ops so the lifespan hooks do not need branching logic.
    """

    def __init__(self) -> None:
        self._database = MemoryDatabase()
        self.is_connected = True

    @property
    def database(self) -> MemoryDatabase:
        return self._database

    def connect(self) -> None:
        pass

    def close(self) -> None:
        pass

    def __repr__(self) -> str:
        return "MemoryConnectionManager(mode=offline-dev)"


# ---------------------------------------------------------------------------
# Query helpers (identical algorithm to the test-support fake_mongo helpers)
# ---------------------------------------------------------------------------

def _matches(document: dict[str, Any], filters: dict[str, Any]) -> bool:
    alternatives = filters.get("$or")
    if alternatives is not None and not any(
        _matches(document, alt) for alt in alternatives
    ):
        return False
    for key, expected in filters.items():
        if key == "$or":
            continue
        actual = _get_path(document, key)
        if isinstance(expected, dict):
            if "$in" in expected and actual not in expected["$in"]:
                return False
            if "$nin" in expected and actual in expected["$nin"]:
                return False
            if "$ne" in expected and actual == expected["$ne"]:
                return False
            if "$lte" in expected and (actual is None or actual > expected["$lte"]):
                return False
            if "$lt" in expected and (actual is None or actual >= expected["$lt"]):
                return False
            if "$gte" in expected and (actual is None or actual < expected["$gte"]):
                return False
            if "$gt" in expected and (actual is None or actual <= expected["$gt"]):
                return False
            continue
        if actual != expected:
            return False
    return True


def _get_path(document: dict[str, Any], path: str) -> Any:
    value: Any = document
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _set_path(document: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    target = document
    for part in parts[:-1]:
        nested = target.get(part)
        if not isinstance(nested, dict):
            nested = {}
            target[part] = nested
        target = nested
    target[parts[-1]] = value
