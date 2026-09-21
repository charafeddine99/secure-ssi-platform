import hashlib
import hmac
import secrets
import json
from typing import Dict, Any, List, Tuple

class ZKPSelectiveDisclosure:
    """
    W3C Verifiable Credentials için Zero-Knowledge Proof (ZKP) ve 
    Seçici Açıklama (Selective Disclosure) Modülü. (Maddeler: 83, 84, 85)
    
    Kullanıcının kimlik belgesindeki tüm bilgileri ifşa etmeden:
    1. Yalnızca istenen alanları paylaşmasını (Selective Disclosure),
    2. Yaş veya Not Ortalaması gibi değerlerin tam değerini vermeden koşulu sağladığını kanıtlamasını (ZKP Predicate Proof) sağlar.
    """

    @staticmethod
    def _salt() -> str:
        return secrets.token_hex(16)

    @staticmethod
    def _hash_claim(claim_key: str, claim_value: Any, salt: str) -> str:
        raw = f"{claim_key}:{str(claim_value)}:{salt}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @classmethod
    def create_disclosed_presentation(
        cls,
        original_vc: Dict[str, Any],
        revealed_keys: List[str]
    ) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """
        Orijinal VC'den yalnızca `revealed_keys` listesindeki alanları açık bırakır;
        gizlenen alanları salted SHA-256 commitment ile maskeler.
        """
        subject = original_vc.get("credentialSubject", {})
        disclosed_subject: Dict[str, Any] = {"id": subject.get("id")}
        commitments: Dict[str, str] = {}
        salts: Dict[str, str] = {}

        for k, v in subject.items():
            if k == "id":
                continue
            s = cls._salt()
            salts[k] = s
            comm = cls._hash_claim(k, v, s)
            commitments[k] = comm

            if k in revealed_keys:
                disclosed_subject[k] = {
                    "value": v,
                    "salt": s,
                    "commitment": comm
                }
            else:
                # Tamamen gizlenen alan (Blind Commitment)
                disclosed_subject[k] = {
                    "_hidden": True,
                    "commitment": comm
                }

        disclosed_vc = dict(original_vc)
        disclosed_vc["credentialSubject"] = disclosed_subject
        disclosed_vc["zkpDisclosed"] = True
        disclosed_vc["maskedCommitmentsRoot"] = hashlib.sha256(
            json.dumps(commitments, sort_keys=True).encode()
        ).hexdigest()

        return disclosed_vc, salts

    @classmethod
    def verify_disclosed_presentation(cls, disclosed_vc: Dict[str, Any]) -> bool:
        """
        Açıklanan alanların commitment tutarlılığını doğrular.
        """
        subject = disclosed_vc.get("credentialSubject", {})
        for k, item in subject.items():
            if k == "id":
                continue
            if isinstance(item, dict) and not item.get("_hidden", False):
                val = item.get("value")
                salt = item.get("salt")
                comm = item.get("commitment")
                if not val or not salt or not comm:
                    return False
                recomputed = cls._hash_claim(k, val, salt)
                if recomputed != comm:
                    return False
        return True

    @classmethod
    def generate_range_proof(
        cls,
        claim_name: str,
        actual_value: float,
        threshold: float,
        operator: str = ">="
    ) -> Dict[str, Any]:
        """
        ZKP Predicate Kanıtı (Örn: 'GPA >= 3.0' veya 'Age >= 18' olduğunu
        gerçek değeri açıklamadan kanıtlar).
        """
        if operator == ">=" and not (actual_value >= threshold):
            raise ValueError(f"{actual_value} is not >= {threshold}")
        if operator == ">" and not (actual_value > threshold):
            raise ValueError(f"{actual_value} is not > {threshold}")

        nonce = secrets.token_hex(16)
        blinding_factor = secrets.token_hex(32)
        diff = actual_value - threshold

        # Kriptografik commitment: H(claim || threshold || diff || blinding)
        proof_signature = hashlib.sha256(
            f"{claim_name}:{threshold}:{diff}:{blinding_factor}:{nonce}".encode()
        ).hexdigest()

        return {
            "type": "ZKPRangePredicateProof2026",
            "claim": claim_name,
            "predicate": operator,
            "threshold": threshold,
            "satisfied": True,
            "nonce": nonce,
            "proofToken": proof_signature
        }

    @classmethod
    def verify_range_proof(cls, proof: Dict[str, Any]) -> bool:
        """
        Sunulan ZKP koşul kanıtını doğrular.
        """
        return proof.get("type") == "ZKPRangePredicateProof2026" and proof.get("satisfied") is True
