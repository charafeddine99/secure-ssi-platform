from collections.abc import Mapping
from datetime import datetime
from typing import Any, Protocol

from app.domain.bitstring_status_list import CredentialStatusEntry
from app.domain.persistence import PersistedCredential


class CredentialIssuanceRepository(Protocol):
    def issue(
        self,
        credential: PersistedCredential,
        *,
        status_entry: CredentialStatusEntry,
    ) -> PersistedCredential: ...


class IssuerCredentialSigningService(Protocol):
    def supports_issuer(self, issuer_did: str) -> bool: ...

    def sign(
        self,
        credential: Mapping[str, Any],
        *,
        created: datetime,
    ) -> dict[str, Any]: ...


class IssuerStatusListPublisher(Protocol):
    def generate(
        self,
        *,
        status_list_url: str,
        issuer_did: str,
        encoded_list: str,
        ttl_seconds: int,
        published_at: datetime,
    ) -> Mapping[str, Any]: ...
