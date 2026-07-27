from copy import deepcopy
from datetime import datetime
from typing import Any

from bson import ObjectId

from app.domain.audit_outbox import (
    AuditOutboxRecord,
    AuditOutboxSource,
    AuditOutboxStatus,
)
from app.domain.bitstring_status_list import (
    CredentialStatusEntry,
    StatusListPublication,
    StatusPurpose,
)
from app.domain.persistence import DocumentMappingError
from app.infrastructure.persistence.mappers import (
    AuditEventDocumentMapper,
    MongoDocument,
    to_object_id,
)


class CredentialStatusEntryDocumentMapper:
    @staticmethod
    def to_document(entry: CredentialStatusEntry) -> MongoDocument:
        return {
            "_id": to_object_id(entry.id),
            "credentialId": entry.credential_id,
            "issuerDid": entry.issuer_did,
            "statusListId": entry.status_list_id,
            "statusListIndex": entry.status_list_index,
            "statusPurpose": entry.status_purpose.value,
            "createdAt": entry.created_at,
            "updatedAt": entry.updated_at,
            "version": entry.version,
        }

    @staticmethod
    def from_document(document: MongoDocument) -> CredentialStatusEntry:
        try:
            return CredentialStatusEntry(
                id=_object_id_string(document["_id"]),
                credential_id=_string(document["credentialId"]),
                issuer_did=_string(document["issuerDid"]),
                status_list_id=_string(document["statusListId"]),
                status_list_index=_integer(document["statusListIndex"]),
                status_purpose=StatusPurpose(document["statusPurpose"]),
                created_at=_datetime(document["createdAt"]),
                updated_at=_datetime(document["updatedAt"]),
                version=_integer(document["version"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise DocumentMappingError(
                "Stored credential status entry is invalid."
            ) from error


class StatusListPublicationDocumentMapper:
    @staticmethod
    def to_document(publication: StatusListPublication) -> MongoDocument:
        return {
            "_id": to_object_id(publication.id),
            "statusListId": publication.status_list_id,
            "issuerDid": publication.issuer_did,
            "statusPurpose": publication.status_purpose.value,
            "encodedList": publication.encoded_list,
            "contentHash": publication.content_hash,
            "document": deepcopy(dict(publication.document)),
            "listLength": publication.list_length,
            "capacity": publication.capacity,
            "assignedEntries": publication.assigned_entries,
            "revokedEntries": publication.revoked_entries,
            "ttlSeconds": publication.ttl_seconds,
            "etag": publication.etag,
            "publishedAt": publication.published_at,
            "createdAt": publication.created_at,
            "updatedAt": publication.updated_at,
            "version": publication.version,
        }

    @staticmethod
    def from_document(document: MongoDocument) -> StatusListPublication:
        try:
            raw_document = document["document"]
            if not isinstance(raw_document, dict):
                raise TypeError("Expected status-list document mapping.")
            return StatusListPublication(
                id=_object_id_string(document["_id"]),
                status_list_id=_string(document["statusListId"]),
                issuer_did=_string(document["issuerDid"]),
                status_purpose=StatusPurpose(document["statusPurpose"]),
                encoded_list=_string(document["encodedList"]),
                content_hash=_string(document["contentHash"]),
                document=deepcopy(raw_document),
                list_length=_integer(document["listLength"]),
                capacity=_integer(
                    document.get("capacity", document["listLength"])
                ),
                assigned_entries=_integer(document["assignedEntries"]),
                revoked_entries=_integer(document["revokedEntries"]),
                ttl_seconds=_integer(document["ttlSeconds"]),
                etag=_string(document["etag"]),
                published_at=_datetime(document["publishedAt"]),
                created_at=_datetime(document["createdAt"]),
                updated_at=_datetime(document["updatedAt"]),
                version=_integer(document["version"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise DocumentMappingError(
                "Stored status-list publication is invalid."
            ) from error


class AuditOutboxDocumentMapper:
    @staticmethod
    def to_document(record: AuditOutboxRecord) -> MongoDocument:
        return {
            "_id": to_object_id(record.event.id),
            "event": AuditEventDocumentMapper.to_document(record.event),
            "aggregateType": record.aggregate_type,
            "aggregateId": record.aggregate_id,
            "source": record.source.value,
            "status": record.status.value,
            "attempts": record.attempts,
            "availableAt": record.available_at,
            "leaseUntil": record.lease_until,
            "deliveredAt": record.delivered_at,
            "lastError": record.last_error,
            "createdAt": record.created_at,
            "updatedAt": record.updated_at,
            "version": record.version,
        }

    @staticmethod
    def from_document(document: MongoDocument) -> AuditOutboxRecord:
        try:
            event_document = document["event"]
            if not isinstance(event_document, dict):
                raise TypeError("Expected embedded audit event.")
            return AuditOutboxRecord(
                event=AuditEventDocumentMapper.from_document(event_document),
                aggregate_type=_string(document["aggregateType"]),
                aggregate_id=_string(document["aggregateId"]),
                source=AuditOutboxSource(document["source"]),
                status=AuditOutboxStatus(document["status"]),
                attempts=_integer(document["attempts"]),
                available_at=_datetime(document["availableAt"]),
                lease_until=_optional_datetime(document.get("leaseUntil")),
                delivered_at=_optional_datetime(
                    document.get("deliveredAt")
                ),
                last_error=_optional_string(document.get("lastError")),
                created_at=_datetime(document["createdAt"]),
                updated_at=_datetime(document["updatedAt"]),
                version=_integer(document["version"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise DocumentMappingError(
                "Stored audit outbox record is invalid."
            ) from error


def _string(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError("Expected string.")
    return value


def _optional_string(value: Any) -> str | None:
    return None if value is None else _string(value)


def _integer(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("Expected integer.")
    return value


def _object_id_string(value: Any) -> str:
    if not isinstance(value, ObjectId):
        raise TypeError("Expected ObjectId.")
    return str(value)


def _datetime(value: Any) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("Expected datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Expected timezone-aware datetime.")
    return value


def _optional_datetime(value: Any) -> datetime | None:
    return None if value is None else _datetime(value)
