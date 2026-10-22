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

        self._verify_data_integrity_signature(
            document=validated,
            issuer=validated["issuer"],
            proof=validated["proof"],
            checks=checks,
            require_local_issuer_trust=True,
        )
        return checks.build(checked_at)

    def verify_data_integrity_document(
        self,
        secured_document: Mapping[str, Any],
        *,
        verified_at: datetime | None = None,
    ) -> tuple[bool, str | None]:
        """Verify this project's Data Integrity proof profile on another VC type.

        Credential-specific trust is intentionally left to the consuming policy,
        which evaluates the issuer through the Trust Registry.
        """
        checked_at = verified_at or self.clock()
        if checked_at.tzinfo is None or checked_at.utcoffset() is None:
            return False, "VERIFICATION_TIME_INVALID"
        try:
            document = copy.deepcopy(dict(secured_document))
        except (TypeError, ValueError):
            return False, "DOCUMENT_MALFORMED"

        context = document.get("@context")
        types = document.get("type")
        issuer = document.get("issuer")
        proof = document.get("proof")
        if (
            not isinstance(context, list)
            or "https://www.w3.org/ns/credentials/v2" not in context
            or not isinstance(types, list)
            or "VerifiableCredential" not in types
            or not isinstance(issuer, str)
            or not issuer.strip()
            or not isinstance(proof, Mapping)
        ):
            return False, "DOCUMENT_PROFILE_INVALID"

        proof = dict(proof)
        if proof.get("type") != DATA_INTEGRITY_PROOF_TYPE:
            return False, "UNSUPPORTED_PROOF_TYPE"
        if proof.get("cryptosuite") != CRYPTOSUITE:
            return False, "UNSUPPORTED_CRYPTOSUITE"
        if proof.get("proofPurpose") != PROOF_PURPOSE:
            return False, "INVALID_PROOF_PURPOSE"
        try:
            self.validator._parse_timestamp(proof.get("created"))
        except Exception:
            return False, "PROOF_TIMESTAMP_INVALID"
        verification_method = proof.get("verificationMethod")
        if (
            not isinstance(verification_method, str)
            or len(verification_method) > 768
            or not verification_method.startswith(f"{issuer}#")
        ):
            return False, "INVALID_VERIFICATION_METHOD"
        proof_value = proof.get("proofValue")
        if (
            not isinstance(proof_value, str)
            or not proof_value.startswith("z")
            or len(proof_value) > 128
        ):
            return False, "INVALID_PROOF_VALUE"

        checks = _VerificationChecks()
        try:
            verified = self._verify_data_integrity_signature(
                document=document,
                issuer=issuer,
                proof=proof,
                checks=checks,
                require_local_issuer_trust=False,
            )
        except Exception:
            return False, "PROOF_VERIFICATION_ERROR"
        if verified:
            return True, None
        failed = next(
            (
                check
                for check in checks.build(checked_at.astimezone(UTC)).checks
                if check.status is VerificationCheckStatus.FAILED
            ),
            None,
        )
        if failed is None:
            return False, "PROOF_VERIFICATION_FAILED"
        return False, (
            f"{failed.name.value}:{failed.reason_code.value}"
        )

    def _verify_data_integrity_signature(
        self,
        *,
        document: Mapping[str, Any],
        issuer: str,
        proof: Mapping[str, Any],
        checks: _VerificationChecks,
        require_local_issuer_trust: bool,
    ) -> bool:
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
            if require_local_issuer_trust:
                checks.failed(
                    VerificationCheckName.ISSUER_TRUST,
                    VerificationReasonCode.ISSUER_NOT_TRUSTED,
                )
            return False
        except (KeyMaterialError, UnknownVerificationMethodError):
            checks.passed(VerificationCheckName.ISSUER_DID_RESOLUTION)
            checks.failed(
                VerificationCheckName.VERIFICATION_METHOD_AUTHORIZATION,
                VerificationReasonCode.VERIFICATION_METHOD_NOT_AUTHORIZED,
            )
            return False
        except Exception:
            checks.failed(
                VerificationCheckName.ISSUER_DID_RESOLUTION,
                VerificationReasonCode.ISSUER_RESOLUTION_FAILED,
            )
            if require_local_issuer_trust:
                checks.failed(
                    VerificationCheckName.ISSUER_TRUST,
                    VerificationReasonCode.ISSUER_NOT_TRUSTED,
                )
            return False

        checks.passed(VerificationCheckName.ISSUER_DID_RESOLUTION)
        checks.passed(
            VerificationCheckName.VERIFICATION_METHOD_AUTHORIZATION
        )

        if require_local_issuer_trust:
            try:
                if not self.key_provider.supports_issuer(issuer):
                    checks.failed(
                        VerificationCheckName.ISSUER_TRUST,
                        VerificationReasonCode.ISSUER_NOT_TRUSTED,
                    )
                    return False
                trusted_key = self.key_provider.get_verification_key(
                    verification_method
                )
            except Exception:
                checks.failed(
                    VerificationCheckName.ISSUER_TRUST,
                    VerificationReasonCode.ISSUER_NOT_TRUSTED,
                )
                return False
            if trusted_key != resolved_key:
                checks.failed(
                    VerificationCheckName.VERIFICATION_METHOD_AUTHORIZATION,
                    VerificationReasonCode.PUBLIC_KEY_MISMATCH,
                )
                checks.failed(
                    VerificationCheckName.ISSUER_TRUST,
                    VerificationReasonCode.ISSUER_NOT_TRUSTED,
                )
                return False
            checks.passed(VerificationCheckName.ISSUER_TRUST)

        try:
            signature = decode_base58_btc(proof["proofValue"])
        except (KeyError, TypeError, ValueError):
            checks.failed(
                VerificationCheckName.SIGNATURE,
                VerificationReasonCode.SIGNATURE_MALFORMED,
            )
            checks.failed(
                VerificationCheckName.CONTENT_INTEGRITY,
                VerificationReasonCode.SIGNATURE_MALFORMED,
            )
            return False

        proof_configuration = copy.deepcopy(dict(proof))
        proof_configuration.pop("proofValue", None)
        unsecured = copy.deepcopy(dict(document))
        unsecured.pop("proof", None)
        try:
            signing_input = self.canonicalizer.create_signing_input(
                unsecured,
                proof_configuration,
            )
        except Exception:
            checks.failed(
                VerificationCheckName.DOCUMENT_STRUCTURE,
                VerificationReasonCode.CANONICALIZATION_FAILED,
            )
            checks.failed(
                VerificationCheckName.CONTENT_INTEGRITY,
                VerificationReasonCode.CANONICALIZATION_FAILED,
            )
            return False

        try:
            signature_valid = self.signer.verify(
                signing_input,
                signature,
                resolved_key,
            )
        except Exception:
            signature_valid = False
        if not signature_valid:
            reason = (
                VerificationReasonCode.SIGNATURE_MALFORMED
                if len(signature) != 64
                else VerificationReasonCode.SIGNATURE_INVALID
            )
            checks.failed(VerificationCheckName.SIGNATURE, reason)
            checks.failed(VerificationCheckName.CONTENT_INTEGRITY, reason)
            return False

        checks.passed(VerificationCheckName.SIGNATURE)
        checks.passed(VerificationCheckName.CONTENT_INTEGRITY)
        return True

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
