import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any
from uuid import UUID, uuid4


VC_V2_CONTEXT = "https://www.w3.org/ns/credentials/v2"
PRESENTATION_TYPE = "VerifiablePresentation"
PRESENTATION_PROOF_PURPOSE = "authentication"
MIN_PRESENTATION_LIFETIME_SECONDS = 30
MAX_PRESENTATION_LIFETIME_SECONDS = 600
MAX_PRESENTATION_CREDENTIALS = 8
MAX_PRESENTATION_BYTES = 65_536

_OBJECT_ID_PATTERN = re.compile(r"^[0-9a-f]{24}$")
_WALLET_ID_PATTERN = re.compile(r"^wallet_[A-Za-z0-9_-]{16,80}$")
_CHALLENGE_ID_PATTERN = re.compile(r"^challenge_[A-Za-z0-9_-]{16,80}$")
_CHALLENGE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
_DOMAIN_PATTERN = re.compile(
    r"^(?=.{1,253}$)"
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)


class PresentationVerificationState(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class PresentationError(Exception):
    """Base class for controlled presentation failures."""


class InvalidPresentationError(PresentationError):
    """A presentation or creation request violates the local VP profile."""


class PresentationNotFoundError(PresentationError):
    """The requested presentation does not exist."""


class PresentationReplayError(PresentationError):
    """A challenge or presentation verification attempt was already used."""


class PresentationCredentialError(PresentationError):
    """A referenced credential is missing or cannot be presented."""


@dataclass(frozen=True)
class PersistedPresentation:
    id: str
    presentation_id: str
    holder_did: str
    challenge: str
    domain: str
    credential_ids: tuple[str, ...]
    document: Mapping[str, Any]
    verification_result: PresentationVerificationState
    created_at: datetime
    expires_at: datetime
    updated_at: datetime
    version: int = 1
    verified_at: datetime | None = None
    rejection_codes: tuple[str, ...] = ()
    wallet_id: str | None = None
    owner_user_id: str | None = None
    challenge_id: str | None = None
    audience: str | None = None
    processing_started_at: datetime | None = None
    reconciliation_attempts: int = 0
    last_reconciled_at: datetime | None = None

    def __post_init__(self) -> None:
        if not _OBJECT_ID_PATTERN.fullmatch(self.id):
            raise ValueError(
                "Presentation storage id must be a 24-character ObjectId string."
            )
        validate_presentation_id(self.presentation_id)
        if (
            not self.holder_did.startswith("did:key:z")
            or len(self.holder_did) > 2_048
        ):
            raise ValueError("Presentation holder DID is invalid.")
        validate_challenge(self.challenge)
        normalized_domain = normalize_domain(self.domain)
        if not 1 <= len(self.credential_ids) <= MAX_PRESENTATION_CREDENTIALS:
            raise ValueError("Presentation credential count is invalid.")
        if len(set(self.credential_ids)) != len(self.credential_ids) or any(
            not value.strip() or len(value) > 2_048
            for value in self.credential_ids
        ):
            raise ValueError("Presentation credential identifiers are invalid.")
        for name, value in (
            ("createdAt", self.created_at),
            ("expiresAt", self.expires_at),
            ("updatedAt", self.updated_at),
        ):
            _require_aware(value, name=name)
        lifetime = (self.expires_at - self.created_at).total_seconds()
        if not (
            MIN_PRESENTATION_LIFETIME_SECONDS
            <= lifetime
            <= MAX_PRESENTATION_LIFETIME_SECONDS
        ):
            raise ValueError("Presentation lifetime is outside policy.")
        if self.updated_at < self.created_at or self.version < 1:
            raise ValueError("Presentation persistence metadata is invalid.")
        if self.verified_at is not None:
            _require_aware(self.verified_at, name="verifiedAt")
        security_values = (
            self.wallet_id,
            self.owner_user_id,
            self.challenge_id,
            self.audience,
        )
        if any(value is not None for value in security_values):
            if any(value is None for value in security_values):
                raise ValueError(
                    "Wallet-bound presentation metadata is incomplete."
                )
            if not _WALLET_ID_PATTERN.fullmatch(self.wallet_id):
                raise ValueError("Presentation wallet id is invalid.")
            if (
                not self.owner_user_id.strip()
                or len(self.owner_user_id) > 200
            ):
                raise ValueError("Presentation owner user id is invalid.")
            if not _CHALLENGE_ID_PATTERN.fullmatch(self.challenge_id):
                raise ValueError("Presentation challenge id is invalid.")
            if (
                not self.audience.strip()
                or len(self.audience) > 256
                or any(
                    ord(character) < 33 or ord(character) > 126
                    for character in self.audience
                )
            ):
                raise ValueError("Presentation audience is invalid.")
        if self.processing_started_at is not None:
            _require_aware(
                self.processing_started_at,
                name="processingStartedAt",
            )
            if self.processing_started_at < self.created_at:
                raise ValueError(
                    "Presentation processing precedes creation."
                )
        if self.reconciliation_attempts < 0:
            raise ValueError(
                "Presentation reconciliation attempts are invalid."
            )
        if self.last_reconciled_at is not None:
            _require_aware(
                self.last_reconciled_at,
                name="lastReconciledAt",
            )
            if (
                self.reconciliation_attempts < 1
                or self.processing_started_at is None
                or self.last_reconciled_at < self.processing_started_at
            ):
                raise ValueError(
                    "Presentation reconciliation metadata is invalid."
                )
        elif self.reconciliation_attempts:
            raise ValueError(
                "Presentation reconciliation timestamp is missing."
            )
        if self.verification_result in {
            PresentationVerificationState.PENDING,
            PresentationVerificationState.PROCESSING,
        }:
            if self.verified_at is not None or self.rejection_codes:
                raise ValueError("Unverified presentation state is inconsistent.")
        elif self.verification_result is PresentationVerificationState.VERIFIED:
            if self.verified_at is None or self.rejection_codes:
                raise ValueError("Verified presentation state is inconsistent.")
        elif self.verified_at is None or not self.rejection_codes:
            raise ValueError("Rejected presentation state is inconsistent.")
        if any(
            not re.fullmatch(r"[A-Z][A-Z0-9_]{0,99}", code)
            for code in self.rejection_codes
        ):
            raise ValueError("Presentation rejection code is invalid.")
        if (
            self.verification_result
            is PresentationVerificationState.PENDING
            and self.processing_started_at is not None
        ):
            raise ValueError("Pending presentation cannot be processing.")
        if (
            self.verification_result
            is PresentationVerificationState.PROCESSING
            and self.processing_started_at is None
        ):
            raise ValueError("Processing presentation requires a start time.")
        object.__setattr__(self, "domain", normalized_domain)
        if self.owner_user_id is not None:
            object.__setattr__(
                self,
                "owner_user_id",
                self.owner_user_id.strip(),
            )
        if self.audience is not None:
            object.__setattr__(self, "audience", self.audience.strip())
        object.__setattr__(
            self,
            "document",
            MappingProxyType(dict(self.document)),
        )


@dataclass(frozen=True)
class PresentationValidationResult:
    valid: bool
    verified_at: datetime
    presentation_id: str | None
    holder_did: str | None
    credential_ids: tuple[str, ...]
    errors: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_aware(self.verified_at, name="verifiedAt")
        if self.valid != (not self.errors):
            raise ValueError("Presentation validation result is inconsistent.")


def generate_presentation_id() -> str:
    return f"urn:uuid:{uuid4()}"


def validate_presentation_id(value: str) -> str:
    if not value.startswith("urn:uuid:"):
        raise ValueError("Presentation id must be a UUID URN.")
    try:
        identifier = UUID(value.removeprefix("urn:uuid:"))
    except ValueError as error:
        raise ValueError("Presentation id must be a UUID URN.") from error
    if identifier.version != 4:
        raise ValueError("Presentation id must contain a UUIDv4.")
    return value


def validate_challenge(value: str) -> str:
    if not _CHALLENGE_PATTERN.fullmatch(value):
        raise ValueError(
            "Challenge must be 16 to 128 URL-safe random characters."
        )
    return value


def normalize_domain(value: str) -> str:
    normalized = value.strip().casefold().rstrip(".")
    if not _DOMAIN_PATTERN.fullmatch(normalized):
        raise ValueError("Presentation domain must be a DNS hostname.")
    return normalized


def _require_aware(value: datetime, *, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware.")
