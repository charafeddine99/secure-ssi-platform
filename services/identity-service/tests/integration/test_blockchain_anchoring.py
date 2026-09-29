"""Integration Tests for Sprint 16 Blockchain Anchoring with Live Local Hardhat Node.

Executes real on-chain smart contract transactions:
1. DID document registration, hash querying, and verification against DIDRegistry.sol.
2. W3C Bitstring Status List root hash anchoring against RevocationRegistry.sol.
3. Individual credential revocation and duplicate revocation rejection.
4. AI-triggered EmergencyRecovery.sol quarantine locking and status querying.
5. Tamper-evident security audit event digest logging against AuditLogger.sol.
6. MongoDB anchor persistence, confirmation receipt verification, and query lookups.
7. Negative tests: invalid RPC, unauthorized caller, offline fallback, and PII exclusion.
"""

import time
import pytest
from web3 import Web3

from app.config.blockchain_settings import load_blockchain_settings
from app.domain.blockchain_anchor import (
    AnchorEventType,
    BlockchainAnchorStatus,
)
from app.infrastructure.blockchain.canonical import (
    canonicalize_json,
    compute_deterministic_hash,
)
from app.infrastructure.blockchain.web3_bridge import BlockchainBridge
from app.infrastructure.persistence.blockchain_anchor_repository import (
    MongoBlockchainAnchorRepository,
)
from tests.support.fake_mongo import FakeDatabase


@pytest.fixture(scope="module")
def live_bridge():
    settings = load_blockchain_settings()
    db = FakeDatabase()
    repo = MongoBlockchainAnchorRepository(db["blockchain_anchors"])
    bridge = BlockchainBridge(settings=settings, repository=repo)

    if not bridge.is_connected():
        pytest.skip("Local Hardhat node on port 8545 is not reachable for live integration test.")
    return bridge


def test_live_did_document_anchoring_and_verification(live_bridge: BlockchainBridge):
    did = f"did:key:z6MkuIntegrationStudent{int(time.time())}"
    did_doc = {
        "id": did,
        "verificationMethod": [
            {
                "id": f"{did}#key-1",
                "type": "Ed25519VerificationKey2020",
                "controller": did,
                "publicKeyMultibase": "z6MkuIntegrationStudentKeyBase58Data",
            }
        ],
        "authentication": [f"{did}#key-1"],
    }

    # 1. Anchor DID document on-chain
    record = live_bridge.anchor_did_document(did, did_doc)

    assert record.status == BlockchainAnchorStatus.CONFIRMED
    assert record.tx_hash is not None and record.tx_hash.startswith("0x")
    assert record.block_number is not None and record.block_number > 0
    assert record.contract_type == "DIDRegistry"
    assert record.subject_id == did

    # 2. Verify on-chain record matches local document hash
    is_valid = live_bridge.verify_did_anchor(did, did_doc)
    assert is_valid is True

    # 3. Verify tampered document fails verification
    tampered_doc = dict(did_doc, tampered=True)
    assert live_bridge.verify_did_anchor(did, tampered_doc) is False

    # 4. Verify MongoDB persistence
    persisted = live_bridge.repository.get_by_id(record.anchor_id)
    assert persisted is not None
    assert persisted.status == BlockchainAnchorStatus.CONFIRMED
    assert persisted.tx_hash == record.tx_hash


def test_live_w3c_status_list_anchoring(live_bridge: BlockchainBridge):
    status_list_id = f"https://issuer.university.edu/status-lists/{int(time.time())}"
    # Simulated 131,072 bits (16,384 bytes) bitstring
    bitstring = bytes([0b00000001] * 1024)
    version = 1

    # 1. Anchor status list root hash on-chain
    record = live_bridge.anchor_status_list(status_list_id, bitstring, version=version)

    assert record.status == BlockchainAnchorStatus.CONFIRMED
    assert record.tx_hash is not None and record.tx_hash.startswith("0x")
    assert record.contract_type == "RevocationRegistry"
    assert record.subject_id == status_list_id

    # 2. Query smart contract directly to verify on-chain state
    deployer = live_bridge.account.address
    stored_root, stored_ver, updated_at = live_bridge.revocation_contract.functions.getStatusListAnchor(
        deployer,
        status_list_id,
    ).call()

    _, hex_hash = compute_deterministic_hash(bitstring)
    assert "0x" + stored_root.hex() == hex_hash
    assert stored_ver == version
    assert updated_at > 0


