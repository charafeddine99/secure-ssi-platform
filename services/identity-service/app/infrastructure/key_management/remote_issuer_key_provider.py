import logging
from collections.abc import Mapping
from hashlib import sha256
from threading import Lock

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.application.ports.key_management import ExternalKeyProvider
from app.domain.crypto import (
    ED25519_PUBLIC_KEY_LENGTH,
    ED25519_SIGNATURE_LENGTH,
    SigningKeyHandle,
    VerificationKey,
)
from app.domain.exceptions import (
    UnknownIssuerError,
    UnknownVerificationMethodError,
)
from app.domain.managed_key import (
    KeyAlgorithm,
    ProviderMetadataError,
)
from app.infrastructure.crypto.multibase import decode_base58_btc


_ED25519_MULTICODEC_PREFIX = b"\xed\x01"
_audit = logging.getLogger("secure_ssi.kms.audit")


def public_key_from_multibase(value: str) -> bytes:
    try:
        decoded = decode_base58_btc(value)
    except ValueError as error:
        raise ProviderMetadataError(
            "KMS public key encoding is invalid."
        ) from error
    if (
        not decoded.startswith(_ED25519_MULTICODEC_PREFIX)
        or len(decoded) != 2 + ED25519_PUBLIC_KEY_LENGTH
    ):
        raise ProviderMetadataError("KMS public key is not Ed25519.")
    return decoded[2:]


class _RemoteSigningKey:
    __slots__ = ("_owner",)

    def __init__(self, owner: "RemoteKmsIssuerKeyProvider") -> None:
        self._owner = owner

    @property
    def verification_method(self) -> str:
        return self._owner.verification_method

    def sign(self, message: bytes) -> bytes:
        return self._owner.sign(message)


class RemoteKmsIssuerKeyProvider:
    """Issuer or status-list signing through an opaque KMS key reference.

    No private key enters this process. Each signature is checked against the
    KMS public key, so a malformed or wrong-key response fails closed, and there
    is deliberately no fallback to any other key.
    """

    def __init__(
        self,
        *,
        kms: ExternalKeyProvider,
        purpose: str,
        issuer_did: str,
        key_reference: str,
        verification_method: str,
        trusted_public_keys: Mapping[str, bytes] | None = None,
    ) -> None:
        self._kms = kms
        self._purpose = purpose
        self._issuer_did = issuer_did
        self._key_reference = key_reference
        self._verification_method = verification_method
        self._trusted = dict(trusted_public_keys or {})
        self._public_key: bytes | None = None
        self._peer: "RemoteKmsIssuerKeyProvider | None" = None
        self._lock = Lock()

    def trust_peer(self, peer: "RemoteKmsIssuerKeyProvider") -> None:
        """Lets credential and status keys verify each other's proofs."""
        self._peer = peer

    @property
    def verification_method(self) -> str:
        return self._verification_method

    @property
    def production_ready(self) -> bool:
        return self._kms.production_ready

    def is_available(self) -> bool:
        return self._kms.is_available()

    def supports_issuer(self, issuer_did: str) -> bool:
        return issuer_did == self._issuer_did

    def get_signing_key(self, issuer_did: str) -> SigningKeyHandle:
        if not self.supports_issuer(issuer_did):
            raise UnknownIssuerError(
                "The issuer is not served by this key provider."
            )
        return _RemoteSigningKey(self)

    def get_verification_key(
        self,
        verification_method: str,
    ) -> VerificationKey:
        if verification_method == self._verification_method:
            public_key = self._current_public_key()
        elif verification_method in self._trusted:
            public_key = self._trusted[verification_method]
        elif (
            self._peer is not None
            and verification_method == self._peer.verification_method
        ):
            return self._peer.get_verification_key(verification_method)
        else:
            raise UnknownVerificationMethodError(
                "The verification method is not trusted by this issuer."
            )
        return VerificationKey(
            verification_method=verification_method,
            controller=self._issuer_did,
            key_type="Multikey",
            public_key_bytes=public_key,
        )

    def sign(self, message: bytes) -> bytes:
        outcome = "FAILED"
        try:
            public_key = self._current_public_key()
            signature = self._kms.sign(
                message,
                provider_key_reference=self._key_reference,
                algorithm=KeyAlgorithm.ED25519,
            )
            if len(signature) != ED25519_SIGNATURE_LENGTH:
                raise ProviderMetadataError(
                    "KMS signature has the wrong length."
                )
            try:
                Ed25519PublicKey.from_public_bytes(public_key).verify(
                    signature,
                    message,
                )
            except InvalidSignature as error:
                raise ProviderMetadataError(
                    "KMS signature does not match the configured key."
                ) from error
            outcome = "SIGNED"
            return signature
        finally:
            _audit.info(
                "kms_sign purpose=%s key=%s digest=%s outcome=%s",
                self._purpose,
                sha256(self._key_reference.encode()).hexdigest()[:16],
                sha256(message).hexdigest()[:16],
                outcome,
            )

    def _current_public_key(self) -> bytes:
        with self._lock:
            if self._public_key is not None:
                return self._public_key
        metadata = self._kms.get_key_metadata(self._key_reference)
        if metadata.destroyed or not metadata.enabled:
            raise ProviderMetadataError("The KMS signing key is not enabled.")
        if metadata.verification_method != self._verification_method:
            raise ProviderMetadataError(
                "KMS key metadata does not match the configured method."
            )
        public_key = public_key_from_multibase(metadata.public_key_multibase)
        with self._lock:
            self._public_key = public_key
        return public_key

    def __repr__(self) -> str:
        return (
            "RemoteKmsIssuerKeyProvider("
            f"purpose={self._purpose!r}, "
            f"verification_method={self._verification_method!r})"
        )
