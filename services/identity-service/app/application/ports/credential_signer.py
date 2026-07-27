from typing import Protocol

from app.domain.crypto import SigningKeyHandle, VerificationKey


class CredentialSigner(Protocol):
    def sign(self, message: bytes, key: SigningKeyHandle) -> bytes: ...

    def verify(
        self,
        message: bytes,
        signature: bytes,
        key: VerificationKey,
    ) -> bool: ...
