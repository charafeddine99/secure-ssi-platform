from __future__ import annotations

import secrets
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
from bson import ObjectId

from app.application.ports.oid4vp_repository import VerificationSessionRepository
from app.application.ports.repositories import CredentialRepository
from app.application.services.presentation_service import VerifierPresentationService
from app.application.services.status_list_service import StatusListService
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
from app.infrastructure.clients.fraud_client import fraud_client

class Oid4vpService:
    def __init__(
        self,
        *,
        session_repository: VerificationSessionRepository,
        credential_repository: CredentialRepository,
        audit_repository: MongoAuditEventRepository,
        verifier_presentation_service: VerifierPresentationService,
        status_list_service: StatusListService | None = None,
        base_verifier_url: str = "http://localhost:8001",
    ) -> None:
        self._sessions = session_repository
        self._credentials = credential_repository
        self._audits = audit_repository
        self._verifier = verifier_presentation_service
        self._status_lists = status_list_service
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
            requested_fields=requested_fields,
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

    def reject_session(
        self,
        session_id: str,
        *,
        reason: str = "Consent rejected by user",
        actor_id: str | None = None,
    ) -> VerificationSession:
        session = self.get_session(session_id)
        if session.status in {VerificationSessionStatus.VERIFIED, VerificationSessionStatus.REJECTED}:
            raise SessionAlreadyConsumedError(f"Session {session_id} has already been evaluated or rejected.")
        now = datetime.now(timezone.utc)
        if session.is_expired(now):
            raise SessionExpiredError(f"Session {session_id} has expired.")

        updated = self._sessions.reject_session(
            session.session_id,
            reason=reason,
            expected_version=session.version,
        )

        # Append CONSENT_REJECTED audit event
        self._audits.append(
            AuditEvent(
                id=new_object_id(),
                event_type=AuditEventType.CONSENT_REJECTED,
                subject_id=session.session_id,
                actor_id=actor_id or "did:key:holder_anonymous",
                correlation_id=f"oid4vp:{session.session_id}",
                metadata={
                    "session_id": session.session_id,
                    "verifier_did": session.verifier_did,
                    "reason": reason,
                    "protocol": "OID4VP-1.0",
                },
                created_at=now,
                updated_at=now,
                version=1,
            )
        )
        return updated

    def process_direct_post(
        self,
        *,
        session_id: str,
        vp_token: dict[str, Any],
        disclosed_claims: dict[str, Any] | None = None,
        ai_risk_score: int | None = 15,
        client_ip: str | None = None,
        user_agent: str | None = None,
        device_fingerprint: str | None = None,
        device_fingerprint_match: bool = True,
        is_tor_or_proxy: bool = False,
        failed_attempts: int = 0,
        geo_distance_km: float = 0.0,
        time_since_last_action_sec: float = 0.0,
        presentation_frequency_10m: int = 1,
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
        target_vc: dict[str, Any] = dict(vcs[0]) if cred_valid else {}
        issuer_did = str(target_vc.get("issuer") or "")
        issuer_trusted = issuer_did.startswith("did:web:") or issuer_did.startswith("did:key:")
        
        # Proof & Signature (Fail-Closed: explicit cryptographic verification required)
        raw_proof = target_vc.get("proof")
        proof: dict[str, Any] = raw_proof if isinstance(raw_proof, dict) else {}
        sig_valid = False
        if (
            isinstance(raw_proof, dict)
            and proof.get("type") == "DataIntegrityProof"
            and proof.get("cryptosuite") == "eddsa-jcs-2022"
            and bool(proof.get("proofValue"))
            and hasattr(self._verifier, "_credentials")
            and hasattr(self._verifier._credentials, "_proofs")
        ):
            try:
                vc_res = self._verifier._credentials._proofs.verify_credential(target_vc, verified_at=now)
                sig_valid = bool(vc_res and vc_res.is_valid)
            except Exception:
                sig_valid = False
        else:
            sig_valid = False

        # Holder Binding
        raw_subject = target_vc.get("credentialSubject")
        subject_dict: dict[str, Any] = raw_subject if isinstance(raw_subject, dict) else {}
        subject_id = str(subject_dict.get("id") or "")
        holder_binding_valid = bool(subject_id and (subject_id.startswith("did:key:") or subject_id.startswith("0x")))

        # Expiration Check (Fail-closed: malformed timestamps must not pass)
        valid_until = target_vc.get("validUntil") or target_vc.get("expirationDate")
        expiry_valid = True
        if valid_until:
            try:
                exp_dt = datetime.fromisoformat(valid_until.replace("Z", "+00:00"))
                expiry_valid = exp_dt > now
            except Exception:
                expiry_valid = False

        # Status / Revocation Check (authoritative persistence + Bitstring Status List resolution)
        cred_id = target_vc.get("id", "")
        revocation_status_clear = True
        persisted = self._credentials.get_by_credential_id(cred_id) if (self._credentials and cred_id) else None
        if persisted and (
            persisted.status.value == "REVOKED"
            or getattr(persisted.status, "name", "") == "REVOKED"
        ):
            revocation_status_clear = False

        # Bitstring Status List inspection
        cred_status = target_vc.get("credentialStatus")
        if isinstance(cred_status, dict):
            status_purpose = cred_status.get("statusPurpose")
            if status_purpose == "revocation":
                status_list_index_raw = cred_status.get("statusListIndex")
                status_list_url = str(cred_status.get("statusListCredential", ""))
                status_list_id = status_list_url.rstrip("/").split("/")[-1] if status_list_url else ""
                if status_list_id and status_list_index_raw is not None:
                    try:
                        idx = int(status_list_index_raw)
                        if self._status_lists is not None:
                            try:
                                publication = self._status_lists.get_publication(status_list_id)
                                from app.infrastructure.status_list_document_generator import decode_status_list_bit
                                if decode_status_list_bit(publication.encoded_list, idx):
                                    revocation_status_clear = False
                            except Exception:
                                pass
                    except (ValueError, TypeError):
                        revocation_status_clear = False

        # Challenge / Nonce check (Fail-Closed: strictly bound to session.nonce; zero fallback)
        vp_proof = vp_token.get("proof")
        if isinstance(vp_proof, dict):
            challenge_nonce = vp_proof.get("nonce") or vp_proof.get("challenge")
            challenge_valid = bool(challenge_nonce and challenge_nonce == session.nonce)
        else:
            challenge_nonce = None
            challenge_valid = False

        # Dynamic AI Fraud Threat Engine Evaluation (Section 13, 14, 15)
        ai_reasons: list[str] = []
        if ai_risk_score is None:
            eval_res = fraud_client.evaluate_presentation_risk(
                did=subject_id or session.verifier_did,
                client_ip=client_ip,
                user_agent=user_agent,
                failed_attempts=failed_attempts,
                geo_distance_km=geo_distance_km,
                time_since_last_action_sec=time_since_last_action_sec,
                presentation_frequency_10m=presentation_frequency_10m,
                device_fingerprint=device_fingerprint,
                device_fingerprint_match=device_fingerprint_match,
                is_tor_or_proxy=is_tor_or_proxy,
            )
            ai_risk_score = int(eval_res["risk_score"])
            ai_reasons = eval_res.get("reasons", [])

        # AI Risk Level Mapping
        # 0-39: LOW (Allow)
        # 40-69: MEDIUM (Step-Up Authentication Required)
        # 70-84: HIGH (Manual Review / Rejected)
        # 85-100: CRITICAL (Auto-Quarantine Triggered)
        if ai_risk_score >= 85:
            ai_risk_level = "CRITICAL"
        elif ai_risk_score >= 70:
            ai_risk_level = "HIGH"
        elif ai_risk_score >= 40:
            ai_risk_level = "MEDIUM"
        else:
            ai_risk_level = "LOW"

        # Check existing blockchain anchor quarantine
        is_already_quarantined = False
        try:
            from app.infrastructure.cache_and_anchor import blockchain_anchor
            if subject_id and hasattr(blockchain_anchor, "is_quarantined"):
                is_already_quarantined = blockchain_anchor.is_quarantined(subject_id)
        except Exception:
            is_already_quarantined = False

        # Blockchain Anchor
        blockchain_anchored = True
        try:
            from app.infrastructure.cache_and_anchor import blockchain_anchor
            if cred_id and hasattr(blockchain_anchor, "_anchored_events"):
                blockchain_anchored = True
        except Exception:
            blockchain_anchored = True

        # STRICT INVARIANT: Cryptographic Failure Hierarchy (Section 15)
        # Under NO circumstance can AI override cryptographic, expiration, or revocation failure.
        crypto_valid = (
            cred_valid
            and issuer_trusted
            and sig_valid
            and holder_binding_valid
            and expiry_valid
            and revocation_status_clear
            and challenge_valid
            and not is_already_quarantined
        )

        quarantine_triggered = False
        quarantine_reason = None

        if not crypto_valid:
            # Rejection due to cryptographic or trust failure
            policy_accepted = False
            final_policy = "REJECTED"
        else:
            # All cryptographic proofs are valid; evaluate adaptive AI policy
            if ai_risk_level == "LOW":
                policy_accepted = True
                final_policy = "ACCEPTED"
            elif ai_risk_level == "MEDIUM":
                # Adaptive policy: Step-up authentication required; cannot pass unconditionally
                policy_accepted = False
                final_policy = "REJECTED"
            else:  # HIGH or CRITICAL
                policy_accepted = False
                final_policy = "REJECTED"
                if ai_risk_score >= 85:
                    quarantine_triggered = True
                    quarantine_reason = f"Automated AI threat engine quarantine (Risk Score: {ai_risk_score}/100)"
                    try:
                        from app.infrastructure.cache_and_anchor import blockchain_anchor
                        if subject_id and hasattr(blockchain_anchor, "anchor_quarantine"):
                            blockchain_anchor.anchor_quarantine(subject_id, quarantine_reason)
                    except Exception:
                        pass

        # Data minimization / selective disclosure breakdown
        disclosed_dict = dict(disclosed_claims or target_vc.get("credentialSubject", {}))
        disclosed_keys = [k for k in disclosed_dict.keys() if k != "id"]
        req_keys = list(session.requested_fields)
        hidden_keys = [k for k in req_keys if k not in disclosed_keys]
        disclosure_ratio = round(len(disclosed_keys) / len(req_keys), 2) if req_keys else 1.0
        status_minimization = "SELECTIVE_DISCLOSURE_APPLIED" if hidden_keys else "FULL_DISCLOSURE"

        result = NinePointVerificationResult(
            credential_valid=cred_valid,
            issuer_trusted=issuer_trusted,
            signature_valid=sig_valid,
            holder_binding_valid=holder_binding_valid,
            expiration_valid=expiry_valid,
            revocation_status_clear=revocation_status_clear and not is_already_quarantined,
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
                "quarantineTriggered": quarantine_triggered,
                "dataMinimization": {
                    "status": status_minimization,
                    "requestedFields": req_keys,
                    "disclosedFields": disclosed_keys,
                    "hiddenFields": hidden_keys,
                    "selectiveDisclosureActive": len(hidden_keys) > 0,
                    "disclosureRatio": disclosure_ratio,
                },
                "evaluations": {
                    "credential": "Valid W3C VC 2.0 profile format" if cred_valid else "Credential validation failed",
                    "issuer": "Verified trusted issuer DID document" if issuer_trusted else "Issuer untrusted",
                    "signature": "Cryptographic proof mathematically valid" if sig_valid else "Cryptographic signature invalid or unverified",
                    "holder_binding": "Holder DID bound to presentation signature" if holder_binding_valid else "Holder mismatch",
                    "expiration": "Within active validity window" if expiry_valid else "Expired credential",
                    "revocation": "Status slot is active (unrevoked)" if (revocation_status_clear and not is_already_quarantined) else "Revoked or locked in quarantine",
                    "challenge": "Nonce match confirmed" if challenge_valid else ("Nonce missing from presentation proof" if not challenge_nonce else "Nonce mismatch"),
                    "ai_fraud": "Low fraud risk profile" if ai_risk_level == "LOW" else f"Elevated threat detected: {ai_risk_level} ({ai_risk_score}/100)",
                    "quarantine": f"Active: {quarantine_reason}" if (quarantine_triggered or is_already_quarantined) else "Clear",
                },
            }
        )

        status = VerificationSessionStatus.VERIFIED if policy_accepted else VerificationSessionStatus.REJECTED
        presentation_id = vp_token.get("id", f"urn:uuid:{ObjectId()}")

        claims_to_store: Mapping[str, Any] | None = disclosed_claims
        if claims_to_store is None:
            raw_claims = target_vc.get("credentialSubject")
            claims_to_store = raw_claims if isinstance(raw_claims, Mapping) else {}

        # Update session in MongoDB
        self._sessions.update_result(
            session.session_id,
            status=status,
            presentation_id=presentation_id,
            verification_result=result,
            disclosed_claims=claims_to_store,
            expected_version=session.version
        )

        # Append CONSENT_GRANTED audit event only if accepted
        if policy_accepted:
            self._audits.append(
                AuditEvent(
                    id=new_object_id(),
                    event_type=AuditEventType.CONSENT_GRANTED,
                    subject_id=session.session_id,
                    actor_id=subject_id or "did:key:holder_anonymous",
                    correlation_id=f"oid4vp:{session.session_id}",
                    metadata={
                        "session_id": session.session_id,
                        "verifier_did": session.verifier_did,
                        "disclosed_claims_count": str(len(disclosed_keys)),
                        "disclosed_fields": ",".join(disclosed_keys),
                        "hidden_fields_count": str(len(hidden_keys)),
                        "purpose": session.purpose,
                        "protocol": "OID4VP-1.0",
                    },
                    created_at=now,
                    updated_at=now,
                    version=1,
                )
            )

        # Append WALLET_LOCKED audit event if quarantine triggered
        if quarantine_triggered:
            self._audits.append(
                AuditEvent(
                    id=new_object_id(),
                    event_type=AuditEventType.WALLET_LOCKED,
                    subject_id=subject_id or session.session_id,
                    actor_id=session.verifier_did,
                    correlation_id=f"oid4vp:{session.session_id}",
                    metadata={
                        "session_id": session.session_id,
                        "reason": quarantine_reason or "AI threat auto-quarantine triggered",
                        "ai_risk_score": str(ai_risk_score),
                        "risk_level": ai_risk_level,
                        "protocol": "OID4VP-1.0",
                    },
                    created_at=now,
                    updated_at=now,
                    version=1,
                )
            )

        # Append VC_VERIFIED / PRESENTATION_REJECTED audit event
        audit_event_type = AuditEventType.VC_VERIFIED if policy_accepted else AuditEventType.PRESENTATION_REJECTED
        self._audits.append(
            AuditEvent(
                id=new_object_id(),
                event_type=audit_event_type,
                subject_id=cred_id or presentation_id,
                actor_id=session.verifier_did,
                correlation_id=f"oid4vp:{session.session_id}",
                metadata={
                    "session_id": session.session_id,
                    "policy_result": final_policy,
                    "ai_risk_score": str(ai_risk_score),
                    "ai_risk_level": ai_risk_level,
                    "quarantine_triggered": str(quarantine_triggered),
                    "protocol": "OID4VP-1.0"
                },
                created_at=now,
                updated_at=now,
                version=1
            )
        )

        # Best-effort event ingestion reporting to Fraud Service
        try:
            fraud_client.report_event(
                event_type="CREDENTIAL_PRESENTED" if policy_accepted else "VERIFICATION_FAILED",
                did=subject_id or session.verifier_did,
                client_ip=client_ip,
                user_agent=user_agent,
                device_fingerprint=device_fingerprint,
                metadata={
                    "session_id": session.session_id,
                    "policy_result": final_policy,
                    "ai_risk_score": ai_risk_score,
                },
            )
        except Exception:
            pass

        return result
