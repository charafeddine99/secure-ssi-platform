from copy import deepcopy
from collections.abc import Callable
from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.domain.bitstring_status_list import (
    CredentialStatusEntry,
    StatusListCapacityError,
    StatusListConflictError,
    StatusListPublication,
    StatusPurpose,
    status_list_sequence,
)
from app.domain.credential_status import CredentialStatus
from app.domain.persistence import PersistenceUnavailableError
from app.infrastructure.persistence.mappers import new_object_id
from app.infrastructure.persistence.status_list_mappers import (
    CredentialStatusEntryDocumentMapper,
    StatusListPublicationDocumentMapper,
)


IdGenerator = Callable[[], str]


class MongoCredentialStatusEntryRepository:
    def __init__(
        self,
        entry_collection: Collection[dict[str, Any]],
        credential_collection: Collection[dict[str, Any]],
        *,
        id_generator: IdGenerator = new_object_id,
    ) -> None:
        self._entries = entry_collection
        self._credentials = credential_collection
        self._id_generator = id_generator

    def ensure(
        self,
        *,
        credential_id: str,
        issuer_did: str,
        status_list_id: str,
        status_purpose: StatusPurpose,
        candidate_index: int,
        list_length: int,
        created_at: datetime,
    ) -> CredentialStatusEntry:
        existing = self.get_by_credential_id(credential_id)
        if existing is not None:
            self._require_same_assignment(
                existing,
                issuer_did=issuer_did,
                status_list_id=status_list_id,
                status_purpose=status_purpose,
                list_length=list_length,
            )
            return existing
        for offset in range(list_length):
            status_list_index = (candidate_index + offset) % list_length
            try:
                assigned_credential = self._credentials.find_one(
                    {
                        "statusListId": status_list_id,
                        "statusListIndex": status_list_index,
                        "deletedAt": None,
                    }
                )
            except PyMongoError as error:
                raise _unavailable("status entry reservation") from error
            if assigned_credential is not None:
                continue
            entry = CredentialStatusEntry(
                id=self._id_generator(),
                credential_id=credential_id,
                issuer_did=issuer_did,
                status_list_id=status_list_id,
                status_list_index=status_list_index,
                status_purpose=status_purpose,
                created_at=created_at,
                updated_at=created_at,
            )
            try:
                self._entries.insert_one(
                    CredentialStatusEntryDocumentMapper.to_document(entry)
                )
                return entry
            except DuplicateKeyError:
                existing = self.get_by_credential_id(credential_id)
                if existing is not None:
                    self._require_same_assignment(
                        existing,
                        issuer_did=issuer_did,
                        status_list_id=status_list_id,
                        status_purpose=status_purpose,
                        list_length=list_length,
                    )
                    return existing
                continue
            except PyMongoError as error:
                raise _unavailable("status entry reservation") from error
        raise StatusListCapacityError(
            "No free credential status index remains in the list."
        )

    def get_by_credential_id(
        self,
        credential_id: str,
    ) -> CredentialStatusEntry | None:
        try:
            credential = self._credentials.find_one(
                {
                    "credentialId": credential_id,
                    "statusEntryId": {"$ne": None},
                    "deletedAt": None,
                }
            )
            if credential is not None:
                return _entry_from_credential_document(credential)
            document = self._entries.find_one(
                {"credentialId": credential_id}
            )
        except PyMongoError as error:
            raise _unavailable("status entry lookup") from error
        return (
            None
            if document is None
            else CredentialStatusEntryDocumentMapper.from_document(document)
        )

    def list_by_status_list(
        self,
        status_list_id: str,
        *,
        limit: int,
    ) -> tuple[CredentialStatusEntry, ...]:
        _require_positive_limit(limit)
        try:
            legacy_cursor = (
                self._entries.find({"statusListId": status_list_id})
                .sort("statusListIndex", ASCENDING)
                .limit(limit)
            )
            embedded_cursor = (
                self._credentials.find(
                    {
                        "statusListId": status_list_id,
                        "statusEntryId": {"$ne": None},
                        "deletedAt": None,
                    }
                )
                .sort("statusListIndex", ASCENDING)
                .limit(limit)
            )
            by_credential = {
                entry.credential_id: entry
                for entry in (
                    *(
                        CredentialStatusEntryDocumentMapper.from_document(
                            document
                        )
                        for document in legacy_cursor
                    ),
                    *(
                        _entry_from_credential_document(document)
                        for document in embedded_cursor
                    ),
                )
            }
            return tuple(
                sorted(
                    by_credential.values(),
                    key=lambda entry: entry.status_list_index,
                )[:limit]
            )
        except (KeyError, TypeError, ValueError) as error:
            raise PersistenceUnavailableError(
                "A persisted credential status entry is invalid."
            ) from error
        except PyMongoError as error:
            raise _unavailable("status entry listing") from error

    def revoked_indices(
        self,
        status_list_id: str,
        *,
        limit: int,
    ) -> tuple[int, ...]:
        _require_positive_limit(limit)
        try:
            entry_documents = list(
                self._entries.find({"statusListId": status_list_id})
                .sort("statusListIndex", ASCENDING)
                .limit(limit)
            )
            legacy_by_credential = {
                document["credentialId"]: document["statusListIndex"]
                for document in entry_documents
            }
            legacy_revoked = self._credentials.find(
                {
                    "credentialId": {"$in": list(legacy_by_credential)},
                    "status": CredentialStatus.REVOKED.value,
                    "deletedAt": None,
                }
            ).limit(limit)
            embedded_revoked = self._credentials.find(
                {
                    "statusListId": status_list_id,
                    "status": CredentialStatus.REVOKED.value,
                    "deletedAt": None,
                }
            ).limit(limit)
            indices = {
                *(
                    legacy_by_credential[document["credentialId"]]
                    for document in legacy_revoked
                ),
                *(
                    document["statusListIndex"]
                    for document in embedded_revoked
                ),
            }
        except (KeyError, TypeError) as error:
            raise PersistenceUnavailableError(
                "A persisted credential status entry is invalid."
            ) from error
        except PyMongoError as error:
            raise _unavailable("revoked status entry listing") from error
        if any(index < 0 or index >= limit for index in indices):
            raise PersistenceUnavailableError(
                "A persisted credential has an invalid status-list index."
            )
        return tuple(sorted(indices))

    def list_status_list_ids(
        self,
        issuer_did: str,
        *,
        status_purpose: StatusPurpose,
    ) -> tuple[str, ...]:
        try:
            legacy = self._entries.find(
                {
                    "issuerDid": issuer_did,
                    "statusPurpose": status_purpose.value,
                }
            )
            embedded = self._credentials.find(
                {
                    "issuerDid": issuer_did,
                    "statusEntryId": {"$ne": None},
                    "deletedAt": None,
                }
            )
            identifiers = {
                document["statusListId"]
                for document in (*tuple(legacy), *tuple(embedded))
            }
            return tuple(sorted(identifiers, key=status_list_sequence))
        except (KeyError, TypeError, ValueError) as error:
            raise PersistenceUnavailableError(
                "A persisted status-list identifier is invalid."
            ) from error
        except PyMongoError as error:
            raise _unavailable("status-list identifier listing") from error

    @staticmethod
    def _require_same_assignment(
        existing: CredentialStatusEntry,
        *,
        issuer_did: str,
        status_list_id: str,
        status_purpose: StatusPurpose,
        list_length: int,
    ) -> None:
        if (
            existing.issuer_did != issuer_did
            or existing.status_list_id != status_list_id
            or existing.status_purpose is not status_purpose
            or existing.status_list_index >= list_length
        ):
            raise StatusListConflictError(
                "Credential status assignment conflicts with persisted state."
            )


