import copy
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from app.application.ports.canonicalizer import CredentialCanonicalizer
from app.application.ports.credential_signer import CredentialSigner
from app.application.ports.key_provider import KeyProvider
from app.domain.crypto import VerificationKey
from app.domain.did import DidResolutionError
from app.domain.exceptions import (
    CanonicalizationError,
    ExistingProofError,
    InvalidSigningTimeError,
    KeyMaterialError,
    UnknownVerificationMethodError,
)
from app.domain.vc import (
    CredentialValidationError,
    CredentialVerificationResult,
    VerificationCheck,
    VerificationCheckName,
    VerificationCheckStatus,
    VerificationReasonCode,
)
from app.infrastructure.crypto.multibase import (
    decode_base58_btc,
    encode_base58_btc,
)
from app.services.credential_validator import CredentialProfileValidator
from app.services.did_resolver import DidResolver


DATA_INTEGRITY_PROOF_TYPE = "DataIntegrityProof"
CRYPTOSUITE = "eddsa-jcs-2022"
PROOF_PURPOSE = "assertionMethod"
ED25519_MULTICODEC_PREFIX = b"\xed\x01"


class _VerificationChecks:
    def __init__(self) -> None:
        self._checks = {
            name: VerificationCheck(
                name=name,
                status=(
                    VerificationCheckStatus.NOT_APPLICABLE
                    if name is VerificationCheckName.CREDENTIAL_STATUS
                    else VerificationCheckStatus.NOT_CHECKED
                ),
            )
            for name in VerificationCheckName
        }

    def passed(self, name: VerificationCheckName) -> None:
        self._checks[name] = VerificationCheck(
            name=name,
            status=VerificationCheckStatus.PASSED,
        )

    def failed(
        self,
        name: VerificationCheckName,
        reason_code: VerificationReasonCode,
    ) -> None:
        self._checks[name] = VerificationCheck(
            name=name,
            status=VerificationCheckStatus.FAILED,
            reason_code=reason_code,
        )

    def build(self, verified_at: datetime) -> CredentialVerificationResult:
        return CredentialVerificationResult(
            verified_at=verified_at,
            checks=tuple(
                self._checks[name] for name in VerificationCheckName
            ),
        )


