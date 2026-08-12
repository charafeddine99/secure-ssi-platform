from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from pymongo.errors import DuplicateKeyError


@dataclass(frozen=True)
class WriteResult:
    matched_count: int


class Cursor:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self.documents = documents

    def sort(self, key: str, direction: int):
        self.documents.sort(
            key=lambda document: _get(document, key), reverse=direction < 0
        )
        return self

    def limit(self, value: int):
        self.documents = self.documents[:value]
        return self

    def __iter__(self):
        return iter(deepcopy(self.documents))


class Collection:
    def __init__(
        self,
        *,
        unique_fields: tuple[str, ...] = (),
        unique_compounds: tuple[tuple[str, ...], ...] = (),
    ) -> None:
        self.documents: list[dict[str, Any]] = []
        self.unique_fields = unique_fields
        self.unique_compounds = unique_compounds
        self.indexes: dict[str, Any] = {}

    def insert_one(self, document: dict[str, Any]):
        self._require_unique(document)
        self.documents.append(deepcopy(document))
        return object()

    def find_one(self, query: dict[str, Any]):
        return next(
            (deepcopy(item) for item in self.documents if _matches(item, query)),
            None,
        )

    def find(self, query: dict[str, Any]) -> Cursor:
        return Cursor(
            [deepcopy(item) for item in self.documents if _matches(item, query)]
        )

    def replace_one(self, query: dict[str, Any], replacement: dict[str, Any]):
        for index, document in enumerate(self.documents):
            if _matches(document, query):
                previous = self.documents.pop(index)
                try:
                    self._require_unique(replacement)
                except Exception:
                    self.documents.insert(index, previous)
                    raise
                self.documents.insert(index, deepcopy(replacement))
                return WriteResult(1)
        return WriteResult(0)

    def count_documents(self, query: dict[str, Any]) -> int:
        return sum(_matches(item, query) for item in self.documents)

    def create_indexes(self, indexes: list[Any]) -> list[str]:
        for index in indexes:
            self.indexes[index.document["name"]] = index
        return list(self.indexes)

    def _require_unique(self, document: dict[str, Any]) -> None:
        for existing in self.documents:
            if existing.get("_id") == document.get("_id"):
                raise DuplicateKeyError("duplicate _id")
            for field in self.unique_fields:
                if _get(existing, field) == _get(document, field):
                    raise DuplicateKeyError(f"duplicate {field}")
            for fields in self.unique_compounds:
                expected = tuple(_get(document, field) for field in fields)
                if all(
                    _get(existing, field) == value
                    for field, value in zip(fields, expected)
                ):
                    raise DuplicateKeyError(f"duplicate {fields}")


class Database:
    def __init__(self) -> None:
        self.collections = {
            "guardians": Collection(
                unique_fields=("guardianId",),
                unique_compounds=(("walletId", "guardianUserId"),),
            ),
            "recovery_policies": Collection(
                unique_fields=("policyId", "walletId")
            ),
            "recovery_requests": Collection(
                unique_fields=("requestId", "session.sessionId")
            ),
            "recovery_approvals": Collection(
                unique_fields=("approvalId",),
                unique_compounds=(("requestId", "guardianId"),),
            ),
            "recovery_secret_shares": Collection(
                unique_fields=("shareId",),
                unique_compounds=(("recoveryRequestId", "guardianId"),),
            ),
            "recovery_audit_events": Collection(unique_fields=("eventId",)),
        }

    def __getitem__(self, name: str) -> Collection:
        return self.collections[name]


def _get(document: dict[str, Any], path: str) -> Any:
    value: Any = document
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _matches(document: dict[str, Any], query: dict[str, Any]) -> bool:
    alternatives = query.get("$or")
    if alternatives is not None and not any(
        _matches(document, item) for item in alternatives
    ):
        return False
    for key, expected in query.items():
        if key == "$or":
            continue
        actual = _get(document, key)
        if isinstance(expected, dict):
            if "$in" in expected:
                choices = expected["$in"]
                if isinstance(actual, list):
                    if not set(actual) & set(choices):
                        return False
                elif actual not in choices:
                    return False
            if "$nin" in expected and actual in expected["$nin"]:
                return False
            if "$ne" in expected and actual == expected["$ne"]:
                return False
            if "$lte" in expected and (
                actual is None or actual > expected["$lte"]
            ):
                return False
            continue
        if actual != expected:
            return False
    return True
