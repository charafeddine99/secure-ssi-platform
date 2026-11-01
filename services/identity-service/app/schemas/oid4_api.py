from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)

class Oid4ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

# --- OID4VCI Schemas ---

class CreateOfferRequest(Oid4ApiModel):
    credential_configuration_ids: list[str] = Field(default_factory=lambda: ["QualifiedElectronicAttestationCredential"])
    subject_data: dict[str, Any] = Field(default_factory=dict)
    ttl_seconds: int = 1800
    user_pin: str | None = None
    recipient_did: str | None = None

class CredentialOfferResponse(Oid4ApiModel):
    offer_id: str
    credential_issuer: str
    credential_configuration_ids: list[str]
    pre_authorized_code: str
    status: str
    deep_link_uri: str
    qr_payload: str
    expires_at: datetime
    subject_data: dict[str, Any]

class ClaimOfferRequest(Oid4ApiModel):
    pre_authorized_code: str
    holder_did: str
    wallet_id: str = "wallet_holder_default"
    user_pin: str | None = None
    owner_user_id: str | None = None

class ClaimOfferResponse(Oid4ApiModel):
    credential: dict[str, Any]
    credential_id: str
    status: str

class TokenRequestSchema(Oid4ApiModel):
    grant_type: str = Field(
        default="urn:ietf:params:oauth:grant-type:pre-authorized_code",
        validation_alias=AliasChoices("grant_type", "grantType"),
    )
    pre_authorized_code: str = Field(
        ...,
        validation_alias=AliasChoices("pre-authorized_code", "pre_authorized_code", "preAuthorizedCode"),
    )
    user_pin: str | None = Field(
        default=None,
        validation_alias=AliasChoices("user_pin", "tx_code", "userPin"),
    )
    client_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("client_id", "clientId"),
    )

class TokenResponseSchema(Oid4ApiModel):
    access_token: str = Field(..., serialization_alias="access_token")
    token_type: str = Field(default="bearer", serialization_alias="token_type")
    expires_in: int = Field(default=3600, serialization_alias="expires_in")
    c_nonce: str | None = Field(default=None, serialization_alias="c_nonce")
    c_nonce_expires_in: int | None = Field(default=None, serialization_alias="c_nonce_expires_in")
    scope: str | None = None
    authorization_details: list[dict[str, Any]] | None = Field(default=None, serialization_alias="authorization_details")

class NonceResponse(Oid4ApiModel):
    c_nonce: str = Field(..., serialization_alias="c_nonce")
    c_nonce_expires_in: int = Field(default=600, serialization_alias="c_nonce_expires_in")

class HolderProofRequest(Oid4ApiModel):
    wallet_id: str
    audience: str = Field(min_length=1, max_length=2_048)
    nonce: str = Field(min_length=16, max_length=2_048)

class HolderProofResponse(Oid4ApiModel):
    holder_did: str
    proof_type: str = "jwt"
    jwt: str

class HolderProofSchema(Oid4ApiModel):
    proof_type: str = Field(..., validation_alias=AliasChoices("proof_type", "proofType"))
    jwt: str | None = None
    ldp_vp: dict[str, Any] | None = Field(default=None, validation_alias=AliasChoices("ldp_vp", "ldpVp"))

class CredentialRequestSchema(Oid4ApiModel):
    credential_configuration_id: str = Field(
        ...,
        validation_alias=AliasChoices("credential_configuration_id", "credentialConfigurationId", "format"),
    )
    proof: HolderProofSchema | dict[str, Any] | None = None
    wallet_id: str | None = Field(default=None, validation_alias=AliasChoices("wallet_id", "walletId"))
    owner_user_id: str | None = Field(default=None, validation_alias=AliasChoices("owner_user_id", "ownerUserId"))

class CredentialResponseSchema(Oid4ApiModel):
    credential: dict[str, Any]
    c_nonce: str | None = Field(default=None, serialization_alias="c_nonce")
    c_nonce_expires_in: int | None = Field(default=None, serialization_alias="c_nonce_expires_in")
    status: str = "ACTIVE"

