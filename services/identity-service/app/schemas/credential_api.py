from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
)

from app.application.services.credential_api_service import (
    CredentialProfileValidationResult,
)
from app.domain.credential_status import (
    CredentialStatus,
    CredentialStatusSnapshot,
)
from app.domain.vc import (
    CredentialVerificationResult,
    VerificationCheckName,
    VerificationCheckStatus,
)


def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )


class CredentialEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credential: dict[str, JsonValue]


class CredentialValidationChecksResponse(ApiModel):
    json_valid: bool
    profile_valid: bool
    context_valid: bool
    type_valid: bool
    issuer_valid: bool
    subject_valid: bool
    proof_valid: bool


class CredentialValidationResponse(ApiModel):
    valid: bool
    checks: CredentialValidationChecksResponse
    errors: list[str]
    cryptographic_verification_performed: Literal[False] = False

    @classmethod
    def from_domain(
        cls,
        result: CredentialProfileValidationResult,
    ) -> "CredentialValidationResponse":
        return cls(
            valid=result.valid,
            checks=CredentialValidationChecksResponse(
                **vars(result.checks)
            ),
            errors=[code.value for code in result.reason_codes],
        )


class CredentialSignResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credential: dict[str, JsonValue]


class CredentialRevocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, Field(min_length=1, max_length=500)]

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or any(
            ord(character) < 32 for character in normalized
        ):
            raise ValueError("Revocation reason is invalid.")
        return normalized


class CredentialStatusResponse(ApiModel):
    credential_id: str
    status: CredentialStatus
    revoked: bool
    revocation_reason: str | None
    revoked_at: datetime | None
    revoked_by: str | None

    @classmethod
    def from_domain(
        cls,
        snapshot: CredentialStatusSnapshot,
    ) -> "CredentialStatusResponse":
        return cls(
            credential_id=snapshot.credential_id,
            status=snapshot.status,
            revoked=snapshot.revoked,
            revocation_reason=snapshot.revocation_reason,
            revoked_at=snapshot.revoked_at,
            revoked_by=snapshot.revoked_by,
        )


class CredentialVerificationChecksResponse(ApiModel):
    profile_valid: bool
    issuer_resolved: bool
    verification_method_resolved: bool
    cryptosuite_supported: bool
    proof_purpose_valid: bool
    timestamp_valid: bool
    signature_valid: bool
    content_integrity_valid: bool


class CredentialVerificationResponse(ApiModel):
    valid: bool
    verified_at: str
    checks: CredentialVerificationChecksResponse
    errors: list[str]

    @classmethod
    def from_domain(
        cls,
        result: CredentialVerificationResult,
    ) -> "CredentialVerificationResponse":
        statuses = {
            check.name: check.status for check in result.checks
        }

        def passed(name: VerificationCheckName) -> bool:
            return statuses[name] is VerificationCheckStatus.PASSED

        return cls(
            valid=result.verified,
            verified_at=(
                result.verified_at.isoformat().replace("+00:00", "Z")
            ),
            checks=CredentialVerificationChecksResponse(
                profile_valid=(
                    passed(VerificationCheckName.DOCUMENT_STRUCTURE)
                    and passed(VerificationCheckName.CONTEXT_AND_TYPE)
                ),
                issuer_resolved=passed(
                    VerificationCheckName.ISSUER_DID_RESOLUTION
                ),
                verification_method_resolved=passed(
                    VerificationCheckName.VERIFICATION_METHOD_AUTHORIZATION
                ),
                cryptosuite_supported=passed(
                    VerificationCheckName.PROOF_CRYPTOSUITE
                ),
                proof_purpose_valid=passed(
                    VerificationCheckName.PROOF_PURPOSE
                ),
                timestamp_valid=passed(
                    VerificationCheckName.PROOF_TIMESTAMP
                ),
                signature_valid=passed(VerificationCheckName.SIGNATURE),
                content_integrity_valid=passed(
                    VerificationCheckName.CONTENT_INTEGRITY
                ),
            ),
            errors=[code.value for code in result.reason_codes],
        )


class DidMethodsResponse(ApiModel):
    issuer: list[str]
    holder_fixtures: list[str]


class CredentialOperationsResponse(ApiModel):
    validation_supported: bool = Field(alias="validate")
    sign: bool
    verify: bool
    persist: bool
    revoke: bool
    present: bool


class CredentialCapabilitiesResponse(ApiModel):
    service: str
    api_version: str
    credential_model: str
    proof_type: str
    cryptosuites: list[str]
    did_methods: DidMethodsResponse
    operations: CredentialOperationsResponse
    limitations: list[str]


class ApiErrorDetail(ApiModel):
    code: str
    location: str | None = None


class ApiError(ApiModel):
    code: str
    message: str
    details: list[ApiErrorDetail]


class ApiErrorResponse(ApiModel):
    error: ApiError
    request_id: str
