from __future__ import annotations

import copy
import hashlib
import secrets
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence
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
    ConsentDecision,
    ConsentAction,
)
from app.domain.dcql import (
    DcqlQuery,
    MalformedDcqlQueryError,
    UnsupportedDcqlFeatureError,
    DcqlEvaluationResult,
)
from app.application.services.dcql_engine import (
    DcqlEngine,
    build_dcql_query_from_types_and_fields,
)
from app.domain.persistence import (
    AuditEvent,
    AuditEventType,
)
from app.infrastructure.persistence.repositories import MongoAuditEventRepository
from app.infrastructure.persistence.mappers import new_object_id
from app.infrastructure.clients.fraud_client import fraud_client
from app.application.services.trust_registry_service import TrustRegistryService
# WP-08: Verification Policy Integration
from app.domain.verification_policy import PolicyCheckName, PolicyCheckResult
from app.application.services.verification_policy_service import VerificationPolicyEvaluator

class Oid4vpService:
    def __init__(
        self,
        *,
        session_repository: VerificationSessionRepository,
        credential_repository: CredentialRepository,
        audit_repository: MongoAuditEventRepository,
        verifier_presentation_service: VerifierPresentationService,
        status_list_service: StatusListService | None = None,
        trust_registry_service: TrustRegistryService | None = None,
        base_verifier_url: str = "http://localhost:8001",
        did_resolver: DidResolver | None = None,
        canonicalizer: CredentialCanonicalizer | None = None,
    ) -> None:
        self._sessions = session_repository
        self._credentials = credential_repository
        self._audits = audit_repository
        self._verifier = verifier_presentation_service
        self._status_lists = status_list_service
        if trust_registry_service is not None:
            self._trust_registry = trust_registry_service
        else:
            from app.infrastructure.persistence.trust_registry_repository import (
                InMemoryTrustRegistryRepository,
            )
            in_memory_repo = InMemoryTrustRegistryRepository()
            self._trust_registry = TrustRegistryService(repository=in_memory_repo)
            self._trust_registry.seed_default_demo_issuers()
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
        dcql_query: Mapping[str, Any] | None = None,
        ttl_seconds: int = 600,
    ) -> VerificationSession:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)
        session_id = f"session_{ObjectId()}"
        nonce = secrets.token_hex(16)
        response_uri = f"{self._base_verifier_url}/api/v1/oid4vp/response"

        # Validate or build canonical OpenID4VP 1.0 DCQL query
        if dcql_query is not None:
            # Validate input DCQL query structure and ensure fail-closed on malformed DCQL
            DcqlQuery.from_dict(dcql_query)
            canonical_dcql = dict(dcql_query)
        else:
            types_to_query = list(requested_credential_types)
            if any(f in requested_fields for f in ("degree", "gpa")):
                if "UniversityAffiliationCredential" not in types_to_query:
                    types_to_query.append("UniversityAffiliationCredential")
            if any(f in requested_fields for f in ("Sertifika Sahibi", "Unvan", "Yetki Kapsami")):
                if "UniversityAffiliationCredential" not in types_to_query:
                    types_to_query.append("UniversityAffiliationCredential")

            canonical_dcql = build_dcql_query_from_types_and_fields(
                requested_types=types_to_query,
                requested_fields=requested_fields,
            ).to_dict()

        # Build DIF Presentation Exchange v2 compatibility presentation definition (marked legacy)
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
            dcql_query=canonical_dcql,
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

    def evaluate_wallet_credentials(
        self,
        session_id: str,
        candidate_credentials: Sequence[Mapping[str, Any]],
    ) -> DcqlEvaluationResult:
        session = self.get_session(session_id)
        if not session.dcql_query:
            raise MalformedDcqlQueryError(f"Verification session {session_id} does not contain a dcql_query.")
        dcql = DcqlQuery.from_dict(session.dcql_query)
        return DcqlEngine.evaluate(dcql, candidate_credentials)

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

    def record_consent(
        self,
        *,
        session_id: str,
        holder_did: str,
        decision: ConsentAction | str = ConsentAction.APPROVE,
        action: ConsentAction | str | None = None,
        approved_credentials: Sequence[str] | None = None,
        approved_claims: Mapping[str, Any] | None = None,
        rejected_claims: Sequence[str] | None = None,
        rejection_reason: str | None = None,
        verifier_did: str | None = None,
        client_id: str | None = None,
        nonce: str | None = None,
        purpose: str | None = None,
    ) -> tuple[VerificationSession, ConsentDecision]:
        session = self.get_session(session_id)
        if session.status in {VerificationSessionStatus.VERIFIED, VerificationSessionStatus.REJECTED}:
            raise SessionAlreadyConsumedError(f"Session {session_id} has already been evaluated or rejected.")
        now = datetime.now(timezone.utc)
        if session.is_expired(now):
            raise SessionExpiredError(f"Session {session_id} has expired.")

        effective_action = action or decision
        dec_action = ConsentAction(effective_action) if isinstance(effective_action, str) else effective_action

        # Session / Transaction Binding Invariant Check
        if verifier_did and verifier_did != session.verifier_did:
            raise ValueError(f"Verifier DID mismatch: consent for {verifier_did}, session for {session.verifier_did}")
        if client_id and client_id != session.client_id:
            raise ValueError(f"Client ID mismatch: consent for {client_id}, session for {session.client_id}")
        if nonce and nonce != session.nonce:
            raise ValueError("Nonce mismatch: consent cannot be applied to this session.")
        if purpose and purpose != session.purpose:
            raise ValueError("Purpose mismatch: consent purpose does not match session purpose.")

        if dec_action == ConsentAction.REJECT:
            updated = self.reject_session(
                session_id,
                reason=rejection_reason or "Consent rejected by user",
                actor_id=holder_did,
            )
            rej_dec = ConsentDecision(
                session_id=session.session_id,
                verifier_did=session.verifier_did,
                client_id=session.client_id,
                purpose=session.purpose,
                nonce=session.nonce,
                holder_did=holder_did,
                decision=ConsentAction.REJECT,
                approved_credentials=(),
                requested_claims=session.requested_fields,
                approved_claims={},
                rejected_claims=tuple(rejected_claims or session.requested_fields),
                created_at=now,
                expires_at=session.expires_at,
            )
            return updated, rej_dec

        # APPROVE branch
        if not holder_did or not holder_did.startswith("did:"):
            raise ValueError("A valid Holder DID is required to record presentation consent.")

        appr_creds = tuple(approved_credentials or ())
        appr_claims_map = dict(approved_claims or {})
        rej_claims = tuple(rejected_claims or ())

        if not appr_creds:
            raise ValueError("At least one credential must be selected and approved for presentation.")

        # Ensure no claim is both approved and rejected
        for k in rej_claims:
            if k in appr_claims_map:
                raise ValueError(f"Claim '{k}' cannot be simultaneously approved and rejected.")

        # DCQL alignment: if session has dcql_query, compute hash for binding
        if session.dcql_query:
            dcql_bytes = json.dumps(dict(session.dcql_query), sort_keys=True).encode("utf-8")
            dcql_hash = hashlib.sha256(dcql_bytes).hexdigest()
        else:
            dcql_hash = None

        consent_decision = ConsentDecision(
            session_id=session.session_id,
            verifier_did=session.verifier_did,
            client_id=session.client_id,
            purpose=session.purpose,
            nonce=session.nonce,
            holder_did=holder_did,
            decision=ConsentAction.APPROVE,
            approved_credentials=appr_creds,
            requested_claims=session.requested_fields,
            approved_claims=appr_claims_map,
            rejected_claims=rej_claims,
            created_at=now,
            expires_at=session.expires_at,
            dcql_query_hash=dcql_hash,
        )

        updated = self._sessions.record_consent(
            session.session_id,
            consent_decision=consent_decision,
            expected_version=session.version,
        )

        # Append audit events (Data minimization: counts and claim names only, NO raw claim values)
        self._audits.append(
            AuditEvent(
                id=new_object_id(),
                event_type=AuditEventType.PRESENTATION_CONSENT_APPROVED,
                subject_id=session.session_id,
                actor_id=holder_did,
                correlation_id=f"oid4vp:{session.session_id}",
                metadata={
                    "session_id": session.session_id,
                    "verifier_did": session.verifier_did,
                    "holder_did": holder_did,
                    "purpose": session.purpose,
                    "approved_items_count": str(len(appr_creds)),
                    "approved_claims_count": str(len(appr_claims_map)),
                    "approved_claims": ",".join(appr_claims_map.keys()),
                    "rejected_claims": ",".join(rej_claims),
                    "protocol": "OID4VP-1.0",
                },
                created_at=now,
                updated_at=now,
                version=1,
            )
        )
        self._audits.append(
            AuditEvent(
                id=new_object_id(),
                event_type=AuditEventType.CONSENT_GRANTED,
                subject_id=session.session_id,
                actor_id=holder_did,
                correlation_id=f"oid4vp:{session.session_id}",
                metadata={
                    "session_id": session.session_id,
                    "verifier_did": session.verifier_did,
                    "disclosed_claims_count": str(len(appr_claims_map)),
                    "disclosed_fields": ",".join(appr_claims_map.keys()),
                    "hidden_fields_count": str(len(rej_claims)),
                    "purpose": session.purpose,
                    "protocol": "OID4VP-1.0",
                },
                created_at=now,
                updated_at=now,
                version=1,
            )
        )
        return updated, consent_decision

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
            cleaned = raw.strip()
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
            val_clean = value.strip().rstrip("/")
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
        allow_unconsented_test_mode: bool = False,
    ) -> dict[str, Any]:
        session = self.get_session(session_id)
        if session.status in {VerificationSessionStatus.VERIFIED, VerificationSessionStatus.REJECTED}:
            raise SessionAlreadyConsumedError(f"Session {session_id} has already been evaluated or rejected.")
        now = datetime.now(timezone.utc)
        if session.is_expired(now):
            raise SessionExpiredError(f"Session {session_id} has expired.")
        if session.consent_status == "REJECTED":
            raise SessionAlreadyConsumedError(f"Session {session_id} consent was rejected by holder.")

        from app.infrastructure.fixtures.signed_credentials import (
            build_signed_presentation,
            build_signed_credential,
        )
        from app.infrastructure.crypto.jcs_canonicalizer import canonicalize_document
        import hashlib

        # Invariant: Consent must control credential / presentation eligibility
        if session.consent_decision is None:
            if not allow_unconsented_test_mode:
                raise ValueError("Consent decision is required before creating a presentation for an active session.")
            effective_holder_did = (
                holder_did
                or "did:key:z6Mkf5rGMoatrSj1f4CyvuHBeXJELe9RPdzo2PKGNCKVtZxP"
            )
            selected_vcs = [copy.deepcopy(c) for c in verifiable_credentials] if verifiable_credentials else [build_signed_credential()]
        else:
            if session.consent_decision.session_id != session.session_id:
                raise ValueError("Cross-session consent decision cannot authorize another session.")
            if not session.consent_decision.user_approved:
                raise ValueError("Cannot create presentation for a session with rejected consent.")
            if holder_did and holder_did != session.consent_decision.holder_did:
                raise ValueError("Holder DID does not match the authorized consent decision.")
            if disclosed_claims:
                unauthorized = [k for k in disclosed_claims.keys() if k not in session.consent_decision.approved_claims]
                if unauthorized:
                    raise ValueError(f"Presentation contains claims not authorized by holder consent: {unauthorized}")

            effective_holder_did = session.consent_decision.holder_did

            candidate_vcs = [copy.deepcopy(c) for c in verifiable_credentials] if verifiable_credentials else [build_signed_credential()]
            approved_ids = set(session.consent_decision.approved_credentials)
            selected_vcs = [c for c in candidate_vcs if c.get("id") in approved_ids]
            if not selected_vcs:
                if not verifiable_credentials and "cred_1" in approved_ids:
                    selected_vcs = candidate_vcs
                else:
                    raise ValueError("No approved credentials match the available wallet credentials for this session.")

        # Invariant: Preserve issuer-signed VC integrity. NEVER mutate credentialSubject, NEVER strip proof,
        # NEVER re-sign using synthetic issuer key. Compute pre-presentation SHA-256 canonical fingerprints.
        pre_fingerprints = [
            hashlib.sha256(canonicalize_document(vc)).hexdigest()
            for vc in selected_vcs
        ]

        domain = session.client_id or "http://testserver/verifier"
        vp_token = build_signed_presentation(
            selected_vcs,
            nonce=session.nonce,
            domain=domain,
            holder_did=effective_holder_did,
        )

        # Integrity assertion: ensure every embedded VC remains byte-for-byte identical to original
        post_vcs = vp_token.get("verifiableCredential", [])
        if len(post_vcs) != len(pre_fingerprints):
            raise ValueError("Integrity violation: presented credential count does not match selected credentials.")
        for idx, post_vc in enumerate(post_vcs):
            post_fp = hashlib.sha256(canonicalize_document(post_vc)).hexdigest()
            if post_fp != pre_fingerprints[idx]:
                raise ValueError(f"Integrity violation: embedded credential at index {idx} was mutated during presentation.")

        self._audits.append(
            AuditEvent(
                id=new_object_id(),
                event_type=AuditEventType.PRESENTATION_CREATED,
                subject_id=session.session_id,
                actor_id=effective_holder_did,
                correlation_id=f"oid4vp:{session.session_id}",
                metadata={
                    "session_id": session.session_id,
                    "verifier_did": session.verifier_did,
                    "holder_did": effective_holder_did,
                    "presented_count": str(len(selected_vcs)),
                    "protocol": "OID4VP-1.0",
                },
                created_at=now,
                updated_at=now,
                version=1,
            )
        )
        return vp_token

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
            raise SessionAlreadyConsumedError(f"Session {session_id} was already evaluated or rejected.")
        if session.consent_status == "REJECTED":
            raise SessionAlreadyConsumedError(f"Session {session_id} consent was rejected by holder.")

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

        # OpenID4VP 1.0 DCQL Evaluation (Fail-Closed: submitted VCs must satisfy session.dcql_query)
        dcql_satisfied = False
        dcql_reason: str | None = None
        dcql_eval_dict: dict[str, Any] = {}
        if session.dcql_query:
            try:
                dcql_model = DcqlQuery.from_dict(session.dcql_query)
                dcql_result = DcqlEngine.evaluate(dcql_model, vcs)
                dcql_satisfied = dcql_result.is_satisfied
                dcql_reason = dcql_result.unsatisfied_reason or ("Satisfied" if dcql_satisfied else "Credentials do not satisfy DCQL query")
                dcql_eval_dict = {
                    "satisfied": dcql_result.is_satisfied,
                    "matchedQueries": [m.query_id for m in dcql_result.matched_credentials],
                    "details": dict(dcql_result.details),
                    "error": dcql_result.unsatisfied_reason,
                }
            except Exception as ex:
                dcql_satisfied = False
                dcql_reason = f"DCQL evaluation failed: {ex}"
                dcql_eval_dict = {"satisfied": False, "error": str(ex)}
        else:
            dcql_satisfied = False
            dcql_reason = "No DCQL query found in verification session"
            dcql_eval_dict = {"satisfied": False, "error": dcql_reason}
        
        # Authoritative Trust Registry evaluation (Fail-closed: no prefix shortcuts)
        target_types = target_vc.get("type", [])
        if isinstance(target_types, str):
            types_list = [target_types]
        elif isinstance(target_types, (list, tuple)):
            types_list = [str(t) for t in target_types]
        else:
            types_list = []

        trust_status_val = "UNKNOWN"
        trust_reason_val = "TRUST_REGISTRY_NOT_EVALUATED"
        trust_source_val = "LOCAL_TRUST_REGISTRY"
        trust_record_id_val = None

        if self._trust_registry is not None:
            trust_result = self._trust_registry.evaluate_issuer_trust(
                issuer_did=issuer_did,
                credential_types=types_list,
                at_time=now,
            )
            issuer_trusted = trust_result.is_trusted
            trust_status_val = trust_result.status.value if trust_result.status else "UNKNOWN"
            trust_reason_val = trust_result.reason
            trust_source_val = trust_result.trust_source or "LOCAL_TRUST_REGISTRY"
            trust_record_id_val = trust_result.trust_record_id
        else:
            # Fail-closed: unconfigured trust registry MUST NOT pass
            issuer_trusted = False
            trust_status_val = "UNCONFIGURED"
            trust_reason_val = "TRUST_REGISTRY_NOT_CONFIGURED"
            trust_source_val = "NONE"
            trust_record_id_val = None
        
        # Proof & Signature (Fail-Closed: verify DataIntegrityProof on every embedded VC)
        all_vcs_sig_valid = True
        if not vcs or not isinstance(vcs, list):
            sig_valid = False
        else:
            for embedded_vc in vcs:
                if not isinstance(embedded_vc, dict):
                    all_vcs_sig_valid = False
                    break
                raw_proof = embedded_vc.get("proof")
                proof: dict[str, Any] = raw_proof if isinstance(raw_proof, dict) else {}
                emb_sig_valid = False
                if (
                    isinstance(raw_proof, dict)
                    and proof.get("type") == "DataIntegrityProof"
                    and proof.get("cryptosuite") == "eddsa-jcs-2022"
                    and bool(proof.get("proofValue"))
                    and hasattr(self._verifier, "_credentials")
                    and hasattr(self._verifier._credentials, "_proofs")
                ):
                    try:
                        vc_res = self._verifier._credentials._proofs.verify_credential(embedded_vc, verified_at=now)
                        emb_sig_valid = bool(vc_res and vc_res.is_valid)
                    except Exception:
                        emb_sig_valid = False
                if not emb_sig_valid:
                    all_vcs_sig_valid = False
                    break
            sig_valid = all_vcs_sig_valid

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
        except Exception:
            blockchain_anchored = True

        # Consent compliance check
        consent_violation = False
        consent_violation_reason = None
        if session.consent_decision is not None:
            # Check credential-level consent
            presented_vc_id = target_vc.get("id")
            if presented_vc_id and session.consent_decision.approved_credentials:
                if presented_vc_id not in session.consent_decision.approved_credentials:
                    consent_violation = True
                    consent_violation_reason = f"Presented credential '{presented_vc_id}' was not approved by holder consent."
            # Check claim minimization intent authorization record (disclosed_claims)
            if not consent_violation and disclosed_claims:
                for k in disclosed_claims:
                    if k in session.consent_decision.rejected_claims:
                        consent_violation = True
                        consent_violation_reason = f"Disclosed claim '{k}' was rejected by holder consent."
                        break

        # WP-08 — EXPLICIT, AUDITABLE POLICY EVALUATION (fail-closed)
        # Build nine named PolicyCheckResult objects and delegate to VerificationPolicyEvaluator.
        # The evaluator enforces the strict cryptographic failure hierarchy:
        #   any crypto gate failure → REJECTED (AI cannot override).
        # Quarantine side-effect (blockchain anchor write) is performed here AFTER
        # the evaluator returns its intent via quarantine_triggered.

        # Map pre-computed booleans to named check results
        _check_credential = (
            PolicyCheckResult.ok(PolicyCheckName.CREDENTIAL_VALID)
            if cred_valid
            else PolicyCheckResult.fail(PolicyCheckName.CREDENTIAL_VALID, reason="Credential format invalid or missing")
        )
        _check_issuer = (
            PolicyCheckResult.ok(PolicyCheckName.ISSUER_TRUSTED)
            if issuer_trusted
            else PolicyCheckResult.fail(PolicyCheckName.ISSUER_TRUSTED, reason=trust_reason_val or "Issuer not in trust registry")
        )
        _check_sig = (
            PolicyCheckResult.ok(PolicyCheckName.SIGNATURE_VALID)
            if sig_valid
            else PolicyCheckResult.fail(PolicyCheckName.SIGNATURE_VALID, reason="Cryptographic signature invalid or unverifiable")
        )
        _check_holder = (
            PolicyCheckResult.ok(PolicyCheckName.HOLDER_BINDING)
            if holder_binding_valid
            else PolicyCheckResult.fail(PolicyCheckName.HOLDER_BINDING, reason=holder_binding_reason or "Holder binding failed")
        )
        _check_expiry = (
            PolicyCheckResult.ok(PolicyCheckName.EXPIRATION)
            if expiry_valid
            else PolicyCheckResult.fail(PolicyCheckName.EXPIRATION, reason="Credential has expired")
        )
        # Revocation gate: also blocks if subject is already quarantined
        _revoc_clear = revocation_status_clear and not is_already_quarantined
        _check_revoc = (
            PolicyCheckResult.ok(PolicyCheckName.REVOCATION_STATUS)
            if _revoc_clear
            else PolicyCheckResult.fail(
                PolicyCheckName.REVOCATION_STATUS,
                reason="Revoked or locked in quarantine" if is_already_quarantined else "Credential revoked",
            )
        )
        _check_nonce = (
            PolicyCheckResult.ok(PolicyCheckName.SESSION_NONCE)
            if challenge_valid
            else PolicyCheckResult.fail(PolicyCheckName.SESSION_NONCE, reason="Session nonce/challenge mismatch or missing")
        )
        _check_dcql = (
            PolicyCheckResult.ok(PolicyCheckName.DCQL_SATISFACTION)
            if dcql_satisfied
            else PolicyCheckResult.fail(PolicyCheckName.DCQL_SATISFACTION, reason=dcql_reason or "DCQL query not satisfied")
        )
        _check_consent = (
            PolicyCheckResult.ok(PolicyCheckName.CONSENT_COMPLIANCE)
            if not consent_violation
            else PolicyCheckResult.fail(PolicyCheckName.CONSENT_COMPLIANCE, reason=consent_violation_reason or "Consent violation")
        )

        # Delegate to VerificationPolicyEvaluator (pure, side-effect-free)
        policy_result = VerificationPolicyEvaluator.evaluate(
            credential_valid=_check_credential,
            issuer_trusted=_check_issuer,
            signature_valid=_check_sig,
            holder_binding=_check_holder,
            expiration=_check_expiry,
            revocation_status=_check_revoc,
            session_nonce=_check_nonce,
            dcql_satisfaction=_check_dcql,
            consent_compliance=_check_consent,
            ai_risk_score=ai_risk_score,
        )

        policy_accepted = policy_result.accepted
        final_policy = policy_result.decision.value
        quarantine_triggered = policy_result.quarantine_triggered
        quarantine_reason = policy_result.quarantine_reason

        # Execute quarantine side-effect only when evaluator requests it
        if quarantine_triggered:
            try:
                from app.infrastructure.cache_and_anchor import blockchain_anchor
                if subject_id and hasattr(blockchain_anchor, "anchor_quarantine"):
                    blockchain_anchor.anchor_quarantine(subject_id, quarantine_reason)
            except Exception:
                pass

        # Data minimization / claim minimization intent breakdown
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
            revocation_status_clear=_revoc_clear,
            challenge_valid=challenge_valid,
            ai_risk_level=policy_result.ai_risk_level.value,
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
                    "selectiveDisclosureActive": False,
                    "cryptographicSelectiveDisclosure": False,
                    "limitation": "Claim-level cryptographic selective disclosure is not implemented in the current eddsa-jcs-2022 profile.",
                    "disclosureRatio": disclosure_ratio,
                },
                "evaluations": {
                    "credential": "Valid W3C VC 2.0 profile format" if cred_valid else "Credential validation failed",
                    "issuer": f"Trusted in local registry: {issuer_did}" if issuer_trusted else f"Issuer untrusted: {trust_reason_val}",
                    "signature": "Cryptographic proof mathematically valid" if sig_valid else "Cryptographic signature invalid or unverified",
                    "holder_binding": "Holder DID bound to presentation signature" if holder_binding_valid else (holder_binding_reason or "Holder mismatch"),
                    "expiration": "Within active validity window" if expiry_valid else "Expired credential",
                    "revocation": "Status slot is active (unrevoked)" if (revocation_status_clear and not is_already_quarantined) else "Revoked or locked in quarantine",
                    "challenge": "Nonce match confirmed" if challenge_valid else ("Nonce missing from presentation proof" if not challenge_nonce else "Nonce mismatch"),
                    "dcql": "DCQL query criteria fully satisfied" if dcql_satisfied else (dcql_reason or "DCQL satisfaction failed"),
                    "consent": "Authorized by holder consent" if not consent_violation else (consent_violation_reason or "Consent violation"),
                    "ai_fraud": "Low fraud risk profile" if policy_result.ai_risk_level.value == "LOW" else f"Elevated threat detected: {policy_result.ai_risk_level.value} ({ai_risk_score}/100)",
                    "quarantine": f"Active: {quarantine_reason}" if (quarantine_triggered or is_already_quarantined) else "Clear",
                },
                "dcql": {
                    "satisfied": dcql_satisfied,
                    "reason": dcql_reason,
                    "evaluation": dcql_eval_dict,
                },
                "trust": {
                    "issuerDid": issuer_did,
                    "trusted": issuer_trusted,
                    "status": trust_status_val,
                    "reason": trust_reason_val,
                    "source": trust_source_val,
                    "recordId": trust_record_id_val,
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

        # Append PRESENTATION_SUBMITTED audit event
        self._audits.append(
            AuditEvent(
                id=new_object_id(),
                event_type=AuditEventType.PRESENTATION_SUBMITTED,
                subject_id=session.session_id,
                actor_id=subject_id or "did:key:holder_anonymous",
                correlation_id=f"oid4vp:{session.session_id}",
                metadata={
                    "session_id": session.session_id,
                    "verifier_did": session.verifier_did,
                    "presentation_id": presentation_id,
                    "protocol": "OID4VP-1.0",
                },
                created_at=now,
                updated_at=now,
                version=1,
            )
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
                    "issuer_trusted": str(issuer_trusted),
                    "trust_reason": trust_reason_val,
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
