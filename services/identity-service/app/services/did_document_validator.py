import json
from collections.abc import Mapping
from typing import Any

from app.core.config import MAX_DID_DOCUMENT_BYTES
from app.domain.did import DidResolutionError, DidResolutionErrorCode


DID_V1_CONTEXT = "https://www.w3.org/ns/did/v1"
MULTIKEY_V1_CONTEXT = "https://w3id.org/security/multikey/v1"
ALLOWED_CONTEXTS = {DID_V1_CONTEXT, MULTIKEY_V1_CONTEXT}
PRIVATE_KEY_FIELDS = {
    "privateKey",
    "privateKeyJwk",
    "privateKeyMultibase",
    "secretKey",
    "secretKeyJwk",
    "secretKeyMultibase",
}


class DidDocumentValidator:
    def __init__(self, *, max_document_bytes: int | None = None) -> None:
        configured_limit = (
            MAX_DID_DOCUMENT_BYTES
            if max_document_bytes is None
            else max_document_bytes
        )
        if configured_limit <= 0:
            raise ValueError("max_document_bytes must be positive")
        self.max_document_bytes = configured_limit

    def validate(
        self,
        document: Mapping[str, Any],
        *,
        expected_did: str,
        raw_size: int | None = None,
    ) -> dict[str, Any]:
        normalized = dict(document)
        document_size = raw_size or len(
            json.dumps(
                normalized,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        if document_size > self.max_document_bytes:
            self._raise(
                DidResolutionErrorCode.DOCUMENT_TOO_LARGE,
                "DID document exceeds the configured size limit.",
                expected_did,
            )

        private_field = self._find_private_key_field(normalized)
        if private_field:
            self._raise(
                DidResolutionErrorCode.PRIVATE_KEY_MATERIAL,
                f"DID document contains prohibited field: {private_field}.",
                expected_did,
            )

        if normalized.get("id") != expected_did:
            self._raise(
                DidResolutionErrorCode.INVALID_DID_DOCUMENT,
                "DID document id does not match the requested DID.",
                expected_did,
            )

        self._validate_context(normalized.get("@context"), expected_did)
        verification_methods = self._validate_verification_methods(
            normalized.get("verificationMethod"),
            expected_did,
        )
        self._validate_assertion_methods(
            normalized.get("assertionMethod"),
            verification_methods,
            expected_did,
        )
        return normalized

    def _validate_context(self, context: Any, expected_did: str) -> None:
        contexts = [context] if isinstance(context, str) else context
        if not isinstance(contexts, list) or not contexts:
            self._raise(
                DidResolutionErrorCode.INVALID_DID_DOCUMENT,
                "DID document must declare an approved context.",
                expected_did,
            )
        if contexts[0] != DID_V1_CONTEXT:
            self._raise(
                DidResolutionErrorCode.INVALID_DID_DOCUMENT,
                "DID Core v1 must be the first context.",
                expected_did,
            )
        if any(
            not isinstance(item, str) or item not in ALLOWED_CONTEXTS
            for item in contexts
        ):
            self._raise(
                DidResolutionErrorCode.INVALID_DID_DOCUMENT,
                "DID document contains an unapproved context.",
                expected_did,
            )

    def _validate_verification_methods(
        self,
        methods: Any,
        expected_did: str,
    ) -> set[str]:
        if not isinstance(methods, list) or not 1 <= len(methods) <= 16:
            self._raise(
                DidResolutionErrorCode.INVALID_DID_DOCUMENT,
                "DID document must contain 1 to 16 verification methods.",
                expected_did,
            )

        method_ids: set[str] = set()
        for method in methods:
            if not isinstance(method, dict):
                self._raise(
                    DidResolutionErrorCode.INVALID_DID_DOCUMENT,
                    "Verification methods must be objects.",
                    expected_did,
                )
            method_id = method.get("id")
            if (
                not isinstance(method_id, str)
                or not method_id.startswith(f"{expected_did}#")
                or method_id in method_ids
            ):
                self._raise(
                    DidResolutionErrorCode.INVALID_DID_DOCUMENT,
                    "Verification method ids must be unique absolute DID URLs.",
                    expected_did,
                )
            if method.get("controller") != expected_did:
                self._raise(
                    DidResolutionErrorCode.INVALID_DID_DOCUMENT,
                    "Verification method controller must match the DID.",
                    expected_did,
                )
            if method.get("type") != "Multikey":
                self._raise(
                    DidResolutionErrorCode.UNSUPPORTED_KEY_TYPE,
                    "Only Multikey verification methods are allowed.",
                    expected_did,
                )
            public_key = method.get("publicKeyMultibase")
            if not isinstance(public_key, str) or not public_key.startswith("z"):
                self._raise(
                    DidResolutionErrorCode.INVALID_DID_DOCUMENT,
                    "A base58-btc publicKeyMultibase value is required.",
                    expected_did,
                )
            method_ids.add(method_id)
        return method_ids

    def _validate_assertion_methods(
        self,
        assertions: Any,
        method_ids: set[str],
        expected_did: str,
    ) -> None:
        if not isinstance(assertions, list) or not assertions:
            self._raise(
                DidResolutionErrorCode.INVALID_DID_DOCUMENT,
                "DID document must authorize at least one assertion method.",
                expected_did,
            )
        if any(not isinstance(item, str) or item not in method_ids for item in assertions):
            self._raise(
                DidResolutionErrorCode.INVALID_DID_DOCUMENT,
                "Assertion methods must reference declared verification methods.",
                expected_did,
            )

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
        code: DidResolutionErrorCode,
        message: str,
        did: str,
    ) -> None:
        raise DidResolutionError(code, message, did=did)
