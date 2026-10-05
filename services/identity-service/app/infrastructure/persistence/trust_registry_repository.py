from __future__ import annotations

from copy import deepcopy
from typing import Any
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.application.ports.trust_registry import TrustRegistryRepository
from app.domain.persistence import (
    DuplicateEntityError,
    OptimisticLockError,
    PersistenceUnavailableError,
)
from app.domain.trust_registry import TrustRecord, TrustRole, TrustStatus
from app.infrastructure.persistence.mappers import to_object_id


class TrustRecordDocumentMapper:
    @staticmethod
    def to_document(record: TrustRecord) -> dict[str, Any]:
        return {
            "_id": to_object_id(record.id),
            "recordId": record.id,
            "issuerDid": record.issuer_did,
            "organizationName": record.organization_name,
            "trustStatus": record.trust_status.value,
            "roles": [r.value for r in record.roles],
            "permittedCredentialTypes": list(record.permitted_credential_types),
            "validFrom": record.valid_from,
            "validUntil": record.valid_until,
            "trustSource": record.trust_source,
            "trustAnchor": record.trust_anchor,
            "createdAt": record.created_at,
            "updatedAt": record.updated_at,
            "createdBy": record.created_by,
            "auditMetadata": deepcopy(dict(record.audit_metadata)),
            "version": record.version,
        }

    @staticmethod
    def from_document(doc: dict[str, Any]) -> TrustRecord:
        raw_roles = doc.get("roles") or ["issuer"]
        roles = tuple(TrustRole(r) for r in raw_roles if r in TrustRole._value2member_map_)
        return TrustRecord(
            id=str(doc.get("recordId") or doc["_id"]),
            issuer_did=doc["issuerDid"],
            organization_name=doc["organizationName"],
            trust_status=TrustStatus(doc["trustStatus"]),
            roles=roles or (TrustRole.ISSUER,),
            permitted_credential_types=tuple(doc.get("permittedCredentialTypes") or ("VerifiableCredential",)),
            valid_from=doc["validFrom"],
            valid_until=doc.get("validUntil"),
            trust_source=doc.get("trustSource", "LOCAL_TRUST_REGISTRY"),
            trust_anchor=doc.get("trustAnchor"),
            created_at=doc["createdAt"],
            updated_at=doc["updatedAt"],
            created_by=doc.get("createdBy", "admin@platform.local"),
            audit_metadata=doc.get("auditMetadata", {}),
            version=doc.get("version", 1),
        )


