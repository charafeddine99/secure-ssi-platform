from dataclasses import replace
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from threading import Lock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from app.domain.managed_key import (
    KeyAlgorithm,
    KeyPurpose,
    ProviderKeyMetadata,
    ProviderKeyNotFoundError,
    ProviderMetadataError,
    ProviderPermissionDeniedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    public_key_fingerprint,
)
from app.infrastructure.crypto.local_holder_key_provider import (
    ED25519_MULTICODEC_PREFIX,
)
from app.infrastructure.crypto.multibase import encode_base58_btc


_DERIVATION_LABEL = b"secure-ssi-development-external-provider-v1\0"


class DevelopmentProviderFailure(StrEnum):
    NONE = "none"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    PERMISSION_DENIED = "permission_denied"
    NOT_FOUND = "not_found"
    SIGNING_FAILED = "signing_failed"
    INCONSISTENT_METADATA = "inconsistent_metadata"


class DevelopmentExternalKeyProvider:
    """Non-production provider with a private, process-local key boundary."""

    def __init__(self, *, name: str = "development") -> None:
        self._name = name
        self._lock = Lock()
        self._metadata: dict[str, ProviderKeyMetadata] = {}
        self._reference_by_idempotency: dict[str, str] = {}
        self._suspended: set[str] = set()
        self._revoked: set[str] = set()
        self._destroyed: set[str] = set()
        self._deletion_schedule: dict[str, datetime] = {}
        self._failure = DevelopmentProviderFailure.NONE

    @property
    def name(self) -> str:
        return self._name

    @property
    def production_ready(self) -> bool:
        return False

    def inject_failure(
        self,
        failure: DevelopmentProviderFailure,
    ) -> None:
        self._failure = failure

    def create_key(
        self,
        *,
        key_id: str,
        algorithm: KeyAlgorithm,
        purpose: KeyPurpose,
        idempotency_key: str,
    ) -> ProviderKeyMetadata:
        del purpose
        self._raise_injected()
        if algorithm is not KeyAlgorithm.ED25519:
            raise ProviderMetadataError(
                "Development provider does not support the algorithm."
            )
        with self._lock:
            existing_reference = self._reference_by_idempotency.get(
                idempotency_key
            )
            if existing_reference is not None:
                return self._metadata[existing_reference]
            reference_digest = sha256(
                f"{key_id}\0{idempotency_key}".encode("utf-8")
            ).hexdigest()
            reference = f"{self.name}:key:{reference_digest[:48]}"
            metadata = self._build_metadata(reference)
            self._metadata[reference] = metadata
            self._reference_by_idempotency[idempotency_key] = reference
            return metadata

    def get_key_metadata(
        self,
        provider_key_reference: str,
    ) -> ProviderKeyMetadata:
        self._raise_injected()
        with self._lock:
            metadata = self._metadata.get(provider_key_reference)
            if (
                metadata is None
                and provider_key_reference.startswith(f"{self.name}:key:")
            ):
                metadata = self._build_metadata(provider_key_reference)
                self._metadata[provider_key_reference] = metadata
            if (
                metadata is None
                or self._failure is DevelopmentProviderFailure.NOT_FOUND
            ):
                raise ProviderKeyNotFoundError(
                    "The provider key does not exist."
                )
            result = replace(
                metadata,
                enabled=provider_key_reference not in self._suspended
                and provider_key_reference not in self._revoked
                and provider_key_reference not in self._destroyed,
                destroyed=provider_key_reference in self._destroyed,
            )
            if (
                self._failure
                is DevelopmentProviderFailure.INCONSISTENT_METADATA
            ):
                object.__setattr__(result, "fingerprint", "0" * 64)
            return result

    def sign(
        self,
        message: bytes,
        *,
        provider_key_reference: str,
        algorithm: KeyAlgorithm,
    ) -> bytes:
        self._raise_injected(signing=True)
        if algorithm is not KeyAlgorithm.ED25519:
            raise ProviderMetadataError(
                "Development provider does not support the algorithm."
            )
        metadata = self.get_key_metadata(provider_key_reference)
        if not metadata.enabled or metadata.destroyed:
            raise ProviderPermissionDeniedError(
                "The provider key is unavailable for signing."
            )
        return self._private_key(provider_key_reference).sign(message)

    def enable_key(self, provider_key_reference: str) -> None:
        self._raise_injected()
        self._require_existing(provider_key_reference)
        with self._lock:
            if provider_key_reference in self._revoked:
                raise ProviderPermissionDeniedError(
                    "A revoked provider key cannot be enabled."
                )
            if provider_key_reference in self._destroyed:
                raise ProviderPermissionDeniedError(
                    "A destroyed provider key cannot be enabled."
                )
            self._suspended.discard(provider_key_reference)

    def suspend_key(self, provider_key_reference: str) -> None:
        self._raise_injected()
        self._require_existing(provider_key_reference)
        with self._lock:
            self._suspended.add(provider_key_reference)

    def revoke_key(self, provider_key_reference: str) -> None:
        self._raise_injected()
        self._require_existing(provider_key_reference)
        with self._lock:
            self._revoked.add(provider_key_reference)
            self._suspended.add(provider_key_reference)

    def schedule_deletion(
        self,
        provider_key_reference: str,
        *,
        delete_at: datetime,
    ) -> None:
        self._raise_injected()
        self._require_existing(provider_key_reference)
        if delete_at.tzinfo is None or delete_at.utcoffset() is None:
            raise ValueError("Provider deletion time must be timezone-aware.")
        with self._lock:
            self._deletion_schedule[provider_key_reference] = delete_at

    def cancel_scheduled_deletion(
        self,
        provider_key_reference: str,
    ) -> None:
        self._raise_injected()
        self._require_existing(provider_key_reference)
        with self._lock:
            self._deletion_schedule.pop(provider_key_reference, None)

    def destroy_key(self, provider_key_reference: str) -> None:
        self._raise_injected()
        self._require_existing(provider_key_reference)
        with self._lock:
            self._destroyed.add(provider_key_reference)
            self._suspended.add(provider_key_reference)
            self._deletion_schedule.pop(provider_key_reference, None)

    def is_available(self) -> bool:
        return self._failure not in {
            DevelopmentProviderFailure.TIMEOUT,
            DevelopmentProviderFailure.UNAVAILABLE,
        }

    def get_public_key_bytes(
        self,
        provider_key_reference: str,
    ) -> bytes:
        metadata = self.get_key_metadata(provider_key_reference)
        if metadata.destroyed:
            raise ProviderKeyNotFoundError(
                "The provider key no longer has public metadata."
            )
        return self._private_key(
            provider_key_reference
        ).public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    def _build_metadata(self, reference: str) -> ProviderKeyMetadata:
        public_bytes = self._private_key(reference).public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        multibase = encode_base58_btc(
            ED25519_MULTICODEC_PREFIX + public_bytes
        )
        holder_did = f"did:key:{multibase}"
        return ProviderKeyMetadata(
            provider=self.name,
            provider_key_reference=reference,
            algorithm=KeyAlgorithm.ED25519,
            public_key_multibase=multibase,
            fingerprint=public_key_fingerprint(multibase),
            holder_did=holder_did,
            verification_method=f"{holder_did}#{multibase}",
            enabled=True,
        )

    @staticmethod
    def _private_key(
        provider_key_reference: str,
    ) -> Ed25519PrivateKey:
        seed = sha256(
            _DERIVATION_LABEL + provider_key_reference.encode("utf-8")
        ).digest()
        return Ed25519PrivateKey.from_private_bytes(seed)

    def _require_existing(self, provider_key_reference: str) -> None:
        with self._lock:
            if (
                provider_key_reference not in self._metadata
                and provider_key_reference.startswith(f"{self.name}:key:")
            ):
                self._metadata[provider_key_reference] = (
                    self._build_metadata(provider_key_reference)
                )
            exists = provider_key_reference in self._metadata
        if not exists:
            raise ProviderKeyNotFoundError(
                "The provider key does not exist."
            )

    def _raise_injected(self, *, signing: bool = False) -> None:
        if self._failure is DevelopmentProviderFailure.TIMEOUT:
            raise ProviderTimeoutError("The key provider request timed out.")
        if self._failure is DevelopmentProviderFailure.UNAVAILABLE:
            raise ProviderUnavailableError(
                "The key provider is temporarily unavailable."
            )
        if self._failure is DevelopmentProviderFailure.PERMISSION_DENIED:
            raise ProviderPermissionDeniedError(
                "The key provider denied the operation."
            )
        if (
            signing
            and self._failure
            is DevelopmentProviderFailure.SIGNING_FAILED
        ):
            raise ProviderUnavailableError(
                "The key provider could not complete signing."
            )

    def __repr__(self) -> str:
        return (
            "DevelopmentExternalKeyProvider("
            f"name={self.name!r}, keys={len(self._metadata)}, "
            "private_material=<redacted>)"
        )
