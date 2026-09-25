from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from bson import ObjectId
from pymongo import DESCENDING
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.application.ports.oid4vci_repository import CredentialOfferRepository
from app.domain.oid4vci import (
    CredentialOffer,
    OfferStatus,
    OfferNotFoundError,
    OfferAlreadyClaimedError,
)
from app.domain.persistence import (
    DuplicateEntityError,
    OptimisticLockError,
    PersistenceUnavailableError,
)
from app.infrastructure.persistence.mappers import to_object_id

class CredentialOfferDocumentMapper:
    @staticmethod
    def to_document(offer: CredentialOffer) -> dict[str, Any]:
        return {
            "_id": to_object_id(offer.id),
            "offerId": offer.offer_id,
            "credentialIssuer": offer.credential_issuer,
            "issuerDid": offer.issuer_did,
            "credentialConfigurationIds": list(offer.credential_configuration_ids),
            "subjectData": deepcopy(dict(offer.subject_data)),
            "preAuthorizedCode": offer.pre_authorized_code,
            "status": offer.status.value,
            "userPin": offer.user_pin,
            "createdAt": offer.created_at,
            "expiresAt": offer.expires_at,
            "claimedAt": offer.claimed_at,
            "claimedByHolderDid": offer.claimed_by_holder_did,
            "issuedCredentialId": offer.issued_credential_id,
            "version": offer.version,
        }

    @staticmethod
    def from_document(doc: dict[str, Any]) -> CredentialOffer:
        return CredentialOffer(
            id=str(doc["_id"]),
            offer_id=doc["offerId"],
            credential_issuer=doc["credentialIssuer"],
            issuer_did=doc["issuerDid"],
            credential_configuration_ids=tuple(doc["credentialConfigurationIds"]),
            subject_data=deepcopy(doc.get("subjectData", {})),
            pre_authorized_code=doc["preAuthorizedCode"],
            status=OfferStatus(doc["status"]),
            user_pin=doc.get("userPin"),
            created_at=doc["createdAt"],
            expires_at=doc["expiresAt"],
            claimed_at=doc.get("claimedAt"),
            claimed_by_holder_did=doc.get("claimedByHolderDid"),
            issued_credential_id=doc.get("issuedCredentialId"),
            version=doc.get("version", 1),
        )

class MongoCredentialOfferRepository(CredentialOfferRepository):
    def __init__(self, collection: Collection[dict[str, Any]]) -> None:
        self._collection = collection

    def add(self, offer: CredentialOffer) -> CredentialOffer:
        try:
            self._collection.insert_one(CredentialOfferDocumentMapper.to_document(offer))
            return offer
        except DuplicateKeyError as e:
            raise DuplicateEntityError(f"Credential offer {offer.offer_id} already exists.") from e
        except PyMongoError as e:
            raise PersistenceUnavailableError("Failed to persist credential offer.") from e

    def get_by_offer_id(self, offer_id: str) -> CredentialOffer | None:
        try:
            doc = self._collection.find_one({"offerId": offer_id})
            return CredentialOfferDocumentMapper.from_document(doc) if doc else None
        except PyMongoError as e:
            raise PersistenceUnavailableError(f"Failed to lookup offer {offer_id}.") from e

    def get_by_pre_authorized_code(self, pre_authorized_code: str) -> CredentialOffer | None:
        try:
            doc = self._collection.find_one({"preAuthorizedCode": pre_authorized_code})
            return CredentialOfferDocumentMapper.from_document(doc) if doc else None
        except PyMongoError as e:
            raise PersistenceUnavailableError("Failed to lookup offer by pre-authorized code.") from e

    def mark_claimed(
        self,
        offer_id: str,
        *,
        holder_did: str,
        issued_credential_id: str,
        expected_version: int,
    ) -> CredentialOffer:
        now = datetime.now(timezone.utc)
        try:
            res = self._collection.update_one(
                {
                    "offerId": offer_id,
                    "version": expected_version,
                    "status": OfferStatus.PENDING.value,
                },
                {
                    "$set": {
                        "status": OfferStatus.CLAIMED.value,
                        "claimedAt": now,
                        "claimedByHolderDid": holder_did,
                        "issuedCredentialId": issued_credential_id,
                    },
                    "$inc": {"version": 1},
                },
            )
        except PyMongoError as e:
            raise PersistenceUnavailableError(f"Failed to mark offer {offer_id} as claimed.") from e

        if res.matched_count == 0:
            current = self.get_by_offer_id(offer_id)
            if current is None:
                raise OfferNotFoundError(f"Offer {offer_id} not found.")
            if current.status == OfferStatus.CLAIMED:
                raise OfferAlreadyClaimedError(f"Offer {offer_id} has already been claimed.")
            raise OptimisticLockError(f"Offer {offer_id} was modified concurrently.")

        updated = self.get_by_offer_id(offer_id)
        assert updated is not None
        return updated

    def list_by_issuer(
        self,
        issuer_did: str,
        *,
        status: OfferStatus | None = None,
        limit: int = 50,
    ) -> tuple[CredentialOffer, ...]:
        query: dict[str, Any] = {"issuerDid": issuer_did}
        if status is not None:
            query["status"] = status.value
        try:
            cursor = self._collection.find(query).sort("createdAt", DESCENDING).limit(limit)
            return tuple(CredentialOfferDocumentMapper.from_document(d) for d in cursor)
        except PyMongoError as e:
            raise PersistenceUnavailableError("Failed to list credential offers.") from e
