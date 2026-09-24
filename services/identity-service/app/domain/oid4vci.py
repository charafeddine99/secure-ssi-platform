from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Mapping

_OBJECT_ID_PATTERN = re.compile(r"^[0-9a-f]{24}$")
_OFFER_ID_PATTERN = re.compile(r"^offer_[A-Za-z0-9_-]{16,80}$")

class OfferStatus(StrEnum):
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"

class Oid4vciError(Exception):
    """Base exception for OID4VCI operations."""

class OfferNotFoundError(Oid4vciError):
    """Requested credential offer was not found or is expired."""

class OfferAlreadyClaimedError(Oid4vciError):
    """Credential offer was already claimed by a holder."""

class InvalidProofOfPossessionError(Oid4vciError):
    """Holder's Proof of Possession (PoP) signature is invalid."""

@dataclass(frozen=True)
class CredentialOffer:
    id: str
    offer_id: str
    credential_issuer: str
    issuer_did: str
    credential_configuration_ids: tuple[str, ...]
    subject_data: Mapping[str, Any]
    pre_authorized_code: str
    status: OfferStatus
    created_at: datetime
    expires_at: datetime
    claimed_at: datetime | None = None
    claimed_by_holder_did: str | None = None
    issued_credential_id: str | None = None
    user_pin: str | None = None
    version: int = 1

    def __post_init__(self) -> None:
        if not _OBJECT_ID_PATTERN.fullmatch(self.id):
            raise ValueError("Offer id must be a 24-character ObjectId string.")
        if not _OFFER_ID_PATTERN.fullmatch(self.offer_id):
            raise ValueError(f"Invalid offer identifier: {self.offer_id}")
        if not self.credential_configuration_ids:
            raise ValueError("Credential offer must offer at least one credential configuration.")
        if self.expires_at <= self.created_at:
            raise ValueError("Offer expiration must be strictly after creation time.")
        if self.version < 1:
            raise ValueError("Offer version must be positive.")

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    def to_standard_offer_payload(self, base_issuer_url: str) -> dict[str, Any]:
        """
        Formats according to OID4VCI draft 13 / EUDI specification.
        """
        payload = {
            "credential_issuer": base_issuer_url.rstrip("/"),
            "credential_configuration_ids": list(self.credential_configuration_ids),
            "grants": {
                "urn:ietf:params:oauth:grant-type:pre-authorized_code": {
                    "pre-authorized_code": self.pre_authorized_code,
                    "user_pin_required": self.user_pin is not None,
                }
            }
        }
        return payload

    def to_deep_link_uri(self, base_issuer_url: str) -> str:
        """
        Generates standard openid-credential-offer:// deep link URI.
        """
        import urllib.parse
        import json
        offer_json = json.dumps(self.to_standard_offer_payload(base_issuer_url))
        encoded = urllib.parse.quote(offer_json)
        return f"openid-credential-offer://?credential_offer={encoded}"
