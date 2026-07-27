import copy
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from app.application.ports.canonicalizer import CredentialCanonicalizer
from app.application.ports.credential_signer import CredentialSigner
from app.application.ports.presentation import (
    HolderKeyMetadataProvider,
    HolderKeyProvider,
    HolderSigner,
)
from app.domain.crypto import VerificationKey
from app.domain.presentation import (
    MAX_PRESENTATION_BYTES,
    MAX_PRESENTATION_CREDENTIALS,
    MAX_PRESENTATION_LIFETIME_SECONDS,
    MIN_PRESENTATION_LIFETIME_SECONDS,
    PRESENTATION_PROOF_PURPOSE,
    PRESENTATION_TYPE,
    VC_V2_CONTEXT,
    InvalidPresentationError,
    PresentationValidationResult,
    generate_presentation_id,
    normalize_domain,
    validate_challenge,
    validate_presentation_id,
)
from app.domain.presentation_challenge import normalize_audience
from app.infrastructure.crypto.multibase import decode_base58_btc, encode_base58_btc
from app.services.did_resolver import DidResolver


DATA_INTEGRITY_PROOF_TYPE = "DataIntegrityProof"
CRYPTOSUITE = "eddsa-jcs-2022"
ED25519_MULTICODEC_PREFIX = b"\xed\x01"

_PRESENTATION_FIELDS = {
    "@context",
    "id",
    "type",
    "holder",
    "verifiableCredential",
    "validFrom",
    "validUntil",
    "proof",
}
_PROOF_FIELDS = {
    "@context",
    "type",
    "cryptosuite",
    "created",
    "verificationMethod",
    "proofPurpose",
    "challenge",
    "domain",
    "proofValue",
}
_AUDIENCE_PROOF_FIELDS = _PROOF_FIELDS | {"audience"}


class PresentationBuilder:
    def __init__(
        self,
        *,
        canonicalizer: CredentialCanonicalizer,
        signer: CredentialSigner,
        key_provider: HolderKeyProvider,
        holder_signer: HolderSigner | None = None,
        key_metadata_provider: HolderKeyMetadataProvider | None = None,
    ) -> None:
        self._canonicalizer = canonicalizer
        self._signer = signer
        self._keys = key_provider
        self._holder_signer = holder_signer
        self._key_metadata = key_metadata_provider

    def build(
        self,
        credentials: Sequence[Mapping[str, Any]],
        *,
        holder_did: str,
        challenge: str,
        domain: str,
        created_at: datetime,
        lifetime_seconds: int,
        audience: str | None = None,
        key_reference: str | None = None,
    ) -> dict[str, Any]:
        validate_challenge(challenge)
        normalized_domain = normalize_domain(domain)
        if key_reference is None and not self._keys.supports_holder(holder_did):
            raise InvalidPresentationError(
                "The holder has no local signing capability."
            )
        if key_reference is not None and self._holder_signer is None:
            raise InvalidPresentationError(
                "The configured holder key cannot be used for signing."
            )
        normalized_audience = (
            None if audience is None else normalize_audience(audience)
        )
        if not 1 <= len(credentials) <= MAX_PRESENTATION_CREDENTIALS:
            raise InvalidPresentationError(
                "A presentation must contain between 1 and 8 credentials."
            )
        if not (
            MIN_PRESENTATION_LIFETIME_SECONDS
            <= lifetime_seconds
            <= MAX_PRESENTATION_LIFETIME_SECONDS
        ):
            raise InvalidPresentationError(
                "Presentation lifetime is outside policy."
            )
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise InvalidPresentationError(
                "Presentation creation time must be timezone-aware."
            )
        created_at = created_at.astimezone(UTC).replace(microsecond=0)
        expires_at = created_at + timedelta(seconds=lifetime_seconds)
        if key_reference is None:
            key = self._keys.get_signing_key(holder_did)
            verification_method = key.verification_method
        else:
            metadata_provider = self._key_metadata or self._keys
            metadata = metadata_provider.get_metadata(key_reference)
            if metadata.holder_did != holder_did:
                raise InvalidPresentationError(
                    "The wallet key does not control the holder DID."
                )
            key = None
            verification_method = metadata.verification_method
        context = [VC_V2_CONTEXT]
        presentation: dict[str, Any] = {
            "@context": context,
            "id": generate_presentation_id(),
            "type": [PRESENTATION_TYPE],
            "holder": holder_did,
            "verifiableCredential": [
                copy.deepcopy(dict(credential))
                for credential in credentials
            ],
            "validFrom": _format_timestamp(created_at),
            "validUntil": _format_timestamp(expires_at),
        }
        proof: dict[str, Any] = {
            "@context": context,
            "type": DATA_INTEGRITY_PROOF_TYPE,
            "cryptosuite": CRYPTOSUITE,
            "created": _format_timestamp(created_at),
            "verificationMethod": verification_method,
            "proofPurpose": PRESENTATION_PROOF_PURPOSE,
            "challenge": challenge,
            "domain": normalized_domain,
        }
        if normalized_audience is not None:
            proof["audience"] = normalized_audience
        signing_input = self._canonicalizer.create_signing_input(
            presentation,
            proof,
        )
        signature = (
            self._holder_signer.sign(
                signing_input,
                key_reference=key_reference,
            )
            if key_reference is not None
            else self._signer.sign(signing_input, key)
        )
        proof["proofValue"] = encode_base58_btc(signature)
        presentation["proof"] = proof
        if (
            len(self._canonicalizer.canonicalize_document(presentation))
            > MAX_PRESENTATION_BYTES
        ):
            raise InvalidPresentationError(
                "The generated presentation exceeds the size limit."
            )
        return presentation


