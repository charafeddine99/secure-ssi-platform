"""Unit tests for Sprint 16 Blockchain Anchoring.

Verifies:
- RFC 8785 deterministic JSON canonicalization
- Strict sensitive data redaction (zero PII / private keys in hashes)
- SHA-256 cryptographic digest determinism
- BlockchainAnchorRecord lifecycle state machine transitions
- MongoBlockchainAnchorRepository persistence and queries
- BlockchainBridge error handling and fail-open resilience
"""

from datetime import UTC, datetime
import pytest

from app.domain.blockchain_anchor import (
    AnchorEventType,
    BlockchainAnchorRecord,
    BlockchainAnchorStatus,
)
from app.infrastructure.blockchain.canonical import (
    canonicalize_json,
    compute_deterministic_hash,
    redact_sensitive_fields,
    to_bytes32,
)
from app.infrastructure.blockchain.web3_bridge import BlockchainBridge
from app.infrastructure.persistence.blockchain_anchor_repository import (
    MongoBlockchainAnchorRepository,
)
from app.config.blockchain_settings import BlockchainSettings
from tests.support.fake_mongo import FakeDatabase


def test_sensitive_field_redaction():
    payload = {
        "id": "did:key:z6Mku123",
        "private_key": "0xSUPER_SECRET",
        "nested": {
            "password": "my_password",
            "safe_attribute": "degree_bachelor",
            "proofValue": "raw_sig_abc",
        },
        "public_key": "did:key:z6Mku123#key-1",
    }
    redacted = redact_sensitive_fields(payload)

    assert "private_key" not in redacted
    assert "password" not in redacted["nested"]
    assert "proofValue" not in redacted["nested"]
    assert redacted["id"] == "did:key:z6Mku123"
    assert redacted["nested"]["safe_attribute"] == "degree_bachelor"
    assert redacted["public_key"] == "did:key:z6Mku123#key-1"


def test_canonical_json_determinism():
    dict_a = {
        "zeta": 1,
        "alpha": "hello",
        "nested": {"z": 10, "a": 20},
    }
    dict_b = {
        "alpha": "hello",
        "nested": {"a": 20, "z": 10},
        "zeta": 1,
    }

    canon_a = canonicalize_json(dict_a)
    canon_b = canonicalize_json(dict_b)

    assert canon_a == canon_b
    assert canon_a == b'{"alpha":"hello","nested":{"a":20,"z":10},"zeta":1}'


def test_compute_deterministic_hash():
    data_1 = {"credential": "Diploma", "issuer": "did:web:university.edu"}
    data_2 = {"issuer": "did:web:university.edu", "credential": "Diploma"}

    digest_1, hex_1 = compute_deterministic_hash(data_1)
    digest_2, hex_2 = compute_deterministic_hash(data_2)

    assert digest_1 == digest_2
    assert hex_1 == hex_2
    assert hex_1.startswith("0x")
    assert len(hex_1) == 66  # "0x" + 64 hex characters
    assert len(digest_1) == 32

    # to_bytes32 conversion
    b32 = to_bytes32(hex_1)
    assert len(b32) == 32
    assert b32 == digest_1


def test_blockchain_anchor_state_machine():
    record = BlockchainAnchorRecord.create_pending(
        event_type=AnchorEventType.DID_DOCUMENT,
        event_hash="0x" + "a" * 64,
        contract_type="DIDRegistry",
        contract_address="0x5FbDB2315678afecb367f032d93F642f64180aa3",
        network="localhost",
        chain_id=1337,
        subject_id="did:key:z6MkuTest123",
    )
    assert record.status == BlockchainAnchorStatus.PENDING
    assert record.tx_hash is None
    assert record.block_number is None

    # Transition to SUBMITTED
    tx_hash = "0x" + "b" * 64
    submitted = record.mark_submitted(tx_hash)
    assert submitted.status == BlockchainAnchorStatus.SUBMITTED
    assert submitted.tx_hash == tx_hash

    # Transition to CONFIRMED
    confirmed = submitted.mark_confirmed(tx_hash, block_number=42)
    assert confirmed.status == BlockchainAnchorStatus.CONFIRMED
    assert confirmed.block_number == 42
    assert confirmed.confirmed_at is not None
    assert confirmed.error_message is None

    # Test FAILED transition
    failed = record.mark_failed("RPC node timed out")
    assert failed.status == BlockchainAnchorStatus.FAILED
    assert failed.error_message == "RPC node timed out"
    assert failed.retry_count == 1


def test_mongo_blockchain_anchor_repository():
    db = FakeDatabase()
    collection = db["blockchain_anchors"]
    repo = MongoBlockchainAnchorRepository(collection)

    record = BlockchainAnchorRecord.create_pending(
        event_type=AnchorEventType.STATUS_LIST,
        event_hash="0x" + "1" * 64,
        contract_type="RevocationRegistry",
        contract_address="0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",
        network="localhost",
        chain_id=1337,
        subject_id="https://issuer.example.com/status/1",
        metadata={"version": 1},
    )

    # Save pending
    saved = repo.save(record)
    assert saved.anchor_id == record.anchor_id

    # Retrieve by id
    fetched = repo.get_by_id(record.anchor_id)
    assert fetched is not None
    assert fetched.anchor_id == record.anchor_id
    assert fetched.status == BlockchainAnchorStatus.PENDING

    # Retrieve by hash
    by_hash = repo.get_by_event_hash(record.event_hash)
    assert by_hash is not None
    assert by_hash.anchor_id == record.anchor_id

    # Update to confirmed
    confirmed = record.mark_confirmed("0x" + "2" * 64, block_number=100)
    repo.save(confirmed)

    updated = repo.get_by_id(record.anchor_id)
    assert updated is not None
    assert updated.status == BlockchainAnchorStatus.CONFIRMED
    assert updated.tx_hash == "0x" + "2" * 64
    assert updated.block_number == 100

    # Retrieve latest by subject
    latest = repo.get_latest_by_subject("https://issuer.example.com/status/1")
    assert latest is not None
    assert latest.anchor_id == record.anchor_id

    # List by status
    confirmed_list = repo.list_by_status(BlockchainAnchorStatus.CONFIRMED)
    assert len(confirmed_list) == 1
    assert confirmed_list[0].anchor_id == record.anchor_id


def test_blockchain_bridge_offline_resilience():
    """Verifies fail-open behavior: when blockchain is offline, methods return FAILED record without throwing."""
    settings = BlockchainSettings(
        rpc_url="http://127.0.0.1:9999",  # unreachable port
        timeout_seconds=0.5,
        enabled=False,
    )
    bridge = BlockchainBridge(settings=settings)

    assert bridge.is_connected() is False

    # DID anchor when offline
    record = bridge.anchor_did_document("did:key:z6MkuOfflineTest", {"test": "data"})
    assert record.status == BlockchainAnchorStatus.FAILED
    assert "offline" in record.error_message.lower() or "not configured" in record.error_message.lower()

    # Status list anchor when offline
    sl_record = bridge.anchor_status_list("https://example.com/sl", b"\x00" * 16)
    assert sl_record.status == BlockchainAnchorStatus.FAILED

    # Quarantine anchor when offline
    q_record = bridge.anchor_quarantine("did:key:z6MkuAttacker", "AI fraud score > 70")
    assert q_record.status == BlockchainAnchorStatus.FAILED

    # Verify DID anchor returns False when offline
    assert bridge.verify_did_anchor("did:key:z6MkuOfflineTest", {"test": "data"}) is False
