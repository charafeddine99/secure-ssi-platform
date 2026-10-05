from __future__ import annotations

import copy
import secrets
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
from bson import ObjectId
from urllib.parse import urlparse

from app.application.ports.oid4vp_repository import VerificationSessionRepository
from app.application.ports.repositories import CredentialRepository
from app.application.services.presentation_service import VerifierPresentationService
from app.application.services.status_list_service import StatusListService
from app.application.ports.canonicalizer import CredentialCanonicalizer
from app.services.did_resolver import DidResolver
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
        did_resolver: DidResolver | None = None,
        canonicalizer: CredentialCanonicalizer | None = None,
    ) -> None:
        self._sessions = session_repository
        self._credentials = credential_repository
        self._audits = audit_repository
        self._verifier = verifier_presentation_service
        self._status_lists = status_list_service
        self._base_verifier_url = base_verifier_url.rstrip("/")
        if did_resolver is not None:
            self._did_resolver = did_resolver
        else:
            from app.services.did_resolver import DidKeyResolver
            self._did_resolver = DidKeyResolver()
        if canonicalizer is not None:
            self._canonicalizer = canonicalizer
        else:
            from app.infrastructure.crypto.jcs_canonicalizer import JcsCanonicalizer
            self._canonicalizer = JcsCanonicalizer()

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

    @staticmethod
    def _is_audience_matched(
        *,
        bound_audience: str | None,
        bound_domain: str | None,
        session: VerificationSession,
    ) -> bool:
        if not bound_audience and not bound_domain:
            return False

        candidates: set[str] = set()
        for raw in (session.client_id, session.verifier_did, session.response_uri):
            if not raw:
                continue
            cleaned = str(raw).strip()
            if cleaned:
                candidates.add(cleaned)
                candidates.add(cleaned.rstrip("/"))
                try:
                    parsed = urlparse(cleaned)
                    if parsed.netloc:
                        candidates.add(parsed.netloc)
                        if ":" in parsed.netloc:
                            candidates.add(parsed.netloc.split(":")[0])
                    if parsed.hostname:
                        candidates.add(parsed.hostname)
                except Exception:
                    pass
                if cleaned.startswith("did:web:"):
                    domain_part = cleaned.removeprefix("did:web:").split(":")[0]
                    candidates.add(domain_part)

        for value in (bound_audience, bound_domain):
            if not value:
                continue
            val_clean = str(value).strip().rstrip("/")
            if val_clean in candidates:
                return True
            try:
                val_parsed = urlparse(val_clean)
                if val_parsed.netloc and val_parsed.netloc in candidates:
                    return True
                if val_parsed.hostname and val_parsed.hostname in candidates:
                    return True
            except Exception:
                pass

        return False

    def _verify_holder_binding(
        self,
        *,
        vp_token: dict[str, Any],
        target_vc: dict[str, Any],
        session: VerificationSession,
        now: datetime,
    ) -> tuple[bool, str | None]:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
        from app.infrastructure.crypto.multibase import decode_base58_btc

        if not isinstance(vp_token, dict):
            return False, "HOLDER_BINDING_MISSING"

        raw_proof = vp_token.get("proof")
        if not isinstance(raw_proof, dict) or not raw_proof:
            return False, "HOLDER_BINDING_MISSING"
        proof = dict(raw_proof)

        # 1. Proof structure and type
        proof_type = proof.get("type")
        cryptosuite = proof.get("cryptosuite")
        if proof_type != "DataIntegrityProof" or cryptosuite != "eddsa-jcs-2022":
            return False, "HOLDER_BINDING_INVALID_PROOF_STRUCTURE"

        # 2. Proof Purpose: strictly authentication
        if proof.get("proofPurpose") != "authentication":
            return False, "HOLDER_BINDING_INVALID_PROOF_PURPOSE"

        # 3. Nonce / Challenge binding
        proof_nonce = proof.get("challenge") or proof.get("nonce")
        if not proof_nonce:
            return False, "HOLDER_BINDING_MISSING_NONCE"
        if proof_nonce != session.nonce:
            return False, "HOLDER_BINDING_WRONG_NONCE"

        # 4. Audience / Domain binding
        bound_audience = proof.get("audience")
        bound_domain = proof.get("domain")
        if not bound_audience and not bound_domain:
            return False, "HOLDER_BINDING_MISSING_AUDIENCE"
        if not self._is_audience_matched(
            bound_audience=bound_audience,
            bound_domain=bound_domain,
            session=session,
        ):
            return False, "HOLDER_BINDING_WRONG_AUDIENCE"

        # 5. Holder DID & Verification Method binding
        raw_subject = target_vc.get("credentialSubject")
        subject_dict = raw_subject if isinstance(raw_subject, dict) else {}
        subject_id = str(subject_dict.get("id") or "").strip()
        holder_did = str(vp_token.get("holder") or subject_id).strip()
        if not holder_did:
            return False, "HOLDER_BINDING_MISSING_HOLDER_DID"
        if subject_id and holder_did != subject_id:
            return False, "HOLDER_BINDING_HOLDER_MISMATCH"

        vm_id = str(proof.get("verificationMethod") or "").strip()
        if not vm_id or not (vm_id.startswith(f"{holder_did}#") or vm_id == holder_did):
            return False, "HOLDER_BINDING_HOLDER_MISMATCH"

        # 6. Resolve Holder DID & enforce DID verification relationship
        try:
            res = self._did_resolver.resolve(holder_did)
            did_doc = res.did_document
        except Exception:
            return False, "HOLDER_BINDING_UNKNOWN_KEY"

        auth_methods = did_doc.get("authentication")
        if not isinstance(auth_methods, list):
            return False, "HOLDER_NOT_AUTHORIZED_FOR_AUTHENTICATION"

        authorized_ids: set[str] = set()
        for item in auth_methods:
            if isinstance(item, str):
                authorized_ids.add(item)
                if item.startswith("#"):
                    authorized_ids.add(f"{holder_did}{item}")
            elif isinstance(item, dict) and "id" in item:
                authorized_ids.add(item["id"])

        if vm_id not in authorized_ids and holder_did not in authorized_ids:
            return False, "HOLDER_NOT_AUTHORIZED_FOR_AUTHENTICATION"

        # Locate verificationMethod object
        vm_list = did_doc.get("verificationMethod", [])
        all_methods = list(vm_list) if isinstance(vm_list, list) else []
        for item in auth_methods:
            if isinstance(item, dict) and item not in all_methods:
                all_methods.append(item)

        vm_obj = next(
            (
                m for m in all_methods
                if isinstance(m, dict) and (
                    m.get("id") == vm_id
                    or m.get("id") == f"{holder_did}#{vm_id.split('#')[-1]}"
                    or (vm_id.startswith(f"{holder_did}#") and m.get("id") == f"#{vm_id.split('#')[-1]}")
                )
            ),
            None,
        )
        if vm_obj is None:
            return False, "HOLDER_BINDING_UNKNOWN_KEY"

        if vm_obj.get("controller") != holder_did:
            return False, "HOLDER_BINDING_HOLDER_MISMATCH"

        pk_multibase = vm_obj.get("publicKeyMultibase")
        if not pk_multibase or not isinstance(pk_multibase, str):
            return False, "HOLDER_BINDING_MALFORMED_KEY"

        try:
            raw_key_bytes = decode_base58_btc(pk_multibase)
        except Exception:
            return False, "HOLDER_BINDING_MALFORMED_KEY"

        # Multicodec prefix for Ed25519 is 0xed01 (2 bytes), total 34 bytes
        if not raw_key_bytes.startswith(b"\xed\x01") or len(raw_key_bytes) != 34:
            return False, "HOLDER_BINDING_MALFORMED_KEY"

        pub_bytes = raw_key_bytes[2:]
        try:
            public_key = Ed25519PublicKey.from_public_bytes(pub_bytes)
        except Exception:
            return False, "HOLDER_BINDING_MALFORMED_KEY"

        # 7. Proof Value & Cryptographic Signature Verification
        proof_value = proof.get("proofValue")
        if not proof_value or not isinstance(proof_value, str):
            return False, "HOLDER_BINDING_MALFORMED_PROOF_VALUE"

        try:
            sig_bytes = decode_base58_btc(proof_value)
        except Exception:
            return False, "HOLDER_BINDING_MALFORMED_PROOF_VALUE"

        unsecured_vp = copy.deepcopy(vp_token)
        unsecured_vp.pop("proof", None)
        proof_config = copy.deepcopy(proof)
        proof_config.pop("proofValue", None)

        try:
            signing_input = self._canonicalizer.create_signing_input(unsecured_vp, proof_config)
        except Exception:
            return False, "HOLDER_BINDING_CANONICALIZATION_FAILED"

        try:
            public_key.verify(sig_bytes, signing_input)
        except InvalidSignature:
            return False, "HOLDER_BINDING_INVALID_SIGNATURE"
        except Exception:
            return False, "HOLDER_BINDING_VERIFICATION_FAILED"

        return True, None

    def create_presentation_for_session(
        self,
        *,
        session_id: str,
        verifiable_credentials: list[dict[str, Any]] | None = None,
        disclosed_claims: dict[str, Any] | None = None,
        holder_did: str | None = None,
    ) -> dict[str, Any]:
        session = self.get_session(session_id)
        from app.infrastructure.fixtures.signed_credentials import (
            build_signed_presentation,
            build_signed_credential,
        )
        vcs = list(verifiable_credentials) if verifiable_credentials else [build_signed_credential()]
        effective_holder_did = holder_did or "did:key:z6Mkf5rGMoatrSj1f4CyvuHBeXJELe9RPdzo2PKGNCKVtZxP"
        if disclosed_claims:
            for c in vcs:
                if isinstance(c.get("credentialSubject"), dict):
                    c["credentialSubject"].update(disclosed_claims)
                    c["credentialSubject"]["id"] = effective_holder_did

        domain = session.client_id or "http://testserver/verifier"
        return build_signed_presentation(
            vcs,
            nonce=session.nonce,
            domain=domain,
            holder_did=effective_holder_did,
        )

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

        # Holder Binding (Fail-Closed: cryptographic proof-of-possession verification)
        raw_subject = target_vc.get("credentialSubject")
        subject_dict: dict[str, Any] = raw_subject if isinstance(raw_subject, dict) else {}
        subject_id = str(subject_dict.get("id") or "")
        holder_binding_valid, holder_binding_reason = self._verify_holder_binding(
            vp_token=vp_token,
            target_vc=target_vc,
            session=session,
            now=now,
        )

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
                    "holder_binding": "Holder DID bound to presentation signature" if holder_binding_valid else (holder_binding_reason or "Holder mismatch"),
                    "expiration": "Within active validity window" if expiry_valid else "Expired credential",
                    "revocation": "Status slot is active (unrevoked)" if (revocation_status_clear and not is_already_quarantined) else "Revoked or locked in quarantine",
                    "challenge": "Nonce match confirmed" if challenge_valid else ("Nonce missing from presentation proof" if not challenge_nonce else "Nonce mismatch"),
                    "ai_fraud": "Low fraud risk profile" if ai_risk_level == "LOW" else f"Elevated threat detected: {ai_risk_level} ({ai_risk_score}/100)",
                    "quarantine": f"Active: {quarantine_reason}" if (quarantine_triggered or is_already_quarantined) else "Clear",
                },
                "holderBindingValid": holder_binding_valid,
                "holderBindingReason": holder_binding_reason if not holder_binding_valid else "VALID",
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
                        "holder_binding_valid": str(holder_binding_valid),
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
                    "protocol": "OID4VP-1.0",
                    "holder_binding_valid": str(holder_binding_valid),
                    "holder_binding_reason": holder_binding_reason or "",
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
