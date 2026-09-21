import json
import time
import uuid
import secrets
from typing import Dict, Any, List, Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class DIDCommV2:
    """
    Hyperledger Aries / DIF DIDComm Messaging v2 Protokolü Uygulaması (Maddeler: 29, 30, 95).
    Kimlik ajanları (Holder, Issuer, Verifier, Guardian) arasındaki güvenli mesajlaşmayı sağlar.
    """

    @staticmethod
    def pack_plaintext(
        msg_type: str,
        body: Dict[str, Any],
        sender_did: str,
        recipient_dids: List[str],
        msg_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Standart DIDComm v2 Plaintext mesaj zarfı oluşturur.
        """
        return {
            "id": msg_id or str(uuid.uuid4()),
            "type": msg_type,
            "body": body,
            "from": sender_did,
            "to": recipient_dids,
            "created_time": int(time.time()),
            "expires_time": int(time.time()) + 3600
        }

    @staticmethod
    def pack_authcrypt(
        plaintext_msg: Dict[str, Any],
        shared_secret_key: bytes
    ) -> Dict[str, Any]:
        """
        DIDComm v2 Encrypted Envelope: AES-256-GCM ile şifrelenmiş mesaj zarfı.
        """
        if len(shared_secret_key) != 32:
            raise ValueError("AES-256 icin 32-byte anahtar gereklidir.")

        aesgcm = AESGCM(shared_secret_key)
        nonce = secrets.token_bytes(12)
        data = json.dumps(plaintext_msg, sort_keys=True).encode("utf-8")
        ciphertext = aesgcm.encrypt(nonce, data, None)

        return {
            "protected": {
                "enc": "A256GCM",
                "typ": "application/didcomm-encrypted+json"
            },
            "iv": nonce.hex(),
            "ciphertext": ciphertext.hex(),
            "recipients": [
                {"header": {"kid": to_did}} for to_did in plaintext_msg.get("to", [])
            ]
        }

    @staticmethod
    def unpack_authcrypt(
        encrypted_msg: Dict[str, Any],
        shared_secret_key: bytes
    ) -> Dict[str, Any]:
        """
        DIDComm v2 Encrypted Envelope şifresini çözer ve orijinal mesajı çıkarır.
        """
        aesgcm = AESGCM(shared_secret_key)
        nonce = bytes.fromhex(encrypted_msg["iv"])
        ciphertext = bytes.fromhex(encrypted_msg["ciphertext"])
        decrypted_data = aesgcm.decrypt(nonce, ciphertext, None)
        return json.loads(decrypted_data.decode("utf-8"))
