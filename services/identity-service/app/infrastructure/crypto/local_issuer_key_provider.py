from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from app.domain.crypto import SigningKeyHandle, VerificationKey
from app.domain.exceptions import (
    UnknownIssuerError,
    UnknownVerificationMethodError,
)
from app.infrastructure.crypto.multibase import encode_base58_btc


SYNTHETIC_ISSUER_DID = "did:web:issuer.example"
SYNTHETIC_VERIFICATION_METHOD = f"{SYNTHETIC_ISSUER_DID}#key-1"
ED25519_MULTICODEC_PREFIX = b"\xed\x01"

# These deterministic seeds are public test material. They provide reproducible
# fixtures only and MUST NOT be used for any real identity or credential.
_PRIMARY_SYNTHETIC_SEED = bytes.fromhex(
    "dbdd31e053d58e33fff0d0a842d9a510"
    "ee0b5c2b52662caa91e8e6d84821b419"
)
_ALTERNATE_SYNTHETIC_SEED = bytes.fromhex(
    "9e928f99faa9ba6d4fb5de8eb24dba7f"
    "ad35f335d55407f25cdb0201ae71c14d"
)


class _LocalSigningKey:
    __slots__ = ("_private_key", "_verification_method")

    def __init__(
        self,
        private_key: Ed25519PrivateKey,
        verification_method: str,
    ) -> None:
        self._private_key = private_key
        self._verification_method = verification_method

    @property
    def verification_method(self) -> str:
        return self._verification_method

    def sign(self, message: bytes) -> bytes:
        return self._private_key.sign(message)

    def __repr__(self) -> str:
        return (
            "_LocalSigningKey("
            f"verification_method={self.verification_method!r}, "
            "private_key=<redacted>)"
        )


class LocalIssuerKeyProvider:
    """In-memory synthetic key provider for local tests and demonstrations."""

    def __init__(self, *, alternate_test_key: bool = False) -> None:
        seed = (
            _ALTERNATE_SYNTHETIC_SEED
            if alternate_test_key
            else _PRIMARY_SYNTHETIC_SEED
        )
        self._private_key = Ed25519PrivateKey.from_private_bytes(seed)
        self._public_key_bytes = self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    @classmethod
    def alternate_for_tests(cls) -> "LocalIssuerKeyProvider":
        return cls(alternate_test_key=True)

    def supports_issuer(self, issuer_did: str) -> bool:
        return issuer_did == SYNTHETIC_ISSUER_DID

    def get_signing_key(self, issuer_did: str) -> SigningKeyHandle:
        if not self.supports_issuer(issuer_did):
            raise UnknownIssuerError(
                "The issuer is not supported by the local key provider."
            )
        return _LocalSigningKey(
            self._private_key,
            SYNTHETIC_VERIFICATION_METHOD,
        )

    def get_verification_key(
        self,
        verification_method: str,
    ) -> VerificationKey:
        if verification_method != SYNTHETIC_VERIFICATION_METHOD:
            raise UnknownVerificationMethodError(
                "The verification method is not available locally."
            )
        return VerificationKey(
            verification_method=SYNTHETIC_VERIFICATION_METHOD,
            controller=SYNTHETIC_ISSUER_DID,
            key_type="Multikey",
            public_key_bytes=self._public_key_bytes,
        )

    @property
    def public_key_multibase(self) -> str:
        return encode_base58_btc(
            ED25519_MULTICODEC_PREFIX + self._public_key_bytes
        )

    def __repr__(self) -> str:
        return (
            "LocalIssuerKeyProvider("
            f"issuer={SYNTHETIC_ISSUER_DID!r}, "
            "private_key=<redacted>)"
        )
