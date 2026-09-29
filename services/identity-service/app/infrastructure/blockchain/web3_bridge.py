"""Web3 Blockchain Bridge for Secure SSI Platform.

Integrates Identity Service with Ethereum/Hardhat smart contracts:
- DIDRegistry.sol: Anchors DID document SHA-256 hashes
- RevocationRegistry.sol: Anchors W3C Bitstring Status List roots and credential revocations
- EmergencyRecovery.sol: On-chain AI-quarantine locking
- AuditLogger.sol: Append-only tamper-evident security audit logs

Adheres strictly to the S16 Non-PII and Fail-Open principles:
- Zero PII or private keys stored on-chain.
- Blockchain outages/timeouts do NOT block core SSI credential issuance or verification.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from eth_account import Account
from web3 import Web3
from web3.exceptions import Web3Exception

from app.config.blockchain_settings import BlockchainSettings, load_blockchain_settings
from app.domain.blockchain_anchor import (
    AnchorEventType,
    BlockchainAnchorRecord,
    BlockchainAnchorStatus,
)
from app.infrastructure.blockchain.canonical import (
    compute_deterministic_hash,
    to_bytes32,
)
from app.infrastructure.persistence.blockchain_anchor_repository import (
    MongoBlockchainAnchorRepository,
)

logger = logging.getLogger(__name__)

# Minimal ABIs for runtime independence and fallback
DID_REGISTRY_ABI = [
    {
        "inputs": [
            {"internalType": "string", "name": "did", "type": "string"},
            {"internalType": "bytes32", "name": "vcHash", "type": "bytes32"},
        ],
        "name": "registerDID",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "string", "name": "did", "type": "string"},
            {"internalType": "bytes32", "name": "newVcHash", "type": "bytes32"},
        ],
        "name": "updateVCHash",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "string", "name": "did", "type": "string"}],
        "name": "getDIDRecord",
        "outputs": [
            {"internalType": "address", "name": "owner", "type": "address"},
            {"internalType": "bytes32", "name": "vcHash", "type": "bytes32"},
            {"internalType": "uint256", "name": "updatedAt", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "string", "name": "did", "type": "string"}],
        "name": "isDIDRegistered",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
]

REVOCATION_REGISTRY_ABI = [
    {
        "inputs": [
            {"internalType": "string", "name": "statusListId", "type": "string"},
            {"internalType": "bytes32", "name": "rootHash", "type": "bytes32"},
            {"internalType": "uint256", "name": "version", "type": "uint256"},
        ],
        "name": "anchorStatusList",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "bytes32", "name": "credentialHash", "type": "bytes32"},
            {"internalType": "bytes32", "name": "reasonHash", "type": "bytes32"},
        ],
        "name": "revokeCredential",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "bytes32", "name": "credentialHash", "type": "bytes32"}],
        "name": "isCredentialRevoked",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "issuer", "type": "address"},
            {"internalType": "string", "name": "statusListId", "type": "string"},
        ],
        "name": "getStatusListAnchor",
        "outputs": [
            {"internalType": "bytes32", "name": "rootHash", "type": "bytes32"},
            {"internalType": "uint256", "name": "version", "type": "uint256"},
            {"internalType": "uint256", "name": "updatedAt", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]

EMERGENCY_RECOVERY_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "wallet", "type": "address"},
            {"internalType": "string", "name": "reason", "type": "string"},
        ],
        "name": "quarantineWallet",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "wallet", "type": "address"}],
        "name": "isWalletQuarantined",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "wallet", "type": "address"}],
        "name": "getWalletOwner",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
]

AUDIT_LOGGER_ABI = [
    {
        "inputs": [
            {"internalType": "bytes32", "name": "eventHash", "type": "bytes32"},
            {"internalType": "uint8", "name": "category", "type": "uint8"},
        ],
        "name": "logEvent",
        "outputs": [{"internalType": "uint256", "name": "recordId", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "totalRecords",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

AUDIT_CATEGORY_MAP = {
    "IDENTITY_ACTION": 0,
    "CREDENTIAL_ISSUED": 1,
    "CREDENTIAL_VERIFIED": 2,
    "FRAUD_DETECTED": 3,
    "ACCOUNT_QUARANTINED": 4,
    "RECOVERY_TRIGGERED": 5,
    "KEY_ROTATED": 6,
}


class BlockchainBridge:
    """Manages secure on-chain transaction lifecycle and fallback caching."""

    def __init__(
        self,
        settings: BlockchainSettings | None = None,
        repository: MongoBlockchainAnchorRepository | None = None,
    ) -> None:
        self.settings = settings or load_blockchain_settings()
        self.repository = repository
        self.w3 = Web3(Web3.HTTPProvider(self.settings.rpc_url, request_kwargs={"timeout": self.settings.timeout_seconds}))
        self.account = None
        if self.settings.private_key:
            try:
                self.account = Account.from_key(self.settings.private_key)
            except Exception as e:
                logger.warning(f"Could not load signer account from private key: {e}")

        # Contracts
        self.did_contract = self._init_contract(self.settings.did_registry_address, DID_REGISTRY_ABI, "DIDRegistry")
        self.revocation_contract = self._init_contract(self.settings.revocation_registry_address, REVOCATION_REGISTRY_ABI, "RevocationRegistry")
        self.recovery_contract = self._init_contract(self.settings.emergency_recovery_address, EMERGENCY_RECOVERY_ABI, "EmergencyRecovery")
        self.audit_contract = self._init_contract(self.settings.audit_logger_address, AUDIT_LOGGER_ABI, "AuditLogger")

    def _init_contract(self, address_str: str, fallback_abi: list, name: str) -> Any:
        try:
            checksum = Web3.to_checksum_address(address_str)
            # Try loading compiled artifact ABI if present
            abi = fallback_abi
            artifact_file = Path(__file__).resolve().parents[4] / "blockchain" / "artifacts" / "contracts" / f"{name}.sol" / f"{name}.json"
            if artifact_file.is_file():
                try:
                    with open(artifact_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        abi = data.get("abi", fallback_abi)
                except Exception:
                    pass
            return self.w3.eth.contract(address=checksum, abi=abi)
        except Exception as e:
            logger.warning(f"Failed to initialize contract {name} at {address_str}: {e}")
            return None

    def is_connected(self) -> bool:
        try:
            return self.settings.enabled and self.w3.is_connected()
        except Exception:
            return False

    def _send_tx(self, contract_call: Any, gas_limit: int = 300_000) -> tuple[str, int]:
        """Builds, signs, submits transaction and waits for receipt. Returns (tx_hash, block_number)."""
        if not self.account:
            raise RuntimeError("Signer account is not configured.")
        nonce = self.w3.eth.get_transaction_count(self.account.address)
        gas_price = self.w3.eth.gas_price
        tx = contract_call.build_transaction({
            "from": self.account.address,
            "nonce": nonce,
            "gas": gas_limit,
            "gasPrice": gas_price,
            "chainId": self.settings.chain_id,
        })
        signed = self.w3.eth.account.sign_transaction(tx, private_key=self.settings.private_key)
        tx_hash_bytes = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        tx_hash_hex = Web3.to_hex(tx_hash_bytes)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash_bytes, timeout=self.settings.timeout_seconds)
        if receipt.status != 1:
            raise RuntimeError(f"Transaction reverted on-chain. Receipt status: {receipt.status}")
        return tx_hash_hex, receipt.blockNumber

    # -------------------------------------------------------------------------
    # 1. DID Document Integrity Anchoring
    # -------------------------------------------------------------------------

    def anchor_did_document(self, did: str, document_dict: dict[str, Any]) -> BlockchainAnchorRecord:
        digest_bytes, hex_hash = compute_deterministic_hash(document_dict)
        bytes32_hash = to_bytes32(digest_bytes)

        record = BlockchainAnchorRecord.create_pending(
            event_type=AnchorEventType.DID_DOCUMENT,
            event_hash=hex_hash,
            contract_type="DIDRegistry",
            contract_address=self.settings.did_registry_address,
            network=self.settings.network_name,
            chain_id=self.settings.chain_id,
            subject_id=did,
        )

        if not self.is_connected() or not self.did_contract:
            record = record.mark_failed("Blockchain RPC node offline or contract not configured.")
            self._save_record(record)
            return record

        try:
            is_reg = self.did_contract.functions.isDIDRegistered(did).call()
            if not is_reg:
                fn_call = self.did_contract.functions.registerDID(did, bytes32_hash)
            else:
                current_owner, current_hash, _ = self.did_contract.functions.getDIDRecord(did).call()
                if current_hash == bytes32_hash:
                    # Idempotent skip: identical hash is already anchored
                    record = record.mark_confirmed(
                        tx_hash="0x" + "0" * 64,
                        block_number=self.w3.eth.block_number,
                    )
                    self._save_record(record)
                    return record
                fn_call = self.did_contract.functions.updateVCHash(did, bytes32_hash)

            tx_hash, block_num = self._send_tx(fn_call)
            record = record.mark_confirmed(tx_hash=tx_hash, block_number=block_num)
        except Exception as e:
            logger.warning(f"DID anchoring on-chain failed (fail-open mode active): {e}")
            record = record.mark_failed(str(e))

        self._save_record(record)
        return record

    def verify_did_anchor(self, did: str, document_dict: dict[str, Any]) -> bool:
        """Verifies if the canonical hash of the DID document matches the on-chain record."""
        if not self.is_connected() or not self.did_contract:
            return False
        try:
            digest_bytes, _ = compute_deterministic_hash(document_dict)
            bytes32_hash = to_bytes32(digest_bytes)
            if not self.did_contract.functions.isDIDRegistered(did).call():
                return False
            _, stored_hash, _ = self.did_contract.functions.getDIDRecord(did).call()
            return stored_hash == bytes32_hash
        except Exception as e:
            logger.warning(f"Error querying DID on-chain anchor: {e}")
            return False

    # -------------------------------------------------------------------------
    # 2. W3C Status List & Revocation Anchoring
    # -------------------------------------------------------------------------

    def anchor_status_list(self, status_list_id: str, bitstring_bytes: bytes, version: int = 1) -> BlockchainAnchorRecord:
        digest_bytes, hex_hash = compute_deterministic_hash(bitstring_bytes)
        bytes32_hash = to_bytes32(digest_bytes)

        record = BlockchainAnchorRecord.create_pending(
            event_type=AnchorEventType.STATUS_LIST,
            event_hash=hex_hash,
            contract_type="RevocationRegistry",
            contract_address=self.settings.revocation_registry_address,
            network=self.settings.network_name,
            chain_id=self.settings.chain_id,
            subject_id=status_list_id,
            metadata={"version": version},
        )

        if not self.is_connected() or not self.revocation_contract:
            record = record.mark_failed("Blockchain RPC node offline or contract not configured.")
            self._save_record(record)
            return record

        try:
            fn_call = self.revocation_contract.functions.anchorStatusList(status_list_id, bytes32_hash, version)
            tx_hash, block_num = self._send_tx(fn_call)
            record = record.mark_confirmed(tx_hash=tx_hash, block_number=block_num)
        except Exception as e:
            logger.warning(f"Status list anchoring failed: {e}")
            record = record.mark_failed(str(e))

        self._save_record(record)
        return record

    def anchor_credential_revocation(self, credential_id: str, reason: str) -> BlockchainAnchorRecord:
        cred_bytes, hex_cred_hash = compute_deterministic_hash(credential_id.encode("utf-8"))
        reason_bytes, hex_reason_hash = compute_deterministic_hash(reason.encode("utf-8"))
        bytes32_cred = to_bytes32(cred_bytes)
        bytes32_reason = to_bytes32(reason_bytes)

        record = BlockchainAnchorRecord.create_pending(
            event_type=AnchorEventType.CREDENTIAL_REVOCATION,
            event_hash=hex_cred_hash,
            contract_type="RevocationRegistry",
            contract_address=self.settings.revocation_registry_address,
            network=self.settings.network_name,
            chain_id=self.settings.chain_id,
            subject_id=credential_id,
            metadata={"reason": reason, "reason_hash": hex_reason_hash},
        )

        if not self.is_connected() or not self.revocation_contract:
            record = record.mark_failed("Blockchain RPC offline.")
            self._save_record(record)
            return record

        try:
            # Check idempotency
            is_revoked = self.revocation_contract.functions.isCredentialRevoked(bytes32_cred).call()
            if is_revoked:
                record = record.mark_confirmed(tx_hash="0x" + "0" * 64, block_number=self.w3.eth.block_number)
                self._save_record(record)
                return record

            fn_call = self.revocation_contract.functions.revokeCredential(bytes32_cred, bytes32_reason)
            tx_hash, block_num = self._send_tx(fn_call)
            record = record.mark_confirmed(tx_hash=tx_hash, block_number=block_num)
        except Exception as e:
            logger.warning(f"Credential revocation anchoring failed: {e}")
            record = record.mark_failed(str(e))

        self._save_record(record)
        return record

    # -------------------------------------------------------------------------
    # 3. Emergency Recovery & AI Quarantine Anchoring
    # -------------------------------------------------------------------------

    def anchor_quarantine(self, target_address_or_did: str, reason: str) -> BlockchainAnchorRecord:
        digest_bytes, hex_hash = compute_deterministic_hash(f"QUARANTINE:{target_address_or_did}:{reason}".encode("utf-8"))
        record = BlockchainAnchorRecord.create_pending(
            event_type=AnchorEventType.QUARANTINE,
            event_hash=hex_hash,
            contract_type="EmergencyRecovery",
            contract_address=self.settings.emergency_recovery_address,
            network=self.settings.network_name,
            chain_id=self.settings.chain_id,
            subject_id=target_address_or_did,
            metadata={"reason": reason},
        )

        if not self.is_connected() or not self.recovery_contract:
            record = record.mark_failed("Blockchain RPC node offline.")
            self._save_record(record)
            return record

        try:
            # EmergencyRecovery requires a valid Ethereum address
            if Web3.is_address(target_address_or_did):
                target_wallet = Web3.to_checksum_address(target_address_or_did)
            else:
                # Derive deterministic mock wallet from DID string for contract call
                raw_hash = Web3.keccak(text=target_address_or_did)
                target_wallet = Web3.to_checksum_address("0x" + raw_hash.hex()[-40:])

            is_already_q = self.recovery_contract.functions.isWalletQuarantined(target_wallet).call()
            if is_already_q:
                record = record.mark_confirmed(tx_hash="0x" + "0" * 64, block_number=self.w3.eth.block_number)
                self._save_record(record)
                return record

            fn_call = self.recovery_contract.functions.quarantineWallet(target_wallet, reason)
            tx_hash, block_num = self._send_tx(fn_call)
            record = record.mark_confirmed(tx_hash=tx_hash, block_number=block_num)
        except Exception as e:
            logger.warning(f"Quarantine on-chain lock failed: {e}")
            record = record.mark_failed(str(e))

        self._save_record(record)
        return record

    def is_quarantined_on_chain(self, target_address_or_did: str) -> bool:
        if not self.is_connected() or not self.recovery_contract:
            return False
        try:
            if Web3.is_address(target_address_or_did):
                wallet = Web3.to_checksum_address(target_address_or_did)
            else:
                raw_hash = Web3.keccak(text=target_address_or_did)
                wallet = Web3.to_checksum_address("0x" + raw_hash.hex()[-40:])
            return self.recovery_contract.functions.isWalletQuarantined(wallet).call()
        except Exception as e:
            logger.warning(f"Error checking on-chain quarantine: {e}")
            return False

    # -------------------------------------------------------------------------
    # 4. Audit Logger Anchoring
    # -------------------------------------------------------------------------

    def anchor_audit_event(
        self,
        event_id: str,
        event_payload: Mapping[str, Any],
        category_name: str = "IDENTITY_ACTION",
    ) -> BlockchainAnchorRecord:
        digest_bytes, hex_hash = compute_deterministic_hash(event_payload)
        bytes32_hash = to_bytes32(digest_bytes)
        cat_enum = AUDIT_CATEGORY_MAP.get(category_name, 0)

        record = BlockchainAnchorRecord.create_pending(
            event_type=AnchorEventType.AUDIT_EVENT,
            event_hash=hex_hash,
            contract_type="AuditLogger",
            contract_address=self.settings.audit_logger_address,
            network=self.settings.network_name,
            chain_id=self.settings.chain_id,
            subject_id=event_id,
            metadata={"category": category_name},
        )

        if not self.is_connected() or not self.audit_contract:
            record = record.mark_failed("Blockchain RPC node offline.")
            self._save_record(record)
            return record

        try:
            fn_call = self.audit_contract.functions.logEvent(bytes32_hash, cat_enum)
            tx_hash, block_num = self._send_tx(fn_call)
            record = record.mark_confirmed(tx_hash=tx_hash, block_number=block_num)
        except Exception as e:
            logger.warning(f"Audit log on-chain anchor failed: {e}")
            record = record.mark_failed(str(e))

        self._save_record(record)
        return record

    def _save_record(self, record: BlockchainAnchorRecord) -> None:
        if self.repository is not None:
            try:
                self.repository.save(record)
            except Exception as e:
                logger.warning(f"Could not persist anchor record to MongoDB: {e}")
