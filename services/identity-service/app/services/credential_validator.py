import json
import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from app.core.config import MAX_CREDENTIAL_BYTES
from app.domain.vc import CredentialValidationError, VerificationReasonCode


VC_V2_CONTEXT = "https://www.w3.org/ns/credentials/v2"
UNIVERSITY_CONTEXT = (
    "https://secure-ssi.example/contexts/university-affiliation/v1"
)
ALLOWED_CONTEXTS = [VC_V2_CONTEXT, UNIVERSITY_CONTEXT]
ALLOWED_TYPES = [
    "VerifiableCredential",
    "UniversityAffiliationCredential",
]
ALLOWED_AFFILIATIONS = {"student", "faculty", "staff"}
REQUIRED_CREDENTIAL_FIELDS = {
    "@context",
    "id",
    "type",
    "issuer",
    "validFrom",
    "validUntil",
    "credentialSubject",
}
ALLOWED_CREDENTIAL_FIELDS = REQUIRED_CREDENTIAL_FIELDS | {
    "credentialStatus",
    "proof",
}
REQUIRED_SUBJECT_FIELDS = {
    "id",
    "affiliation",
    "programCode",
    "degree",
    "graduationYear",
}
REQUIRED_PROOF_FIELDS = {
    "@context",
    "type",
    "cryptosuite",
    "created",
    "verificationMethod",
    "proofPurpose",
    "proofValue",
}
PRIVATE_KEY_FIELDS = {
    "privateKey",
    "privateKeyJwk",
    "privateKeyMultibase",
    "secretKey",
    "secretKeyJwk",
    "secretKeyMultibase",
}
ISSUER_DID_PATTERN = re.compile(r"^did:web:[A-Za-z0-9._:%-]+$")
SUBJECT_DID_PATTERN = re.compile(r"^did:key:z[1-9A-HJ-NP-Za-km-z]+$")
PROGRAM_CODE_PATTERN = re.compile(r"^SYN-[A-Z0-9-]{2,28}$")
PROOF_VALUE_PATTERN = re.compile(r"^z[1-9A-HJ-NP-Za-km-z]{79,99}$")
UTC_TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z$"
)
STATUS_LIST_ID_PATTERN = re.compile(
    r"^https?://[^?#\s]+/revocation-[0-9a-f]{24}"
    r"(?:-[0-9]{6})?$"
)


class _DuplicatePropertyError(ValueError):
    def __init__(self, property_name: str) -> None:
        super().__init__("JSON object contains a duplicate property.")
        self.property_name = property_name