class PresentationValidator:
    def __init__(
        self,
        *,
        canonicalizer: CredentialCanonicalizer,
        signer: CredentialSigner,
        key_provider: HolderKeyProvider,
        did_resolver: DidResolver,
    ) -> None:
        self._canonicalizer = canonicalizer
        self._signer = signer
        self._keys = key_provider
        self._did_resolver = did_resolver

    def validate(
        self,
        presentation: Mapping[str, Any],
        *,
        expected_challenge: str,
        expected_domain: str,
        expected_audience: str | None = None,
        verified_at: datetime,
    ) -> PresentationValidationResult:
        errors: list[str] = []
        presentation_id: str | None = None
        holder_did: str | None = None
        credential_ids: tuple[str, ...] = ()
        checked_at = verified_at.astimezone(UTC)
        expected_domain = normalize_domain(expected_domain)
        expected_audience = (
            None
            if expected_audience is None
            else normalize_audience(expected_audience)
        )
        validate_challenge(expected_challenge)

        try:
            if (
                len(self._canonicalizer.canonicalize_document(presentation))
                > MAX_PRESENTATION_BYTES
            ):
                errors.append("PRESENTATION_TOO_LARGE")
                return _result(
                    checked_at,
                    presentation_id,
                    holder_did,
                    credential_ids,
                    errors,
                )
        except Exception:
            errors.append("PRESENTATION_NOT_CANONICALIZABLE")
            return _result(
                checked_at,
                presentation_id,
                holder_did,
                credential_ids,
                errors,
            )

        if set(presentation) != _PRESENTATION_FIELDS:
            errors.append("INVALID_PRESENTATION_STRUCTURE")
        raw_id = presentation.get("id")
        if isinstance(raw_id, str):
            try:
                presentation_id = validate_presentation_id(raw_id)
            except ValueError:
                errors.append("INVALID_PRESENTATION_ID")
        else:
            errors.append("INVALID_PRESENTATION_ID")
        if presentation.get("@context") != [VC_V2_CONTEXT]:
            errors.append("UNSUPPORTED_PRESENTATION_CONTEXT")
        if presentation.get("type") != [PRESENTATION_TYPE]:
            errors.append("UNSUPPORTED_PRESENTATION_TYPE")
        raw_holder = presentation.get("holder")
        if isinstance(raw_holder, str) and raw_holder.startswith("did:key:z"):
            holder_did = raw_holder
        else:
            errors.append("INVALID_HOLDER")

        raw_credentials = presentation.get("verifiableCredential")
        if (
            not isinstance(raw_credentials, list)
            or not 1 <= len(raw_credentials) <= MAX_PRESENTATION_CREDENTIALS
        ):
            errors.append("INVALID_CREDENTIAL_COUNT")
        else:
            ids: list[str] = []
            for credential in raw_credentials:
                if not isinstance(credential, dict):
                    errors.append("INVALID_CREDENTIAL_DOCUMENT")
                    continue
                credential_id = credential.get("id")
                if (
                    not isinstance(credential_id, str)
                    or not credential_id.strip()
                    or len(credential_id) > 2_048
                ):
                    errors.append("INVALID_CREDENTIAL_ID")
                    continue
                ids.append(credential_id)
            if len(ids) != len(set(ids)):
                errors.append("DUPLICATE_CREDENTIAL_ID")
            credential_ids = tuple(ids)

        valid_from = _parse_timestamp(
            presentation.get("validFrom"),
            errors,
            code="INVALID_PRESENTATION_VALID_FROM",
        )
        valid_until = _parse_timestamp(
            presentation.get("validUntil"),
            errors,
            code="INVALID_PRESENTATION_VALID_UNTIL",
        )
        if valid_from is not None and valid_until is not None:
            lifetime = (valid_until - valid_from).total_seconds()
            if not (
                MIN_PRESENTATION_LIFETIME_SECONDS
                <= lifetime
                <= MAX_PRESENTATION_LIFETIME_SECONDS
            ):
                errors.append("INVALID_PRESENTATION_LIFETIME")
            if checked_at < valid_from:
                errors.append("PRESENTATION_NOT_YET_VALID")
            if checked_at > valid_until:
                errors.append("PRESENTATION_EXPIRED")

        proof = presentation.get("proof")
        if not isinstance(proof, dict):
            errors.append("INVALID_PRESENTATION_PROOF")
            return _result(
                checked_at,
                presentation_id,
                holder_did,
                credential_ids,
                errors,
            )
        expected_proof_fields = (
            _PROOF_FIELDS
            if expected_audience is None
            else _AUDIENCE_PROOF_FIELDS
        )
        if set(proof) != expected_proof_fields:
            errors.append("INVALID_PROOF_STRUCTURE")
        if proof.get("@context") != [VC_V2_CONTEXT]:
            errors.append("UNSUPPORTED_PROOF_CONTEXT")
        if (
            proof.get("type") != DATA_INTEGRITY_PROOF_TYPE
            or proof.get("cryptosuite") != CRYPTOSUITE
        ):
            errors.append("UNSUPPORTED_PROOF_SUITE")
        if proof.get("proofPurpose") != PRESENTATION_PROOF_PURPOSE:
            errors.append("INVALID_PROOF_PURPOSE")
        if proof.get("challenge") != expected_challenge:
            errors.append("CHALLENGE_MISMATCH")
        try:
            proof_domain = normalize_domain(proof.get("domain", ""))
        except (TypeError, ValueError):
            proof_domain = None
            errors.append("INVALID_PROOF_DOMAIN")
        if proof_domain is not None and proof_domain != expected_domain:
            errors.append("DOMAIN_MISMATCH")
        if expected_audience is not None:
            try:
                proof_audience = normalize_audience(
                    proof.get("audience", "")
                )
            except (TypeError, ValueError):
                errors.append("INVALID_PROOF_AUDIENCE")
            else:
                if proof_audience != expected_audience:
                    errors.append("AUDIENCE_MISMATCH")
        proof_created = _parse_timestamp(
            proof.get("created"),
            errors,
            code="INVALID_PROOF_TIMESTAMP",
        )
        if (
            proof_created is not None
            and valid_from is not None
            and proof_created != valid_from
        ):
            errors.append("PROOF_TIMESTAMP_MISMATCH")

        verification_method = proof.get("verificationMethod")
        if (
            holder_did is None
            or not isinstance(verification_method, str)
            or not verification_method.startswith(f"{holder_did}#")
        ):
            errors.append("INVALID_HOLDER_VERIFICATION_METHOD")
            return _result(
                checked_at,
                presentation_id,
                holder_did,
                credential_ids,
                errors,
            )
        try:
            resolved_key = self._resolve_authentication_key(
                holder_did,
                verification_method,
            )
            trusted_key = self._keys.get_verification_key(
                verification_method
            )
            if resolved_key != trusted_key:
                errors.append("HOLDER_KEY_MISMATCH")
        except Exception:
            errors.append("HOLDER_RESOLUTION_FAILED")
            return _result(
                checked_at,
                presentation_id,
                holder_did,
                credential_ids,
                errors,
            )

        proof_value = proof.get("proofValue")
        try:
            signature = decode_base58_btc(proof_value)
        except (TypeError, ValueError):
            errors.append("MALFORMED_PRESENTATION_SIGNATURE")
            return _result(
                checked_at,
                presentation_id,
                holder_did,
                credential_ids,
                errors,
            )
        proof_configuration = copy.deepcopy(proof)
        proof_configuration.pop("proofValue", None)
        unsecured = copy.deepcopy(dict(presentation))
        unsecured.pop("proof", None)
        try:
            signing_input = self._canonicalizer.create_signing_input(
                unsecured,
                proof_configuration,
            )
        except Exception:
            errors.append("PRESENTATION_NOT_CANONICALIZABLE")
        else:
            if not self._signer.verify(
                signing_input,
                signature,
                resolved_key,
            ):
                errors.append("INVALID_PRESENTATION_SIGNATURE")
        return _result(
            checked_at,
            presentation_id,
            holder_did,
            credential_ids,
            errors,
        )

    def _resolve_authentication_key(
        self,
        holder_did: str,
        verification_method: str,
    ) -> VerificationKey:
        document = self._did_resolver.resolve(holder_did).did_document
        authentication = document.get("authentication")
        if (
            not isinstance(authentication, list)
            or verification_method not in authentication
        ):
            raise ValueError("Holder key is not authorized for authentication.")
        methods = document.get("verificationMethod")
        method = next(
            (
                item
                for item in methods
                if isinstance(item, dict)
                and item.get("id") == verification_method
            ),
            None,
        ) if isinstance(methods, list) else None
        if (
            method is None
            or method.get("controller") != holder_did
            or method.get("type") != "Multikey"
        ):
            raise ValueError("Holder verification method is invalid.")
        raw_key = decode_base58_btc(method["publicKeyMultibase"])
        if (
            not raw_key.startswith(ED25519_MULTICODEC_PREFIX)
            or len(raw_key) != 34
        ):
            raise ValueError("Holder key is not an Ed25519 Multikey.")
        return VerificationKey(
            verification_method=verification_method,
            controller=holder_did,
            key_type="Multikey",
            public_key_bytes=raw_key[2:],
        )


def _result(
    checked_at: datetime,
    presentation_id: str | None,
    holder_did: str | None,
    credential_ids: tuple[str, ...],
    errors: list[str],
) -> PresentationValidationResult:
    normalized_errors = tuple(dict.fromkeys(errors))
    return PresentationValidationResult(
        valid=not normalized_errors,
        verified_at=checked_at,
        presentation_id=presentation_id,
        holder_did=holder_did,
        credential_ids=credential_ids,
        errors=normalized_errors,
    )


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def _parse_timestamp(
    value: Any,
    errors: list[str],
    *,
    code: str,
) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        errors.append(code)
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(code)
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        errors.append(code)
        return None
    return parsed.astimezone(UTC)