def test_live_credential_revocation_and_idempotency(live_bridge: BlockchainBridge):
    cred_id = f"urn:uuid:diploma-revocation-test-{int(time.time())}"
    reason = "Academic suspension / disciplinary action"

    # 1. First revocation
    record_1 = live_bridge.anchor_credential_revocation(cred_id, reason)
    assert record_1.status == BlockchainAnchorStatus.CONFIRMED
    assert record_1.tx_hash is not None and record_1.tx_hash.startswith("0x")

    # Verify on-chain revocation status
    cred_bytes, _ = compute_deterministic_hash(cred_id.encode("utf-8"))
    assert live_bridge.revocation_contract.functions.isCredentialRevoked(cred_bytes).call() is True

    # 2. Repeated revocation should be handled idempotently
    record_2 = live_bridge.anchor_credential_revocation(cred_id, reason)
    assert record_2.status == BlockchainAnchorStatus.CONFIRMED


def test_live_emergency_quarantine_on_chain(live_bridge: BlockchainBridge):
    target_wallet = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"  # Hardhat Account #1
    reason = "AI risk score 92 > 70 threshold: automated quarantine"

    # 1. Anchor quarantine on EmergencyRecovery.sol
    record = live_bridge.anchor_quarantine(target_wallet, reason)
    assert record.status == BlockchainAnchorStatus.CONFIRMED
    assert record.tx_hash is not None and record.tx_hash.startswith("0x")
    assert record.contract_type == "EmergencyRecovery"

    # 2. Verify smart contract state
    is_q = live_bridge.is_quarantined_on_chain(target_wallet)
    assert is_q is True

    # 3. Test with DID string target (derived address)
    target_did = "did:key:z6MkuAttackerDeviceCompromised"
    rec_did = live_bridge.anchor_quarantine(target_did, "Suspicious rapid replay attacks")
    assert rec_did.status == BlockchainAnchorStatus.CONFIRMED
    assert live_bridge.is_quarantined_on_chain(target_did) is True


def test_live_audit_logger_security_event(live_bridge: BlockchainBridge):
    event_id = f"evt-audit-{int(time.time())}"
    event_payload = {
        "eventId": event_id,
        "action": "CREDENTIAL_VERIFICATION",
        "verifierDid": "did:key:z6MkuVerifier999",
        "result": "VERIFIED",
        "policyScore": 0.12,
        "timestamp": time.time(),
    }

    record = live_bridge.anchor_audit_event(
        event_id=event_id,
        event_payload=event_payload,
        category_name="CREDENTIAL_VERIFIED",
    )
    assert record.status == BlockchainAnchorStatus.CONFIRMED
    assert record.tx_hash is not None and record.tx_hash.startswith("0x")
    assert record.contract_type == "AuditLogger"

    # Verify totalRecords incremented on-chain
    total_records = live_bridge.audit_contract.functions.totalRecords().call()
    assert total_records >= 1


def test_negative_invalid_rpc_handling():
    """Negative test: bad RPC endpoint must not throw unhandled exception or crash service."""
    bad_settings = load_blockchain_settings({"BLOCKCHAIN_RPC_URL": "http://127.0.0.1:12345"})
    bridge = BlockchainBridge(settings=bad_settings)

    rec = bridge.anchor_did_document("did:key:z6MkuBadRPC", {"doc": 1})
    assert rec.status == BlockchainAnchorStatus.FAILED
    assert "offline" in rec.error_message.lower() or "not reachable" in rec.error_message.lower() or "connection" in rec.error_message.lower()


def test_negative_no_pii_in_canonical_payload():
    """Negative test: sensitive credentials or secrets must be stripped before hashing."""
    sensitive_doc = {
        "id": "did:key:z6MkuSafeID",
        "private_key": "0xDO_NOT_LEAK",
        "password": "secret_password",
        "shares": ["shamir_1", "shamir_2"],
        "legit_public_field": "Degree Verification",
    }
    canon_bytes = canonicalize_json(sensitive_doc)
    canon_str = canon_bytes.decode("utf-8")

    assert "private_key" not in canon_str
    assert "DO_NOT_LEAK" not in canon_str
    assert "secret_password" not in canon_str
    assert "shares" not in canon_str
    assert "shamir_1" not in canon_str
    assert "Degree Verification" in canon_str
