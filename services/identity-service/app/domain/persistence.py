import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from app.domain.auth import User
from app.domain.credential_status import CredentialStatus
from app.domain.holder_wallet import validate_wallet_id
from app.domain.permissions import Role, normalize_roles


_OBJECT_ID_PATTERN = re.compile(r"^[0-9a-f]{24}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SENSITIVE_AUDIT_KEY_PARTS = {
    "authorization",
    "credential",
    "hash",
    "password",
    "proof",
    "secret",
    "token",
}


class CredentialStorageStatus(StrEnum):
    """Legacy read compatibility for pre-revocation Mongo documents."""

    STORED = "stored"
    VERIFIED = "verified"


class AuditEventType(StrEnum):
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILURE = "LOGIN_FAILURE"
    VC_SIGNED = "VC_SIGNED"
    VC_VERIFIED = "VC_VERIFIED"
    TOKEN_ISSUED = "TOKEN_ISSUED"
    TOKEN_REJECTED = "TOKEN_REJECTED"
    CREDENTIAL_REVOKED = "CREDENTIAL_REVOKED"
    STATUS_CHECKED = "STATUS_CHECKED"
    PRESENTATION_CREATED = "PRESENTATION_CREATED"
    PRESENTATION_VERIFIED = "PRESENTATION_VERIFIED"
    PRESENTATION_REJECTED = "PRESENTATION_REJECTED"
    WALLET_CREATED = "WALLET_CREATED"
    WALLET_LOCKED = "WALLET_LOCKED"
    WALLET_DISABLED = "WALLET_DISABLED"
    CHALLENGE_ISSUED = "CHALLENGE_ISSUED"
    CHALLENGE_CONSUMED = "CHALLENGE_CONSUMED"
    CHALLENGE_REJECTED = "CHALLENGE_REJECTED"
    PRESENTATION_RECONCILED = "PRESENTATION_RECONCILED"
    PRESENTATION_RECONCILIATION_FAILED = (
        "PRESENTATION_RECONCILIATION_FAILED"
    )
    HOLDER_OWNERSHIP_REJECTED = "HOLDER_OWNERSHIP_REJECTED"
    MANAGED_KEY_REQUESTED = "MANAGED_KEY_REQUESTED"
    PROVIDER_KEY_CREATED = "PROVIDER_KEY_CREATED"
    MANAGED_KEY_ACTIVATED = "MANAGED_KEY_ACTIVATED"
    MANAGED_KEY_CREATION_FAILED = "MANAGED_KEY_CREATION_FAILED"
    KEY_ROTATION_REQUESTED = "KEY_ROTATION_REQUESTED"
    SUCCESSOR_KEY_CREATED = "SUCCESSOR_KEY_CREATED"
    KEY_ROTATION_COMPLETED = "KEY_ROTATION_COMPLETED"
    KEY_ROTATION_FAILED = "KEY_ROTATION_FAILED"
    MANAGED_KEY_SUSPENDED = "MANAGED_KEY_SUSPENDED"
    MANAGED_KEY_RESUMED = "MANAGED_KEY_RESUMED"
    MANAGED_KEY_COMPROMISED = "MANAGED_KEY_COMPROMISED"
    MANAGED_KEY_REVOKED = "MANAGED_KEY_REVOKED"
    KEY_DESTRUCTION_SCHEDULED = "KEY_DESTRUCTION_SCHEDULED"
    KEY_DESTRUCTION_CANCELLED = "KEY_DESTRUCTION_CANCELLED"
    MANAGED_KEY_DESTROYED = "MANAGED_KEY_DESTROYED"
    KEY_PROVIDER_MISMATCH = "KEY_PROVIDER_MISMATCH"
    KEY_RECONCILIATION_CLAIMED = "KEY_RECONCILIATION_CLAIMED"
    KEY_RECONCILIATION_COMPLETED = "KEY_RECONCILIATION_COMPLETED"
    KEY_RECONCILIATION_FAILED = "KEY_RECONCILIATION_FAILED"
    UNAUTHORIZED_KEY_ACCESS = "UNAUTHORIZED_KEY_ACCESS"
    MANAGED_KEY_SIGNING_REJECTED = "MANAGED_KEY_SIGNING_REJECTED"


