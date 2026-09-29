"""MongoDB Repository for Blockchain Anchors.

Persists and queries cryptographic anchor records, receipts, and state transitions
for on-chain integrity attestations.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from app.domain.blockchain_anchor import (
    AnchorEventType,
    BlockchainAnchorRecord,
    BlockchainAnchorStatus,
)
from app.domain.persistence import PersistenceUnavailableError


Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


def _to_document(record: BlockchainAnchorRecord) -> dict[str, Any]:
    return {
        "anchorId": record.anchor_id,
        "eventType": record.event_type.value,
        "eventHash": record.event_hash,
        "contractType": record.contract_type,
        "contractAddress": record.contract_address,
        "network": record.network,
        "chainId": record.chain_id,
        "status": record.status.value,
        "createdAt": record.created_at,
        "subjectId": record.subject_id,
        "txHash": record.tx_hash,
        "blockNumber": record.block_number,
        "confirmedAt": record.confirmed_at,
        "errorMessage": record.error_message,
        "retryCount": record.retry_count,
        "metadata": dict(record.metadata),
    }


def _to_record(doc: dict[str, Any]) -> BlockchainAnchorRecord:
    return BlockchainAnchorRecord(
        anchor_id=doc["anchorId"],
        event_type=AnchorEventType(doc["eventType"]),
        event_hash=doc["eventHash"],
        contract_type=doc["contractType"],
        contract_address=doc["contractAddress"],
        network=doc["network"],
        chain_id=int(doc["chainId"]),
        status=BlockchainAnchorStatus(doc["status"]),
        created_at=doc["createdAt"],
        subject_id=doc.get("subjectId"),
        tx_hash=doc.get("txHash"),
        block_number=doc.get("blockNumber"),
        confirmed_at=doc.get("confirmedAt"),
        error_message=doc.get("errorMessage"),
        retry_count=int(doc.get("retryCount", 0)),
        metadata=doc.get("metadata", {}),
    )


class MongoBlockchainAnchorRepository:
    def __init__(
        self,
        collection: Collection[dict[str, Any]],
        *,
        clock: Clock = utc_now,
    ) -> None:
        self._collection = collection
        self._clock = clock

    def save(self, record: BlockchainAnchorRecord) -> BlockchainAnchorRecord:
        doc = _to_document(record)
        try:
            self._collection.update_one(
                {"anchorId": record.anchor_id},
                {"$set": doc},
                upsert=True,
            )
            return record
        except PyMongoError as err:
            raise PersistenceUnavailableError(
                f"Failed to persist blockchain anchor: {err}"
            ) from err

    def get_by_id(self, anchor_id: str) -> BlockchainAnchorRecord | None:
        try:
            doc = self._collection.find_one({"anchorId": anchor_id})
            return _to_record(doc) if doc else None
        except PyMongoError as err:
            raise PersistenceUnavailableError(
                f"Failed to query blockchain anchor by id: {err}"
            ) from err

    def get_by_event_hash(self, event_hash: str) -> BlockchainAnchorRecord | None:
        try:
            doc = self._collection.find_one({"eventHash": event_hash})
            return _to_record(doc) if doc else None
        except PyMongoError as err:
            raise PersistenceUnavailableError(
                f"Failed to query blockchain anchor by event hash: {err}"
            ) from err

    def get_latest_by_subject(
        self,
        subject_id: str,
        event_type: AnchorEventType | None = None,
    ) -> BlockchainAnchorRecord | None:
        query: dict[str, Any] = {"subjectId": subject_id}
        if event_type:
            query["eventType"] = event_type.value
        try:
            cursor = self._collection.find(query).sort("createdAt", DESCENDING)
            docs = list(cursor)
            doc = docs[0] if docs else None
            return _to_record(doc) if doc else None
        except PyMongoError as err:
            raise PersistenceUnavailableError(
                f"Failed to query blockchain anchor by subject: {err}"
            ) from err

    def list_by_status(
        self,
        status: BlockchainAnchorStatus,
        limit: int = 50,
    ) -> list[BlockchainAnchorRecord]:
        try:
            cursor = self._collection.find(
                {"status": status.value}
            ).sort("createdAt", DESCENDING).limit(limit)
            return [_to_record(doc) for doc in cursor]
        except PyMongoError as err:
            raise PersistenceUnavailableError(
                f"Failed to list blockchain anchors by status: {err}"
            ) from err

    def list_all(self, limit: int = 100) -> list[BlockchainAnchorRecord]:
        try:
            cursor = self._collection.find(
                {}
            ).sort("createdAt", DESCENDING).limit(limit)
            return [_to_record(doc) for doc in cursor]
        except PyMongoError as err:
            raise PersistenceUnavailableError(
                f"Failed to list blockchain anchors: {err}"
            ) from err
