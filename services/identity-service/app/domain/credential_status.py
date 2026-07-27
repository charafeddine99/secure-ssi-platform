from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class CredentialStatus(StrEnum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    SUSPENDED = "SUSPENDED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class CredentialStatusSnapshot:
    credential_id: str
    status: CredentialStatus
    expiration_date: datetime | None
    revoked_at: datetime | None
    revocation_reason: str | None
    revoked_by: str | None
    version: int

    def __post_init__(self) -> None:
        if not self.credential_id.strip() or len(self.credential_id) > 2_048:
            raise ValueError("Credential id is empty or too long.")
        if self.version < 1:
            raise ValueError("Credential status version must be positive.")
        if self.expiration_date is not None:
            _require_aware(self.expiration_date, name="expirationDate")
        revocation_values = (
            self.revoked_at,
            self.revocation_reason,
            self.revoked_by,
        )
        if self.status is CredentialStatus.REVOKED:
            if any(value is None for value in revocation_values):
                raise ValueError(
                    "Revoked status requires complete revocation metadata."
                )
            _require_aware(self.revoked_at, name="revokedAt")
        elif any(value is not None for value in revocation_values):
            raise ValueError(
                "Non-revoked status cannot contain revocation metadata."
            )

    @property
    def revoked(self) -> bool:
        return self.status is CredentialStatus.REVOKED


class CredentialStatusError(Exception):
    """Base class for controlled credential lifecycle failures."""


class CredentialNotFoundError(CredentialStatusError):
    """The requested active credential does not exist."""


class CredentialAlreadyRevokedError(CredentialStatusError):
    """The requested credential was previously revoked."""


class InvalidRevocationReasonError(CredentialStatusError):
    """A revocation reason is empty or outside the bounded policy."""


class InvalidCredentialStatusTransitionError(CredentialStatusError):
    """A requested credential lifecycle transition is forbidden."""


class RevocationPolicy:
    MAX_REASON_LENGTH = 500

    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = value.strip()
        if (
            not normalized
            or len(normalized) > cls.MAX_REASON_LENGTH
            or any(ord(character) < 32 for character in normalized)
        ):
            raise InvalidRevocationReasonError(
                "Revocation reason is empty or invalid."
            )
        return normalized

    @staticmethod
    def require_revocable(status: CredentialStatus) -> None:
        if status is CredentialStatus.REVOKED:
            raise CredentialAlreadyRevokedError(
                "Credential has already been revoked."
            )

    @staticmethod
    def effective_status(
        *,
        stored_status: CredentialStatus,
        expiration_date: datetime | None,
        checked_at: datetime,
    ) -> CredentialStatus:
        _require_aware(checked_at, name="checkedAt")
        if stored_status is CredentialStatus.REVOKED:
            return CredentialStatus.REVOKED
        if expiration_date is not None and checked_at >= expiration_date:
            return CredentialStatus.EXPIRED
        return stored_status

    @staticmethod
    def require_transition(
        *,
        current: CredentialStatus,
        target: CredentialStatus,
    ) -> None:
        if current is CredentialStatus.REVOKED and target is not current:
            raise InvalidCredentialStatusTransitionError(
                "A revoked credential cannot transition to another status."
            )
        if current is target:
            return
        allowed = {
            CredentialStatus.ACTIVE: {
                CredentialStatus.REVOKED,
                CredentialStatus.SUSPENDED,
                CredentialStatus.EXPIRED,
            },
            CredentialStatus.SUSPENDED: {
                CredentialStatus.REVOKED,
                CredentialStatus.EXPIRED,
            },
            CredentialStatus.EXPIRED: {CredentialStatus.REVOKED},
            CredentialStatus.REVOKED: set(),
        }
        if target not in allowed[current]:
            raise InvalidCredentialStatusTransitionError(
                "Credential status transition is not allowed."
            )


def _require_aware(value: datetime | None, *, name: str) -> None:
    if (
        value is None
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{name} must be timezone-aware.")
