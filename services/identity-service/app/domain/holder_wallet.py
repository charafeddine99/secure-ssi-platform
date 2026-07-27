import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


_OBJECT_ID_PATTERN = re.compile(r"^[0-9a-f]{24}$")
_WALLET_ID_PATTERN = re.compile(r"^wallet_[A-Za-z0-9_-]{16,80}$")
_KEY_REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._/-]{7,255}$")


class WalletStatus(StrEnum):
    ACTIVE = "ACTIVE"
    LOCKED = "LOCKED"
    DISABLED = "DISABLED"


class HolderWalletError(Exception):
    """Base class for controlled wallet and ownership failures."""


class HolderWalletNotFoundError(HolderWalletError):
    """The wallet is absent or intentionally hidden from this actor."""


class HolderWalletConflictError(HolderWalletError):
    """A wallet identifier, DID, or key reference is already in use."""


class HolderWalletUnavailableError(HolderWalletError):
    """The wallet exists but cannot perform holder operations."""


class HolderOwnershipError(HolderWalletError):
    """The actor does not own the requested wallet-bound object."""


@dataclass(frozen=True)
class HolderKeyMetadata:
    key_reference: str = field(repr=False)
    holder_did: str
    verification_method: str
    algorithm: str

    def __post_init__(self) -> None:
        validate_key_reference(self.key_reference)
        validate_holder_did(self.holder_did)
        if (
            not self.verification_method.startswith(f"{self.holder_did}#")
            or len(self.verification_method) > 4_096
        ):
            raise ValueError("Holder verification method is invalid.")
        if self.algorithm not in {"Ed25519"}:
            raise ValueError("Holder key algorithm is unsupported.")


@dataclass(frozen=True)
class HolderWallet:
    id: str
    wallet_id: str
    owner_user_id: str
    holder_did: str
    status: WalletStatus
    key_reference: str = field(repr=False)
    created_at: datetime
    updated_at: datetime
    version: int = 1
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        if not _OBJECT_ID_PATTERN.fullmatch(self.id):
            raise ValueError(
                "Wallet storage id must be a 24-character ObjectId string."
            )
        validate_wallet_id(self.wallet_id)
        if (
            not self.owner_user_id.strip()
            or len(self.owner_user_id) > 200
        ):
            raise ValueError("Wallet owner user id is invalid.")
        validate_holder_did(self.holder_did)
        validate_key_reference(self.key_reference)
        _require_aware(self.created_at, name="createdAt")
        _require_aware(self.updated_at, name="updatedAt")
        if self.updated_at < self.created_at or self.version < 1:
            raise ValueError("Wallet persistence metadata is invalid.")
        if self.deleted_at is not None:
            _require_aware(self.deleted_at, name="deletedAt")
            if self.deleted_at < self.created_at:
                raise ValueError("Wallet deletion precedes creation.")
            if self.status is not WalletStatus.DISABLED:
                raise ValueError("A soft-deleted wallet must be disabled.")
        object.__setattr__(self, "owner_user_id", self.owner_user_id.strip())

    @property
    def usable_for_signing(self) -> bool:
        return (
            self.status is WalletStatus.ACTIVE
            and self.deleted_at is None
        )

    def require_usable_for_signing(self) -> None:
        if not self.usable_for_signing:
            raise HolderWalletUnavailableError(
                "The holder wallet is not available for signing."
            )


def validate_wallet_id(value: str) -> str:
    if not _WALLET_ID_PATTERN.fullmatch(value):
        raise ValueError("Wallet id is invalid.")
    return value


def validate_holder_did(value: str) -> str:
    normalized = value.strip()
    if (
        not normalized.startswith("did:")
        or len(normalized) > 2_048
        or any(character.isspace() for character in normalized)
    ):
        raise ValueError("Holder DID is invalid.")
    return normalized


def validate_key_reference(value: str) -> str:
    if not _KEY_REFERENCE_PATTERN.fullmatch(value):
        raise ValueError("Holder key reference is invalid.")
    return value


def _require_aware(value: datetime, *, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware.")
