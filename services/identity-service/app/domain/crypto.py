from dataclasses import dataclass
from typing import Protocol


ED25519_PUBLIC_KEY_LENGTH = 32
ED25519_SIGNATURE_LENGTH = 64


class SigningKeyHandle(Protocol):
    """Opaque signing capability; it never exposes private key bytes."""

    @property
    def verification_method(self) -> str: ...

    def sign(self, message: bytes) -> bytes: ...


@dataclass(frozen=True)
class VerificationKey:
    verification_method: str
    controller: str
    key_type: str
    public_key_bytes: bytes

    def __post_init__(self) -> None:
        if len(self.public_key_bytes) != ED25519_PUBLIC_KEY_LENGTH:
            raise ValueError("Ed25519 public keys must contain exactly 32 bytes.")

    def __repr__(self) -> str:
        return (
            "VerificationKey("
            f"verification_method={self.verification_method!r}, "
            f"controller={self.controller!r}, "
            f"key_type={self.key_type!r}, "
            "public_key_bytes=<redacted>)"
        )
