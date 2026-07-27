from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class DidResolutionErrorCode(StrEnum):
    INVALID_DID = "INVALID_DID"
    METHOD_NOT_SUPPORTED = "METHOD_NOT_SUPPORTED"
    NOT_FOUND = "NOT_FOUND"
    INVALID_DID_DOCUMENT = "INVALID_DID_DOCUMENT"
    DOCUMENT_TOO_LARGE = "DOCUMENT_TOO_LARGE"
    PRIVATE_KEY_MATERIAL = "PRIVATE_KEY_MATERIAL"
    UNSUPPORTED_KEY_TYPE = "UNSUPPORTED_KEY_TYPE"


class DidResolutionError(Exception):
    def __init__(
        self,
        code: DidResolutionErrorCode,
        message: str,
        *,
        did: str,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.did = did


@dataclass(frozen=True)
class DidResolutionMetadata:
    method: str
    source: str
    content_type: str = "application/did+ld+json"


@dataclass(frozen=True)
class DidResolutionResult:
    did: str
    did_document: dict[str, Any]
    metadata: DidResolutionMetadata
