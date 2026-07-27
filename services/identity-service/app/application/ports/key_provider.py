from typing import Protocol

from app.domain.crypto import SigningKeyHandle, VerificationKey


class KeyProvider(Protocol):
    def supports_issuer(self, issuer_did: str) -> bool: ...

    def get_signing_key(self, issuer_did: str) -> SigningKeyHandle: ...

    def get_verification_key(
        self,
        verification_method: str,
    ) -> VerificationKey: ...