# --- OID4VP Schemas ---

class CreateVerificationSessionRequest(Oid4ApiModel):
    purpose: str = "Verification of digital identity and qualifications"
    requested_credential_types: list[str] = Field(
        default_factory=lambda: ["QualifiedElectronicAttestationCredential"],
        min_length=1,
    )
    requested_fields: list[str] = Field(
        default_factory=lambda: ["Sertifika Sahibi", "Unvan", "Yetki Kapsami"]
    )
    ttl_seconds: int = 600
    dcql_query: dict[str, Any] | None = Field(
        default=None,
        description="Optional explicit OpenID4VP 1.0 DCQL query. If omitted, built dynamically.",
    )

class VerificationSessionResponse(Oid4ApiModel):
    session_id: str
    verifier_did: str
    client_id: str
    response_uri: str
    nonce: str
    dcql_query: dict[str, Any] = Field(default_factory=dict, description="Canonical OpenID4VP 1.0 DCQL query")
    presentation_definition: dict[str, Any] = Field(
        default_factory=dict,
        description="Legacy DIF Presentation Exchange v2 compatibility representation",
    )
    status: str
    deep_link_uri: str
    qr_payload: str
    expires_at: datetime
    purpose: str = "Verification of digital identity and qualifications"
    consent_status: str = "PENDING"
    rejection_reason: str | None = None
    requested_fields: list[str] = Field(default_factory=list)
    verification_result: dict[str, Any] | None = None
    disclosed_claims: dict[str, Any] | None = None
    consent_decision: dict[str, Any] | None = None
    approved_credentials: list[str] = Field(default_factory=list)
    approved_claims: dict[str, Any] | None = None
    rejected_claims: list[str] = Field(default_factory=list)


class VerificationSessionListResponse(Oid4ApiModel):
    items: list[VerificationSessionResponse]
    limit: int
    offset: int
    has_more: bool


class HolderOid4vpRequestResponse(Oid4ApiModel):
    """Protocol request context returned to an authenticated Holder wallet."""

    session_id: str
    verifier_did: str
    client_id: str
    response_uri: str
    nonce: str
    dcql_query: dict[str, Any] = Field(default_factory=dict)
    presentation_definition: dict[str, Any] = Field(default_factory=dict)
    status: str
    consent_status: str
    deep_link_uri: str
    qr_payload: str
    expires_at: datetime
    purpose: str
    requested_fields: list[str] = Field(default_factory=list)

class RecordConsentRequest(Oid4ApiModel):
    decision: str = Field(
        default="APPROVE",
        validation_alias=AliasChoices("decision", "action"),
    )
    action: str | None = Field(
        default=None,
        validation_alias=AliasChoices("action", "decision"),
    )
    holder_did: str = Field(
        ...,
        validation_alias=AliasChoices("holder_did", "holderDid"),
    )
    approved_credentials: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("approved_credentials", "approvedCredentials"),
    )
    approved_claims: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("approved_claims", "approvedClaims"),
    )
    rejected_claims: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("rejected_claims", "rejectedClaims"),
    )
    rejection_reason: str | None = Field(
        default=None,
        validation_alias=AliasChoices("rejection_reason", "rejectionReason"),
    )
    verifier_did: str | None = Field(
        default=None,
        validation_alias=AliasChoices("verifier_did", "verifierDid"),
    )
    client_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("client_id", "clientId"),
    )
    nonce: str | None = None
    purpose: str | None = None


class WalletOid4vpConsentRequest(Oid4ApiModel):
    decision: str = Field(
        default="APPROVE",
        validation_alias=AliasChoices("decision", "action"),
    )
    action: str | None = Field(
        default=None,
        validation_alias=AliasChoices("action", "decision"),
    )
    holder_did: str = Field(
        ...,
        validation_alias=AliasChoices("holder_did", "holderDid"),
    )
    approved_credentials: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("approved_credentials", "approvedCredentials"),
    )
    approved_claims: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("approved_claims", "approvedClaims"),
    )
    rejected_claims: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("rejected_claims", "rejectedClaims"),
    )
    rejection_reason: str | None = Field(
        default=None,
        validation_alias=AliasChoices("rejection_reason", "rejectionReason"),
    )
    wallet_id: str = Field(
        ...,
        validation_alias=AliasChoices("wallet_id", "walletId"),
    )

