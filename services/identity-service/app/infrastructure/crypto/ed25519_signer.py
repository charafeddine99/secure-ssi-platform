from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.domain.crypto import (
    ED25519_SIGNATURE_LENGTH,
    SigningKeyHandle,
    VerificationKey,
)
from app.domain.exceptions import SigningError


class Ed25519CredentialSigner:
    def sign(self, message: bytes, key: SigningKeyHandle) -> bytes:
        try:
            signature = key.sign(message)
        except Exception as error:
            raise SigningError(
                "The Ed25519 signing operation failed."
            ) from error
        if len(signature) != ED25519_SIGNATURE_LENGTH:
            raise SigningError(
                "The Ed25519 signer returned an invalid signature length."
            )
        return signature

    def verify(
        self,
        message: bytes,
        signature: bytes,
        key: VerificationKey,
    ) -> bool:
        if len(signature) != ED25519_SIGNATURE_LENGTH:
            return False
        try:
            public_key = Ed25519PublicKey.from_public_bytes(
                key.public_key_bytes
            )
            public_key.verify(signature, message)
        except (InvalidSignature, ValueError):
            return False
        return True
