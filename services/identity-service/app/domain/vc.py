from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class VerificationCheckName(StrEnum):
    DOCUMENT_STRUCTURE = "documentStructure"
    CONTEXT_AND_TYPE = "contextAndType"
    ISSUER_DID_RESOLUTION = "issuerDidResolution"
    VERIFICATION_METHOD_AUTHORIZATION = "verificationMethodAuthorization"
    PROOF_CRYPTOSUITE = "proofCryptosuite"
    PROOF_PURPOSE = "proofPurpose"
    PROOF_TIMESTAMP = "proofTimestamp"
    SIGNATURE = "signature"
    CONTENT_INTEGRITY = "contentIntegrity"
    VALIDITY_WINDOW = "validityWindow"
    CREDENTIAL_STATUS = "credentialStatus"
    ISSUER_TRUST = "issuerTrust"


class VerificationCheckStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_CHECKED = "notChecked"
    NOT_APPLICABLE = "notApplicable"


class VerificationReasonCode(StrEnum):
    CREDENTIAL_TOO_LARGE = "CREDENTIAL_TOO_LARGE"
    DUPLICATE_JSON_PROPERTY = "DUPLICATE_JSON_PROPERTY"
    DOCUMENT_INVALID = "DOCUMENT_INVALID"
    PRIVATE_KEY_MATERIAL = "PRIVATE_KEY_MATERIAL"
    UNSUPPORTED_CONTEXT = "UNSUPPORTED_CONTEXT"
    UNSUPPORTED_TYPE = "UNSUPPORTED_TYPE"
    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"
    INVALID_IDENTIFIER = "INVALID_IDENTIFIER"
    INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
    INVALID_VALIDITY_WINDOW = "INVALID_VALIDITY_WINDOW"
    MISSING_PROOF = "MISSING_PROOF"
    UNSUPPORTED_PROOF_TYPE = "UNSUPPORTED_PROOF_TYPE"
    UNSUPPORTED_CRYPTOSUITE = "UNSUPPORTED_CRYPTOSUITE"
    INVALID_PROOF_PURPOSE = "INVALID_PROOF_PURPOSE"
    INVALID_VERIFICATION_METHOD = "INVALID_VERIFICATION_METHOD"
    INVALID_PROOF_VALUE = "INVALID_PROOF_VALUE"
    PROOF_TIMESTAMP_INVALID = "PROOF_TIMESTAMP_INVALID"
    CANONICALIZATION_FAILED = "CANONICALIZATION_FAILED"
    ISSUER_RESOLUTION_FAILED = "ISSUER_RESOLUTION_FAILED"
    VERIFICATION_METHOD_NOT_AUTHORIZED = "VERIFICATION_METHOD_NOT_AUTHORIZED"
    PUBLIC_KEY_MISMATCH = "PUBLIC_KEY_MISMATCH"
    SIGNATURE_MALFORMED = "SIGNATURE_MALFORMED"
    SIGNATURE_INVALID = "SIGNATURE_INVALID"
    CREDENTIAL_NOT_YET_VALID = "CREDENTIAL_NOT_YET_VALID"
    CREDENTIAL_EXPIRED = "CREDENTIAL_EXPIRED"
    CREDENTIAL_STATUS_FAILED = "CREDENTIAL_STATUS_FAILED"
    INVALID_CREDENTIAL_STATUS = "INVALID_CREDENTIAL_STATUS"
    ISSUER_NOT_TRUSTED = "ISSUER_NOT_TRUSTED"
    CHECK_NOT_PERFORMED = "CHECK_NOT_PERFORMED"


class CredentialValidationError(Exception):
    def __init__(
        self,
        code: VerificationReasonCode,
        message: str,
    ) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class VerificationCheck:
    name: VerificationCheckName
    status: VerificationCheckStatus
    reason_code: VerificationReasonCode | None = None

    def __post_init__(self) -> None:
        if (
            self.status is VerificationCheckStatus.FAILED
            and self.reason_code is None
        ):
            raise ValueError("A failed verification check requires a reason code.")
        if (
            self.status
            in {
                VerificationCheckStatus.PASSED,
                VerificationCheckStatus.NOT_APPLICABLE,
            }
            and self.reason_code is not None
        ):
            raise ValueError(
                "Passed and not-applicable checks cannot carry a reason code."
            )


@dataclass(frozen=True)
class CredentialVerificationResult:
    verified_at: datetime
    checks: tuple[VerificationCheck, ...]

    def __post_init__(self) -> None:
        if (
            self.verified_at.tzinfo is None
            or self.verified_at.utcoffset() is None
        ):
            raise ValueError("verified_at must be timezone-aware.")

        check_names = [check.name for check in self.checks]
        if len(check_names) != len(set(check_names)):
            raise ValueError("Verification checks must be unique.")
        if set(check_names) != set(VerificationCheckName):
            raise ValueError("Every verification check must be present exactly once.")

    @property
    def verified(self) -> bool:
        by_name = {check.name: check.status for check in self.checks}
        required = set(VerificationCheckName) - {
            VerificationCheckName.CREDENTIAL_STATUS
        }
        required_passed = all(
            by_name[name] is VerificationCheckStatus.PASSED
            for name in required
        )
        status_accepted = by_name[
            VerificationCheckName.CREDENTIAL_STATUS
        ] in {
            VerificationCheckStatus.PASSED,
            VerificationCheckStatus.NOT_APPLICABLE,
        }
        return required_passed and status_accepted

    @property
    def reason_codes(self) -> tuple[VerificationReasonCode, ...]:
        return tuple(
            dict.fromkeys(
                check.reason_code
                for check in self.checks
                if check.reason_code is not None
            )
        )

    def to_dict(self) -> dict[str, object]:
        checks_by_name = {
            check.name.value: {
                "status": check.status.value,
                "reasonCode": (
                    check.reason_code.value
                    if check.reason_code is not None
                    else None
                ),
            }
            for check in self.checks
        }
        verified_at = self.verified_at.astimezone(UTC).isoformat().replace(
            "+00:00",
            "Z",
        )
        return {
            "verified": self.verified,
            "verifiedAt": verified_at,
            "checks": checks_by_name,
            "reasonCodes": [code.value for code in self.reason_codes],
        }
