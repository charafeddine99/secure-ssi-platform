from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from app.domain.presentation import (
    MAX_PRESENTATION_CREDENTIALS,
    MAX_PRESENTATION_LIFETIME_SECONDS,
    MIN_PRESENTATION_LIFETIME_SECONDS,
    PersistedPresentation,
    PresentationValidationResult,
    normalize_domain,
    validate_challenge,
)
from app.schemas.credential_api import ApiModel
from app.domain.presentation_challenge import normalize_audience


class PresentationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credentialIds: list[  # noqa: N815
        Annotated[str, Field(min_length=1, max_length=2_048)]
    ] = Field(min_length=1, max_length=MAX_PRESENTATION_CREDENTIALS)
    walletId: str | None = Field(  # noqa: N815
        default=None,
        min_length=23,
        max_length=87,
    )
    challengeId: str | None = Field(  # noqa: N815
        default=None,
        min_length=26,
        max_length=90,
    )
    challenge: str | None = Field(
        default=None,
        min_length=16,
        max_length=128,
    )
    domain: str | None = Field(
        default=None,
        min_length=1,
        max_length=253,
    )
    audience: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
    )
    lifetimeSeconds: int = Field(  # noqa: N815
        default=300,
        ge=MIN_PRESENTATION_LIFETIME_SECONDS,
        le=MAX_PRESENTATION_LIFETIME_SECONDS,
    )

    @field_validator("credentialIds")
    @classmethod
    def credential_ids_are_unique(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value]
        if len(normalized) != len(set(normalized)):
            raise ValueError("Credential ids must be unique.")
        return normalized

    @field_validator("challenge")
    @classmethod
    def challenge_is_safe(cls, value: str | None) -> str | None:
        return None if value is None else validate_challenge(value)

    @field_validator("domain")
    @classmethod
    def domain_is_safe(cls, value: str | None) -> str | None:
        return None if value is None else normalize_domain(value)

    @field_validator("audience")
    @classmethod
    def audience_is_safe(cls, value: str | None) -> str | None:
        return None if value is None else normalize_audience(value)


class PresentationVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    presentation: dict[str, JsonValue]
    expectedChallenge: str | None = Field(  # noqa: N815
        default=None,
        min_length=16,
        max_length=128,
    )
    expectedDomain: str | None = Field(  # noqa: N815
        default=None,
        min_length=1,
        max_length=253,
    )
    expectedAudience: str | None = Field(  # noqa: N815
        default=None,
        min_length=1,
        max_length=256,
    )

    @field_validator("expectedChallenge")
    @classmethod
    def challenge_is_safe(cls, value: str | None) -> str | None:
        return None if value is None else validate_challenge(value)

    @field_validator("expectedDomain")
    @classmethod
    def domain_is_safe(cls, value: str | None) -> str | None:
        return None if value is None else normalize_domain(value)

    @field_validator("expectedAudience")
    @classmethod
    def audience_is_safe(cls, value: str | None) -> str | None:
        return None if value is None else normalize_audience(value)


class PresentationMetadataResponse(ApiModel):
    presentation_id: str
    holder_did: str
    challenge: str
    domain: str
    credential_ids: list[str]
    verification_result: str
    created_at: datetime
    expires_at: datetime
    verified_at: datetime | None
    rejection_codes: list[str]
    version: int
    wallet_id: str | None
    owner_user_id: str | None
    challenge_id: str | None
    audience: str | None
    processing_started_at: datetime | None
    reconciliation_attempts: int
    last_reconciled_at: datetime | None

    @classmethod
    def from_domain(
        cls,
        presentation: PersistedPresentation,
    ) -> "PresentationMetadataResponse":
        return cls(
            presentation_id=presentation.presentation_id,
            holder_did=presentation.holder_did,
            challenge=presentation.challenge,
            domain=presentation.domain,
            credential_ids=list(presentation.credential_ids),
            verification_result=presentation.verification_result.value,
            created_at=presentation.created_at,
            expires_at=presentation.expires_at,
            verified_at=presentation.verified_at,
            rejection_codes=list(presentation.rejection_codes),
            version=presentation.version,
            wallet_id=presentation.wallet_id,
            owner_user_id=presentation.owner_user_id,
            challenge_id=presentation.challenge_id,
            audience=presentation.audience,
            processing_started_at=presentation.processing_started_at,
            reconciliation_attempts=presentation.reconciliation_attempts,
            last_reconciled_at=presentation.last_reconciled_at,
        )


class PresentationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    presentation: dict[str, JsonValue]
    metadata: PresentationMetadataResponse

    @classmethod
    def from_domain(
        cls,
        presentation: PersistedPresentation,
    ) -> "PresentationResponse":
        return cls(
            presentation=dict(presentation.document),
            metadata=PresentationMetadataResponse.from_domain(
                presentation
            ),
        )


class PresentationVerificationResponse(ApiModel):
    valid: bool
    presentation_id: str | None
    holder_did: str | None
    credential_ids: list[str]
    verified_at: datetime
    errors: list[str]

    @classmethod
    def from_domain(
        cls,
        result: PresentationValidationResult,
    ) -> "PresentationVerificationResponse":
        return cls(
            valid=result.valid,
            presentation_id=result.presentation_id,
            holder_did=result.holder_did,
            credential_ids=list(result.credential_ids),
            verified_at=result.verified_at,
            errors=list(result.errors),
        )
