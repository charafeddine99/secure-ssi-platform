from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.holder_wallet import HolderWallet, validate_holder_did
from app.domain.persistence import PersistedCredential
from app.domain.presentation import normalize_domain
from app.domain.presentation_challenge import (
    PresentationChallenge,
    normalize_audience,
)
from app.schemas.credential_api import ApiModel


class HolderWalletCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HolderWalletResponse(ApiModel):
    wallet_id: str
    owner_user_id: str
    holder_did: str
    status: str
    created_at: datetime
    updated_at: datetime
    version: int

    @classmethod
    def from_domain(cls, wallet: HolderWallet) -> "HolderWalletResponse":
        return cls(
            wallet_id=wallet.wallet_id,
            owner_user_id=wallet.owner_user_id,
            holder_did=wallet.holder_did,
            status=wallet.status.value,
            created_at=wallet.created_at,
            updated_at=wallet.updated_at,
            version=wallet.version,
        )


class WalletCredentialResponse(ApiModel):
    credential_id: str
    holder_did: str
    status: str
    issuance_date: datetime
    expiration_date: datetime | None

    @classmethod
    def from_domain(
        cls,
        credential: PersistedCredential,
    ) -> "WalletCredentialResponse":
        return cls(
            credential_id=credential.credential_id,
            holder_did=credential.holder_did,
            status=credential.status.value,
            issuance_date=credential.issuance_date,
            expiration_date=credential.expiration_date,
        )


class WalletCredentialInventoryResponse(ApiModel):
    wallet_id: str
    credentials: list[WalletCredentialResponse]


class PresentationChallengeCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: Annotated[str, Field(min_length=1, max_length=253)]
    audience: Annotated[str, Field(min_length=1, max_length=256)]
    requestedHolderDid: str | None = Field(  # noqa: N815
        default=None,
        min_length=7,
        max_length=2_048,
    )
    lifetimeSeconds: int = Field(default=300, ge=30, le=3_600)  # noqa: N815

    @field_validator("domain")
    @classmethod
    def domain_is_safe(cls, value: str) -> str:
        return normalize_domain(value)

    @field_validator("audience")
    @classmethod
    def audience_is_safe(cls, value: str) -> str:
        return normalize_audience(value)

    @field_validator("requestedHolderDid")
    @classmethod
    def holder_did_is_safe(cls, value: str | None) -> str | None:
        return None if value is None else validate_holder_did(value)


class PresentationChallengeResponse(ApiModel):
    challenge_id: str
    challenge: str
    domain: str
    audience: str
    requested_holder_did: str | None
    issued_by: str
    issued_at: datetime
    expires_at: datetime
    consumed_at: datetime | None
    status: str
    version: int

    @classmethod
    def from_domain(
        cls,
        challenge: PresentationChallenge,
    ) -> "PresentationChallengeResponse":
        return cls(
            challenge_id=challenge.challenge_id,
            challenge=challenge.challenge,
            domain=challenge.domain,
            audience=challenge.audience,
            requested_holder_did=challenge.requested_holder_did,
            issued_by=challenge.issued_by,
            issued_at=challenge.issued_at,
            expires_at=challenge.expires_at,
            consumed_at=challenge.consumed_at,
            status=challenge.status.value,
            version=challenge.version,
        )
