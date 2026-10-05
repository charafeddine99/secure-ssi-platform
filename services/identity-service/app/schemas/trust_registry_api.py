from __future__ import annotations

from typing import Any
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class TrustRegistryApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )


class TrustRecordResponse(TrustRegistryApiModel):
    id: str
    issuer_did: str = Field(validation_alias=AliasChoices("issuer_did", "issuerDid"))
    organization_name: str = Field(validation_alias=AliasChoices("organization_name", "organizationName"))
    trust_status: str = Field(validation_alias=AliasChoices("trust_status", "trustStatus"))
    roles: list[str] = Field(default_factory=lambda: ["issuer"])
    permitted_credential_types: list[str] = Field(
        default_factory=lambda: ["VerifiableCredential"],
        validation_alias=AliasChoices("permitted_credential_types", "permittedCredentialTypes"),
    )
    valid_from: str = Field(validation_alias=AliasChoices("valid_from", "validFrom"))
    valid_until: str | None = Field(default=None, validation_alias=AliasChoices("valid_until", "validUntil"))
    trust_source: str = Field(
        default="LOCAL_TRUST_REGISTRY",
        validation_alias=AliasChoices("trust_source", "trustSource"),
    )
    trust_anchor: str | None = Field(default=None, validation_alias=AliasChoices("trust_anchor", "trustAnchor"))
    created_at: str = Field(validation_alias=AliasChoices("created_at", "createdAt"))
    updated_at: str = Field(validation_alias=AliasChoices("updated_at", "updatedAt"))
    created_by: str = Field(
        default="admin@platform.local",
        validation_alias=AliasChoices("created_by", "createdBy"),
    )
    audit_metadata: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("audit_metadata", "auditMetadata"),
    )
    version: int = 1


class RegisterTrustedIssuerRequest(TrustRegistryApiModel):
    issuer_did: str = Field(validation_alias=AliasChoices("issuer_did", "issuerDid"))
    organization_name: str = Field(validation_alias=AliasChoices("organization_name", "organizationName"))
    roles: list[str] = Field(default_factory=lambda: ["issuer"])
    permitted_credential_types: list[str] = Field(
        default_factory=lambda: ["VerifiableCredential"],
        validation_alias=AliasChoices("permitted_credential_types", "permittedCredentialTypes"),
    )
    valid_days: int = Field(default=365, ge=1, le=3650, validation_alias=AliasChoices("valid_days", "validDays"))
    trust_source: str = Field(
        default="LOCAL_TRUST_REGISTRY",
        validation_alias=AliasChoices("trust_source", "trustSource"),
    )
    trust_anchor: str | None = Field(default=None, validation_alias=AliasChoices("trust_anchor", "trustAnchor"))
    notes: str | None = None


class UpdateTrustRecordRequest(TrustRegistryApiModel):
    organization_name: str | None = Field(default=None, validation_alias=AliasChoices("organization_name", "organizationName"))
    trust_status: str | None = Field(default=None, validation_alias=AliasChoices("trust_status", "trustStatus"))
    roles: list[str] | None = None
    permitted_credential_types: list[str] | None = Field(
        default=None,
        validation_alias=AliasChoices("permitted_credential_types", "permittedCredentialTypes"),
    )
    valid_days_extended: int | None = Field(
        default=None,
        ge=1,
        le=3650,
        validation_alias=AliasChoices("valid_days_extended", "validDaysExtended"),
    )
    notes: str | None = None


class ReasonRequest(TrustRegistryApiModel):
    reason: str = Field(default="Administrative trust modification")


class TrustEvaluationRequest(TrustRegistryApiModel):
    issuer_did: str = Field(validation_alias=AliasChoices("issuer_did", "issuerDid"))
    credential_types: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("credential_types", "credentialTypes"),
    )


class TrustEvaluationResponse(TrustRegistryApiModel):
    is_trusted: bool = Field(validation_alias=AliasChoices("is_trusted", "isTrusted"))
    issuer_did: str = Field(validation_alias=AliasChoices("issuer_did", "issuerDid"))
    status: str | None = None
    reason: str
    trust_record_id: str | None = Field(default=None, validation_alias=AliasChoices("trust_record_id", "trustRecordId"))
    trust_source: str | None = Field(default=None, validation_alias=AliasChoices("trust_source", "trustSource"))
    matched_types: list[str] = Field(default_factory=list, validation_alias=AliasChoices("matched_types", "matchedTypes"))
