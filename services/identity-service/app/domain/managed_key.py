import re
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from hashlib import sha256


_OBJECT_ID_PATTERN = re.compile(r"^[0-9a-f]{24}$")
_KEY_ID_PATTERN = re.compile(r"^key_[A-Za-z0-9_-]{16,80}$")
_SAFE_REFERENCE_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9:._/@=-]{7,511}$"
)
_FINGERPRINT_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ManagedKeyState(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    ROTATING = "ROTATING"
    SUSPENDED = "SUSPENDED"
    COMPROMISED = "COMPROMISED"
    REVOKED = "REVOKED"
    DESTROY_PENDING = "DESTROY_PENDING"
    DESTROYED = "DESTROYED"
    FAILED = "FAILED"


class KeyPurpose(StrEnum):
    HOLDER_AUTHENTICATION = "HOLDER_AUTHENTICATION"
    HOLDER_ASSERTION = "HOLDER_ASSERTION"
    CREDENTIAL_SIGNING = "CREDENTIAL_SIGNING"
    PRESENTATION_SIGNING = "PRESENTATION_SIGNING"
    ISSUER_ASSERTION = "ISSUER_ASSERTION"
    STATUS_LIST_SIGNING = "STATUS_LIST_SIGNING"


class KeyAlgorithm(StrEnum):
    ED25519 = "Ed25519"


VALID_KEY_TRANSITIONS: dict[
    ManagedKeyState,
    frozenset[ManagedKeyState],
] = {
    ManagedKeyState.PENDING: frozenset(
        {ManagedKeyState.ACTIVE, ManagedKeyState.FAILED}
    ),
    ManagedKeyState.ACTIVE: frozenset(
        {
            ManagedKeyState.ROTATING,
            ManagedKeyState.SUSPENDED,
            ManagedKeyState.COMPROMISED,
            ManagedKeyState.REVOKED,
            ManagedKeyState.FAILED,
        }
    ),
    ManagedKeyState.ROTATING: frozenset(
        {
            ManagedKeyState.ACTIVE,
            ManagedKeyState.SUSPENDED,
            ManagedKeyState.COMPROMISED,
            ManagedKeyState.REVOKED,
            ManagedKeyState.FAILED,
        }
    ),
    ManagedKeyState.SUSPENDED: frozenset(
        {
            ManagedKeyState.ACTIVE,
            ManagedKeyState.COMPROMISED,
            ManagedKeyState.REVOKED,
            ManagedKeyState.FAILED,
        }
    ),
    ManagedKeyState.COMPROMISED: frozenset(
        {ManagedKeyState.REVOKED, ManagedKeyState.FAILED}
    ),
    ManagedKeyState.REVOKED: frozenset(
        {ManagedKeyState.DESTROY_PENDING, ManagedKeyState.FAILED}
    ),
    ManagedKeyState.DESTROY_PENDING: frozenset(
        {
            ManagedKeyState.REVOKED,
            ManagedKeyState.DESTROYED,
            ManagedKeyState.FAILED,
        }
    ),
    ManagedKeyState.DESTROYED: frozenset(),
    ManagedKeyState.FAILED: frozenset(),
}


class ManagedKeyError(Exception):
    """Base class for controlled key management failures."""


class ManagedKeyNotFoundError(ManagedKeyError):
    """The key is absent or intentionally hidden from the actor."""


class ManagedKeyConflictError(ManagedKeyError):
    """The requested idempotent or concurrent operation conflicts."""


class InvalidKeyTransitionError(ManagedKeyError):
    """A lifecycle transition is forbidden."""


class KeyPolicyError(ManagedKeyError):
    """The configured key policy rejects an operation."""


class ProviderUnavailableError(ManagedKeyError):
    """The configured key provider is temporarily unavailable."""


class ProviderTimeoutError(ProviderUnavailableError):
    """The provider request exceeded its safe time limit."""


class ProviderPermissionDeniedError(ManagedKeyError):
    """The provider denied the operation."""


class ProviderKeyNotFoundError(ManagedKeyError):
    """The referenced provider key does not exist."""


class ProviderMetadataError(ManagedKeyError):
    """Provider public metadata is missing or inconsistent."""


class ManagedKeySigningRejectedError(ManagedKeyError):
    """The managed key cannot be used for this signing operation."""


class KeyDestructionNotReadyError(ManagedKeyError):
    """The policy-defined destruction delay has not elapsed."""


@dataclass(frozen=True)
class ProviderKeyMetadata:
    provider: str
    provider_key_reference: str = field(repr=False)
    algorithm: KeyAlgorithm
    public_key_multibase: str
    fingerprint: str
    holder_did: str
    verification_method: str
    enabled: bool
    destroyed: bool = False

    def __post_init__(self) -> None:
        _validate_name(self.provider, name="provider")
        _validate_reference(self.provider_key_reference)
        _validate_public_metadata(
            public_key_multibase=self.public_key_multibase,
            fingerprint=self.fingerprint,
            holder_did=self.holder_did,
            verification_method=self.verification_method,
        )
        if self.destroyed and self.enabled:
            raise ValueError("Destroyed provider key metadata cannot be enabled.")


@dataclass(frozen=True)
class ManagedKey:
    id: str
    key_id: str
    wallet_id: str
    owner_user_id: str
    holder_did: str
    provider: str
    provider_key_reference: str | None = field(default=None, repr=False)
    algorithm: KeyAlgorithm = KeyAlgorithm.ED25519
    purpose: KeyPurpose = KeyPurpose.PRESENTATION_SIGNING
    key_version: int = 1
    state: ManagedKeyState = ManagedKeyState.PENDING
    public_key_multibase: str | None = None
    fingerprint: str | None = None
    verification_method: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    activated_at: datetime | None = None
    rotated_at: datetime | None = None
    suspended_at: datetime | None = None
    revoked_at: datetime | None = None
    destroyed_at: datetime | None = None
    destruction_scheduled_at: datetime | None = None
    expires_at: datetime | None = None
    predecessor_key_id: str | None = None
    successor_key_id: str | None = None
    compromise_reason: str | None = field(default=None, repr=False)
    idempotency_key_hash: str | None = field(default=None, repr=False)
    reconciliation_attempts: int = 0
    reconciliation_lease_until: datetime | None = None
    last_provider_sync_at: datetime | None = None
    failure_code: str | None = None
    version: int = 1

    def __post_init__(self) -> None:
        if not _OBJECT_ID_PATTERN.fullmatch(self.id):
            raise ValueError(
                "Managed key storage id must be a 24-character ObjectId string."
            )
        if not _KEY_ID_PATTERN.fullmatch(self.key_id):
            raise ValueError("Managed key id is invalid.")
        _validate_name(self.wallet_id, name="walletId", maximum=100)
        _validate_name(self.owner_user_id, name="ownerUserId", maximum=200)
        _validate_name(self.holder_did, name="holderDid", maximum=2_048)
        if not self.holder_did.startswith("did:"):
            raise ValueError("Managed key holder DID is invalid.")
        _validate_name(self.provider, name="provider")
        if self.provider_key_reference is not None:
            _validate_reference(self.provider_key_reference)
        if self.key_version < 1 or self.version < 1:
            raise ValueError("Managed key versions must be positive.")
        if self.reconciliation_attempts < 0:
            raise ValueError("Reconciliation attempts cannot be negative.")
        if self.created_at is None or self.updated_at is None:
            raise ValueError("Managed key timestamps are required.")
        _require_aware(self.created_at, name="createdAt")
        _require_aware(self.updated_at, name="updatedAt")
        if self.updated_at < self.created_at:
            raise ValueError("Managed key update precedes creation.")
        for name, value in (
            ("activatedAt", self.activated_at),
            ("rotatedAt", self.rotated_at),
            ("suspendedAt", self.suspended_at),
            ("revokedAt", self.revoked_at),
            ("destroyedAt", self.destroyed_at),
            ("destructionScheduledAt", self.destruction_scheduled_at),
            ("expiresAt", self.expires_at),
            ("reconciliationLeaseUntil", self.reconciliation_lease_until),
            ("lastProviderSyncAt", self.last_provider_sync_at),
        ):
            if value is not None:
                _require_aware(value, name=name)
        if any(
            value is not None
            for value in (
                self.public_key_multibase,
                self.fingerprint,
                self.verification_method,
            )
        ):
            if None in (
                self.public_key_multibase,
                self.fingerprint,
                self.verification_method,
            ):
                raise ValueError("Managed key public metadata is incomplete.")
            _validate_public_metadata(
                public_key_multibase=self.public_key_multibase or "",
                fingerprint=self.fingerprint or "",
                holder_did=self.holder_did,
                verification_method=self.verification_method or "",
            )
        if self.state in {
            ManagedKeyState.ACTIVE,
            ManagedKeyState.ROTATING,
            ManagedKeyState.SUSPENDED,
            ManagedKeyState.COMPROMISED,
            ManagedKeyState.REVOKED,
            ManagedKeyState.DESTROY_PENDING,
            ManagedKeyState.DESTROYED,
        } and (
            self.provider_key_reference is None
            or self.public_key_multibase is None
        ):
            raise ValueError("Provisioned managed key metadata is required.")
        if (
            self.state is ManagedKeyState.DESTROYED
            and self.destroyed_at is None
        ):
            raise ValueError("Destroyed keys require destroyedAt.")
        if (
            self.state is ManagedKeyState.DESTROY_PENDING
            and self.destruction_scheduled_at is None
        ):
            raise ValueError(
                "Keys pending destruction require a scheduled time."
            )
        if self.idempotency_key_hash is not None and not re.fullmatch(
            r"^[0-9a-f]{64}$",
            self.idempotency_key_hash,
        ):
            raise ValueError("Idempotency key hash is invalid.")

    @property
    def can_sign(self) -> bool:
        return (
            self.state is ManagedKeyState.ACTIVE
            and self.provider_key_reference is not None
            and self.public_key_multibase is not None
        )

    def require_signing(
        self,
        *,
        purpose: KeyPurpose,
        algorithm: KeyAlgorithm,
    ) -> None:
        if self.state is not ManagedKeyState.ACTIVE:
            raise ManagedKeySigningRejectedError(
                "The managed key lifecycle state prohibits signing."
            )
        if self.purpose is not purpose:
            raise ManagedKeySigningRejectedError(
                "The managed key purpose does not permit this operation."
            )
        if self.algorithm is not algorithm:
            raise ManagedKeySigningRejectedError(
                "The managed key algorithm is incompatible."
            )

    def transition(
        self,
        new_state: ManagedKeyState,
        *,
        at: datetime,
        reason: str | None = None,
        destruction_scheduled_at: datetime | None = None,
    ) -> "ManagedKey":
        _require_aware(at, name="transitionAt")
        if new_state is self.state:
            return self
        if new_state not in VALID_KEY_TRANSITIONS[self.state]:
            raise InvalidKeyTransitionError(
                f"Managed key cannot transition from {self.state.value} "
                f"to {new_state.value}."
            )
        changes: dict[str, object] = {
            "state": new_state,
            "updated_at": at,
            "version": self.version + 1,
        }
        if new_state is ManagedKeyState.ACTIVE:
            changes["activated_at"] = self.activated_at or at
            changes["suspended_at"] = None
            changes["destruction_scheduled_at"] = None
        elif new_state is ManagedKeyState.ROTATING:
            changes["rotated_at"] = at
        elif new_state is ManagedKeyState.SUSPENDED:
            changes["suspended_at"] = at
        elif new_state is ManagedKeyState.COMPROMISED:
            normalized_reason = (reason or "").strip()
            if len(normalized_reason) < 8:
                raise ValueError("Compromise reason is required.")
            changes["compromise_reason"] = normalized_reason[:500]
        elif new_state is ManagedKeyState.REVOKED:
            changes["revoked_at"] = at
            changes["destruction_scheduled_at"] = None
        elif new_state is ManagedKeyState.DESTROY_PENDING:
            if destruction_scheduled_at is None:
                raise ValueError("Destruction schedule is required.")
            _require_aware(
                destruction_scheduled_at,
                name="destructionScheduledAt",
            )
            if destruction_scheduled_at <= at:
                raise ValueError("Destruction schedule must be in the future.")
            changes["destruction_scheduled_at"] = destruction_scheduled_at
        elif new_state is ManagedKeyState.DESTROYED:
            changes["destroyed_at"] = at
        elif new_state is ManagedKeyState.FAILED:
            changes["failure_code"] = _safe_reason_code(reason)
        return replace(self, **changes)


def idempotency_hash(value: str) -> str:
    normalized = value.strip()
    if not 8 <= len(normalized) <= 256:
        raise ValueError("Idempotency key length is invalid.")
    return sha256(normalized.encode("utf-8")).hexdigest()


def public_key_fingerprint(public_key_multibase: str) -> str:
    if (
        not public_key_multibase.startswith("z")
        or len(public_key_multibase) > 512
        or any(character.isspace() for character in public_key_multibase)
    ):
        raise ProviderMetadataError("Provider public key encoding is invalid.")
    return sha256(public_key_multibase.encode("ascii")).hexdigest()


def validate_provider_metadata(
    metadata: ProviderKeyMetadata,
    *,
    provider: str,
    algorithm: KeyAlgorithm,
    provider_key_reference: str | None = None,
) -> None:
    if metadata.provider != provider:
        raise ProviderMetadataError("Provider metadata identity mismatch.")
    if metadata.algorithm is not algorithm:
        raise ProviderMetadataError("Provider key algorithm mismatch.")
    if (
        provider_key_reference is not None
        and metadata.provider_key_reference != provider_key_reference
    ):
        raise ProviderMetadataError("Provider key reference mismatch.")
    if metadata.fingerprint != public_key_fingerprint(
        metadata.public_key_multibase
    ):
        raise ProviderMetadataError("Provider public key fingerprint mismatch.")
    if metadata.destroyed:
        raise ProviderMetadataError("Provider returned a destroyed key.")


def _validate_public_metadata(
    *,
    public_key_multibase: str,
    fingerprint: str,
    holder_did: str,
    verification_method: str,
) -> None:
    calculated = public_key_fingerprint(public_key_multibase)
    if not _FINGERPRINT_PATTERN.fullmatch(fingerprint):
        raise ValueError("Managed key fingerprint is invalid.")
    if calculated != fingerprint:
        raise ValueError("Managed key fingerprint is inconsistent.")
    if not holder_did.startswith("did:") or len(holder_did) > 2_048:
        raise ValueError("Managed key holder DID is invalid.")
    if (
        not verification_method.startswith(f"{holder_did}#")
        or len(verification_method) > 4_096
    ):
        raise ValueError("Managed key verification method is invalid.")


def _validate_name(
    value: str,
    *,
    name: str,
    maximum: int = 100,
) -> None:
    normalized = value.strip()
    if (
        not normalized
        or len(normalized) > maximum
        or any(character.isspace() for character in normalized)
    ):
        raise ValueError(f"Managed key {name} is invalid.")


def _validate_reference(value: str) -> None:
    if not _SAFE_REFERENCE_PATTERN.fullmatch(value):
        raise ValueError("Provider key reference is invalid.")


def _safe_reason_code(value: str | None) -> str:
    normalized = (value or "UNSPECIFIED_FAILURE").strip().upper()
    if not re.fullmatch(r"^[A-Z][A-Z0-9_]{2,63}$", normalized):
        return "PROVIDER_OPERATION_FAILED"
    return normalized


def _require_aware(value: datetime, *, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware.")
