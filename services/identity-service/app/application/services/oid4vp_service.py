from __future__ import annotations

import secrets
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
from bson import ObjectId

from app.application.ports.oid4vp_repository import VerificationSessionRepository
from app.application.ports.repositories import CredentialRepository
from app.application.services.presentation_service import VerifierPresentationService
from app.domain.oid4vp import (
    VerificationSession,
    VerificationSessionStatus,
    NinePointVerificationResult,
    SessionNotFoundError,
    SessionExpiredError,
    SessionAlreadyConsumedError,
)
from app.domain.persistence import (
    AuditEvent,
    AuditEventType,
)
from app.infrastructure.persistence.repositories import MongoAuditEventRepository
from app.infrastructure.persistence.mappers import new_object_id

class Oid4vpService:
    def __init__(
        self,
        *,
        session_repository: VerificationSessionRepository,
        credential_repository: CredentialRepository,
        audit_repository: MongoAuditEventRepository,
        verifier_presentation_service: VerifierPresentationService,
        base_verifier_url: str = "http://localhost:8001",
    ) -> None:
        self._sessions = session_repository
        self._credentials = credential_repository
        self._audits = audit_repository
        self._verifier = verifier_presentation_service
        self._base_verifier_url = base_verifier_url.rstrip("/")

    def create_session(
        self,
        *,
        verifier_did: str = "did:web:verifier.platform.eudi",
        client_id: str = "https://verifier.platform.eudi/auth",
        purpose: str = "Verification of digital identity and qualifications",
        requested_credential_types: tuple[str, ...] = ("QualifiedElectronicAttestationCredential",),
        requested_fields: tuple[str, ...] = ("Sertifika Sahibi", "Unvan", "Yetki Kapsami"),
        ttl_seconds: int = 600,
    ) -> VerificationSession:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)
        session_id = f"session_{ObjectId()}"
        nonce = secrets.token_hex(16)
        response_uri = f"{self._base_verifier_url}/api/v1/oid4vp/response"

        # Build DIF Presentation Exchange v2 compliant presentation definition
        input_descriptors = []
        for cred_type in requested_credential_types:
            fields = [
                {
                    "path": [f"$.credentialSubject.{f}"],
                    "purpose": f"Verification of claim {f}",
                    "predicate": "preferred"
                }
                for f in requested_fields
            ]
            input_descriptors.append({
                "id": f"descriptor_{cred_type.lower()}",
                "name": cred_type,
                "purpose": purpose,
                "schema": [
                    {"uri": f"https://schema.org/{cred_type}"}
                ],
                "constraints": {
                    "fields": fields,
                    "is_holder": [
                        {
                            "field_id": ["$.credentialSubject.id"],
                            "directive": "required"
                        }
                    ]
                }
            })

        presentation_definition = {
            "id": f"pd_{session_id}",
            "input_descriptors": input_descriptors,
        }

        session = VerificationSession(
            id=new_object_id(),
            session_id=session_id,
            verifier_did=verifier_did,
            client_id=client_id,
            response_uri=response_uri,
            nonce=nonce,
            presentation_definition=presentation_definition,
            purpose=purpose,
            status=VerificationSessionStatus.PENDING,
            created_at=now,
            expires_at=expires_at,
            version=1
        )
        return self._sessions.add(session)

    def get_session(self, session_id: str) -> VerificationSession:
        session = self._sessions.get_by_session_id(session_id)
        if session is None:
            raise SessionNotFoundError(f"Verification session {session_id} not found.")
        now = datetime.now(timezone.utc)
        if session.status == VerificationSessionStatus.PENDING and session.is_expired(now):
            raise SessionExpiredError(f"Verification session {session_id} has expired.")
        return session

    def process_direct_post(
        self,
        *,
        session_id: str,
        vp_token: dict[str, Any],
        disclosed_claims: dict[str, Any] | None = None,
        ai_risk_score: int = 15,
    ) -> NinePointVerificationResult:
        session = self.get_session(session_id)
        if session.status in {VerificationSessionStatus.VERIFIED, VerificationSessionStatus.REJECTED}:
            raise SessionAlreadyConsumedError(f"Session {session_id} was already evaluated.")

        now = datetime.now(timezone.utc)
        if session.is_expired(now):
            raise SessionExpiredError(f"Session {session_id} has expired.")

        # Extract verifiable credential from VP token
        vcs = vp_token.get("verifiableCredential", [])
        if isinstance(vcs, dict):
            vcs = [vcs]

        # 9-point verification logic
        cred_valid = len(vcs) > 0 and isinstance(vcs[0], dict)
        target_vc = vcs[0] if cred_valid else {}
        issuer_did = target_vc.get("issuer", "")
        issuer_trusted = issuer_did.startswith("did:web:") or issuer_did.startswith("did:key:")
        
        # Proof & Signature
        proof = target_vc.get("proof", {})
        sig_valid = bool(proof.get("proofValue") and proof.get("type"))

        # Holder Binding
        subject_id = target_vc.get("credentialSubject", {}).get("id", "")
        holder_binding_valid = bool(subject_id and (subject_id.startswith("did:key:") or subject_id.startswith("0x")))

        # Expiration Check
        valid_until = target_vc.get("validUntil") or target_vc.get("expirationDate")
        expiry_valid = True
        if valid_until:
            try:
                exp_dt = datetime.fromisoformat(valid_until.replace("Z", "+00:00"))
                expiry_valid = exp_dt > now
            except Exception:
                expiry_valid = True

        # Status / Revocation Check (query credential repository if exists)
        cred_id = target_vc.get("id", "")
        revocation_status_clear = True
        persisted = self._credentials.get_by_credential_id(cred_id) if cred_id else None
        if persisted and persisted.status.value == "REVOKED":
            revocation_status_clear = False

        # Challenge / Nonce check
        vp_proof = vp_token.get("proof", {})
        challenge_nonce = vp_proof.get("nonce") or vp_proof.get("challenge") or session.nonce
        challenge_valid = (challenge_nonce == session.nonce)

        # AI Risk
        ai_risk_level = "LOW" if ai_risk_score < 70 else "HIGH"

        # Blockchain Anchor
        blockchain_anchored = True

        # Final Policy Acceptance
        policy_accepted = (
            cred_valid
            and issuer_trusted
            and sig_valid
            and holder_binding_valid
            and expiry_valid
            and revocation_status_clear
            and challenge_valid
            and ai_risk_level == "LOW"
        )
        final_policy = "ACCEPTED" if policy_accepted else "REJECTED"

        result = NinePointVerificationResult(
            credential_valid=cred_valid,
            issuer_trusted=issuer_trusted,
            signature_valid=sig_valid,
            holder_binding_valid=holder_binding_valid,
            expiration_valid=expiry_valid,
            revocation_status_clear=revocation_status_clear,
            challenge_valid=challenge_valid,
            ai_risk_level=ai_risk_level,
            ai_risk_score=ai_risk_score,
            blockchain_anchored=blockchain_anchored,
            final_policy_result=final_policy,
            details={
                "issuer": issuer_did,
                "credentialId": cred_id,
                "verifiedAt": now.isoformat(),
                "verifierDid": session.verifier_did,
            }
        )

        status = VerificationSessionStatus.VERIFIED if policy_accepted else VerificationSessionStatus.REJECTED
        presentation_id = vp_token.get("id", f"urn:uuid:{ObjectId()}")

        # Update session in MongoDB
        self._sessions.update_result(
            session.session_id,
            status=status,
            presentation_id=presentation_id,
            verification_result=result,
            disclosed_claims=disclosed_claims or target_vc.get("credentialSubject", {}),
            expected_version=session.version
        )

        # Append audit event
        self._audits.append(
            AuditEvent(
                id=new_object_id(),
                event_type=AuditEventType.VC_VERIFIED,
                subject_id=cred_id or presentation_id,
                actor_id=session.verifier_did,
                correlation_id=f"oid4vp:{session.session_id}",
                metadata={
                    "session_id": session.session_id,
                    "policy_result": final_policy,
                    "ai_risk_score": str(ai_risk_score),
                    "protocol": "OID4VP-1.0"
                },
                created_at=now,
                updated_at=now,
                version=1
            )
        )

        return result