@dataclass(frozen=True)
class PersistedUser:
    id: str
    username: str
    display_name: str
    roles: tuple[Role, ...]
    enabled: bool
    password_hash: str = field(repr=False)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    version: int = 1
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        _validate_object_id(self.id, name="User id")
        normalized_username = self.username.strip().casefold()
        if not normalized_username or len(normalized_username) > 254:
            raise ValueError("Username must contain 1 to 254 characters.")
        if not self.display_name.strip() or len(self.display_name) > 200:
            raise ValueError("Display name must contain 1 to 200 characters.")
        if not self.password_hash.startswith("$argon2"):
            raise ValueError("A persisted user requires an Argon2 hash.")
        object.__setattr__(self, "username", normalized_username)
        object.__setattr__(self, "display_name", self.display_name.strip())
        object.__setattr__(self, "roles", normalize_roles(self.roles))
        if not self.roles:
            raise ValueError("A persisted user must have at least one role.")
        _validate_record_metadata(
            created_at=self.created_at,
            updated_at=self.updated_at,
            deleted_at=self.deleted_at,
            version=self.version,
        )

    def to_public_user(self) -> User:
        return User(
            id=self.id,
            username=self.username,
            display_name=self.display_name,
            roles=self.roles,
            enabled=self.enabled,
        )


@dataclass(frozen=True)
class PersistedCredential:
    id: str
    credential_id: str
    issuer_did: str
    holder_did: str
    credential_type: tuple[str, ...]
    issuance_date: datetime
    expiration_date: datetime | None
    credential_hash: str
    status: CredentialStatus | CredentialStorageStatus
    raw_credential: Mapping[str, Any] | None
    created_at: datetime
    updated_at: datetime
    version: int = 1
    deleted_at: datetime | None = None
    revoked_at: datetime | None = None
    revoked_by: str | None = None
    revocation_reason: str | None = None
    status_list_id: str | None = None
    status_list_index: int | None = None
    status_entry_id: str | None = None
    wallet_id: str | None = None
    owner_user_id: str | None = None

    def __post_init__(self) -> None:
        _validate_object_id(self.id, name="Credential storage id")
        for name, value in (
            ("Credential id", self.credential_id),
            ("Issuer DID", self.issuer_did),
            ("Holder DID", self.holder_did),
        ):
            if not value.strip() or len(value) > 2_048:
                raise ValueError(f"{name} is empty or too long.")
        normalized_types = tuple(dict.fromkeys(self.credential_type))
        if not normalized_types or any(
            not value.strip() or len(value) > 200
            for value in normalized_types
        ):
            raise ValueError("Credential types must be non-empty strings.")
        if not _SHA256_PATTERN.fullmatch(self.credential_hash):
            raise ValueError(
                "Credential hash must be a lowercase SHA-256 hex digest."
            )
        _validate_aware_utc(self.issuance_date, name="Issuance date")
        if self.expiration_date is not None:
            _validate_aware_utc(
                self.expiration_date,
                name="Expiration date",
            )
            if self.expiration_date <= self.issuance_date:
                raise ValueError(
                    "Expiration date must be after issuance date."
                )
        if self.raw_credential is not None and not isinstance(
            self.raw_credential,
            Mapping,
        ):
            raise ValueError("Raw credential must be a mapping.")
        normalized_status = (
            CredentialStatus.ACTIVE
            if isinstance(self.status, CredentialStorageStatus)
            else CredentialStatus(self.status)
        )
        revocation_values = (
            self.revoked_at,
            self.revoked_by,
            self.revocation_reason,
        )
        if normalized_status is CredentialStatus.REVOKED:
            if any(value is None for value in revocation_values):
                raise ValueError(
                    "Revoked credential requires complete revocation metadata."
                )
            _validate_aware_utc(self.revoked_at, name="revokedAt")
            if self.revoked_at < self.issuance_date:
                raise ValueError("revokedAt cannot precede issuanceDate.")
            if (
                not self.revoked_by.strip()
                or len(self.revoked_by) > 200
                or not self.revocation_reason.strip()
                or len(self.revocation_reason) > 500
            ):
                raise ValueError("Revocation metadata is invalid.")
        elif any(value is not None for value in revocation_values):
            raise ValueError(
                "Non-revoked credential cannot contain revocation metadata."
            )
        status_entry_values = (self.status_list_id, self.status_list_index)
        if any(value is not None for value in status_entry_values):
            if any(value is None for value in status_entry_values):
                raise ValueError(
                    "Credential status-list mapping must be complete."
                )
            if (
                not self.status_list_id.strip()
                or len(self.status_list_id) > 100
                or self.status_list_index < 0
            ):
                raise ValueError("Credential status-list mapping is invalid.")
        if self.status_entry_id is not None:
            if self.status_list_id is None:
                raise ValueError(
                    "Credential status entry requires a list mapping."
                )
            _validate_object_id(
                self.status_entry_id,
                name="Credential status entry id",
            )
        ownership_values = (self.wallet_id, self.owner_user_id)
        if any(value is not None for value in ownership_values):
            if any(value is None for value in ownership_values):
                raise ValueError(
                    "Credential wallet ownership mapping must be complete."
                )
            validate_wallet_id(self.wallet_id)
            if (
                not self.owner_user_id.strip()
                or len(self.owner_user_id) > 200
            ):
                raise ValueError("Credential owner user id is invalid.")
        object.__setattr__(self, "credential_id", self.credential_id.strip())
        object.__setattr__(self, "issuer_did", self.issuer_did.strip())
        object.__setattr__(self, "holder_did", self.holder_did.strip())
        object.__setattr__(self, "credential_type", normalized_types)
        object.__setattr__(self, "status", normalized_status)
        if self.revoked_by is not None:
            object.__setattr__(self, "revoked_by", self.revoked_by.strip())
        if self.revocation_reason is not None:
            object.__setattr__(
                self,
                "revocation_reason",
                self.revocation_reason.strip(),
            )
        if self.status_list_id is not None:
            object.__setattr__(
                self,
                "status_list_id",
                self.status_list_id.strip(),
            )
        if self.owner_user_id is not None:
            object.__setattr__(
                self,
                "owner_user_id",
                self.owner_user_id.strip(),
            )
        _validate_record_metadata(
            created_at=self.created_at,
            updated_at=self.updated_at,
            deleted_at=self.deleted_at,
            version=self.version,
        )