class CredentialProfileValidator:
    def __init__(self, *, max_credential_bytes: int | None = None) -> None:
        configured_limit = (
            MAX_CREDENTIAL_BYTES
            if max_credential_bytes is None
            else max_credential_bytes
        )
        if configured_limit <= 0:
            raise ValueError("max_credential_bytes must be positive")
        self.max_credential_bytes = configured_limit

    def load_and_validate(
        self,
        raw_credential: str | bytes,
        *,
        require_proof: bool = False,
    ) -> dict[str, Any]:
        raw_bytes = (
            raw_credential.encode("utf-8")
            if isinstance(raw_credential, str)
            else raw_credential
        )
        if len(raw_bytes) > self.max_credential_bytes:
            self._raise(
                VerificationReasonCode.CREDENTIAL_TOO_LARGE,
                "Credential exceeds the configured size limit.",
            )

        try:
            raw_text = raw_bytes.decode("utf-8")
            document = json.loads(
                raw_text,
                object_pairs_hook=self._reject_duplicate_properties,
                parse_constant=self._reject_non_finite_number,
            )
        except _DuplicatePropertyError:
            self._raise(
                VerificationReasonCode.DUPLICATE_JSON_PROPERTY,
                "Credential contains a duplicate JSON property.",
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            self._raise(
                VerificationReasonCode.DOCUMENT_INVALID,
                "Credential must be a valid UTF-8 JSON object.",
            )

        if not isinstance(document, dict):
            self._raise(
                VerificationReasonCode.DOCUMENT_INVALID,
                "Credential must be a JSON object.",
            )
        return self.validate(
            document,
            require_proof=require_proof,
            raw_size=len(raw_bytes),
        )

    def validate(
        self,
        credential: Mapping[str, Any],
        *,
        require_proof: bool = False,
        raw_size: int | None = None,
    ) -> dict[str, Any]:
        normalized = dict(credential)
        try:
            size = raw_size or len(
                json.dumps(
                    normalized,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
            )
        except (TypeError, ValueError):
            self._raise(
                VerificationReasonCode.DOCUMENT_INVALID,
                "Credential must contain only valid JSON values.",
            )
        if size > self.max_credential_bytes:
            self._raise(
                VerificationReasonCode.CREDENTIAL_TOO_LARGE,
                "Credential exceeds the configured size limit.",
            )

        private_field = self._find_private_key_field(normalized)
        if private_field is not None:
            self._raise(
                VerificationReasonCode.PRIVATE_KEY_MATERIAL,
                "Credential contains prohibited private key material.",
            )

        self._validate_top_level_shape(normalized, require_proof=require_proof)
        self._validate_context_and_type(normalized)
        self._validate_identifiers(normalized)
        self._validate_subject(normalized["credentialSubject"])
        credential_status = normalized.get("credentialStatus")
        if credential_status is not None:
            self._validate_credential_status(credential_status)
        valid_from = self._parse_timestamp(normalized["validFrom"])
        valid_until = self._parse_timestamp(normalized["validUntil"])
        if valid_until <= valid_from:
            self._raise(
                VerificationReasonCode.INVALID_VALIDITY_WINDOW,
                "validUntil must be later than validFrom.",
            )

        proof = normalized.get("proof")
        if proof is not None:
            self._validate_proof(
                proof,
                issuer=normalized["issuer"],
                credential_context=normalized["@context"],
            )
        return normalized

    def _validate_top_level_shape(
        self,
        credential: dict[str, Any],
        *,
        require_proof: bool,
    ) -> None:
        fields = set(credential)
        if (
            not REQUIRED_CREDENTIAL_FIELDS.issubset(fields)
            or not fields.issubset(ALLOWED_CREDENTIAL_FIELDS)
        ):
            self._raise(
                VerificationReasonCode.DOCUMENT_INVALID,
                "Credential fields do not match the approved profile.",
            )
        if require_proof and "proof" not in credential:
            self._raise(
                VerificationReasonCode.MISSING_PROOF,
                "A secured credential must contain a proof.",
            )

    def _validate_context_and_type(self, credential: dict[str, Any]) -> None:
        if credential["@context"] != ALLOWED_CONTEXTS:
            self._raise(
                VerificationReasonCode.UNSUPPORTED_CONTEXT,
                "Credential contexts do not match the pinned profile.",
            )
        if credential["type"] != ALLOWED_TYPES:
            self._raise(
                VerificationReasonCode.UNSUPPORTED_TYPE,
                "Credential types do not match the approved profile.",
            )

    def _validate_identifiers(self, credential: dict[str, Any]) -> None:
        credential_id = credential["id"]
        if not isinstance(credential_id, str) or not credential_id.startswith(
            "urn:uuid:"
        ):
            self._raise(
                VerificationReasonCode.INVALID_IDENTIFIER,
                "Credential id must be a canonical UUID URN.",
            )
        try:
            parsed_uuid = UUID(credential_id.removeprefix("urn:uuid:"))
        except (ValueError, AttributeError):
            self._raise(
                VerificationReasonCode.INVALID_IDENTIFIER,
                "Credential id must be a canonical UUID URN.",
            )
        if credential_id != f"urn:uuid:{parsed_uuid}":
            self._raise(
                VerificationReasonCode.INVALID_IDENTIFIER,
                "Credential id must use canonical lowercase UUID syntax.",
            )

        issuer = credential["issuer"]
        if (
            not isinstance(issuer, str)
            or len(issuer) > 512
            or ISSUER_DID_PATTERN.fullmatch(issuer) is None
        ):
            self._raise(
                VerificationReasonCode.INVALID_IDENTIFIER,
                "Issuer must use an approved did:web identifier.",
            )

    def _validate_subject(self, subject: Any) -> None:
        if not isinstance(subject, dict) or set(subject) != REQUIRED_SUBJECT_FIELDS:
            self._raise(
                VerificationReasonCode.UNSUPPORTED_CLAIM,
                "Credential subject claims do not match the allowlist.",
            )
        subject_id = subject.get("id")
        if (
            not isinstance(subject_id, str)
            or len(subject_id) > 512
            or SUBJECT_DID_PATTERN.fullmatch(subject_id) is None
        ):
            self._raise(
                VerificationReasonCode.INVALID_IDENTIFIER,
                "Credential subject must use a synthetic did:key identifier.",
            )
        if subject.get("affiliation") not in ALLOWED_AFFILIATIONS:
            self._raise(
                VerificationReasonCode.UNSUPPORTED_CLAIM,
                "Affiliation value is outside the approved synthetic allowlist.",
            )
        program_code = subject.get("programCode")
        if (
            not isinstance(program_code, str)
            or PROGRAM_CODE_PATTERN.fullmatch(program_code) is None
        ):
            self._raise(
                VerificationReasonCode.UNSUPPORTED_CLAIM,
                "Program code does not match the synthetic fixture profile.",
            )
        degree = subject.get("degree")
        if degree not in {
            "Bachelor of Science",
            "Master of Science",
            "Doctor of Philosophy",
        }:
            self._raise(
                VerificationReasonCode.UNSUPPORTED_CLAIM,
                "Degree value is outside the approved synthetic allowlist.",
            )
        graduation_year = subject.get("graduationYear")
        if (
            not isinstance(graduation_year, int)
            or isinstance(graduation_year, bool)
            or not 2000 <= graduation_year <= 2100
        ):
            self._raise(
                VerificationReasonCode.UNSUPPORTED_CLAIM,
                "Graduation year is outside the synthetic fixture profile.",
            )

    def _validate_proof(
        self,
        proof: Any,
        *,
        issuer: str,
        credential_context: Any,
    ) -> None:
        if not isinstance(proof, dict) or set(proof) != REQUIRED_PROOF_FIELDS:
            self._raise(
                VerificationReasonCode.DOCUMENT_INVALID,
                "Proof fields do not match the approved profile.",
            )
        if proof.get("@context") != credential_context:
            self._raise(
                VerificationReasonCode.UNSUPPORTED_CONTEXT,
                "Proof context must match the pinned credential contexts.",
            )
        if proof.get("type") != "DataIntegrityProof":
            self._raise(
                VerificationReasonCode.UNSUPPORTED_PROOF_TYPE,
                "Only DataIntegrityProof is supported.",
            )
        if proof.get("cryptosuite") != "eddsa-jcs-2022":
            self._raise(
                VerificationReasonCode.UNSUPPORTED_CRYPTOSUITE,
                "Only eddsa-jcs-2022 is supported.",
            )
        try:
            self._parse_timestamp(proof.get("created"))
        except CredentialValidationError as error:
            if error.code is VerificationReasonCode.INVALID_TIMESTAMP:
                self._raise(
                    VerificationReasonCode.PROOF_TIMESTAMP_INVALID,
                    "Proof created must use a valid RFC 3339 UTC timestamp.",
                )
            raise
        verification_method = proof.get("verificationMethod")
        if (
            not isinstance(verification_method, str)
            or len(verification_method) > 768
            or not verification_method.startswith(f"{issuer}#")
        ):
            self._raise(
                VerificationReasonCode.INVALID_VERIFICATION_METHOD,
                "Proof verificationMethod must be an absolute issuer DID URL.",
            )
        if proof.get("proofPurpose") != "assertionMethod":
            self._raise(
                VerificationReasonCode.INVALID_PROOF_PURPOSE,
                "Proof purpose must be assertionMethod.",
            )
        proof_value = proof.get("proofValue")
        if (
            not isinstance(proof_value, str)
            or PROOF_VALUE_PATTERN.fullmatch(proof_value) is None
        ):
            self._raise(
                VerificationReasonCode.INVALID_PROOF_VALUE,
                "Proof value must be a bounded base58-btc multibase value.",
            )

    def _validate_credential_status(self, value: Any) -> None:
        required = {
            "id",
            "type",
            "statusPurpose",
            "statusListIndex",
            "statusListCredential",
        }
        if not isinstance(value, dict) or set(value) != required:
            self._raise(
                VerificationReasonCode.INVALID_CREDENTIAL_STATUS,
                "credentialStatus fields are invalid.",
            )
        if value.get("type") != "BitstringStatusListEntry":
            self._raise(
                VerificationReasonCode.INVALID_CREDENTIAL_STATUS,
                "credentialStatus type is unsupported.",
            )
        if value.get("statusPurpose") != "revocation":
            self._raise(
                VerificationReasonCode.INVALID_CREDENTIAL_STATUS,
                "credentialStatus purpose is unsupported.",
            )
        entry_id = value.get("id")
        if (
            not isinstance(entry_id, str)
            or not entry_id.startswith("urn:uuid:")
        ):
            self._raise(
                VerificationReasonCode.INVALID_CREDENTIAL_STATUS,
                "credentialStatus id is invalid.",
            )
        index = value.get("statusListIndex")
        if (
            not isinstance(index, str)
            or re.fullmatch(r"0|[1-9][0-9]{0,7}", index) is None
            or int(index) >= 16_777_216
        ):
            self._raise(
                VerificationReasonCode.INVALID_CREDENTIAL_STATUS,
                "credentialStatus index is invalid.",
            )
        status_list_credential = value.get("statusListCredential")
        if (
            not isinstance(status_list_credential, str)
            or len(status_list_credential) > 2_048
            or STATUS_LIST_ID_PATTERN.fullmatch(
                status_list_credential
            )
            is None
        ):
            self._raise(
                VerificationReasonCode.INVALID_CREDENTIAL_STATUS,
                "credentialStatus publication URL is invalid.",
            )

    def _parse_timestamp(self, value: Any) -> datetime:
        if (
            not isinstance(value, str)
            or len(value) > 40
            or UTC_TIMESTAMP_PATTERN.fullmatch(value) is None
        ):
            self._raise(
                VerificationReasonCode.INVALID_TIMESTAMP,
                "Timestamps must use an RFC 3339 UTC representation.",
            )
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            self._raise(
                VerificationReasonCode.INVALID_TIMESTAMP,
                "Timestamp is not a valid calendar date.",
            )

    @staticmethod
    def _reject_duplicate_properties(
        pairs: list[tuple[str, Any]],
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise _DuplicatePropertyError(key)
            result[key] = value
        return result

    @staticmethod
    def _reject_non_finite_number(value: str) -> None:
        raise ValueError(f"Non-finite JSON number is not allowed: {value}")

    def _find_private_key_field(self, value: Any) -> str | None:
        if isinstance(value, dict):
            for key, item in value.items():
                if isinstance(key, str) and (
                    key in PRIVATE_KEY_FIELDS
                    or key.lower().startswith(("privatekey", "secretkey"))
                ):
                    return key
                nested = self._find_private_key_field(item)
                if nested:
                    return nested
        elif isinstance(value, list):
            for item in value:
                nested = self._find_private_key_field(item)
                if nested:
                    return nested
        return None

    @staticmethod
    def _raise(
        code: VerificationReasonCode,
        message: str,
    ) -> None:
        raise CredentialValidationError(code, message)
