from copy import deepcopy
from datetime import datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId

from app.domain.credential_status import CredentialStatus
from app.domain.permissions import Role
from app.domain.persistence import (
    AuditEvent,
    AuditEventType,
    CredentialStorageStatus,
    DocumentMappingError,
    PersistedCredential,
    PersistedUser,
)


MongoDocument = dict[str, Any]


def new_object_id() -> str:
    return str(ObjectId())


def to_object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as error:
        raise DocumentMappingError(
            "Domain id cannot be converted to ObjectId."
        ) from error


class UserDocumentMapper:
    @staticmethod
    def to_document(user: PersistedUser) -> MongoDocument:
        return {
            "_id": to_object_id(user.id),
            "username": user.username,
            "displayName": user.display_name,
            "roles": [role.value for role in user.roles],
            "enabled": user.enabled,
            "passwordHash": user.password_hash,
            "createdAt": user.created_at,
            "updatedAt": user.updated_at,
            "version": user.version,
            "deletedAt": user.deleted_at,
        }

    @staticmethod
    def from_document(document: MongoDocument) -> PersistedUser:
        try:
            return PersistedUser(
                id=_object_id_string(document["_id"]),
                username=_string(document["username"]),
                display_name=_string(document["displayName"]),
                roles=tuple(Role(value) for value in document["roles"]),
                enabled=_boolean(document["enabled"]),
                password_hash=_string(document["passwordHash"]),
                created_at=_datetime(document["createdAt"]),
                updated_at=_datetime(document["updatedAt"]),
                version=_integer(document["version"]),
                deleted_at=_optional_datetime(document.get("deletedAt")),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise DocumentMappingError(
                "Stored user document is invalid."
            ) from error


class CredentialDocumentMapper:
    @staticmethod
    def to_document(
        credential: PersistedCredential,
    ) -> MongoDocument:
        return {
            "_id": to_object_id(credential.id),
            "credentialId": credential.credential_id,
            "issuerDid": credential.issuer_did,
            "holderDid": credential.holder_did,
            "credentialType": list(credential.credential_type),
            "issuanceDate": credential.issuance_date,
            "expirationDate": credential.expiration_date,
            "credentialHash": credential.credential_hash,
            "status": credential.status.value,
            "revokedAt": credential.revoked_at,
            "revokedBy": credential.revoked_by,
            "revocationReason": credential.revocation_reason,
            "statusListId": credential.status_list_id,
            "statusListIndex": credential.status_list_index,
            "statusEntryId": (
                None
                if credential.status_entry_id is None
                else to_object_id(credential.status_entry_id)
            ),
            "walletId": credential.wallet_id,
            "ownerUserId": credential.owner_user_id,
            "rawCredential": (
                None
                if credential.raw_credential is None
                else deepcopy(dict(credential.raw_credential))
            ),
            "createdAt": credential.created_at,
            "updatedAt": credential.updated_at,
            "version": credential.version,
            "deletedAt": credential.deleted_at,
        }

    @staticmethod
    def from_document(
        document: MongoDocument,
    ) -> PersistedCredential:
        try:
            raw_credential = document.get("rawCredential")
            return PersistedCredential(
                id=_object_id_string(document["_id"]),
                credential_id=_string(document["credentialId"]),
                issuer_did=_string(document["issuerDid"]),
                holder_did=_string(document["holderDid"]),
                credential_type=tuple(
                    _string(value)
                    for value in document["credentialType"]
                ),
                issuance_date=_datetime(document["issuanceDate"]),
                expiration_date=_optional_datetime(
                    document.get("expirationDate")
                ),
                credential_hash=_string(document["credentialHash"]),
                status=_credential_status(document["status"]),
                raw_credential=deepcopy(raw_credential),
                created_at=_datetime(document["createdAt"]),
                updated_at=_datetime(document["updatedAt"]),
                version=_integer(document["version"]),
                deleted_at=_optional_datetime(document.get("deletedAt")),
                revoked_at=_optional_datetime(document.get("revokedAt")),
                revoked_by=_optional_string(document.get("revokedBy")),
                revocation_reason=_optional_string(
                    document.get("revocationReason")
                ),
                status_list_id=_optional_string(
                    document.get("statusListId")
                ),
                status_list_index=_optional_integer(
                    document.get("statusListIndex")
                ),
                status_entry_id=_optional_object_id_string(
                    document.get("statusEntryId")
                ),
                wallet_id=_optional_string(document.get("walletId")),
                owner_user_id=_optional_string(
                    document.get("ownerUserId")
                ),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise DocumentMappingError(
                "Stored credential document is invalid."
            ) from error


class AuditEventDocumentMapper:
    @staticmethod
    def to_document(event: AuditEvent) -> MongoDocument:
        return {
            "_id": to_object_id(event.id),
            "eventType": event.event_type.value,
            "subjectId": event.subject_id,
            "actorId": event.actor_id,
            "correlationId": event.correlation_id,
            "metadata": dict(event.metadata),
            "createdAt": event.created_at,
            "updatedAt": event.updated_at,
            "version": event.version,
        }

    @staticmethod
    def from_document(document: MongoDocument) -> AuditEvent:
        try:
            return AuditEvent(
                id=_object_id_string(document["_id"]),
                event_type=AuditEventType(document["eventType"]),
                subject_id=_optional_string(document.get("subjectId")),
                actor_id=_optional_string(document.get("actorId")),
                correlation_id=_optional_string(
                    document.get("correlationId")
                ),
                metadata={
                    _string(key): _string(value)
                    for key, value in document.get("metadata", {}).items()
                },
                created_at=_datetime(document["createdAt"]),
                updated_at=_datetime(document["updatedAt"]),
                version=_integer(document["version"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise DocumentMappingError(
                "Stored audit event document is invalid."
            ) from error


def _object_id_string(value: Any) -> str:
    if not isinstance(value, ObjectId):
        raise TypeError("Expected ObjectId.")
    return str(value)


def _string(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError("Expected string.")
    return value


def _optional_string(value: Any) -> str | None:
    return None if value is None else _string(value)


def _optional_object_id_string(value: Any) -> str | None:
    return None if value is None else _object_id_string(value)


def _boolean(value: Any) -> bool:
    if not isinstance(value, bool):
        raise TypeError("Expected boolean.")
    return value


def _integer(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("Expected integer.")
    return value


def _datetime(value: Any) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("Expected datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Expected timezone-aware datetime.")
    return value


def _optional_datetime(value: Any) -> datetime | None:
    return None if value is None else _datetime(value)


def _optional_integer(value: Any) -> int | None:
    return None if value is None else _integer(value)


def _credential_status(
    value: Any,
) -> CredentialStatus | CredentialStorageStatus:
    if not isinstance(value, str):
        raise TypeError("Expected credential status string.")
    if value in {
        CredentialStorageStatus.STORED.value,
        CredentialStorageStatus.VERIFIED.value,
    }:
        return CredentialStorageStatus(value)
    return CredentialStatus(value)
