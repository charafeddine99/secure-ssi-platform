from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.managed_key import (
    KeyAlgorithm,
    KeyPurpose,
    ManagedKey,
)
from app.schemas.credential_api import ApiModel


class ManagedKeyCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: KeyPurpose = KeyPurpose.PRESENTATION_SIGNING
    algorithm: KeyAlgorithm = KeyAlgorithm.ED25519
    provider: Annotated[
        str | None,
        Field(default=None, min_length=1, max_length=100),
    ]

    @field_validator("provider")
    @classmethod
    def normalize_provider(cls, value: str | None) -> str | None:
        return None if value is None else value.strip().casefold()


class ManagedKeyRotateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ManagedKeyReasonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, Field(min_length=8, max_length=500)]

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return value.strip()


class ManagedKeyDestructionRequest(ManagedKeyReasonRequest):
    confirmation: Annotated[str, Field(min_length=20, max_length=84)]


class ManagedKeyResponse(ApiModel):
    key_id: str
    wallet_id: str
    owner_user_id: str
    holder_did: str
    provider: str
    algorithm: str
    purpose: str
    key_version: int
    state: str
    public_key_multibase: str | None
    fingerprint: str | None
    verification_method: str | None
    created_at: datetime
    updated_at: datetime
    activated_at: datetime | None
    rotated_at: datetime | None
    suspended_at: datetime | None
    revoked_at: datetime | None
    destroyed_at: datetime | None
    destruction_scheduled_at: datetime | None
    expires_at: datetime | None
    predecessor_key_id: str | None
    successor_key_id: str | None
    version: int

    @classmethod
    def from_domain(cls, key: ManagedKey) -> "ManagedKeyResponse":
        if key.created_at is None or key.updated_at is None:
            raise ValueError("Managed key timestamps are unavailable.")
        return cls(
            key_id=key.key_id,
            wallet_id=key.wallet_id,
            owner_user_id=key.owner_user_id,
            holder_did=key.holder_did,
            provider=key.provider,
            algorithm=key.algorithm.value,
            purpose=key.purpose.value,
            key_version=key.key_version,
            state=key.state.value,
            public_key_multibase=key.public_key_multibase,
            fingerprint=key.fingerprint,
            verification_method=key.verification_method,
            created_at=key.created_at,
            updated_at=key.updated_at,
            activated_at=key.activated_at,
            rotated_at=key.rotated_at,
            suspended_at=key.suspended_at,
            revoked_at=key.revoked_at,
            destroyed_at=key.destroyed_at,
            destruction_scheduled_at=key.destruction_scheduled_at,
            expires_at=key.expires_at,
            predecessor_key_id=key.predecessor_key_id,
            successor_key_id=key.successor_key_id,
            version=key.version,
        )


class ManagedKeyListResponse(ApiModel):
    wallet_id: str
    items: list[ManagedKeyResponse]
    next_cursor: str | None
