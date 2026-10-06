import json
from pathlib import Path
from typing import Any, Mapping

from app.domain.did import DidResolutionError, DidResolutionErrorCode, DidResolutionResult, DidResolutionMetadata
from app.services.did_document_validator import DidDocumentValidator
from app.services.did_resolver import DID_WEB_PATTERN

class DidWebTestFixtureResolver:
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