class MongoStatusListRepository:
    def __init__(
        self,
        collection: Collection[dict[str, Any]],
    ) -> None:
        self._collection = collection

    def get(
        self,
        status_list_id: str,
    ) -> StatusListPublication | None:
        try:
            document = self._collection.find_one(
                {"statusListId": status_list_id}
            )
        except PyMongoError as error:
            raise _unavailable("status list lookup") from error
        return (
            None
            if document is None
            else StatusListPublicationDocumentMapper.from_document(document)
        )

    def publish(
        self,
        publication: StatusListPublication,
        *,
        expected_version: int | None,
    ) -> StatusListPublication:
        try:
            if expected_version is None:
                if publication.version != 1:
                    raise ValueError(
                        "A new status list must start at version 1."
                    )
                document = (
                    StatusListPublicationDocumentMapper.to_document(
                        publication
                    )
                )
                document["history"] = [deepcopy(document)]
                self._collection.insert_one(document)
                return publication
            if publication.version != expected_version + 1:
                raise ValueError(
                    "Status-list publication version is inconsistent."
                )
            current = self._collection.find_one(
                {
                    "statusListId": publication.status_list_id,
                    "version": expected_version,
                }
            )
            if current is None:
                raise StatusListConflictError(
                    "Status list changed before publication."
                )
            raw_history = current.get("history")
            if isinstance(raw_history, list):
                history = deepcopy(raw_history)
            else:
                previous = deepcopy(current)
                previous.pop("history", None)
                history = [previous]
            if any(
                isinstance(item, dict)
                and item.get("version") == publication.version
                for item in history
            ):
                raise StatusListConflictError(
                    "Status-list version already exists."
                )
            document = StatusListPublicationDocumentMapper.to_document(
                publication
            )
            history.append(deepcopy(document))
            document["history"] = history
            result = self._collection.replace_one(
                {
                    "statusListId": publication.status_list_id,
                    "version": expected_version,
                },
                document,
            )
        except DuplicateKeyError:
            existing = self.get(publication.status_list_id)
            if (
                existing is not None
                and existing.content_hash == publication.content_hash
            ):
                return existing
            raise StatusListConflictError(
                "Status list was published concurrently."
            ) from None
        except PyMongoError as error:
            raise _unavailable("status list publication") from error
        if result.matched_count != 1:
            raise StatusListConflictError(
                "Status list changed before publication."
            )
        return publication

    def list_history(
        self,
        status_list_id: str,
    ) -> tuple[StatusListPublication, ...]:
        try:
            document = self._collection.find_one(
                {"statusListId": status_list_id}
            )
        except PyMongoError as error:
            raise _unavailable("status list history lookup") from error
        if document is None:
            return ()
        raw_history = document.get("history")
        history_documents = (
            raw_history if isinstance(raw_history, list) else [document]
        )
        try:
            publications = tuple(
                StatusListPublicationDocumentMapper.from_document(item)
                for item in history_documents
                if isinstance(item, dict)
            )
        except (TypeError, ValueError) as error:
            raise PersistenceUnavailableError(
                "Persisted status-list history is invalid."
            ) from error
        return tuple(sorted(publications, key=lambda item: item.version))

    def get_version(
        self,
        status_list_id: str,
        version: int,
    ) -> StatusListPublication | None:
        if version < 1:
            raise ValueError("Status-list version must be positive.")
        return next(
            (
                publication
                for publication in self.list_history(status_list_id)
                if publication.version == version
            ),
            None,
        )


def _require_positive_limit(value: int) -> None:
    if value < 1:
        raise ValueError("Repository list limit must be positive.")


def _unavailable(operation: str) -> PersistenceUnavailableError:
    return PersistenceUnavailableError(
        f"MongoDB {operation} could not be completed."
    )


def _entry_from_credential_document(
    document: dict[str, Any],
) -> CredentialStatusEntry:
    status_entry_id = document["statusEntryId"]
    if not isinstance(status_entry_id, ObjectId):
        raise TypeError("Embedded status entry id must be an ObjectId.")
    created_at = document["createdAt"]
    return CredentialStatusEntry(
        id=str(status_entry_id),
        credential_id=document["credentialId"],
        issuer_did=document["issuerDid"],
        status_list_id=document["statusListId"],
        status_list_index=document["statusListIndex"],
        status_purpose=StatusPurpose.REVOCATION,
        created_at=created_at,
        updated_at=created_at,
        version=1,
    )
