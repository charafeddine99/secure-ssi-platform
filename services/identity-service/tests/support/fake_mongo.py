from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from pymongo.errors import DuplicateKeyError


@dataclass(frozen=True)
class FakeWriteResult:
    matched_count: int


class FakeCursor:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self._documents = documents

    def sort(self, key: str, direction: int) -> "FakeCursor":
        self._documents.sort(
            key=lambda document: _get_path(document, key),
            reverse=direction < 0,
        )
        return self

    def limit(self, value: int) -> "FakeCursor":
        self._documents = self._documents[:value]
        return self

    def __iter__(self):
        return iter(deepcopy(self._documents))


class FakeCollection:
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
            if existing["_id"] == document["_id"]:
                raise DuplicateKeyError("duplicate _id")
            for field in self.unique_fields:
                if _get_path(existing, field) == _get_path(document, field):
                    raise DuplicateKeyError(f"duplicate {field}")
            for fields in self.unique_compounds:
                document_values = tuple(
                    _get_path(document, field) for field in fields
                )
                if any(value is None for value in document_values):
                    continue
                if all(
                    _get_path(existing, field)
                    == value
                    for field, value in zip(fields, document_values)
                ):
                    raise DuplicateKeyError(
                        f"duplicate compound {fields}"
                    )
        self.documents.append(deepcopy(document))
        return object()

    def find_one(
        self,
        filters: dict[str, Any],
    ) -> dict[str, Any] | None:
        for document in self.documents:
            if _matches(document, filters):
                return deepcopy(document)
        return None

    def find(self, filters: dict[str, Any]) -> FakeCursor:
        return FakeCursor(
            [
                deepcopy(document)
                for document in self.documents
                if _matches(document, filters)
            ]
        )

    def replace_one(
        self,
        filters: dict[str, Any],
        replacement: dict[str, Any],
    ) -> FakeWriteResult:
        for index, document in enumerate(self.documents):
            if _matches(document, filters):
                for other_index, existing in enumerate(self.documents):
                    if index == other_index:
                        continue
                    for field in self.unique_fields:
                        if _get_path(existing, field) == _get_path(
                            replacement,
                            field,
                        ):
                            raise DuplicateKeyError(f"duplicate {field}")
                    for fields in self.unique_compounds:
                        replacement_values = tuple(
                            _get_path(replacement, field)
                            for field in fields
                        )
                        if any(
                            value is None
                            for value in replacement_values
                        ):
                            continue
                        if all(
                            _get_path(existing, field)
                            == value
                            for field, value in zip(
                                fields,
                                replacement_values,
                            )
                        ):
                            raise DuplicateKeyError(
                                f"duplicate compound {fields}"
                            )
                self.documents[index] = deepcopy(replacement)
                return FakeWriteResult(matched_count=1)
        return FakeWriteResult(matched_count=0)

    def update_one(
        self,
        filters: dict[str, Any],
        update: dict[str, Any],
    ) -> FakeWriteResult:
        for document in self.documents:
            if _matches(document, filters):
                for field, value in update.get("$set", {}).items():
                    _set_path(document, field, deepcopy(value))
                for field, increment in update.get("$inc", {}).items():
                    _set_path(
                        document,
                        field,
                        _get_path(document, field) + increment,
                    )
                return FakeWriteResult(matched_count=1)
        return FakeWriteResult(matched_count=0)

    def create_indexes(self, indexes: list[Any]) -> list[str]:
        self.indexes.extend(indexes)
        return [index.document["name"] for index in indexes]


class FakeDatabase:
    def __init__(self) -> None:
        self.collections = {
            "users": FakeCollection(unique_fields=("username",)),
            "credentials": FakeCollection(
                unique_fields=("credentialId",),
                unique_compounds=(("statusListId", "statusListIndex"),),
            ),
            "audit_events": FakeCollection(),
            "credential_status_entries": FakeCollection(
                unique_fields=("credentialId",),
                unique_compounds=(("statusListId", "statusListIndex"),),
            ),
            "status_lists": FakeCollection(
                unique_fields=("statusListId",),
            ),
            "audit_outbox": FakeCollection(),
            "presentations": FakeCollection(
                unique_fields=("presentationId",),
                unique_compounds=(("challenge", "domain"),),
            ),
            "holder_wallets": FakeCollection(
                unique_fields=(
                    "walletId",
                    "keyReference",
                    "holderDid",
                ),
            ),
            "presentation_challenges": FakeCollection(
                unique_fields=("challengeId", "challenge"),
            ),
        }

    def __getitem__(self, name: str) -> FakeCollection:
        return self.collections[name]


def _matches(
    document: dict[str, Any],
    filters: dict[str, Any],
) -> bool:
    alternatives = filters.get("$or")
    if alternatives is not None and not any(
        _matches(document, alternative)
        for alternative in alternatives
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
            if "$lte" in expected and (
                actual is None or actual > expected["$lte"]
            ):
                return False
            if "$lt" in expected and (
                actual is None or actual >= expected["$lt"]
            ):
                return False
            if "$gte" in expected and (
                actual is None or actual < expected["$gte"]
            ):
                return False
            if "$gt" in expected and (
                actual is None or actual <= expected["$gt"]
            ):
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


def _set_path(
    document: dict[str, Any],
    path: str,
    value: Any,
) -> None:
    parts = path.split(".")
    target = document
    for part in parts[:-1]:
        nested = target.get(part)
        if not isinstance(nested, dict):
            nested = {}
            target[part] = nested
        target = nested
    target[parts[-1]] = value