class RecordConsentResponse(Oid4ApiModel):
    session_id: str
    status: str
    consent_status: str
    decision_id: str | None = None
    action: str = "APPROVE"
    decision: str = "APPROVE"
    holder_did: str
    approved_credentials: list[str] = Field(default_factory=list)
    approved_claims: dict[str, Any] = Field(default_factory=dict)
    rejected_claims: list[str] = Field(default_factory=list)
    timestamp: datetime
    rejection_reason: str | None = None

class EvaluateDcqlRequest(Oid4ApiModel):
    candidate_credentials: list[dict[str, Any]] = Field(
        description="Candidate credentials from holder wallet to evaluate against the session's DCQL query"
    )

class EvaluateDcqlResponse(Oid4ApiModel):
    is_satisfied: bool
    matched_credentials: list[dict[str, Any]] = Field(default_factory=list)
    unsatisfied_reason: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class DirectPostRequest(Oid4ApiModel):
    session_id: str
    vp_token: dict[str, Any]
    disclosed_claims: dict[str, Any] | None = None
    ai_risk_score: int | None = Field(
        default=None,
        ge=0,
        le=100,
        deprecated=True,
        description="Ignored for verification decisions; risk scoring is server-owned.",
    )
    client_ip: str | None = None
    user_agent: str | None = None
    device_fingerprint: str | None = None
    device_fingerprint_match: bool = True
    is_tor_or_proxy: bool = False
    failed_attempts: int = 0
    geo_distance_km: float = 0.0
    time_since_last_action_sec: float = 0.0
    presentation_frequency_10m: int = 1

class DirectPostResponse(Oid4ApiModel):
    status: str
    result: dict[str, Any]

class RejectVerificationSessionRequest(Oid4ApiModel):
    reason: str = Field(
        default="Consent rejected by user",
        validation_alias=AliasChoices("reason", "rejectionReason", "rejection_reason"),
    )
    holder_did: str | None = Field(
        default=None,
        validation_alias=AliasChoices("holder_did", "holderDid"),
    )

class RejectVerificationSessionResponse(Oid4ApiModel):
    session_id: str
    status: str
    consent_status: str = "REJECTED"
    reason: str
    rejection_reason: str | None = None

class CreateOid4vpPresentationRequest(Oid4ApiModel):
    session_id: str = Field(
        validation_alias=AliasChoices("session_id", "sessionId"),
    )
    verifiable_credentials: list[dict[str, Any]] = Field(
        default_factory=list,
        validation_alias=AliasChoices("verifiable_credentials", "verifiableCredentials"),
    )
    disclosed_claims: dict[str, Any] | None = Field(
        default=None,
        validation_alias=AliasChoices("disclosed_claims", "disclosedClaims"),
    )
    holder_did: str | None = Field(
        default=None,
        validation_alias=AliasChoices("holder_did", "holderDid"),
    )
    allow_unconsented_test_mode: bool = Field(
        default=False,
        validation_alias=AliasChoices("allow_unconsented_test_mode", "allowUnconsentedTestMode"),
        description="Non-canonical test/fixture bypass. Canonical Golden Path strictly requires recorded consent.",
    )

class CreateOid4vpPresentationResponse(Oid4ApiModel):
    session_id: str
    vp_token: dict[str, Any]


class CreateWalletOid4vpPresentationRequest(Oid4ApiModel):
    session_id: str = Field(
        validation_alias=AliasChoices("session_id", "sessionId"),
    )
    wallet_id: str = Field(
        validation_alias=AliasChoices("wallet_id", "walletId"),
    )
    credential_ids: list[str] = Field(
        min_length=1,
        max_length=8,
        validation_alias=AliasChoices("credential_ids", "credentialIds"),
    )
    disclosed_claims: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("disclosed_claims", "disclosedClaims"),
    )

