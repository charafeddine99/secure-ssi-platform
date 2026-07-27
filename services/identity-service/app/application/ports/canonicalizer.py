from collections.abc import Mapping
from typing import Any, Protocol


class CredentialCanonicalizer(Protocol):
    def canonicalize_document(self, document: Mapping[str, Any]) -> bytes: ...

    def calculate_digest(self, document: Mapping[str, Any]) -> bytes: ...

    def create_signing_input(
        self,
        credential_without_proof: Mapping[str, Any],
        proof_configuration: Mapping[str, Any],
    ) -> bytes: ...
