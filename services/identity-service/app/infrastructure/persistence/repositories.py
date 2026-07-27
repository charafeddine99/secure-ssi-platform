from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from pymongo import DESCENDING
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.domain.audit_outbox import (
    AuditOutboxRecord,
    AuditOutboxSource,
    AuditOutboxStatus,
)
from app.domain.bitstring_status_list import CredentialStatusEntry
from app.domain.credential_status import (
    CredentialAlreadyRevokedError,
    CredentialNotFoundError,
    CredentialStatus,
    InvalidCredentialStatusTransitionError,
)
from app.domain.persistence import (
    AuditEvent,
    AuditEventType,
    CredentialStorageStatus,
    DuplicateEntityError,
    OptimisticLockError,
    PersistedCredential,
    PersistedUser,
    PersistenceUnavailableError,
)
from app.infrastructure.persistence.mappers import (
    AuditEventDocumentMapper,
    CredentialDocumentMapper,
    UserDocumentMapper,
    to_object_id,
)
from app.infrastructure.persistence.status_list_mappers import (
    AuditOutboxDocumentMapper,
)


Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


class MongoUserRepository:
    def __init__(
        self,
        collection: Collection[dict[str, Any]],
        *,
        clock: Clock = utc_now,
    ) -> None:
        self._collection = collection
        self._clock = clock

    def add(self, user: PersistedUser) -> PersistedUser:
        if user.version != 1 or user.deleted_at is not None:
            raise ValueError("A new user must be active at version 1.")
        try:
            self._collection.insert_one(
                UserDocumentMapper.to_document(user)
            )
        except DuplicateKeyError as error:
            raise DuplicateEntityError(
                "A user with the same id or username already exists."
            ) from error
        except PyMongoError as error:
            raise _unavailable("user insertion") from error
        return user

    def get_by_id(self, user_id: str) -> PersistedUser | None:
        try:
            document = self._collection.find_one(
                {"_id": to_object_id(user_id), "deletedAt": None}
            )
        except PyMongoError as error:
            raise _unavailable("user lookup") from error
        return (
            None
            if document is None
            else UserDocumentMapper.from_document(document)
        )

    def get_by_username(self, username: str) -> PersistedUser | None:
        try:
            document = self._collection.find_one(
                {
                    "username": username.strip().casefold(),
                    "deletedAt": None,
                }
            )
        except PyMongoError as error:
            raise _unavailable("user lookup") from error
        return (
            None
            if document is None
            else UserDocumentMapper.from_document(document)
        )

    def update(
        self,
        user: PersistedUser,
        *,
        expected_version: int,
    ) -> PersistedUser:
        _validate_update_version(user.version, expected_version)
        if user.deleted_at is not None:
            raise ValueError("A deleted user cannot be updated.")
        updated = replace(
            user,
            updated_at=self._clock(),
            version=expected_version + 1,
        )
        try:
            result = self._collection.replace_one(
                {
                    "_id": to_object_id(user.id),
                    "version": expected_version,
                    "deletedAt": None,
                },
                UserDocumentMapper.to_document(updated),
            )
        except DuplicateKeyError as error:
            raise DuplicateEntityError(
                "A user with the same username already exists."
            ) from error
        except PyMongoError as error:
            raise _unavailable("user update") from error
        _require_match(result.matched_count, entity="user")
        return updated

    def soft_delete(
        self,
        user_id: str,
        *,
        expected_version: int,
    ) -> None:
        deleted_at = self._clock()
        try:
            result = self._collection.update_one(
                {
                    "_id": to_object_id(user_id),
                    "version": expected_version,
                    "deletedAt": None,
                },
                {
                    "$set": {
                        "enabled": False,
                        "updatedAt": deleted_at,
                        "deletedAt": deleted_at,
                    },
                    "$inc": {"version": 1},
                },
            )
        except PyMongoError as error:
            raise _unavailable("user soft deletion") from error
        _require_match(result.matched_count, entity="user")


