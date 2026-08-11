from datetime import datetime
from typing import Any

from pymongo import ASCENDING
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.domain.managed_key import (
    KeyPurpose,
    ManagedKey,
    ManagedKeyConflictError,
    ManagedKeyState,
)
from app.domain.persistence import (
    OptimisticLockError,
    PersistenceUnavailableError,
)
from app.infrastructure.persistence.managed_key_mappers import (
    ManagedKeyDocumentMapper,
)


class MongoManagedKeyRepository:
    def __init__(
        self,
        collection: Collection[dict[str, Any]],
    ) -> None:
        self._collection = collection

    def add(self, key: ManagedKey) -> ManagedKey:
        if key.version != 1:
            raise ValueError("A new managed key must be at version 1.")
        try:
            self._collection.insert_one(
                ManagedKeyDocumentMapper.to_document(key)
            )
        except DuplicateKeyError as error:
            raise ManagedKeyConflictError(
                "Managed key or idempotency identity already exists."
            ) from error
        except PyMongoError as error:
            raise _unavailable("managed key insertion") from error
        return key

    def get(self, key_id: str) -> ManagedKey | None:
        return self._find_one({"keyId": key_id})

    def get_by_provider_reference(
        self,
        *,
        provider: str,
        provider_key_reference: str,
    ) -> ManagedKey | None:
        return self._find_one(
            {
                "provider": provider,
                "providerKeyReference": provider_key_reference,
            }
        )

    def get_by_verification_method(
        self,
        verification_method: str,
    ) -> ManagedKey | None:
        return self._find_one(
            {"verificationMethod": verification_method}
        )

    def get_by_idempotency_hash(
        self,
        *,
        wallet_id: str,
        purpose: KeyPurpose,
        idempotency_key_hash: str,
    ) -> ManagedKey | None:
        return self._find_one(
            {
                "walletId": wallet_id,
                "purpose": purpose.value,
                "idempotencyKeyHash": idempotency_key_hash,
            }
        )

    def get_active(
        self,
        *,
        wallet_id: str,
        purpose: KeyPurpose,
    ) -> ManagedKey | None:
        return self._find_one(
            {
                "walletId": wallet_id,
                "purpose": purpose.value,
                "state": ManagedKeyState.ACTIVE.value,
            }
        )

    def list_for_wallet(
        self,
        wallet_id: str,
        *,
        limit: int = 100,
        after_key_id: str | None = None,
    ) -> tuple[ManagedKey, ...]:
        if not 1 <= limit <= 500:
            raise ValueError("Managed key list limit must be 1 to 500.")
        filters: dict[str, Any] = {"walletId": wallet_id}
        if after_key_id is not None:
            filters["keyId"] = {"$gt": after_key_id}
        return self._find_many(
            filters,
            sort_field="keyId",
            sort_direction=ASCENDING,
            limit=limit,
        )

    def list_versions(
        self,
        *,
        wallet_id: str,
        purpose: KeyPurpose,
    ) -> tuple[ManagedKey, ...]:
        return self._find_many(
            {"walletId": wallet_id, "purpose": purpose.value},
            sort_field="keyVersion",
            sort_direction=ASCENDING,
            limit=500,
        )

    def update(
        self,
        key: ManagedKey,
        *,
        expected_version: int,
    ) -> ManagedKey:
        if key.version != expected_version + 1:
            raise ValueError(
                "Managed key update must increment its metadata version."
            )
        try:
            result = self._collection.replace_one(
                {"keyId": key.key_id, "version": expected_version},
                ManagedKeyDocumentMapper.to_document(key),
            )
        except DuplicateKeyError as error:
            raise ManagedKeyConflictError(
                "Managed key lifecycle update conflicts."
            ) from error
        except PyMongoError as error:
            raise _unavailable("managed key update") from error
        if result.matched_count != 1:
            raise OptimisticLockError(
                "The managed key changed or no longer exists."
            )
        return key

    def claim_rotation(
        self,
        key_id: str,
        *,
        rotated_at: datetime,
        expected_version: int,
    ) -> ManagedKey:
        try:
            result = self._collection.update_one(
                {
                    "keyId": key_id,
                    "state": ManagedKeyState.ACTIVE.value,
                    "version": expected_version,
                },
                {
                    "$set": {
                        "state": ManagedKeyState.ROTATING.value,
                        "rotatedAt": rotated_at,
                        "updatedAt": rotated_at,
                    },
                    "$inc": {"version": 1},
                },
            )
        except PyMongoError as error:
            raise _unavailable("managed key rotation claim") from error
        if result.matched_count != 1:
            raise OptimisticLockError(
                "The managed key rotation was claimed concurrently."
            )
        updated = self.get(key_id)
        if updated is None:
            raise _unavailable("managed key rotation readback")
        return updated

    def link_successor(
        self,
        key_id: str,
        *,
        successor_key_id: str,
        updated_at: datetime,
        expected_version: int,
    ) -> ManagedKey:
        try:
            result = self._collection.update_one(
                {
                    "keyId": key_id,
                    "state": ManagedKeyState.ROTATING.value,
                    "version": expected_version,
                    "successorKeyId": None,
                },
                {
                    "$set": {
                        "successorKeyId": successor_key_id,
                        "updatedAt": updated_at,
                    },
                    "$inc": {"version": 1},
                },
            )
        except PyMongoError as error:
            raise _unavailable("managed key successor link") from error
        if result.matched_count != 1:
            raise OptimisticLockError(
                "The managed key successor was linked concurrently."
            )
        updated = self.get(key_id)
        if updated is None:
            raise _unavailable("managed key successor readback")
        return updated

    def claim_reconciliation(
        self,
        key_id: str,
        *,
        now: datetime,
        lease_until: datetime,
        expected_version: int,
    ) -> ManagedKey | None:
        try:
            result = self._collection.update_one(
                {
                    "keyId": key_id,
                    "version": expected_version,
                    "$or": [
                        {"reconciliationLeaseUntil": None},
                        {"reconciliationLeaseUntil": {"$lte": now}},
                    ],
                },
                {
                    "$set": {
                        "reconciliationLeaseUntil": lease_until,
                        "updatedAt": now,
                    },
                    "$inc": {
                        "reconciliationAttempts": 1,
                        "version": 1,
                    },
                },
            )
        except PyMongoError as error:
            raise _unavailable("managed key reconciliation claim") from error
        return None if result.matched_count != 1 else self.get(key_id)

    def list_reconciliation_candidates(
        self,
        *,
        stale_before: datetime,
        due_before: datetime,
        limit: int,
    ) -> tuple[ManagedKey, ...]:
        if not 1 <= limit <= 500:
            raise ValueError("Reconciliation limit must be 1 to 500.")
        return self._find_many(
            {
                "$or": [
                    {
                        "state": {
                            "$in": [
                                ManagedKeyState.PENDING.value,
                                ManagedKeyState.ROTATING.value,
                                ManagedKeyState.FAILED.value,
                            ]
                        },
                        "updatedAt": {"$lte": stale_before},
                    },
                    {
                        "state": ManagedKeyState.DESTROY_PENDING.value,
                        "destructionScheduledAt": {"$lte": due_before},
                    },
                    {
                        "state": ManagedKeyState.ACTIVE.value,
                        "lastProviderSyncAt": {"$lte": stale_before},
                    },
                ]
            },
            sort_field="updatedAt",
            sort_direction=ASCENDING,
            limit=limit,
        )

    def count_by_state(self) -> dict[ManagedKeyState, int]:
        counts = {state: 0 for state in ManagedKeyState}
        try:
            for document in self._collection.find({}):
                state = ManagedKeyState(document["state"])
                counts[state] += 1
        except (KeyError, ValueError) as error:
            raise _unavailable("managed key state count") from error
        except PyMongoError as error:
            raise _unavailable("managed key state count") from error
        return counts

    def count_active_by_provider_purpose(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        try:
            for document in self._collection.find(
                {"state": ManagedKeyState.ACTIVE.value}
            ):
                provider = str(document["provider"]).casefold()
                purpose = KeyPurpose(document["purpose"]).value
                label = f"{provider}:{purpose}"
                counts[label] = counts.get(label, 0) + 1
        except (KeyError, ValueError) as error:
            raise _unavailable("active managed key count") from error
        except PyMongoError as error:
            raise _unavailable("active managed key count") from error
        return counts

    def _find_one(
        self,
        filters: dict[str, Any],
    ) -> ManagedKey | None:
        try:
            document = self._collection.find_one(filters)
        except PyMongoError as error:
            raise _unavailable("managed key lookup") from error
        return (
            None
            if document is None
            else ManagedKeyDocumentMapper.from_document(document)
        )

    def _find_many(
        self,
        filters: dict[str, Any],
        *,
        sort_field: str,
        sort_direction: int,
        limit: int,
    ) -> tuple[ManagedKey, ...]:
        try:
            cursor = (
                self._collection.find(filters)
                .sort(sort_field, sort_direction)
                .limit(limit)
            )
            return tuple(
                ManagedKeyDocumentMapper.from_document(document)
                for document in cursor
            )
        except PyMongoError as error:
            raise _unavailable("managed key listing") from error


def _unavailable(operation: str) -> PersistenceUnavailableError:
    return PersistenceUnavailableError(
        f"MongoDB {operation} could not be completed."
    )
