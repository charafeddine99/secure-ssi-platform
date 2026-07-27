from collections.abc import Mapping
from datetime import datetime
from typing import Any

from app.application.ports.key_provider import KeyProvider
from app.application.services.credential_proof_service import (
    CredentialProofService,
)


class LocalIssuerSigningService:
    """Adapter boundary replaceable by a future KMS/HSM implementation."""

    def __init__(
        self,
        *,
        proof_service: CredentialProofService,
        key_provider: KeyProvider,
    ) -> None:
        self._proof_service = proof_service
        self._key_provider = key_provider

    def supports_issuer(self, issuer_did: str) -> bool:
        return self._key_provider.supports_issuer(issuer_did)

    def sign(
        self,
        credential: Mapping[str, Any],
        *,
        created: datetime,
    ) -> dict[str, Any]:
        return self._proof_service.sign_credential(
            credential,
            created=created,
        )
