from hashlib import sha256

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from app.domain.crypto import SigningKeyHandle, VerificationKey
from app.domain.holder_wallet import HolderKeyMetadata, validate_key_reference
from app.domain.exceptions import (
    UnknownIssuerError,
    UnknownVerificationMethodError,
)
from app.infrastructure.crypto.multibase import encode_base58_btc


ED25519_MULTICODEC_PREFIX = b"\xed\x01"
_SYNTHETIC_HOLDER_SEED = bytes.fromhex(
    "19cb73da98c4c2bd8121c77ad4a54534"
    "a9b88aa8b97378149c18b7c05b5582f8"
)
SYNTHETIC_HOLDER_KEY_REFERENCE = "local-dev:holder:synthetic:v1"
_DERIVATION_LABEL = b"secure-ssi-local-holder-key-v1\0"


class _LocalHolderSigningKey:
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
            "_LocalHolderSigningKey("
            f"verification_method={self.verification_method!r}, "
            "private_key=<redacted>)"
        )


class LocalHolderKeyProvider:
    """Development-only deterministic adapter behind opaque key references."""

    def __init__(self) -> None:
        self._references_by_holder: dict[str, str] = {}
        self._references_by_method: dict[str, str] = {}
        synthetic = self.get_metadata(
            SYNTHETIC_HOLDER_KEY_REFERENCE
        )
        self._holder_did = synthetic.holder_did
        self._verification_method = synthetic.verification_method

    @property
    def holder_did(self) -> str:
        return self._holder_did

    @property
    def verification_method(self) -> str:
        return self._verification_method

    def supports_holder(self, holder_did: str) -> bool:
        return holder_did in self._references_by_holder

    def get_signing_key(self, holder_did: str) -> SigningKeyHandle:
        key_reference = self._references_by_holder.get(holder_did)
        if key_reference is None:
            raise UnknownIssuerError(
                "The holder is not supported by the local key provider."
            )
        metadata = self.get_metadata(key_reference)
        return _LocalHolderSigningKey(
            self._private_key(key_reference),
            metadata.verification_method,
        )

    def provision(self, key_reference: str) -> HolderKeyMetadata:
        return self.get_metadata(key_reference)

    def get_metadata(self, key_reference: str) -> HolderKeyMetadata:
        validate_key_reference(key_reference)
        private_key = self._private_key(key_reference)
        public_key_bytes = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        fingerprint = encode_base58_btc(
            ED25519_MULTICODEC_PREFIX + public_key_bytes
        )
        holder_did = f"did:key:{fingerprint}"
        verification_method = f"{holder_did}#{fingerprint}"
        self._references_by_holder[holder_did] = key_reference
        self._references_by_method[verification_method] = key_reference
        return HolderKeyMetadata(
            key_reference=key_reference,
            holder_did=holder_did,
            verification_method=verification_method,
            algorithm="Ed25519",
        )

    def sign(
        self,
        message: bytes,
        *,
        key_reference: str,
    ) -> bytes:
        self.get_metadata(key_reference)
        return self._private_key(key_reference).sign(message)

    def get_verification_key(
        self,
        verification_method: str,
    ) -> VerificationKey:
        key_reference = self._references_by_method.get(
            verification_method
        )
        if key_reference is None:
            raise UnknownVerificationMethodError(
                "The holder verification method is unavailable locally."
            )
        metadata = self.get_metadata(key_reference)
        public_key_bytes = self._private_key(
            key_reference
        ).public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return VerificationKey(
            verification_method=metadata.verification_method,
            controller=metadata.holder_did,
            key_type="Multikey",
            public_key_bytes=public_key_bytes,
        )

    @staticmethod
    def _private_key(key_reference: str) -> Ed25519PrivateKey:
        seed = (
            _SYNTHETIC_HOLDER_SEED
            if key_reference == SYNTHETIC_HOLDER_KEY_REFERENCE
            else sha256(
                _DERIVATION_LABEL + key_reference.encode("utf-8")
            ).digest()
        )
        return Ed25519PrivateKey.from_private_bytes(seed)

    def __repr__(self) -> str:
        return (
            "LocalHolderKeyProvider("
            f"holders={len(self._references_by_holder)}, "
            "private_keys=<redacted>)"
        )


class LocalDevelopmentHolderSigner:
    """Signs by opaque reference without exposing key handles to services."""

    def __init__(self, provider: LocalHolderKeyProvider) -> None:
        self._provider = provider

    def sign(
        self,
        message: bytes,
        *,
        key_reference: str,
    ) -> bytes:
        return self._provider.sign(
            message,
            key_reference=key_reference,
        )

    def __repr__(self) -> str:
        return "LocalDevelopmentHolderSigner(private_keys=<redacted>)"


SYNTHETIC_HOLDER_DID = LocalHolderKeyProvider().holder_did
SYNTHETIC_HOLDER_VERIFICATION_METHOD = (
    LocalHolderKeyProvider().verification_method
)
