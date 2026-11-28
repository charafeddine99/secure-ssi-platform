from typing import Any

from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.application.services.revocation_ledger_service import (
    LedgerDuplicateError,
)
from app.domain.persistence import PersistenceUnavailableError
from app.domain.revocation_ledger import RevocationEvent


REVOCATION_LEDGER_COLLECTION = "revocation_ledger_events"


def ensure_revocation_ledger_indexes(
    collection: Collection[dict[str, Any]],
) -> None:
    collection.create_index(
        [("sequence", ASCENDING)],
        name="uq_revocation_ledger_sequence",
        unique=True,
    )
    collection.create_index(
        [("eventKey", ASCENDING)],
        name="uq_revocation_ledger_event_key",
        unique=True,
    )
    collection.create_index(
        [("statusListId", ASCENDING)],
        name="idx_revocation_ledger_status_list",
    )
    collection.create_index(
        [("credentialId", ASCENDING)],
        name="idx_revocation_ledger_credential",
    )


class MongoRevocationLedgerRepository:
    """Uses find and insert only, so it runs under an append-only principal."""

    def __init__(self, collection: Collection[dict[str, Any]]) -> None:
        self._collection = collection

    def head(self) -> RevocationEvent | None:
        try:
            documents = list(
                self._collection.find({})
                .sort("sequence", DESCENDING)
                .limit(1)
            )
        except PyMongoError as error:
            raise _unavailable() from error
        return (
            RevocationEvent.from_document(documents[0]) if documents else None
        )

    def by_key(self, key: str) -> RevocationEvent | None:
        return self._one({"eventKey": key})

    def by_sequence(self, sequence: int) -> RevocationEvent | None:
        return self._one({"sequence": sequence})

    def by_status_list(
        self,
        status_list_id: str,
    ) -> tuple[RevocationEvent, ...]:
        return self._many({"statusListId": status_list_id})

    def by_credential(
        self,
        credential_id: str,
    ) -> tuple[RevocationEvent, ...]:
        return self._many({"credentialId": credential_id})

    def ordered(self) -> tuple[RevocationEvent, ...]:
        return self._many({})

    def append(self, event: RevocationEvent) -> None:
        try:
            self._collection.insert_one(
                {"_id": event.event_key, **event.to_document()}
            )
        except DuplicateKeyError as error:
            raise LedgerDuplicateError() from error
        except PyMongoError as error:
            raise _unavailable() from error

    def _one(self, query: dict[str, Any]) -> RevocationEvent | None:
        try:
            document = self._collection.find_one(query)
        except PyMongoError as error:
            raise _unavailable() from error
        return None if document is None else RevocationEvent.from_document(document)

    def _many(self, query: dict[str, Any]) -> tuple[RevocationEvent, ...]:
        try:
            documents = list(
                self._collection.find(query).sort("sequence", ASCENDING)
            )
        except PyMongoError as error:
            raise _unavailable() from error
        return tuple(RevocationEvent.from_document(item) for item in documents)


def _unavailable() -> PersistenceUnavailableError:
    return PersistenceUnavailableError("The revocation ledger is unavailable.")