class MongoTrustRegistryRepository(TrustRegistryRepository):
    def __init__(self, collection: Collection[dict[str, Any]]) -> None:
        self._collection = collection

    def add(self, record: TrustRecord) -> TrustRecord:
        try:
            doc = TrustRecordDocumentMapper.to_document(record)
            self._collection.insert_one(doc)
            return record
        except DuplicateKeyError as error:
            raise DuplicateEntityError(
                f"Trust record for issuer '{record.issuer_did}' already exists."
            ) from error
        except PyMongoError as error:
            raise PersistenceUnavailableError(
                f"Failed to persist trust record for issuer '{record.issuer_did}'."
            ) from error

    def get_by_issuer_did(self, issuer_did: str) -> TrustRecord | None:
        try:
            doc = self._collection.find_one({"issuerDid": issuer_did})
            return TrustRecordDocumentMapper.from_document(doc) if doc else None
        except PyMongoError as error:
            raise PersistenceUnavailableError(
                f"Failed to lookup trust record for issuer '{issuer_did}'."
            ) from error

    def get_by_id(self, record_id: str) -> TrustRecord | None:
        try:
            try:
                oid = to_object_id(record_id)
                query: dict[str, Any] = {"$or": [{"_id": oid}, {"recordId": record_id}]}
            except Exception:
                query = {"recordId": record_id}
            doc = self._collection.find_one(query)
            return TrustRecordDocumentMapper.from_document(doc) if doc else None
        except PyMongoError as error:
            raise PersistenceUnavailableError(
                f"Failed to lookup trust record by id '{record_id}'."
            ) from error

    def list_all(
        self,
        status: TrustStatus | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[TrustRecord]:
        try:
            query: dict[str, Any] = {}
            if status is not None:
                query["trustStatus"] = status.value
            cursor = (
                self._collection.find(query)
                .sort("createdAt", DESCENDING)
                .skip(skip)
                .limit(limit)
            )
            return [TrustRecordDocumentMapper.from_document(doc) for doc in cursor]
        except PyMongoError as error:
            raise PersistenceUnavailableError(
                "Failed to list trust records."
            ) from error

    def update(self, record: TrustRecord, expected_version: int) -> TrustRecord:
        try:
            new_version = expected_version + 1
            update_fields = {
                "organizationName": record.organization_name,
                "trustStatus": record.trust_status.value,
                "roles": [r.value for r in record.roles],
                "permittedCredentialTypes": list(record.permitted_credential_types),
                "validFrom": record.valid_from,
                "validUntil": record.valid_until,
                "trustSource": record.trust_source,
                "trustAnchor": record.trust_anchor,
                "updatedAt": record.updated_at,
                "auditMetadata": deepcopy(dict(record.audit_metadata)),
                "version": new_version,
            }
            try:
                oid = to_object_id(record.id)
                query: dict[str, Any] = {
                    "$or": [{"_id": oid}, {"recordId": record.id}],
                    "version": expected_version,
                }
            except Exception:
                query = {"recordId": record.id, "version": expected_version}

            result = self._collection.update_one(query, {"$set": update_fields})
            if result.matched_count == 0:
                raise OptimisticLockError(
                    f"Trust record '{record.id}' version mismatch or record not found."
                )
            # Return updated record with incremented version
            return TrustRecord(
                id=record.id,
                issuer_did=record.issuer_did,
                organization_name=record.organization_name,
                trust_status=record.trust_status,
                roles=record.roles,
                permitted_credential_types=record.permitted_credential_types,
                valid_from=record.valid_from,
                valid_until=record.valid_until,
                trust_source=record.trust_source,
                trust_anchor=record.trust_anchor,
                created_at=record.created_at,
                updated_at=record.updated_at,
                created_by=record.created_by,
                audit_metadata=record.audit_metadata,
                version=new_version,
            )
        except (OptimisticLockError, DuplicateEntityError):
            raise
        except PyMongoError as error:
            raise PersistenceUnavailableError(
                f"Failed to update trust record '{record.id}'."
            ) from error

    def delete(self, record_id: str) -> bool:
        try:
            try:
                oid = to_object_id(record_id)
                query: dict[str, Any] = {"$or": [{"_id": oid}, {"recordId": record_id}]}
            except Exception:
                query = {"recordId": record_id}
            result = self._collection.delete_one(query)
            return result.deleted_count > 0
        except PyMongoError as error:
            raise PersistenceUnavailableError(
                f"Failed to delete trust record '{record_id}'."
            ) from error


class InMemoryTrustRegistryRepository(TrustRegistryRepository):
    """In-memory trust registry repository for unit testing and local fallbacks."""

    def __init__(self) -> None:
        self._records: dict[str, TrustRecord] = {}

    def add(self, record: TrustRecord) -> TrustRecord:
        for r in self._records.values():
            if r.issuer_did == record.issuer_did:
                raise DuplicateEntityError(
                    f"Trust record for '{record.issuer_did}' already exists."
                )
        self._records[record.id] = record
        return record

    def get_by_issuer_did(self, issuer_did: str) -> TrustRecord | None:
        for r in self._records.values():
            if r.issuer_did == issuer_did:
                return r
        return None

    def get_by_id(self, record_id: str) -> TrustRecord | None:
        return self._records.get(record_id)

    def list_all(
        self,
        status: TrustStatus | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[TrustRecord]:
        results = [
            r for r in self._records.values()
            if status is None or r.trust_status == status
        ]
        return results[skip : skip + limit]

    def update(
        self,
        record: TrustRecord,
        expected_version: int,
    ) -> TrustRecord:
        existing = self._records.get(record.id)
        if existing is None:
            raise ValueError(f"Trust record with id '{record.id}' not found.")
        if existing.version != expected_version:
            raise OptimisticLockError(
                f"Version mismatch: {existing.version} != {expected_version}"
            )
        new_version = existing.version + 1
        updated = TrustRecord(
            id=record.id,
            issuer_did=record.issuer_did,
            organization_name=record.organization_name,
            trust_status=record.trust_status,
            roles=record.roles,
            permitted_credential_types=record.permitted_credential_types,
            valid_from=record.valid_from,
            valid_until=record.valid_until,
            trust_source=record.trust_source,
            trust_anchor=record.trust_anchor,
            created_at=record.created_at,
            updated_at=record.updated_at,
            created_by=record.created_by,
            audit_metadata=record.audit_metadata,
            version=new_version,
        )
        self._records[record.id] = updated
        return updated

    def delete(self, record_id: str) -> bool:
        if record_id in self._records:
            del self._records[record_id]
            return True
        return False