class MongoCredentialRepository:
    def __init__(
        self,
        collection: Collection[dict[str, Any]],
        *,
        clock: Clock = utc_now,
    ) -> None:
        self._collection = collection
        self._clock = clock

    def add(
        self,
        credential: PersistedCredential,
    ) -> PersistedCredential:
        if credential.version != 1 or credential.deleted_at is not None:
            raise ValueError(
                "A new credential must be active at version 1."
            )
        try:
            self._collection.insert_one(
                CredentialDocumentMapper.to_document(credential)
            )
        except DuplicateKeyError as error:
            raise DuplicateEntityError(
                "A credential with the same id already exists."
            ) from error
        except PyMongoError as error:
            raise _unavailable("credential insertion") from error
        return credential

    def get_by_credential_id(
        self,
        credential_id: str,
    ) -> PersistedCredential | None:
        try:
            document = self._collection.find_one(
                {
                    "credentialId": credential_id,
                    "deletedAt": None,
                }
            )
        except PyMongoError as error:
            raise _unavailable("credential lookup") from error
        return (
            None
            if document is None
            else CredentialDocumentMapper.from_document(document)
        )

    def update(
        self,
        credential: PersistedCredential,
        *,
        expected_version: int,
    ) -> PersistedCredential:
        _validate_update_version(credential.version, expected_version)
        if credential.deleted_at is not None:
            raise ValueError("A deleted credential cannot be updated.")
        updated = replace(
            credential,
            updated_at=self._clock(),
            version=expected_version + 1,
        )
        if updated.status is CredentialStatus.REVOKED:
            raise InvalidCredentialStatusTransitionError(
                "Revocation must use the auditable revocation repository."
            )
        status_filter = _allowed_current_statuses(updated.status)
        try:
            result = self._collection.replace_one(
                {
                    "_id": to_object_id(credential.id),
                    "version": expected_version,
                    "deletedAt": None,
                    "status": {"$in": status_filter},
                },
                CredentialDocumentMapper.to_document(updated),
            )
        except DuplicateKeyError as error:
            raise DuplicateEntityError(
                "A credential with the same credentialId already exists."
            ) from error
        except PyMongoError as error:
            raise _unavailable("credential update") from error
        _require_match(result.matched_count, entity="credential")
        return updated

    def soft_delete(
        self,
        credential_id: str,
        *,
        expected_version: int,
    ) -> None:
        deleted_at = self._clock()
        try:
            result = self._collection.update_one(
                {
                    "credentialId": credential_id,
                    "version": expected_version,
                    "deletedAt": None,
                },
                {
                    "$set": {
                        "updatedAt": deleted_at,
                        "deletedAt": deleted_at,
                    },
                    "$inc": {"version": 1},
                },
            )
        except PyMongoError as error:
            raise _unavailable("credential soft deletion") from error
        _require_match(result.matched_count, entity="credential")

    def list_by_issuer(
        self,
        issuer_did: str,
        *,
        limit: int = 100,
    ) -> tuple[PersistedCredential, ...]:
        return self._list({"issuerDid": issuer_did}, limit=limit)

    def list_by_holder(
        self,
        holder_did: str,
        *,
        limit: int = 100,
    ) -> tuple[PersistedCredential, ...]:
        return self._list({"holderDid": holder_did}, limit=limit)

    def list_by_wallet(
        self,
        wallet_id: str,
        *,
        owner_user_id: str,
        limit: int = 100,
    ) -> tuple[PersistedCredential, ...]:
        return self._list(
            {
                "walletId": wallet_id,
                "ownerUserId": owner_user_id,
            },
            limit=limit,
        )

    def list_by_status(
        self,
        status: CredentialStatus | CredentialStorageStatus,
        *,
        limit: int = 100,
    ) -> tuple[PersistedCredential, ...]:
        return self._list(
            {"status": {"$in": _query_status_values(status)}},
            limit=limit,
        )

    def _list(
        self,
        filters: dict[str, Any],
        *,
        limit: int,
    ) -> tuple[PersistedCredential, ...]:
        filters["deletedAt"] = None
        try:
            cursor = (
                self._collection.find(filters)
                .sort("createdAt", DESCENDING)
                .limit(_bounded_limit(limit))
            )
            return tuple(
                CredentialDocumentMapper.from_document(document)
                for document in cursor
            )
        except PyMongoError as error:
            raise _unavailable("credential listing") from error


