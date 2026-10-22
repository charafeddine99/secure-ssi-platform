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

class InvalidGrantError(Oid4vciError):
    """Invalid, expired, or replayed grant (pre-authorized code or user pin)."""

class InvalidTokenError(Oid4vciError):
    """Missing, invalid, expired, or malformed bearer access token."""

class InvalidProofError(Oid4vciError):
    """Missing, invalid, expired, tampered, or mismatched holder proof-of-possession."""

class InvalidNonceError(Oid4vciError):
    """Missing, expired, unknown, or replayed issuer c_nonce."""

class UnsupportedProofTypeError(Oid4vciError):
    """Requested proof type is unsupported by the credential issuer."""

class UnsupportedCredentialConfigurationError(Oid4vciError):
    """Requested credential configuration ID is unsupported or not permitted by grant."""

class InvalidCredentialSubjectError(Oid4vciError, ValueError):
    """Credential subject claims are missing or invalid for the requested credential."""

class IssuanceState(StrEnum):
    OFFER_CREATED = "OFFER_CREATED"
    OFFER_RETRIEVED = "OFFER_RETRIEVED"
    OFFER_VALIDATED = "OFFER_VALIDATED"
    PREAUTH_CODE_AVAILABLE = "PREAUTH_CODE_AVAILABLE"
    TOKEN_REQUESTED = "TOKEN_REQUESTED"
    ACCESS_TOKEN_ISSUED = "ACCESS_TOKEN_ISSUED"
    NONCE_AVAILABLE = "NONCE_AVAILABLE"
    CREDENTIAL_PROOF_CREATED = "CREDENTIAL_PROOF_CREATED"
    CREDENTIAL_REQUEST_SUBMITTED = "CREDENTIAL_REQUEST_SUBMITTED"
    HOLDER_PROOF_VALIDATED = "HOLDER_PROOF_VALIDATED"
    CREDENTIAL_ISSUED = "CREDENTIAL_ISSUED"
    CREDENTIAL_PERSISTED = "CREDENTIAL_PERSISTED"
    ISSUANCE_COMPLETE = "ISSUANCE_COMPLETE"

    # Terminal failure states
    OFFER_EXPIRED = "OFFER_EXPIRED"
    PREAUTH_CODE_INVALID = "PREAUTH_CODE_INVALID"
    PREAUTH_CODE_REPLAYED = "PREAUTH_CODE_REPLAYED"
    TOKEN_DENIED = "TOKEN_DENIED"
    NONCE_INVALID = "NONCE_INVALID"
    PROOF_INVALID = "PROOF_INVALID"
    PROOF_EXPIRED = "PROOF_EXPIRED"
    WRONG_AUDIENCE = "WRONG_AUDIENCE"
    WRONG_HOLDER_KEY = "WRONG_HOLDER_KEY"
    CREDENTIAL_REQUEST_REJECTED = "CREDENTIAL_REQUEST_REJECTED"
    ISSUANCE_FAILED = "ISSUANCE_FAILED"

@dataclass(frozen=True)
class HolderProof:
    proof_type: str
    jwt: str | None = None
    ldp_vp: Mapping[str, Any] | None = None

@dataclass(frozen=True)
class TokenRequest:
    grant_type: str
    pre_authorized_code: str
    user_pin: str | None = None
    client_id: str | None = None

@dataclass(frozen=True)
class TokenResponse:
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    c_nonce: str | None = None
    c_nonce_expires_in: int | None = None
    scope: str | None = None
    authorization_details: tuple[Mapping[str, Any], ...] | None = None

@dataclass(frozen=True)
class NonceResponse:
    c_nonce: str
    c_nonce_expires_in: int = 600

@dataclass(frozen=True)
class CredentialRequest:
    credential_configuration_id: str
    proof: HolderProof | None = None
    wallet_id: str | None = None
    owner_user_id: str | None = None

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
