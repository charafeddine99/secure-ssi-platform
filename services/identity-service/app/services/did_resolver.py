import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from app.domain.did import (
    DidResolutionError,
    DidResolutionErrorCode,
    DidResolutionMetadata,
    DidResolutionResult,
)
from app.services.did_document_validator import (
    DID_V1_CONTEXT,
    MULTIKEY_V1_CONTEXT,
    DidDocumentValidator,
)


DID_PATTERN = re.compile(r"^did:([a-z0-9]+):(.+)$")
DID_KEY_PATTERN = re.compile(r"^did:key:(z[1-9A-HJ-NP-Za-km-z]+)$")
DID_WEB_PATTERN = re.compile(
    r"^did:web:([a-z0-9](?:[a-z0-9.-]*[a-z0-9])?)(?::[A-Za-z0-9._~-]+)*$"
)
BASE58_BTC_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
ED25519_PUBLIC_KEY_MULTICODEC_PREFIX = b"\xed\x01"
ED25519_PUBLIC_KEY_LENGTH = 32


class DidResolver(Protocol):
    method: str

    def resolve(self, did: str) -> DidResolutionResult: ...


class DidKeyResolver:
    method = "key"

    def __init__(self, validator: DidDocumentValidator | None = None) -> None:
        self.validator = validator or DidDocumentValidator()

    def resolve(self, did: str) -> DidResolutionResult:
        match = DID_KEY_PATTERN.fullmatch(did)
        if not match:
            raise DidResolutionError(
                DidResolutionErrorCode.INVALID_DID,
                "The did:key identifier is malformed or uses an unsupported encoding.",
                did=did,
            )

        multibase_value = match.group(1)
        decoded = self._decode_base58_btc(multibase_value[1:], did)
        if not decoded.startswith(ED25519_PUBLIC_KEY_MULTICODEC_PREFIX):
            raise DidResolutionError(
                DidResolutionErrorCode.UNSUPPORTED_KEY_TYPE,
                "Only Ed25519 did:key identifiers are supported.",
                did=did,
            )
        public_key = decoded[len(ED25519_PUBLIC_KEY_MULTICODEC_PREFIX) :]
        if len(public_key) != ED25519_PUBLIC_KEY_LENGTH:
            raise DidResolutionError(
                DidResolutionErrorCode.INVALID_DID,
                "The Ed25519 did:key payload must contain a 32-byte public key.",
                did=did,
            )

        verification_method_id = f"{did}#{multibase_value}"
        document = {
            "@context": [DID_V1_CONTEXT, MULTIKEY_V1_CONTEXT],
            "id": did,
            "verificationMethod": [
                {
                    "id": verification_method_id,
                    "type": "Multikey",
                    "controller": did,
                    "publicKeyMultibase": multibase_value,
                }
            ],
            "authentication": [verification_method_id],
            "assertionMethod": [verification_method_id],
            "capabilityInvocation": [verification_method_id],
            "capabilityDelegation": [verification_method_id],
        }
        validated = self.validator.validate(document, expected_did=did)
        return DidResolutionResult(
            did=did,
            did_document=validated,
            metadata=DidResolutionMetadata(method=self.method, source="generated"),
        )

    @staticmethod
    def _decode_base58_btc(value: str, did: str) -> bytes:
        number = 0
        try:
            for character in value:
                number = number * 58 + BASE58_BTC_ALPHABET.index(character)
        except ValueError as error:
            raise DidResolutionError(
                DidResolutionErrorCode.INVALID_DID,
                "The did:key identifier contains an invalid base58-btc character.",
                did=did,
            ) from error

        decoded = number.to_bytes((number.bit_length() + 7) // 8, "big")
        leading_zeroes = len(value) - len(value.lstrip("1"))
        return b"\x00" * leading_zeroes + decoded


class DidWebFixtureResolver:
    method = "web"

    def __init__(
        self,
        fixtures: Mapping[str, Path],
        validator: DidDocumentValidator | None = None,
    ) -> None:
        self.fixtures = {did: path.resolve() for did, path in fixtures.items()}
        self.validator = validator or DidDocumentValidator()

    def resolve(self, did: str) -> DidResolutionResult:
        if not DID_WEB_PATTERN.fullmatch(did):
            raise DidResolutionError(
                DidResolutionErrorCode.INVALID_DID,
                "The did:web identifier is malformed.",
                did=did,
            )
        fixture_path = self.fixtures.get(did)
        if fixture_path is None or not fixture_path.is_file():
            raise DidResolutionError(
                DidResolutionErrorCode.NOT_FOUND,
                "No local fixture is registered for this did:web identifier.",
                did=did,
            )

        raw = fixture_path.read_bytes()
        if len(raw) > self.validator.max_document_bytes:
            raise DidResolutionError(
                DidResolutionErrorCode.DOCUMENT_TOO_LARGE,
                "DID document exceeds the configured size limit.",
                did=did,
            )
        try:
            document = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=self._reject_duplicate_properties,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            raise DidResolutionError(
                DidResolutionErrorCode.INVALID_DID_DOCUMENT,
                "The local did:web fixture is not valid unambiguous UTF-8 JSON.",
                did=did,
            ) from error
        if not isinstance(document, dict):
            raise DidResolutionError(
                DidResolutionErrorCode.INVALID_DID_DOCUMENT,
                "The DID document root must be an object.",
                did=did,
            )

        validated = self.validator.validate(
            document,
            expected_did=did,
            raw_size=len(raw),
        )
        return DidResolutionResult(
            did=did,
            did_document=validated,
            metadata=DidResolutionMetadata(method=self.method, source="local-fixture"),
        )

    @staticmethod
    def _reject_duplicate_properties(
        pairs: list[tuple[str, Any]],
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON property: {key}")
            result[key] = value
        return result


class CompositeDidResolver:
    def __init__(self, resolvers: Mapping[str, DidResolver]) -> None:
        self.resolvers = dict(resolvers)

    def resolve(self, did: str) -> DidResolutionResult:
        match = DID_PATTERN.fullmatch(did)
        if not match:
            raise DidResolutionError(
                DidResolutionErrorCode.INVALID_DID,
                "The identifier is not a valid DID.",
                did=did,
            )
        method = match.group(1)
        resolver = self.resolvers.get(method)
        if resolver is None:
            raise DidResolutionError(
                DidResolutionErrorCode.METHOD_NOT_SUPPORTED,
                "The DID method is not allowed by the prototype profile.",
                did=did,
            )
        return resolver.resolve(did)