class MongoAuditEventRepository:
    def __init__(
        self,
        collection: Collection[dict[str, Any]],
    ) -> None:
        self._collection = collection

    def append(self, event: AuditEvent) -> AuditEvent:
        try:
            self._collection.insert_one(
                AuditEventDocumentMapper.to_document(event)
            )
        except DuplicateKeyError as error:
            raise DuplicateEntityError(
                "An audit event with the same id already exists."
            ) from error
        except PyMongoError as error:
            raise _unavailable("audit event insertion") from error
        return event

    def get_by_id(self, event_id: str) -> AuditEvent | None:
        try:
            document = self._collection.find_one(
                {"_id": to_object_id(event_id)}
            )
        except PyMongoError as error:
            raise _unavailable("audit event lookup") from error
        return (
            None
            if document is None
            else AuditEventDocumentMapper.from_document(document)
        )

    def list_recent(
        self,
        *,
        event_type: AuditEventType | None = None,
        limit: int = 100,
    ) -> tuple[AuditEvent, ...]:
        filters = (
            {} if event_type is None else {"eventType": event_type.value}
        )
        try:
            cursor = (
                self._collection.find(filters)
                .sort("createdAt", DESCENDING)
                .limit(_bounded_limit(limit))
            )
            return tuple(
                AuditEventDocumentMapper.from_document(document)
                for document in cursor
            )
        except PyMongoError as error:
            raise _unavailable("audit event listing") from error


class MongoRevocationRepository:
    def __init__(
        self,
        collection: Collection[dict[str, Any]],
    ) -> None:
        self._collection = collection

    def get_by_credential_id(
        self,
        credential_id: str,
    ) -> PersistedCredential | None:
        try:
            document = self._collection.find_one(
                {
                    "credentialId": credential_id,
                    "deletedAt": None,
                }
            )
        except PyMongoError as error:
            raise _unavailable("credential status lookup") from error
        return (
            None
            if document is None
            else CredentialDocumentMapper.from_document(document)
        )

    def revoke(
        self,
        credential_id: str,
        *,
        revoked_at: datetime,
        revoked_by: str,
        revocation_reason: str,
        expected_version: int,
        status_entry: CredentialStatusEntry,
        audit_outbox: AuditOutboxRecord,
    ) -> PersistedCredential:
        self._validate_revocation_records(
            credential_id=credential_id,
            revoked_at=revoked_at,
            revoked_by=revoked_by,
            status_entry=status_entry,
            audit_outbox=audit_outbox,
        )
        try:
            result = self._collection.update_one(
                {
                    "credentialId": credential_id,
                    "version": expected_version,
                    "deletedAt": None,
                    "status": {
                        "$in": [
                            CredentialStatus.ACTIVE.value,
                            CredentialStatus.SUSPENDED.value,
                            CredentialStatus.EXPIRED.value,
                            CredentialStorageStatus.STORED.value,
                            CredentialStorageStatus.VERIFIED.value,
                        ]
                    },
                },
                {
                    "$set": {
                        "status": CredentialStatus.REVOKED.value,
                        "revokedAt": revoked_at,
                        "revokedBy": revoked_by,
                        "revocationReason": revocation_reason,
                        "statusListId": status_entry.status_list_id,
                        "statusListIndex": status_entry.status_list_index,
                        "statusEntryId": to_object_id(status_entry.id),
                        "auditOutbox": (
                            AuditOutboxDocumentMapper.to_document(
                                audit_outbox
                            )
                        ),
                        "updatedAt": revoked_at,
                    },
                    "$inc": {"version": 1},
                },
            )
        except PyMongoError as error:
            raise _unavailable("credential revocation") from error
        if result.matched_count != 1:
            self._raise_revocation_conflict(
                credential_id,
                expected_version=expected_version,
            )
        revoked = self.get_by_credential_id(credential_id)
        if revoked is None:
            raise _unavailable("credential revocation readback")
        return revoked

    @staticmethod
    def _validate_revocation_records(
        *,
        credential_id: str,
        revoked_at: datetime,
        revoked_by: str,
        status_entry: CredentialStatusEntry,
        audit_outbox: AuditOutboxRecord,
    ) -> None:
        event = audit_outbox.event
        if (
            status_entry.credential_id != credential_id
            or audit_outbox.source is not AuditOutboxSource.CREDENTIAL
            or audit_outbox.status is not AuditOutboxStatus.PENDING
            or audit_outbox.aggregate_type != "credential"
            or audit_outbox.aggregate_id != credential_id
            or event.event_type is not AuditEventType.CREDENTIAL_REVOKED
            or event.subject_id != credential_id
            or event.actor_id != revoked_by
            or event.created_at != revoked_at
            or event.metadata
            != {"status": CredentialStatus.REVOKED.value}
        ):
            raise ValueError(
                "Revocation status and outbox records are inconsistent."
            )

    def mark_expired(
        self,
        credential_id: str,
        *,
        expired_at: datetime,
        expected_version: int,
    ) -> PersistedCredential:
        try:
            result = self._collection.update_one(
                {
                    "credentialId": credential_id,
                    "version": expected_version,
                    "deletedAt": None,
                    "status": {
                        "$in": [
                            CredentialStatus.ACTIVE.value,
                            CredentialStatus.SUSPENDED.value,
                            CredentialStorageStatus.STORED.value,
                            CredentialStorageStatus.VERIFIED.value,
                        ]
                    },
                },
                {
                    "$set": {
                        "status": CredentialStatus.EXPIRED.value,
                        "updatedAt": expired_at,
                    },
                    "$inc": {"version": 1},
                },
            )
        except PyMongoError as error:
            raise _unavailable("credential expiration update") from error
        if result.matched_count != 1:
            current = self.get_by_credential_id(credential_id)
            if current is None:
                raise CredentialNotFoundError(
                    "Credential does not exist."
                )
            if current.status in {
                CredentialStatus.REVOKED,
                CredentialStatus.EXPIRED,
            }:
                return current
            raise OptimisticLockError(
                "Credential status changed before expiration update."
            )
        expired = self.get_by_credential_id(credential_id)
        if expired is None:
            raise _unavailable("credential expiration readback")
        return expired

    def _raise_revocation_conflict(
        self,
        credential_id: str,
        *,
        expected_version: int,
    ) -> None:
        current = self.get_by_credential_id(credential_id)
        if current is None:
            raise CredentialNotFoundError("Credential does not exist.")
        if current.status is CredentialStatus.REVOKED:
            raise CredentialAlreadyRevokedError(
                "Credential has already been revoked."
            )
        if current.version != expected_version:
            raise OptimisticLockError(
                "Credential status changed before revocation."
            )
        raise InvalidCredentialStatusTransitionError(
            "Credential cannot be revoked from its current status."
        )


