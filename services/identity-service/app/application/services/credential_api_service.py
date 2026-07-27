from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.application.services.credential_proof_service import (
    CredentialProofService,
)
from app.application.services.credential_issuance_service import (
    CredentialIssuanceService,
)
from app.domain.vc import (
    CredentialValidationError,
    CredentialVerificationResult,
    VerificationReasonCode,
)
from app.services.credential_validator import CredentialProfileValidator


@dataclass(frozen=True)
class CredentialProfileChecks:
    json_valid: bool
    profile_valid: bool
    context_valid: bool
    type_valid: bool
    issuer_valid: bool
    subject_valid: bool
    proof_valid: bool


@dataclass(frozen=True)
class CredentialProfileValidationResult:
    valid: bool
    checks: CredentialProfileChecks
    reason_codes: tuple[VerificationReasonCode, ...]


class CredentialApiService:
    """Coordinates the existing credential core without HTTP dependencies."""

    def __init__(
        self,
        *,
        validator: CredentialProfileValidator,
        proof_service: CredentialProofService,
        issuance_service: CredentialIssuanceService | None = None,
    ) -> None:
        self.validator = validator
        self.proof_service = proof_service
        self.issuance_service = issuance_service

    def validate_credential(
        self,
        credential: Mapping[str, Any],
    ) -> CredentialProfileValidationResult:
        try:
            self.validator.validate(credential, require_proof=False)
        except CredentialValidationError as error:
            if error.code is VerificationReasonCode.CREDENTIAL_TOO_LARGE:
                raise
            return CredentialProfileValidationResult(
                valid=False,
                checks=self._failed_profile_checks(error.code),
                reason_codes=(error.code,),
            )

        return CredentialProfileValidationResult(
            valid=True,
            checks=CredentialProfileChecks(
                json_valid=True,
                profile_valid=True,
                context_valid=True,
                type_valid=True,
                issuer_valid=True,
                subject_valid=True,
                proof_valid=True,
            ),
            reason_codes=(),
        )

    def sign_credential(
        self,
        credential: Mapping[str, Any],
    ) -> dict[str, Any]:
        if self.issuance_service is not None:
            return self.issuance_service.issue(credential)
        return self.proof_service.sign_credential(credential)

    def verify_credential(
        self,
        credential: Mapping[str, Any],
    ) -> CredentialVerificationResult:
        try:
            self.validator.validate(credential, require_proof=True)
        except CredentialValidationError as error:
            if error.code is VerificationReasonCode.CREDENTIAL_TOO_LARGE:
                raise
        return self.proof_service.verify_credential(credential)

    @staticmethod
    def _failed_profile_checks(
        code: VerificationReasonCode,
    ) -> CredentialProfileChecks:
        context_valid = code is not VerificationReasonCode.UNSUPPORTED_CONTEXT
        type_valid = code is not VerificationReasonCode.UNSUPPORTED_TYPE
        issuer_valid = code not in {
            VerificationReasonCode.INVALID_IDENTIFIER,
            VerificationReasonCode.ISSUER_RESOLUTION_FAILED,
        }
        subject_valid = code not in {
            VerificationReasonCode.INVALID_IDENTIFIER,
            VerificationReasonCode.UNSUPPORTED_CLAIM,
        }
        proof_valid = code not in {
            VerificationReasonCode.MISSING_PROOF,
            VerificationReasonCode.UNSUPPORTED_PROOF_TYPE,
            VerificationReasonCode.UNSUPPORTED_CRYPTOSUITE,
            VerificationReasonCode.INVALID_PROOF_PURPOSE,
            VerificationReasonCode.INVALID_VERIFICATION_METHOD,
            VerificationReasonCode.INVALID_PROOF_VALUE,
            VerificationReasonCode.PROOF_TIMESTAMP_INVALID,
        }
        return CredentialProfileChecks(
            json_valid=True,
            profile_valid=False,
            context_valid=context_valid,
            type_valid=type_valid,
            issuer_valid=issuer_valid,
            subject_valid=subject_valid,
            proof_valid=proof_valid,
        )
