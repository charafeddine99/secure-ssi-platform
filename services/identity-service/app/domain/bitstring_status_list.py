import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from types import MappingProxyType
from typing import Any
from uuid import NAMESPACE_URL, uuid5


MINIMUM_STATUS_LIST_ENTRIES = 131_072
MAXIMUM_STATUS_LIST_ENTRIES = 16_777_216
_OBJECT_ID_PATTERN = re.compile(r"^[0-9a-f]{24}$")
_STATUS_LIST_ID_PATTERN = re.compile(
    r"^revocation-[0-9a-f]{24}(?:-[0-9]{6})?$"
)


class StatusPurpose(StrEnum):
    REVOCATION = "revocation"


class StatusListError(Exception):
    """Base class for controlled status-list failures."""


class StatusListNotFoundError(StatusListError):
    """The requested status list has no assigned credential entries."""


class StatusListVersionNotFoundError(StatusListNotFoundError):
    """The requested immutable publication version does not exist."""


class StatusListCapacityError(StatusListError):
    """No free status index remains in the configured list."""


class StatusListConflictError(StatusListError):
    """A status list changed during optimistic publication."""


class StatusListGenerationError(StatusListError):
    """A status-list credential could not be generated safely."""


@dataclass(frozen=True)
class CredentialStatusEntry:
    id: str
    credential_id: str
    issuer_did: str
    status_list_id: str
    status_list_index: int
    status_purpose: StatusPurpose
    created_at: datetime
    updated_at: datetime
    version: int = 1

    def __post_init__(self) -> None:
        if not _OBJECT_ID_PATTERN.fullmatch(self.id):
            raise ValueError(
                "Status entry id must be a 24-character ObjectId string."
            )
        for name, value, maximum in (
            ("credentialId", self.credential_id, 2_048),
            ("issuerDid", self.issuer_did, 2_048),
        ):
            if not value.strip() or len(value) > maximum:
                raise ValueError(f"{name} is empty or too long.")
        if not _STATUS_LIST_ID_PATTERN.fullmatch(self.status_list_id):
            raise ValueError("Status list id is invalid.")
        if not 0 <= self.status_list_index < MAXIMUM_STATUS_LIST_ENTRIES:
            raise ValueError("Status list index is outside the list.")
        _require_aware(self.created_at, name="createdAt")
        _require_aware(self.updated_at, name="updatedAt")
        if self.updated_at < self.created_at or self.version < 1:
            raise ValueError("Status entry metadata is invalid.")

    @property
    def entry_urn(self) -> str:
        return f"urn:uuid:{uuid5(NAMESPACE_URL, self.credential_id)}"

    def to_credential_status(
        self,
        *,
        status_list_credential_url: str,
    ) -> Mapping[str, str]:
        if not status_list_credential_url.startswith(("http://", "https://")):
            raise ValueError("Status list credential URL must use HTTP(S).")
        return MappingProxyType(
            {
                "id": self.entry_urn,
                "type": "BitstringStatusListEntry",
                "statusPurpose": self.status_purpose.value,
                "statusListIndex": str(self.status_list_index),
                "statusListCredential": status_list_credential_url,
            }
        )


@dataclass(frozen=True)
class StatusListPublication:
    id: str
    status_list_id: str
    issuer_did: str
    status_purpose: StatusPurpose
    encoded_list: str
    content_hash: str
    document: Mapping[str, Any]
    list_length: int
    capacity: int
    assigned_entries: int
    revoked_entries: int
    ttl_seconds: int
    etag: str
    published_at: datetime
    created_at: datetime
    updated_at: datetime
    version: int = 1

    def __post_init__(self) -> None:
        if not _OBJECT_ID_PATTERN.fullmatch(self.id):
            raise ValueError(
                "Status list id must be a 24-character ObjectId string."
            )
        if not _STATUS_LIST_ID_PATTERN.fullmatch(self.status_list_id):
            raise ValueError("Status list identifier is invalid.")
        if not self.issuer_did.strip() or len(self.issuer_did) > 2_048:
            raise ValueError("Status list issuer is invalid.")
        if not (
            MINIMUM_STATUS_LIST_ENTRIES
            <= self.list_length
            <= MAXIMUM_STATUS_LIST_ENTRIES
        ):
            raise ValueError("Status list is shorter than the W3C minimum.")
        if not 0 <= self.revoked_entries <= self.assigned_entries:
            raise ValueError("Status list counts are inconsistent.")
        if not 1 <= self.capacity <= self.list_length:
            raise ValueError("Status list capacity is invalid.")
        if self.assigned_entries > self.capacity:
            raise ValueError("Status list has too many assigned entries.")
        if self.ttl_seconds < 1 or self.version < 1:
            raise ValueError("Status list cache/version metadata is invalid.")
        if (
            not self.encoded_list.startswith("u")
            or not re.fullmatch(r"[A-Za-z0-9_-]+", self.encoded_list[1:])
        ):
            raise ValueError("Status list encoding is invalid.")
        if not re.fullmatch(r"[0-9a-f]{64}", self.content_hash):
            raise ValueError("Status list content hash is invalid.")
        if self.etag != f'"{self.content_hash}-v{self.version}"':
            raise ValueError("Status list ETag does not match its content.")
        for name, value in (
            ("publishedAt", self.published_at),
            ("createdAt", self.created_at),
            ("updatedAt", self.updated_at),
        ):
            _require_aware(value, name=name)
        if (
            self.created_at > self.updated_at
            or self.published_at != self.updated_at
        ):
            raise ValueError("Status list timestamps are inconsistent.")
        object.__setattr__(
            self,
            "document",
            MappingProxyType(dict(self.document)),
        )

    @property
    def cache_control(self) -> str:
        return f"public, max-age={self.ttl_seconds}, must-revalidate"


def generate_status_list_id(
    issuer_did: str,
    *,
    status_purpose: StatusPurpose = StatusPurpose.REVOCATION,
    sequence: int = 1,
) -> str:
    normalized = issuer_did.strip()
    if not normalized or len(normalized) > 2_048:
        raise ValueError("Issuer DID is invalid.")
    digest = sha256(
        f"{status_purpose.value}\0{normalized}".encode("utf-8")
    ).hexdigest()
    if not 1 <= sequence <= 999_999:
        raise ValueError("Status list sequence is invalid.")
    base = f"{status_purpose.value}-{digest[:24]}"
    return base if sequence == 1 else f"{base}-{sequence:06d}"


def status_list_sequence(status_list_id: str) -> int:
    if not _STATUS_LIST_ID_PATTERN.fullmatch(status_list_id):
        raise ValueError("Status list identifier is invalid.")
    suffix = status_list_id.rsplit("-", maxsplit=1)[-1]
    return int(suffix) if len(suffix) == 6 and suffix.isdecimal() else 1


def deterministic_index_candidate(
    credential_id: str,
    *,
    list_length: int = MINIMUM_STATUS_LIST_ENTRIES,
) -> int:
    if not credential_id.strip() or not (
        1 <= list_length <= MAXIMUM_STATUS_LIST_ENTRIES
    ):
        raise ValueError("Credential id or list length is invalid.")
    digest = sha256(credential_id.strip().encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % list_length


def _require_aware(value: datetime, *, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware.")