@dataclass(frozen=True)
class AuditEvent:
    id: str
    event_type: AuditEventType
    subject_id: str | None
    actor_id: str | None
    correlation_id: str | None
    metadata: Mapping[str, str]
    created_at: datetime
    updated_at: datetime
    version: int = 1

    def __post_init__(self) -> None:
        _validate_object_id(self.id, name="Audit event id")
        for name, value, maximum in (
            ("Subject id", self.subject_id, 2_048),
            ("Actor id", self.actor_id, 2_048),
            ("Correlation id", self.correlation_id, 200),
        ):
            if value is not None and (
                not value.strip() or len(value) > maximum
            ):
                raise ValueError(f"{name} is empty or too long.")
        if len(self.metadata) > 20:
            raise ValueError("Audit metadata has too many entries.")
        safe_metadata: dict[str, str] = {}
        for key, value in self.metadata.items():
            normalized_key = key.strip()
            if (
                not normalized_key
                or len(normalized_key) > 100
                or len(value) > 500
            ):
                raise ValueError("Audit metadata is empty or too long.")
            key_parts = {
                part
                for part in re.split(r"[^a-z0-9]+", normalized_key.casefold())
                if part
            }
            compact_key = "".join(key_parts)
            if key_parts.intersection(
                _SENSITIVE_AUDIT_KEY_PARTS
            ) or any(
                part in compact_key
                for part in _SENSITIVE_AUDIT_KEY_PARTS
            ):
                raise ValueError(
                    "Sensitive values are prohibited in audit metadata."
                )
            safe_metadata[normalized_key] = value
        object.__setattr__(
            self,
            "metadata",
            MappingProxyType(safe_metadata),
        )
        _validate_record_metadata(
            created_at=self.created_at,
            updated_at=self.updated_at,
            deleted_at=None,
            version=self.version,
        )
        if self.version != 1 or self.updated_at != self.created_at:
            raise ValueError("Audit events are immutable append-only records.")


class RepositoryError(Exception):
    """Base class for controlled persistence failures."""


class DuplicateEntityError(RepositoryError):
    """A unique repository key already exists."""


class EntityNotFoundError(RepositoryError):
    """A requested active entity does not exist."""


class OptimisticLockError(RepositoryError):
    """The stored version changed before an update completed."""


class PersistenceConfigurationError(RepositoryError):
    """MongoDB configuration is missing or unsafe."""


class PersistenceUnavailableError(RepositoryError):
    """MongoDB is unavailable or the connection is not active."""


class DocumentMappingError(RepositoryError):
    """A BSON document cannot be mapped to the domain model."""


def _validate_record_metadata(
    *,
    created_at: datetime,
    updated_at: datetime,
    deleted_at: datetime | None,
    version: int,
) -> None:
    _validate_aware_utc(created_at, name="createdAt")
    _validate_aware_utc(updated_at, name="updatedAt")
    if updated_at < created_at:
        raise ValueError("updatedAt cannot precede createdAt.")
    if deleted_at is not None:
        _validate_aware_utc(deleted_at, name="deletedAt")
        if deleted_at < created_at:
            raise ValueError("deletedAt cannot precede createdAt.")
    if version < 1:
        raise ValueError("Version must be a positive integer.")


def _validate_aware_utc(value: datetime, *, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware.")


def _validate_object_id(value: str, *, name: str) -> None:
    if not _OBJECT_ID_PATTERN.fullmatch(value):
        raise ValueError(f"{name} must be a 24-character ObjectId string.")
