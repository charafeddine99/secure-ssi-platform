"""Re-issuance after a holder's DID changed.

A signed credential is never edited. The old one stays as it is, and the issuer
decides whether to issue a new one to the holder's current DID. The holder then
claims it through the normal OID4VCI flow.
"""

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from app.domain.exceptions import PermissionDeniedError
from app.domain.persistence import PersistenceUnavailableError


REISSUANCE_COLLECTION = "credential_reissuance_requests"
_NON_SUBJECT_CLAIMS = frozenset({"id"})


class ReissuanceError(ValueError):
    """The request cannot go ahead in its current state."""


class ReissuanceNotFoundError(ReissuanceError):
    """Absent or not visible to this caller."""


@dataclass(frozen=True)
class ReissuanceRequest:
    request_id: str
    credential_id: str
    credential_type: str
    issuer_did: str
    wallet_id: str
    old_holder_did: str
    new_holder_did: str
    status: str
    created_at: datetime
    decided_at: datetime | None
    offer_link: str | None

    @classmethod
    def from_document(cls, value: dict[str, Any]) -> "ReissuanceRequest":
        return cls(
            request_id=value["_id"],
            credential_id=value["credentialId"],
            credential_type=value["credentialType"],
            issuer_did=value["issuerDid"],
            wallet_id=value["walletId"],
            old_holder_did=value["oldHolderDid"],
            new_holder_did=value["newHolderDid"],
            status=value["status"],
            created_at=value["createdAt"],
            decided_at=value.get("decidedAt"),
            offer_link=value.get("offerLink"),
        )


class ReissuanceService:
    def __init__(
        self,
        *,
        requests: Collection[dict[str, Any]],
        wallets: Any,
        credentials: Any,
        ledger: Any,
        clock: Callable[[], datetime],
    ) -> None:
        self._requests = requests
        self._wallets = wallets
        self._credentials = credentials
        self._ledger = ledger
        self._clock = clock

    def request(
        self,
        wallet_id: str,
        credential_id: str,
        *,
        owner_user_id: str,
    ) -> ReissuanceRequest:
        wallet = self._wallets.require_owned_active(
            wallet_id,
            owner_user_id=owner_user_id,
            correlation_id=f"reissuance:{wallet_id}",
        )
        record = next(
            (
                item
                for item in self._credentials.list_by_wallet(
                    wallet_id, owner_user_id=owner_user_id, limit=100
                )
                if item.credential_id == credential_id
                and item.raw_credential is not None
            ),
            None,
        )
        if record is None:
            raise ReissuanceNotFoundError("The credential was not found.")
        raw = dict(record.raw_credential)
        subject = raw.get("credentialSubject")
        old_did = subject.get("id") if isinstance(subject, dict) else None
        if old_did == wallet.holder_did:
            raise ReissuanceError(
                "This credential already belongs to your current DID."
            )
        if self._ledger.is_revoked(credential_id):
            raise ReissuanceError("A revoked credential cannot be re-issued.")
        types = [item for item in raw.get("type", []) if item != "VerifiableCredential"]
        now = self._now()
        document = {
            "_id": f"reissue_{secrets.token_urlsafe(18)}",
            "credentialId": credential_id,
            "credentialType": types[0] if types else "VerifiableCredential",
            "issuerDid": _issuer_of(raw),
            "walletId": wallet_id,
            "ownerUserId": owner_user_id,
            "oldHolderDid": str(old_did),
            "newHolderDid": wallet.holder_did,
            "status": "PENDING",
            "createdAt": now,
            "decidedAt": None,
            "offerLink": None,
        }
        try:
            duplicate = self._requests.find_one(
                {"credentialId": credential_id, "status": "PENDING"}
            )
            if duplicate is not None:
                return ReissuanceRequest.from_document(duplicate)
            self._requests.insert_one(document)
        except PyMongoError as error:
            raise _unavailable() from error
        return ReissuanceRequest.from_document(document)

    def list_for_holder(self, owner_user_id: str) -> tuple[ReissuanceRequest, ...]:
        return self._list({"ownerUserId": owner_user_id})

    def list_for_issuer(self, issuer_did: str) -> tuple[ReissuanceRequest, ...]:
        return self._list({"issuerDid": issuer_did})

    def approve(
        self,
        request_id: str,
        *,
        issuer_did: str,
        create_offer: Callable[[str, dict[str, Any]], str],
    ) -> ReissuanceRequest:
        """create_offer receives the credential type and the old subject claims."""
        current = self._pending(request_id, issuer_did)
        if self._ledger.is_revoked(current.credential_id):
            raise ReissuanceError("A revoked credential cannot be re-issued.")
        record = self._credentials.get_by_credential_id(current.credential_id)
        if record is None or record.raw_credential is None:
            raise ReissuanceError("The original credential is no longer stored.")
        subject = dict(record.raw_credential.get("credentialSubject") or {})
        claims = {
            key: value
            for key, value in subject.items()
            if key not in _NON_SUBJECT_CLAIMS
        }
        claims["recipient_did"] = current.new_holder_did
        link = create_offer(current.credential_type, claims)
        return self._decide(request_id, "OFFERED", offer_link=link)

    def reject(self, request_id: str, *, issuer_did: str) -> ReissuanceRequest:
        self._pending(request_id, issuer_did)
        return self._decide(request_id, "REJECTED", offer_link=None)

    def _pending(self, request_id: str, issuer_did: str) -> ReissuanceRequest:
        try:
            document = self._requests.find_one({"_id": request_id})
        except PyMongoError as error:
            raise _unavailable() from error
        if document is None:
            raise ReissuanceNotFoundError("The request was not found.")
        if document["issuerDid"] != issuer_did:
            raise PermissionDeniedError(
                "Only the original issuer can decide this request."
            )
        if document["status"] != "PENDING":
            raise ReissuanceError("This request was already decided.")
        return ReissuanceRequest.from_document(document)

    def _decide(
        self,
        request_id: str,
        status: str,
        *,
        offer_link: str | None,
    ) -> ReissuanceRequest:
        try:
            result = self._requests.update_one(
                {"_id": request_id, "status": "PENDING"},
                {
                    "$set": {
                        "status": status,
                        "decidedAt": self._now(),
                        "offerLink": offer_link,
                    }
                },
            )
            if result.matched_count != 1:
                raise ReissuanceError("This request was already decided.")
            return ReissuanceRequest.from_document(
                self._requests.find_one({"_id": request_id})
            )
        except PyMongoError as error:
            raise _unavailable() from error

    def _list(self, query: dict[str, Any]) -> tuple[ReissuanceRequest, ...]:
        try:
            documents = list(
                self._requests.find(query).sort("createdAt", -1).limit(100)
            )
        except PyMongoError as error:
            raise _unavailable() from error
        return tuple(ReissuanceRequest.from_document(item) for item in documents)

    def _now(self) -> datetime:
        return self._clock().astimezone(UTC)


def _issuer_of(raw: dict[str, Any]) -> str:
    issuer = raw.get("issuer")
    return str(issuer.get("id") if isinstance(issuer, dict) else issuer)


def _unavailable() -> PersistenceUnavailableError:
    return PersistenceUnavailableError("Re-issuance data is unavailable.")
