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
    Blockchain Katmanı (DIDRegistry, RevocationRegistry, AuditLogger) ile
    Identity Service arasındaki Web3 bağlantı köprüsü (Maddeler: 44, 46, 47, 48).
    """
    def __init__(self, rpc_url: str = "http://127.0.0.1:8545"):
        self.rpc_url = rpc_url
        self._anchored_events: list = []

    def anchor_did_document(self, did: str, document_dict: dict) -> str:
        raw_doc = str(sorted(document_dict.items())).encode("utf-8")
        doc_hash = "0x" + hashlib.sha256(raw_doc).hexdigest()
        self._anchored_events.append({
            "type": "DID_ANCHOR",
            "did": did,
            "doc_hash": doc_hash,
            "timestamp": time.time()
        })
        return doc_hash

    def anchor_revocation_status(self, credential_id: str, reason: str) -> str:
        raw_rec = f"{credential_id}:{reason}".encode("utf-8")
        rev_hash = "0x" + hashlib.sha256(raw_rec).hexdigest()
        self._anchored_events.append({
            "type": "REVOCATION_ANCHOR",
            "credential_id": credential_id,
            "rev_hash": rev_hash,
            "timestamp": time.time()
        })
        return rev_hash

# Global cache instance
status_cache = CredentialStatusCache()
blockchain_anchor = BlockchainAnchorClient()
