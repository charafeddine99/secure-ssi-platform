from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any


class TrustStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class TrustRole(StrEnum):
    ISSUER = "issuer"
    VERIFIER = "verifier"


@dataclass(frozen=True)
class TrustRecord:
    id: str
    issuer_did: str
    organization_name: str
    trust_status: TrustStatus
    roles: tuple[TrustRole, ...] = (TrustRole.ISSUER,)
    permitted_credential_types: tuple[str, ...] = ("VerifiableCredential",)
    valid_from: datetime = field(default_factory=lambda: datetime.now(UTC))
    valid_until: datetime | None = None
    trust_source: str = "LOCAL_TRUST_REGISTRY"
    trust_anchor: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    created_by: str = "admin@platform.local"
    audit_metadata: Mapping[str, Any] = field(default_factory=dict)
    version: int = 1

    def __post_init__(self) -> None:
        if not self.id or not isinstance(self.id, str):
            raise ValueError("Trust record id must be a non-empty string.")
        if not self.issuer_did or not isinstance(self.issuer_did, str):
            raise ValueError("Trust record issuer_did must be a non-empty string.")
        if not self.organization_name or not isinstance(self.organization_name, str):
            raise ValueError("Trust record organization_name must be a non-empty string.")

    def is_active(self) -> bool:
        return self.trust_status == TrustStatus.ACTIVE

    def is_valid_at(self, when: datetime) -> bool:
        if self.trust_status != TrustStatus.ACTIVE:
            return False
        # Normalize when and self timestamps
        check_time = when.astimezone(UTC) if when.tzinfo else when.replace(tzinfo=UTC)
        v_from = self.valid_from.astimezone(UTC) if self.valid_from.tzinfo else self.valid_from.replace(tzinfo=UTC)
        if check_time < v_from:
            return False
        if self.valid_until is not None:
            v_until = self.valid_until.astimezone(UTC) if self.valid_until.tzinfo else self.valid_until.replace(tzinfo=UTC)
            if check_time > v_until:
                return False
        return True

    def allows_credential_type(self, cred_type: str) -> bool:
        if "*" in self.permitted_credential_types:
            return True
        return cred_type in self.permitted_credential_types

    def allows_any_credential_type(self, cred_types: tuple[str, ...] | list[str]) -> bool:
        if not cred_types or "*" in self.permitted_credential_types:
            return True
        return any(self.allows_credential_type(t) for t in cred_types)


@dataclass(frozen=True)
class TrustEvaluationResult:
    is_trusted: bool
    issuer_did: str
    status: TrustStatus | None
    reason: str
    trust_record_id: str | None = None
    trust_source: str | None = None
    matched_types: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "isTrusted": self.is_trusted,
            "issuerDid": self.issuer_did,
            "status": self.status.value if self.status else None,
            "reason": self.reason,
            "trustRecordId": self.trust_record_id,
            "trustSource": self.trust_source,
            "matchedTypes": list(self.matched_types),
        }
