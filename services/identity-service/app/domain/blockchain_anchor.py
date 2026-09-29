"""Blockchain Anchor Domain Model.

Defines the entity, value objects, and lifecycle states for cryptographic integrity
anchors persisted to Ethereum-compatible smart contracts and tracked in MongoDB.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping
import uuid


class BlockchainAnchorStatus(str, Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


class AnchorEventType(str, Enum):
    DID_DOCUMENT = "DID_DOCUMENT"
    STATUS_LIST = "STATUS_LIST"
    CREDENTIAL_REVOCATION = "CREDENTIAL_REVOCATION"
    QUARANTINE = "QUARANTINE"
    AUDIT_EVENT = "AUDIT_EVENT"


@dataclass(frozen=True)
class BlockchainAnchorRecord:
    anchor_id: str
    event_type: AnchorEventType
    event_hash: str  # 0x-prefixed 32-byte hex string (SHA-256)
    contract_type: str  # e.g. "DIDRegistry", "RevocationRegistry", "EmergencyRecovery", "AuditLogger"
    contract_address: str
    network: str
    chain_id: int
    status: BlockchainAnchorStatus
    created_at: datetime
    subject_id: str | None = None
    tx_hash: str | None = None
    block_number: int | None = None
    confirmed_at: datetime | None = None
    error_message: str | None = None
    retry_count: int = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def create_pending(
        cls,
        *,
        event_type: AnchorEventType,
        event_hash: str,
        contract_type: str,
        contract_address: str,
        network: str,
        chain_id: int,
        subject_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        anchor_id: str | None = None,
    ) -> BlockchainAnchorRecord:
        return cls(
            anchor_id=anchor_id or str(uuid.uuid4()),
            event_type=event_type,
            event_hash=event_hash,
            contract_type=contract_type,
            contract_address=contract_address,
            network=network,
            chain_id=chain_id,
            status=BlockchainAnchorStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            subject_id=subject_id,
            metadata=dict(metadata or {}),
        )

    def mark_submitted(self, tx_hash: str) -> BlockchainAnchorRecord:
        return BlockchainAnchorRecord(
            anchor_id=self.anchor_id,
            event_type=self.event_type,
            event_hash=self.event_hash,
            contract_type=self.contract_type,
            contract_address=self.contract_address,
            network=self.network,
            chain_id=self.chain_id,
            status=BlockchainAnchorStatus.SUBMITTED,
            created_at=self.created_at,
            subject_id=self.subject_id,
            tx_hash=tx_hash,
            block_number=self.block_number,
            confirmed_at=self.confirmed_at,
            error_message=None,
            retry_count=self.retry_count,
            metadata=self.metadata,
        )

    def mark_confirmed(self, tx_hash: str, block_number: int) -> BlockchainAnchorRecord:
        return BlockchainAnchorRecord(
            anchor_id=self.anchor_id,
            event_type=self.event_type,
            event_hash=self.event_hash,
            contract_type=self.contract_type,
            contract_address=self.contract_address,
            network=self.network,
            chain_id=self.chain_id,
            status=BlockchainAnchorStatus.CONFIRMED,
            created_at=self.created_at,
            subject_id=self.subject_id,
            tx_hash=tx_hash,
            block_number=block_number,
            confirmed_at=datetime.now(timezone.utc),
            error_message=None,
            retry_count=self.retry_count,
            metadata=self.metadata,
        )

    def mark_failed(self, error_message: str) -> BlockchainAnchorRecord:
        return BlockchainAnchorRecord(
            anchor_id=self.anchor_id,
            event_type=self.event_type,
            event_hash=self.event_hash,
            contract_type=self.contract_type,
            contract_address=self.contract_address,
            network=self.network,
            chain_id=self.chain_id,
            status=BlockchainAnchorStatus.FAILED,
            created_at=self.created_at,
            subject_id=self.subject_id,
            tx_hash=self.tx_hash,
            block_number=self.block_number,
            confirmed_at=self.confirmed_at,
            error_message=error_message,
            retry_count=self.retry_count + 1,
            metadata=self.metadata,
        )