def _bounded_limit(value: int) -> int:
    if not 1 <= value <= 500:
        raise ValueError("Repository list limit must be between 1 and 500.")
    return value


def _validate_update_version(
    entity_version: int,
    expected_version: int,
) -> None:
    if expected_version < 1 or entity_version != expected_version:
        raise OptimisticLockError(
            "The supplied entity version is stale."
        )


def _require_match(matched_count: int, *, entity: str) -> None:
    if matched_count != 1:
        raise OptimisticLockError(
            f"The active {entity} was changed or no longer exists."
        )


def _unavailable(operation: str) -> PersistenceUnavailableError:
    return PersistenceUnavailableError(
        f"MongoDB {operation} could not be completed."
    )


def _allowed_current_statuses(
    target: CredentialStatus,
) -> list[str]:
    legacy_active = [
        CredentialStorageStatus.STORED.value,
        CredentialStorageStatus.VERIFIED.value,
    ]
    if target is CredentialStatus.ACTIVE:
        return [CredentialStatus.ACTIVE.value, *legacy_active]
    if target is CredentialStatus.SUSPENDED:
        return [
            CredentialStatus.ACTIVE.value,
            CredentialStatus.SUSPENDED.value,
            *legacy_active,
        ]
    if target is CredentialStatus.EXPIRED:
        return [
            CredentialStatus.ACTIVE.value,
            CredentialStatus.SUSPENDED.value,
            CredentialStatus.EXPIRED.value,
            *legacy_active,
        ]
    return []


def _query_status_values(
    status: CredentialStatus | CredentialStorageStatus,
) -> list[str]:
    if isinstance(status, CredentialStorageStatus):
        return [
            CredentialStatus.ACTIVE.value,
            CredentialStorageStatus.STORED.value,
            CredentialStorageStatus.VERIFIED.value,
        ]
    if status is CredentialStatus.ACTIVE:
        return [
            CredentialStatus.ACTIVE.value,
            CredentialStorageStatus.STORED.value,
            CredentialStorageStatus.VERIFIED.value,
        ]
    return [status.value]
