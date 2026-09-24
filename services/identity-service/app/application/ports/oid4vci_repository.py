from typing import Protocol
from app.domain.oid4vci import CredentialOffer, OfferStatus

class CredentialOfferRepository(Protocol):
    def add(self, offer: CredentialOffer) -> CredentialOffer:
        ...

    def get_by_offer_id(self, offer_id: str) -> CredentialOffer | None:
        ...

    def get_by_pre_authorized_code(self, pre_authorized_code: str) -> CredentialOffer | None:
        ...

    def mark_claimed(
        self,
        offer_id: str,
        *,
        holder_did: str,
        issued_credential_id: str,
        expected_version: int,
    ) -> CredentialOffer:
        ...

    def list_by_issuer(
        self,
        issuer_did: str,
        *,
        status: OfferStatus | None = None,
        limit: int = 50,
    ) -> tuple[CredentialOffer, ...]:
        ...
