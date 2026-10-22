import time
import hashlib
from typing import Optional, Dict, Any

class CredentialStatusCache:
    """
    Tasarım Raporu Tablo 3.3 ve Madde 109, 156, 169 gereğince:
    Credential ve Status List sorgularını Redis / Memory katmanında önbelleğe alarak
    doğrulama gecikmesini 120-180 ms'den ~85 ms altına düşürür.
    """
    def __init__(self, ttl_seconds: int = 300):
        self.ttl = ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if not entry:
            return None
        if time.time() > entry["expires_at"]:
            del self._cache[key]
            return None
        return entry["value"]

    def set(self, key: str, value: Any, custom_ttl: Optional[int] = None) -> None:
        ttl = custom_ttl if custom_ttl is not None else self.ttl
        self._cache[key] = {
            "value": value,
            "expires_at": time.time() + ttl
        }

    def invalidate(self, key: str) -> None:
        self._cache.pop(key, None)

class BlockchainAnchorClient:
    """
    Blockchain Katmanı (DIDRegistry, RevocationRegistry, AuditLogger, EmergencyRecovery) ile
    Identity Service arasındaki Web3 bağlantı köprüsü (Maddeler: 44, 46, 47, 48).
    Supports optional Hardhat anchoring and explicit in-memory demo state.
    A locally requested anchor is never represented as a confirmed receipt.
    """
    def __init__(self, rpc_url: str = "http://127.0.0.1:8545"):
        self.rpc_url = rpc_url
        self._anchored_events: list = []
        self._quarantined_subjects: set[str] = set()
        try:
            from app.config.blockchain_settings import load_blockchain_settings
            from app.infrastructure.blockchain.web3_bridge import BlockchainBridge
            settings = load_blockchain_settings({"BLOCKCHAIN_RPC_URL": rpc_url})
            self._bridge = BlockchainBridge(settings=settings)
        except Exception:
            self._bridge = None

    @property
    def bridge(self) -> Any:
        return self._bridge

    def anchor_did_document(self, did: str, document_dict: dict) -> str:
        tx_hash = None
        block_number = None
        record = None
        if self._bridge:
            try:
                rec = self._bridge.anchor_did_document(did, document_dict)
                record = rec
                doc_hash = rec.event_hash
                tx_hash = rec.tx_hash
                block_number = rec.block_number
            except Exception:
                from app.infrastructure.blockchain.canonical import compute_deterministic_hash
                _, doc_hash = compute_deterministic_hash(document_dict)
        else:
            raw_doc = str(sorted(document_dict.items())).encode("utf-8")
            doc_hash = "0x" + hashlib.sha256(raw_doc).hexdigest()

        self._anchored_events.append({
            "type": "DID_ANCHOR",
            "did": did,
            "doc_hash": doc_hash,
            "tx_hash": tx_hash,
            "block_number": block_number,
            "anchor_status": record.status.value if record else "UNANCHORED",
            "timestamp": time.time(),
        })
        return doc_hash

    def anchor_revocation_status(self, credential_id: str, reason: str) -> str:
        tx_hash = None
        block_number = None
        record = None
        if self._bridge:
            try:
                rec = self._bridge.anchor_credential_revocation(credential_id, reason)
                record = rec
                rev_hash = rec.event_hash
                tx_hash = rec.tx_hash
                block_number = rec.block_number
            except Exception:
                from app.infrastructure.blockchain.canonical import compute_deterministic_hash
                _, rev_hash = compute_deterministic_hash(f"{credential_id}:{reason}".encode("utf-8"))
        else:
            raw_rec = f"{credential_id}:{reason}".encode("utf-8")
            rev_hash = "0x" + hashlib.sha256(raw_rec).hexdigest()

        self._anchored_events.append({
            "type": "REVOCATION_ANCHOR",
            "credential_id": credential_id,
            "rev_hash": rev_hash,
            "tx_hash": tx_hash,
            "block_number": block_number,
            "anchor_status": record.status.value if record else "UNANCHORED",
            "timestamp": time.time(),
        })
        return rev_hash

    def anchor_status_list(self, status_list_id: str, bitstring_bytes: bytes, version: int = 1) -> str:
        tx_hash = None
        block_number = None
        record = None
        if self._bridge:
            try:
                rec = self._bridge.anchor_status_list(status_list_id, bitstring_bytes, version)
                record = rec
                sl_hash = rec.event_hash
                tx_hash = rec.tx_hash
                block_number = rec.block_number
            except Exception:
                from app.infrastructure.blockchain.canonical import compute_deterministic_hash
                _, sl_hash = compute_deterministic_hash(bitstring_bytes)
        else:
            sl_hash = "0x" + hashlib.sha256(bitstring_bytes).hexdigest()

        self._anchored_events.append({
            "type": "STATUS_LIST_ANCHOR",
            "status_list_id": status_list_id,
            "root_hash": sl_hash,
            "version": version,
            "tx_hash": tx_hash,
            "block_number": block_number,
            "anchor_status": record.status.value if record else "UNANCHORED",
            "timestamp": time.time(),
        })
        return sl_hash

    def anchor_quarantine(self, target_did: str, reason: str) -> dict[str, Any]:
        tx_hash = None
        block_number = None
        record = None
        # Quarantine is separate local demo state; anchoring is optional and
        # its outcome cannot be inferred from this set.
        self._quarantined_subjects.add(target_did)
        if self._bridge:
            try:
                rec = self._bridge.anchor_quarantine(target_did, reason)
                record = rec
                q_hash = rec.event_hash
                tx_hash = rec.tx_hash
                block_number = rec.block_number
            except Exception:
                from app.infrastructure.blockchain.canonical import compute_deterministic_hash
                _, q_hash = compute_deterministic_hash(f"QUARANTINE:{target_did}:{reason}".encode("utf-8"))
        else:
            raw_rec = f"QUARANTINE:{target_did}:{reason}".encode("utf-8")
            q_hash = "0x" + hashlib.sha256(raw_rec).hexdigest()

        anchor_status = record.status.value if record else (
            "FAILED" if self._bridge else "UNANCHORED"
        )
        self._anchored_events.append({
            "type": "QUARANTINE_ANCHOR",
            "target_did": target_did,
            "q_hash": q_hash,
            "reason": reason,
            "tx_hash": tx_hash,
            "block_number": block_number,
            "anchor_status": anchor_status,
            "timestamp": time.time(),
        })
        return {
            "event_hash": q_hash,
            "status": anchor_status,
            "tx_hash": tx_hash if anchor_status == "CONFIRMED" else None,
            "block_number": block_number if anchor_status == "CONFIRMED" else None,
        }

    def is_quarantined(self, target_did: str) -> bool:
        return target_did in self._quarantined_subjects

    def anchor_audit_event(self, event_id: str, event_payload: dict, category_name: str = "IDENTITY_ACTION") -> str:
        tx_hash = None
        block_number = None
        record = None
        if self._bridge:
            try:
                rec = self._bridge.anchor_audit_event(event_id, event_payload, category_name)
                record = rec
                audit_hash = rec.event_hash
                tx_hash = rec.tx_hash
                block_number = rec.block_number
            except Exception:
                from app.infrastructure.blockchain.canonical import compute_deterministic_hash
                _, audit_hash = compute_deterministic_hash(event_payload)
        else:
            raw_rec = str(sorted(event_payload.items())).encode("utf-8")
            audit_hash = "0x" + hashlib.sha256(raw_rec).hexdigest()

        self._anchored_events.append({
            "type": "AUDIT_EVENT_ANCHOR",
            "event_id": event_id,
            "audit_hash": audit_hash,
            "tx_hash": tx_hash,
            "block_number": block_number,
            "anchor_status": record.status.value if record else "UNANCHORED",
            "timestamp": time.time(),
        })
        return audit_hash

# Global cache instance
status_cache = CredentialStatusCache()
blockchain_anchor = BlockchainAnchorClient()
