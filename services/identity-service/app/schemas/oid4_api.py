from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

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

class ClaimOfferResponse(Oid4ApiModel):
    credential: dict[str, Any]
    credential_id: str
    status: str

# --- OID4VP Schemas ---

class CreateVerificationSessionRequest(Oid4ApiModel):
    purpose: str = "Verification of digital identity and qualifications"
    requested_credential_types: list[str] = Field(
        default_factory=lambda: ["QualifiedElectronicAttestationCredential"]
    )
    requested_fields: list[str] = Field(
        default_factory=lambda: ["Sertifika Sahibi", "Unvan", "Yetki Kapsami"]
    )
    ttl_seconds: int = 600

class VerificationSessionResponse(Oid4ApiModel):
    session_id: str
    verifier_did: str
    client_id: str
    response_uri: str
    nonce: str
    presentation_definition: dict[str, Any]
    status: str
    deep_link_uri: str
    qr_payload: str
    expires_at: datetime
    verification_result: dict[str, Any] | None = None
    disclosed_claims: dict[str, Any] | None = None

class DirectPostRequest(Oid4ApiModel):
    session_id: str
    vp_token: dict[str, Any]
    disclosed_claims: dict[str, Any] | None = None
    ai_risk_score: int = 15

class DirectPostResponse(Oid4ApiModel):
    status: str
    result: dict[str, Any]
