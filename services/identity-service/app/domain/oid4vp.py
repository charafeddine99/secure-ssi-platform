from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Mapping

_OBJECT_ID_PATTERN = re.compile(r"^[0-9a-f]{24}$")
_SESSION_ID_PATTERN = re.compile(r"^session_[A-Za-z0-9_-]{16,80}$")

class VerificationSessionStatus(StrEnum):
    PENDING = "PENDING"
    RECEIVED = "RECEIVED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

class Oid4vpError(Exception):
    """Base exception for OID4VP operations."""

class SessionNotFoundError(Oid4vpError):
    """Requested verification session was not found."""

class SessionExpiredError(Oid4vpError):
    """Verification session challenge has expired."""

class SessionAlreadyConsumedError(Oid4vpError):
    """Verification session was already completed or rejected."""

@dataclass(frozen=True)
class NinePointVerificationResult:
    """
    Verbatim 9-point verification criteria from Master Implementation Plan Section 13:
    1. Credential           ✓ Valid
    2. Issuer / Trust       ✓ Valid
    3. Signature            ✓ Valid
    4. Holder Binding       ✓ Valid
    5. Expiration           ✓ Valid
    6. Revocation / Status  ✓ Clear
    7. Challenge            ✓ Valid
    8. AI Risk              LOW / MEDIUM / HIGH
    9. Blockchain Anchor    ✓
    FINAL POLICY RESULT: ACCEPTED / REJECTED
    """
    credential_valid: bool
    issuer_trusted: bool
    signature_valid: bool
    holder_binding_valid: bool
    expiration_valid: bool
    revocation_status_clear: bool
    challenge_valid: bool
    ai_risk_level: str  # "LOW", "MEDIUM", "HIGH"
    ai_risk_score: int
    blockchain_anchored: bool
    final_policy_result: str  # "ACCEPTED" or "REJECTED"
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "credentialValid": self.credential_valid,
            "issuerTrusted": self.issuer_trusted,
            "signatureValid": self.signature_valid,
            "holderBindingValid": self.holder_binding_valid,
            "expirationValid": self.expiration_valid,
            "revocationStatusClear": self.revocation_status_clear,
            "challengeValid": self.challenge_valid,
            "aiRiskLevel": self.ai_risk_level,
            "aiRiskScore": self.ai_risk_score,
            "blockchainAnchored": self.blockchain_anchored,
            "finalPolicyResult": self.final_policy_result,
            "details": dict(self.details),
        }

class ConsentAction(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


import uuid

@dataclass(frozen=True)
class ConsentDecision:
    session_id: str
    verifier_did: str
    client_id: str
    purpose: str
    nonce: str
    holder_did: str
    decision: ConsentAction
    approved_credentials: tuple[str, ...]
    requested_claims: tuple[str, ...]
    approved_claims: Mapping[str, Any]
    rejected_claims: tuple[str, ...] = field(default_factory=tuple)
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=datetime.utcnow)
    dcql_query_hash: str | None = None
    decision_id: str = field(default_factory=lambda: f"urn:uuid:{uuid.uuid4()}")

    @property
    def action(self) -> ConsentAction:
        return self.decision

    @property
    def timestamp(self) -> datetime:
        return self.created_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "decisionId": self.decision_id,
            "sessionId": self.session_id,
            "verifierDid": self.verifier_did,
            "clientId": self.client_id,
            "purpose": self.purpose,
            "nonce": self.nonce,
            "holderDid": self.holder_did,
            "decision": self.decision.value if hasattr(self.decision, "value") else str(self.decision),
            "approvedCredentials": list(self.approved_credentials),
            "requestedClaims": list(self.requested_claims),
            "approvedClaims": dict(self.approved_claims),
            "rejectedClaims": list(self.rejected_claims),
            "createdAt": self.created_at.isoformat() if hasattr(self.created_at, "isoformat") else str(self.created_at),
            "expiresAt": self.expires_at.isoformat() if hasattr(self.expires_at, "isoformat") else str(self.expires_at),
            "dcqlQueryHash": self.dcql_query_hash,
            "timestamp": self.created_at.isoformat() if hasattr(self.created_at, "isoformat") else str(self.created_at),
        }


@dataclass(frozen=True)
class VerificationSession:
    id: str
    session_id: str
    verifier_did: str
    client_id: str
    response_uri: str
    nonce: str
    dcql_query: Mapping[str, Any] = field(default_factory=dict)
    presentation_definition: Mapping[str, Any] = field(default_factory=dict)
    status: VerificationSessionStatus = VerificationSessionStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=datetime.utcnow)
    purpose: str = "Verification of digital credentials"
    presentation_id: str | None = None
    verification_result: NinePointVerificationResult | None = None
    disclosed_claims: Mapping[str, Any] | None = None
    consent_status: str = "PENDING"
    rejection_reason: str | None = None
    requested_fields: tuple[str, ...] = field(default_factory=tuple)
    consent_decision: ConsentDecision | None = None
    approved_credentials: tuple[str, ...] = field(default_factory=tuple)
    approved_claims: Mapping[str, Any] | None = None
    rejected_claims: tuple[str, ...] = field(default_factory=tuple)
    version: int = 1

    def __post_init__(self) -> None:
        if not _OBJECT_ID_PATTERN.fullmatch(self.id):
            raise ValueError("Session id must be a 24-character ObjectId string.")
        if not _SESSION_ID_PATTERN.fullmatch(self.session_id):
            raise ValueError(f"Invalid session identifier: {self.session_id}")
        if self.expires_at <= self.created_at:
            raise ValueError("Session expiration must be after creation time.")
        if self.version < 1:
            raise ValueError("Session version must be positive.")

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    def to_authorization_request_uri(self, *, include_legacy_pe: bool = False) -> str:
        """
        Builds standard openid4vp:// authorization request URI conforming to OpenID4VP 1.0 Final.
        Canonical path utilizes 'dcql_query'. Legacy PE is optional and strictly isolated.
        """
        import urllib.parse
        import json
        params: dict[str, str] = {
            "client_id": self.client_id,
            "response_uri": self.response_uri,
            "response_type": "vp_token",
            "response_mode": "direct_post",
            "nonce": self.nonce,
            "state": self.session_id,
        }
        if self.dcql_query:
            params["dcql_query"] = json.dumps(dict(self.dcql_query))
        if include_legacy_pe and self.presentation_definition:
            params["presentation_definition"] = json.dumps(dict(self.presentation_definition))
        query = urllib.parse.urlencode(params)
        return f"openid4vp://?{query}"

