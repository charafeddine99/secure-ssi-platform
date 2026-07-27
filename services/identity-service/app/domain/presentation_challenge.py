import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.domain.holder_wallet import validate_holder_did
from app.domain.presentation import normalize_domain, validate_challenge


_OBJECT_ID_PATTERN = re.compile(r"^[0-9a-f]{24}$")
_CHALLENGE_ID_PATTERN = re.compile(r"^challenge_[A-Za-z0-9_-]{16,80}$")


class ChallengeStatus(StrEnum):
    ISSUED = "ISSUED"
    CONSUMED = "CONSUMED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class PresentationChallengeError(Exception):
    """Base class for controlled challenge lifecycle failures."""


class PresentationChallengeNotFoundError(PresentationChallengeError):
    """The challenge is absent or hidden from the current actor."""


class PresentationChallengeConflictError(PresentationChallengeError):
    """A challenge identifier or random value is already in use."""


class PresentationChallengeRejectedError(PresentationChallengeError):
    """The challenge cannot be used for the requested presentation."""


class PresentationChallengeReplayError(PresentationChallengeRejectedError):
    """The challenge was already consumed."""


class PresentationChallengeExpiredError(PresentationChallengeRejectedError):
    """The challenge validity window has elapsed."""


@dataclass(frozen=True)
class PresentationChallenge:
    id: str
    challenge_id: str
    challenge: str = field(repr=False)
    domain: str
    audience: str
    requested_holder_did: str | None
    issued_by: str
    issued_at: datetime
    expires_at: datetime
    consumed_at: datetime | None
    status: ChallengeStatus
    version: int = 1

    def __post_init__(self) -> None:
        if not _OBJECT_ID_PATTERN.fullmatch(self.id):
            raise ValueError(
                "Challenge storage id must be a 24-character ObjectId string."
            )
        validate_challenge_id(self.challenge_id)
        validate_challenge(self.challenge)
        normalized_domain = normalize_domain(self.domain)
        normalized_audience = normalize_audience(self.audience)
        if self.requested_holder_did is not None:
            object.__setattr__(
                self,
                "requested_holder_did",
                validate_holder_did(self.requested_holder_did),
            )
        if not self.issued_by.strip() or len(self.issued_by) > 200:
            raise ValueError("Challenge issuer is invalid.")
        _require_aware(self.issued_at, name="issuedAt")
        _require_aware(self.expires_at, name="expiresAt")
        lifetime = (self.expires_at - self.issued_at).total_seconds()
        if not 30 <= lifetime <= 3_600:
            raise ValueError("Challenge lifetime is outside policy.")
        if self.consumed_at is not None:
            _require_aware(self.consumed_at, name="consumedAt")
            if not self.issued_at <= self.consumed_at <= self.expires_at:
                raise ValueError("Challenge consumption time is invalid.")
        if self.version < 1:
            raise ValueError("Challenge version must be positive.")
        if self.status is ChallengeStatus.CONSUMED:
            if self.consumed_at is None:
                raise ValueError("Consumed challenge requires consumedAt.")
        elif self.consumed_at is not None:
            raise ValueError(
                "Only a consumed challenge may contain consumedAt."
            )
        object.__setattr__(self, "domain", normalized_domain)
        object.__setattr__(self, "audience", normalized_audience)
        object.__setattr__(self, "issued_by", self.issued_by.strip())


def validate_challenge_id(value: str) -> str:
    if not _CHALLENGE_ID_PATTERN.fullmatch(value):
        raise ValueError("Challenge id is invalid.")
    return value


def normalize_audience(value: str) -> str:
    normalized = value.strip()
    if (
        not normalized
        or len(normalized) > 256
        or any(ord(character) < 33 or ord(character) > 126 for character in normalized)
    ):
        raise ValueError("Challenge audience is invalid.")
    return normalized


def _require_aware(value: datetime, *, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware.")