class CredentialProofService:
    def __init__(
        self,
        *,
        validator: CredentialProfileValidator,
        canonicalizer: CredentialCanonicalizer,
        signer: CredentialSigner,
        key_provider: KeyProvider,
        did_resolver: DidResolver,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.validator = validator
        self.canonicalizer = canonicalizer
        self.signer = signer
        self.key_provider = key_provider
        self.did_resolver = did_resolver
        self.clock = clock or (lambda: datetime.now(UTC))

    def sign_credential(
        self,
        unsigned_credential: Mapping[str, Any],
        *,
        created: datetime | None = None,
    ) -> dict[str, Any]:
        credential = copy.deepcopy(dict(unsigned_credential))
        if "proof" in credential:
            raise ExistingProofError(
                "The credential already contains a proof and cannot be re-signed."
            )

        validated = self.validator.validate(credential, require_proof=False)
        issuer = validated["issuer"]
        signing_key = self.key_provider.get_signing_key(issuer)
        verification_method = signing_key.verification_method

        resolved_key = self._resolve_verification_key(
            issuer,
            verification_method,
        )
        local_key = self.key_provider.get_verification_key(
            verification_method
        )
        if resolved_key != local_key:
            raise KeyMaterialError(
                "The local signing key does not match the issuer DID document."
            )

        created_at = created or self.clock()
        proof = {
            "@context": copy.deepcopy(validated["@context"]),
            "type": DATA_INTEGRITY_PROOF_TYPE,
            "cryptosuite": CRYPTOSUITE,
            "created": self._format_utc_timestamp(created_at),
            "verificationMethod": verification_method,
            "proofPurpose": PROOF_PURPOSE,
        }
        signing_input = self.canonicalizer.create_signing_input(
            validated,
            proof,
        )
        signature = self.signer.sign(signing_input, signing_key)
        proof["proofValue"] = encode_base58_btc(signature)

        secured = copy.deepcopy(validated)
        secured["proof"] = proof
        return self.validator.validate(secured, require_proof=True)

    def verify_credential(
        self,
        secured_credential: Mapping[str, Any],
        *,
        verified_at: datetime | None = None,
    ) -> CredentialVerificationResult:
        checked_at = verified_at or self.clock()
        if checked_at.tzinfo is None or checked_at.utcoffset() is None:
            raise InvalidSigningTimeError(
                "Verification time must be timezone-aware."
            )
        checked_at = checked_at.astimezone(UTC)
        checks = _VerificationChecks()
        credential = copy.deepcopy(dict(secured_credential))

        try:
            validated = self.validator.validate(
                credential,
                require_proof=True,
            )
        except CredentialValidationError as error:
            self._record_profile_failure(checks, error.code)
            return checks.build(checked_at)

        checks.passed(VerificationCheckName.DOCUMENT_STRUCTURE)
        checks.passed(VerificationCheckName.CONTEXT_AND_TYPE)
        checks.passed(VerificationCheckName.PROOF_CRYPTOSUITE)
        checks.passed(VerificationCheckName.PROOF_PURPOSE)
        checks.passed(VerificationCheckName.PROOF_TIMESTAMP)

        if not self._check_validity_window(validated, checked_at, checks):
            return checks.build(checked_at)

        issuer = validated["issuer"]
        proof = validated["proof"]
        verification_method = proof["verificationMethod"]
        try:
            resolved_key = self._resolve_verification_key(
                issuer,
                verification_method,
            )
        except DidResolutionError:
            checks.failed(
                VerificationCheckName.ISSUER_DID_RESOLUTION,
                VerificationReasonCode.ISSUER_RESOLUTION_FAILED,
            )
            checks.failed(
                VerificationCheckName.ISSUER_TRUST,
                VerificationReasonCode.ISSUER_NOT_TRUSTED,
            )
            return checks.build(checked_at)
        except (KeyMaterialError, UnknownVerificationMethodError):
            checks.passed(VerificationCheckName.ISSUER_DID_RESOLUTION)
            checks.failed(
                VerificationCheckName.VERIFICATION_METHOD_AUTHORIZATION,
                VerificationReasonCode.VERIFICATION_METHOD_NOT_AUTHORIZED,
            )
            return checks.build(checked_at)

        checks.passed(VerificationCheckName.ISSUER_DID_RESOLUTION)
        checks.passed(
            VerificationCheckName.VERIFICATION_METHOD_AUTHORIZATION
        )

        if not self.key_provider.supports_issuer(issuer):
            checks.failed(
                VerificationCheckName.ISSUER_TRUST,
                VerificationReasonCode.ISSUER_NOT_TRUSTED,
            )
            return checks.build(checked_at)
        try:
            trusted_key = self.key_provider.get_verification_key(
                verification_method
            )
        except UnknownVerificationMethodError:
            checks.failed(
                VerificationCheckName.ISSUER_TRUST,
                VerificationReasonCode.ISSUER_NOT_TRUSTED,
            )
            return checks.build(checked_at)
        if trusted_key != resolved_key:
            checks.failed(
                VerificationCheckName.VERIFICATION_METHOD_AUTHORIZATION,
                VerificationReasonCode.PUBLIC_KEY_MISMATCH,
            )
            checks.failed(
                VerificationCheckName.ISSUER_TRUST,
                VerificationReasonCode.ISSUER_NOT_TRUSTED,
            )
            return checks.build(checked_at)
        checks.passed(VerificationCheckName.ISSUER_TRUST)

        try:
            signature = decode_base58_btc(proof["proofValue"])
        except ValueError:
            checks.failed(
                VerificationCheckName.SIGNATURE,
                VerificationReasonCode.SIGNATURE_MALFORMED,
            )
            checks.failed(
                VerificationCheckName.CONTENT_INTEGRITY,
                VerificationReasonCode.SIGNATURE_MALFORMED,
            )
            return checks.build(checked_at)

        proof_configuration = copy.deepcopy(proof)
        proof_configuration.pop("proofValue")
        unsecured = copy.deepcopy(validated)
        unsecured.pop("proof")
        try:
            signing_input = self.canonicalizer.create_signing_input(
                unsecured,
                proof_configuration,
            )
        except CanonicalizationError:
            checks.failed(
                VerificationCheckName.DOCUMENT_STRUCTURE,
                VerificationReasonCode.CANONICALIZATION_FAILED,
            )
            checks.failed(
                VerificationCheckName.CONTENT_INTEGRITY,
                VerificationReasonCode.CANONICALIZATION_FAILED,
            )
            return checks.build(checked_at)

        if not self.signer.verify(signing_input, signature, resolved_key):
            reason = (
                VerificationReasonCode.SIGNATURE_MALFORMED
                if len(signature) != 64
                else VerificationReasonCode.SIGNATURE_INVALID
            )
            checks.failed(VerificationCheckName.SIGNATURE, reason)
            checks.failed(VerificationCheckName.CONTENT_INTEGRITY, reason)
            return checks.build(checked_at)

        checks.passed(VerificationCheckName.SIGNATURE)
        checks.passed(VerificationCheckName.CONTENT_INTEGRITY)
        return checks.build(checked_at)

    def _resolve_verification_key(
        self,
        issuer: str,
        verification_method: str,
    ) -> VerificationKey:
        resolution = self.did_resolver.resolve(issuer)
        document = resolution.did_document
        assertions = document.get("assertionMethod")
        if (
            not isinstance(assertions, list)
            or verification_method not in assertions
        ):
            raise UnknownVerificationMethodError(
                "The verification method is not authorized for assertions."
            )

        methods = document.get("verificationMethod")
        if not isinstance(methods, list):
            raise KeyMaterialError(
                "The issuer DID document has no verification methods."
            )
        method = next(
            (
                item
                for item in methods
                if isinstance(item, dict)
                and item.get("id") == verification_method
            ),
            None,
        )
        if (
            method is None
            or method.get("controller") != issuer
            or method.get("type") != "Multikey"
        ):
            raise UnknownVerificationMethodError(
                "The verification method is not controlled by the issuer."
            )

        try:
            multikey = decode_base58_btc(method["publicKeyMultibase"])
        except (KeyError, TypeError, ValueError) as error:
            raise KeyMaterialError(
                "The issuer public key is malformed."
            ) from error
        if (
            not multikey.startswith(ED25519_MULTICODEC_PREFIX)
            or len(multikey) != len(ED25519_MULTICODEC_PREFIX) + 32
        ):
            raise KeyMaterialError(
                "The issuer verification method is not an Ed25519 Multikey."
            )
        return VerificationKey(
            verification_method=verification_method,
            controller=issuer,
            key_type="Multikey",
            public_key_bytes=multikey[len(ED25519_MULTICODEC_PREFIX) :],
        )

    @staticmethod
    def _format_utc_timestamp(value: datetime) -> str:
        if value.tzinfo is None or value.utcoffset() is None:
            raise InvalidSigningTimeError(
                "Proof creation time must be timezone-aware."
            )
        return (
            value.astimezone(UTC)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )

    @staticmethod
    def _check_validity_window(
        credential: Mapping[str, Any],
        checked_at: datetime,
        checks: _VerificationChecks,
    ) -> bool:
        valid_from = datetime.fromisoformat(
            credential["validFrom"].replace("Z", "+00:00")
        )
        valid_until = datetime.fromisoformat(
            credential["validUntil"].replace("Z", "+00:00")
        )
        if checked_at < valid_from:
            checks.failed(
                VerificationCheckName.VALIDITY_WINDOW,
                VerificationReasonCode.CREDENTIAL_NOT_YET_VALID,
            )
            return False
        if checked_at > valid_until:
            checks.failed(
                VerificationCheckName.VALIDITY_WINDOW,
                VerificationReasonCode.CREDENTIAL_EXPIRED,
            )
            return False
        checks.passed(VerificationCheckName.VALIDITY_WINDOW)
        return True

    @staticmethod
    def _record_profile_failure(
        checks: _VerificationChecks,
        code: VerificationReasonCode,
    ) -> None:
        if code is VerificationReasonCode.UNSUPPORTED_CONTEXT:
            checks.failed(VerificationCheckName.CONTEXT_AND_TYPE, code)
        elif code is VerificationReasonCode.UNSUPPORTED_TYPE:
            checks.failed(VerificationCheckName.CONTEXT_AND_TYPE, code)
        elif code in {
            VerificationReasonCode.UNSUPPORTED_PROOF_TYPE,
            VerificationReasonCode.UNSUPPORTED_CRYPTOSUITE,
        }:
            checks.failed(VerificationCheckName.PROOF_CRYPTOSUITE, code)
        elif code is VerificationReasonCode.INVALID_PROOF_PURPOSE:
            checks.failed(VerificationCheckName.PROOF_PURPOSE, code)
        elif code is VerificationReasonCode.INVALID_VERIFICATION_METHOD:
            checks.failed(
                VerificationCheckName.VERIFICATION_METHOD_AUTHORIZATION,
                code,
            )
        elif code is VerificationReasonCode.INVALID_PROOF_VALUE:
            checks.failed(VerificationCheckName.SIGNATURE, code)
        elif code is VerificationReasonCode.INVALID_VALIDITY_WINDOW:
            checks.failed(VerificationCheckName.VALIDITY_WINDOW, code)
        elif code is VerificationReasonCode.PROOF_TIMESTAMP_INVALID:
            checks.failed(VerificationCheckName.PROOF_TIMESTAMP, code)
        elif code is VerificationReasonCode.INVALID_TIMESTAMP:
            checks.failed(VerificationCheckName.VALIDITY_WINDOW, code)
        else:
            checks.failed(VerificationCheckName.DOCUMENT_STRUCTURE, code)
