from __future__ import annotations

import copy
import hashlib
import logging
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
from app.infrastructure.clients.fraud_client import (
    FraudRiskUnavailableError,
    fraud_client,
)
from app.application.services.trust_registry_service import TrustRegistryService
# WP-08: Verification Policy Integration
from app.domain.verification_policy import PolicyCheckName, PolicyCheckResult
from app.application.services.verification_policy_service import VerificationPolicyEvaluator

logger = logging.getLogger(__name__)


def _read_quarantine_status(
    quarantine_service: Any,
    subject_id: str | None,
) -> tuple[bool | None, str | None]:
    """Return an indeterminate state instead of treating lookup errors as clear."""
    if not subject_id:
        return False, None
    if quarantine_service is None:
        return None, "QUARANTINE_LOOKUP_UNAVAILABLE"

    lookup = getattr(quarantine_service, "is_quarantined", None)
    if not callable(lookup):
        return None, "QUARANTINE_LOOKUP_UNAVAILABLE"
    try:
        quarantined = lookup(subject_id)
    except Exception as error:
        logger.warning(
            "Quarantine status lookup failed (%s)", type(error).__name__
        )
        return None, f"QUARANTINE_LOOKUP_FAILED:{type(error).__name__}"
    if type(quarantined) is not bool:
        logger.warning("Quarantine status lookup returned an invalid result")
        return None, "QUARANTINE_LOOKUP_INVALID_RESULT"
    return quarantined, None


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
        self._trust_registry = trust_registry_service
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
        owner_user_id: str | None = None,
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
            canonical_dcql = build_dcql_query_from_types_and_fields(
                requested_types=requested_credential_types,
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
            owner_user_id=owner_user_id,
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
        if (
            session.status == VerificationSessionStatus.PENDING
            and session.is_expired(now)
        ):
            raise SessionExpiredError(f"Verification session {session_id} has expired.")
        return session

    def get_session_for_owner(
        self,
        session_id: str,
        *,
        owner_user_id: str,
    ) -> VerificationSession:
        """Return verifier-private session state only to its creator.

        Existing records without an owner are deliberately inaccessible through
        this method; callers must use the Holder request view for protocol input.
        """
        session = self._sessions.get_by_session_id(session_id)
        if (
            session is None
            or session.owner_user_id is None
            or session.owner_user_id != owner_user_id
        ):
            # Conceal both existence and ownership from non-owners.
            raise SessionNotFoundError("Verification session not found.")
        now = datetime.now(timezone.utc)
        if session.status == VerificationSessionStatus.PENDING and session.is_expired(now):
            raise SessionExpiredError(f"Verification session {session_id} has expired.")
        return session

    def list_sessions_for_owner(
        self,
        *,
        owner_user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[VerificationSession, ...]:
        """List only sessions created by the authenticated verifier principal."""
        if not owner_user_id or len(owner_user_id) > 200:
            raise ValueError("Verification session owner is invalid.")
        if not 1 <= limit <= 101 or not 0 <= offset <= 10_000:
            raise ValueError("Verification session pagination is out of range.")
        return self._sessions.list_by_owner(
            owner_user_id,
            limit=limit,
            skip=offset,
        )

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

        # Keep consent evidence distinct from credential disclosure. This profile
        # sends a complete signed credential and does not provide claim-level
        # cryptographic selective disclosure.
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
                    "approved_field_count": str(len(appr_claims_map)),
                    "rejected_field_count": str(len(rej_claims)),
                    "disclosure_profile": "FULL_SIGNED_VC",
                    "selective_disclosure_supported": "false",
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
                    "approved_field_count": str(len(appr_claims_map)),
                    "rejected_field_count": str(len(rej_claims)),
                    "disclosure_profile": "FULL_SIGNED_VC",
                    "selective_disclosure_supported": "false",
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

    def _verify_status_list_credential(
        self,
        *,
        status_doc: Any,
        expected_status_list_url: str,
        expected_issuer: str,
        expected_purpose: str,
        expected_list_length: int,
        verified_at: datetime,
    ) -> tuple[bool, str | None, str | None]:
        from collections.abc import Mapping
        from pydantic import ValidationError
        from app.schemas.status_list_api import (
            BitstringStatusListCredentialResponse,
        )

        if not isinstance(status_doc, Mapping):
            return False, "STATUS_LIST_CREDENTIAL_MALFORMED", None

        raw_proof = status_doc.get("proof")
        if not isinstance(raw_proof, Mapping):
            return False, "STATUS_LIST_PROOF_MISSING", None
        if raw_proof.get("type") != "DataIntegrityProof":
            return False, "STATUS_LIST_PROOF_UNSUPPORTED_TYPE", None

        try:
            credential = BitstringStatusListCredentialResponse.model_validate(
                dict(status_doc)
            )
        except ValidationError:
            return False, "STATUS_LIST_CREDENTIAL_MALFORMED", None

        if (
            "VerifiableCredential" not in credential.type
            or "BitstringStatusListCredential" not in credential.type
        ):
            return False, "STATUS_LIST_CREDENTIAL_UNSUPPORTED_TYPE", None
        if credential.issuer != expected_issuer:
            return False, "STATUS_LIST_ISSUER_MISMATCH_WITH_PUBLICATION", None
        if credential.id != expected_status_list_url:
            return False, "STATUS_LIST_CREDENTIAL_ID_MISMATCH", None
        if credential.credentialSubject.statusPurpose != expected_purpose:
            return False, "STATUS_LIST_PURPOSE_MISMATCH", None

        proof_service = self._verifier._credentials._proofs
        try:
            proof_valid, proof_error = proof_service.verify_data_integrity_document(
                credential.model_dump(by_alias=True),
                verified_at=verified_at,
            )
        except Exception as error:
            logger.warning(
                "Status-list proof verification failed (%s)",
                type(error).__name__,
            )
            return (
                False,
                f"STATUS_LIST_PROOF_VERIFICATION_ERROR:{type(error).__name__}",
                None,
            )
        if not proof_valid:
            return False, f"STATUS_LIST_PROOF_INVALID:{proof_error}", None

        if self._trust_registry is None:
            return False, "STATUS_LIST_TRUST_REGISTRY_UNCONFIGURED", None
        try:
            trust_result = self._trust_registry.evaluate_issuer_trust(
                issuer_did=credential.issuer,
                at_time=verified_at,
            )
        except Exception as error:
            logger.warning(
                "Status-list Trust Registry lookup failed (%s)",
                type(error).__name__,
            )
            return (
                False,
                f"STATUS_LIST_TRUST_REGISTRY_ERROR:{type(error).__name__}",
                None,
            )
        trust_is_valid = getattr(trust_result, "is_trusted", None)
        if type(trust_is_valid) is not bool:
            logger.warning(
                "Status-list Trust Registry returned an invalid result"
            )
            return False, "STATUS_LIST_TRUST_REGISTRY_INVALID_RESULT", None
        if not trust_is_valid:
            trust_reason = getattr(trust_result, "reason", None)
            return (
                False,
                "STATUS_LIST_ISSUER_NOT_TRUSTED:"
                f"{trust_reason if isinstance(trust_reason, str) else 'UNTRUSTED'}",
                None,
            )

        try:
            valid_from = proof_service.validator._parse_timestamp(
                credential.validFrom
            )
        except Exception:
            return False, "STATUS_LIST_VALID_FROM_INVALID", None
        if valid_from > verified_at:
            return False, "STATUS_LIST_NOT_YET_VALID", None

        try:
            from app.infrastructure.status_list_document_generator import (
                decompress_status_list,
            )

            decoded_list = decompress_status_list(
                credential.credentialSubject.encodedList
            )
        except Exception as error:
            return (
                False,
                f"STATUS_LIST_ENCODED_LIST_INVALID:{type(error).__name__}",
                None,
            )
        if len(decoded_list) * 8 != expected_list_length:
            return False, "STATUS_LIST_LENGTH_MISMATCH", None

        return True, None, credential.credentialSubject.encodedList

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

    def _evaluate_credential_status(
        self,
        credential: Mapping[str, Any],
        *,
        verified_at: datetime,
    ) -> tuple[bool, str | None, bool]:
        """Evaluate authoritative and Bitstring status for one embedded VC."""
        credential_id = str(credential.get("id") or "")
        status_clear = True
        status_reason: str | None = None
        status_evaluated = False

        persisted = None
        if self._credentials and credential_id:
            try:
                persisted = self._credentials.get_by_credential_id(credential_id)
            except Exception as error:
                logger.warning(
                    "Credential status persistence lookup failed (%s)",
                    type(error).__name__,
                )
                status_clear = False
                status_reason = (
                    "Credential status persistence unavailable: "
                    f"{type(error).__name__}"
                )
        if persisted:
            status_evaluated = True
            persisted_status = (
                persisted.status.value
                if hasattr(persisted.status, "value")
                else getattr(persisted.status, "name", str(persisted.status))
            )
            if persisted_status == "REVOKED":
                status_clear = False
                status_reason = "Credential revoked in persistence"
            elif persisted_status == "SUSPENDED":
                status_clear = False
                status_reason = "Credential suspended in persistence"
            elif persisted_status != "ACTIVE":
                status_clear = False
                status_reason = (
                    f"Credential status not active: {persisted_status}"
                )

        credential_status = credential.get("credentialStatus")
        if credential_status is None:
            return status_clear, status_reason, status_evaluated

        status_evaluated = True
        if isinstance(credential_status, dict):
            entries = [credential_status]
        elif isinstance(credential_status, list):
            entries = credential_status
            if not entries:
                status_clear = False
                status_reason = (
                    "credentialStatus must contain at least one status entry"
                )
        else:
            status_clear = False
            status_reason = "credentialStatus is invalid format"
            entries = []

        for entry in entries:
            if not isinstance(entry, dict):
                status_clear = False
                status_reason = "credentialStatus entry is not an object"
                break
            if entry.get("type") != "BitstringStatusListEntry":
                status_clear = False
                status_reason = (
                    "credentialStatus entry type is unsupported or missing"
                )
                break

            purpose = entry.get("statusPurpose")
            if purpose not in ("revocation", "suspension"):
                status_clear = False
                status_reason = (
                    f"Unsupported or malformed statusPurpose: {purpose}"
                )
                break

            list_url = str(entry.get("statusListCredential", ""))
            list_id = list_url.rstrip("/").split("/")[-1] if list_url else ""
            index_raw = entry.get("statusListIndex")
            if not list_id or index_raw is None:
                status_clear = False
                status_reason = (
                    "credentialStatus missing required statusListCredential or statusListIndex"
                )
                break
            if (
                not isinstance(index_raw, str)
                or not index_raw.isascii()
                or not index_raw.isdecimal()
                or len(index_raw) > 8
                or (len(index_raw) > 1 and index_raw.startswith("0"))
            ):
                status_clear = False
                status_reason = "statusListIndex is invalid"
                break
            index = int(index_raw)
            if self._status_lists is None:
                status_clear = False
                status_reason = "Status list service unavailable"
                break
            try:
                publication = self._status_lists.get_publication(list_id)
            except Exception as error:
                logger.warning(
                    "Status-list resolution failed (%s)", type(error).__name__
                )
                status_clear = False
                status_reason = (
                    f"Status service resolution failed: {type(error).__name__}"
                )
                break

            status_doc = getattr(publication, "document", None)
            if not status_doc:
                status_clear = False
                status_reason = (
                    "Status list credential document missing from publication"
                )
                break
            publication_id = getattr(publication, "status_list_id", None)
            publication_issuer = getattr(publication, "issuer_did", None)
            publication_purpose = getattr(
                getattr(publication, "status_purpose", None),
                "value",
                getattr(publication, "status_purpose", None),
            )
            list_length = getattr(publication, "list_length", None)
            if publication_id != list_id:
                status_clear = False
                status_reason = "Status list publication identifier mismatch"
                break
            if publication_purpose != purpose:
                status_clear = False
                status_reason = "Status list publication purpose mismatch"
                break
            if not isinstance(publication_issuer, str) or not publication_issuer:
                status_clear = False
                status_reason = "Status list publication issuer is invalid"
                break
            if not isinstance(list_length, int) or index >= list_length:
                status_clear = False
                status_reason = "statusListIndex is outside the published list"
                break

            valid_list, list_error, encoded_list = (
                self._verify_status_list_credential(
                    status_doc=status_doc,
                    expected_status_list_url=list_url,
                    expected_issuer=publication_issuer,
                    expected_purpose=purpose,
                    expected_list_length=list_length,
                    verified_at=verified_at,
                )
            )
            if not valid_list or not encoded_list:
                status_clear = False
                if list_error and "PROOF" in list_error:
                    status_reason = (
                        f"Status list proof validation failed: {list_error}"
                    )
                else:
                    status_reason = (
                        f"Status list credential validation failed: {list_error}"
                    )
                break
            try:
                from app.infrastructure.status_list_document_generator import (
                    decode_status_list_bit,
                )

                is_set = decode_status_list_bit(encoded_list, index)
            except Exception as error:
                status_clear = False
                status_reason = (
                    f"Failed to decode status bit: {type(error).__name__}"
                )
                break
            if is_set:
                status_clear = False
                status_reason = (
                    "Credential revoked (status bit set)"
                    if purpose == "revocation"
                    else "Credential suspended (status bit set)"
                )
                break

        return status_clear, status_reason, status_evaluated

    def process_direct_post(
        self,
        *,
        session_id: str,
        vp_token: dict[str, Any],
        disclosed_claims: dict[str, Any] | None = None,
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
        cred_valid = (
            isinstance(vcs, list)
            and bool(vcs)
            and all(isinstance(credential, dict) for credential in vcs)
        )
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
            try:
                trust_result = self._trust_registry.evaluate_issuer_trust(
                    issuer_did=issuer_did,
                    credential_types=types_list,
                    at_time=now,
                )
            except Exception as error:
                logger.warning(
                    "Issuer Trust Registry lookup failed (%s)",
                    type(error).__name__,
                )
                issuer_trusted = False
                trust_status_val = "ERROR"
                trust_reason_val = (
                    f"TRUST_REGISTRY_UNAVAILABLE:{type(error).__name__}"
                )
                trust_source_val = "LOCAL_TRUST_REGISTRY"
                trust_record_id_val = None
            else:
                result_is_trusted = getattr(
                    trust_result, "is_trusted", None
                )
                trust_status = getattr(trust_result, "status", None)
                trust_status_value = getattr(
                    trust_status, "value", trust_status
                )
                trust_reason_value = getattr(
                    trust_result, "reason", None
                )
                trust_source_value = getattr(
                    trust_result, "trust_source", None
                )
                issuer_trusted = (
                    type(result_is_trusted) is bool and result_is_trusted
                )
                trust_status_val = (
                    trust_status_value
                    if isinstance(trust_status_value, str)
                    else "UNKNOWN"
                )
                trust_reason_val = (
                    trust_reason_value
                    if isinstance(trust_reason_value, str)
                    else "TRUST_REGISTRY_INVALID_RESULT"
                )
                trust_source_val = (
                    trust_source_value
                    if isinstance(trust_source_value, str)
                    and trust_source_value
                    else "LOCAL_TRUST_REGISTRY"
                )
                trust_record_id_val = getattr(
                    trust_result, "trust_record_id", None
                )
                if type(result_is_trusted) is not bool:
                    logger.warning(
                        "Issuer Trust Registry returned an invalid result"
                    )
                    trust_status_val = "ERROR"
                    trust_reason_val = "TRUST_REGISTRY_INVALID_RESULT"
        else:
            # Fail-closed: unconfigured trust registry MUST NOT pass
            issuer_trusted = False
            trust_status_val = "UNCONFIGURED"
            trust_reason_val = "TRUST_REGISTRY_NOT_CONFIGURED"
            trust_source_val = "NONE"
            trust_record_id_val = None

        # A DCQL result may contain multiple credentials. Trust every issuer;
        # trusting only the first credential would leave the rest unchecked.
        if isinstance(vcs, list):
            for additional_vc in vcs[1:]:
                if not isinstance(additional_vc, dict):
                    issuer_trusted = False
                    trust_reason_val = "PRESENTED_CREDENTIAL_FORMAT_INVALID"
                    break
                additional_issuer = str(additional_vc.get("issuer") or "")
                additional_types = additional_vc.get("type", [])
                if isinstance(additional_types, str):
                    additional_types = [additional_types]
                elif isinstance(additional_types, (list, tuple)):
                    additional_types = [str(value) for value in additional_types]
                else:
                    additional_types = []
                if self._trust_registry is None or not additional_issuer:
                    issuer_trusted = False
                    trust_reason_val = (
                        "TRUST_REGISTRY_NOT_CONFIGURED"
                        if self._trust_registry is None
                        else "PRESENTED_CREDENTIAL_ISSUER_MISSING"
                    )
                    break
                try:
                    additional_trust = self._trust_registry.evaluate_issuer_trust(
                        issuer_did=additional_issuer,
                        credential_types=additional_types,
                        at_time=now,
                    )
                    additional_trusted = getattr(
                        additional_trust, "is_trusted", None
                    )
                    additional_reason = getattr(
                        additional_trust, "reason", None
                    )
                    additional_trusted = (
                        type(additional_trusted) is bool and additional_trusted
                    )
                except Exception as error:
                    logger.warning(
                        "Issuer Trust Registry lookup failed (%s)",
                        type(error).__name__,
                    )
                    additional_trusted = False
                    additional_reason = (
                        f"TRUST_REGISTRY_UNAVAILABLE:{type(error).__name__}"
                    )
                if not additional_trusted:
                    issuer_trusted = False
                    trust_reason_val = (
                        additional_reason
                        if isinstance(additional_reason, str)
                        else "ADDITIONAL_PRESENTED_ISSUER_UNTRUSTED"
                    )
        
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
        vp_holder = str(vp_token.get("holder") or "")
        if not isinstance(vcs, list) or not vp_holder or any(
            not isinstance(embedded_vc, dict)
            or not isinstance(embedded_vc.get("credentialSubject"), dict)
            or str(embedded_vc["credentialSubject"].get("id") or "") != vp_holder
            for embedded_vc in vcs
        ):
            holder_binding_valid = False
            holder_binding_reason = (
                "Every presented credential must be bound to the authenticated VP holder"
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
        if isinstance(vcs, list):
            for additional_vc in vcs[1:]:
                if not isinstance(additional_vc, dict):
                    expiry_valid = False
                    break
                additional_expiry = (
                    additional_vc.get("validUntil")
                    or additional_vc.get("expirationDate")
                )
                if additional_expiry:
                    try:
                        additional_expiry_dt = datetime.fromisoformat(
                            additional_expiry.replace("Z", "+00:00")
                        )
                    except Exception:
                        expiry_valid = False
                        break
                    if additional_expiry_dt <= now:
                        expiry_valid = False
                        break

        # Evaluate authoritative persistence and Bitstring status for every embedded VC.
        cred_id = str(target_vc.get("id") or "")
        status_results = [
            self._evaluate_credential_status(embedded_vc, verified_at=now)
            for embedded_vc in vcs
            if isinstance(embedded_vc, dict)
        ] if isinstance(vcs, list) else []
        status_evaluated = any(item[2] for item in status_results)
        revocation_status_clear = (
            isinstance(vcs, list)
            and bool(vcs)
            and len(status_results) == len(vcs)
            and all(item[0] for item in status_results)
        )
        status_eval_reason = next(
            (reason for clear, reason, _ in status_results if not clear and reason),
            None,
        )

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
        ai_risk_score: int | None = None
        ai_risk_evidence: dict[str, Any] = {
            "source": "fraud_service",
            "modelVersion": None,
            "riskSignals": [],
            "advisoryOnly": True,
            "status": "UNAVAILABLE",
            "reason": "RISK_UNAVAILABLE",
        }
        try:
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
            ai_risk_evidence = {
                "source": eval_res.get("source", "unknown"),
                "modelVersion": eval_res.get("model_version", "unknown"),
                "riskSignals": list(eval_res.get("risk_signals", [])),
                "advisoryOnly": eval_res.get("advisory_only") is True,
                "status": "AVAILABLE",
                "reason": None,
            }
        except FraudRiskUnavailableError:
            logger.warning("OID4VP decision denied because risk evaluation is unavailable")

        # AI Risk Level Mapping
        # 0-39: LOW (Allow)
        # 40-69: MEDIUM (Step-Up Authentication Required)
        # 70-84: HIGH (Manual Review / Rejected)
        # 85-100: CRITICAL (Auto-Quarantine Triggered)
        if ai_risk_score is None:
            ai_risk_level = "UNAVAILABLE"
        elif ai_risk_score >= 85:
            ai_risk_level = "CRITICAL"
        elif ai_risk_score >= 70:
            ai_risk_level = "HIGH"
        elif ai_risk_score >= 40:
            ai_risk_level = "MEDIUM"
        else:
            ai_risk_level = "LOW"

        # An unavailable quarantine check is indeterminate and must not be
        # represented as a clear result in the final security policy.
        is_already_quarantined = False
        quarantine_status_error: str | None = None
        if subject_id:
            try:
                from app.infrastructure.cache_and_anchor import blockchain_anchor
            except Exception as error:
                quarantine_status_error = (
                    f"QUARANTINE_LOOKUP_FAILED:{type(error).__name__}"
                )
            else:
                quarantine_state, quarantine_status_error = _read_quarantine_status(
                    blockchain_anchor,
                    subject_id,
                )
                if quarantine_state is None:
                    is_already_quarantined = False
                else:
                    is_already_quarantined = quarantine_state

        if not revocation_status_clear:
            logger.warning(
                "Credential status verification rejected (%s)",
                status_eval_reason or "STATUS_CHECK_FAILED",
            )
        if quarantine_status_error is not None:
            logger.warning(
                "Quarantine status unavailable (%s)", quarantine_status_error
            )

        # This path does not verify an anchor for the presented credential.
        # Report that fact instead of synthesizing a successful anchor claim.
        blockchain_anchored = False

        # Consent compliance check
        consent_violation = False
        consent_violation_reason = None
        consent = session.consent_decision
        if consent is None:
            consent_violation = True
            consent_violation_reason = (
                "Holder consent is required before accepting a presentation"
            )
        elif not consent.user_approved:
            consent_violation = True
            consent_violation_reason = "Holder did not approve this presentation"
        elif (
            consent.session_id != session.session_id
            or consent.verifier_did != session.verifier_did
            or consent.client_id != session.client_id
            or consent.nonce != session.nonce
        ):
            consent_violation = True
            consent_violation_reason = (
                "Holder consent is not bound to this verification session"
            )
        else:
            presented_ids: list[str] = []
            approved_ids = set(consent.approved_credentials)
            for embedded_vc in vcs if isinstance(vcs, list) else []:
                presented_vc_id = (
                    str(embedded_vc.get("id") or "").strip()
                    if isinstance(embedded_vc, dict)
                    else ""
                )
                if not presented_vc_id:
                    consent_violation = True
                    consent_violation_reason = (
                        "Presented credential is missing an identifier required by holder consent"
                    )
                    break
                if presented_vc_id in presented_ids:
                    consent_violation = True
                    consent_violation_reason = (
                        "Presentation contains a duplicate credential identifier"
                    )
                    break
                presented_ids.append(presented_vc_id)
                if presented_vc_id not in approved_ids:
                    consent_violation = True
                    consent_violation_reason = (
                        f"Presented credential '{presented_vc_id}' was not approved by holder consent."
                    )
                    break

            if not consent_violation and not presented_ids:
                consent_violation = True
                consent_violation_reason = (
                    "Presentation contains no credential covered by holder consent"
                )

            # The complete VP payload is evaluated here; every embedded credential
            # must belong to the same Holder who made the session-bound decision.
            if not consent_violation:
                consent_subjects = [
                    vc.get("credentialSubject") if isinstance(vc, dict) else None
                    for vc in vcs
                ] if isinstance(vcs, list) else []
                consent_holder_dids = {
                    str(subject.get("id") or "")
                    for subject in consent_subjects
                    if isinstance(subject, dict)
                }
                if (
                    len(consent_subjects) != len(presented_ids)
                    or any(not isinstance(subject, dict) for subject in consent_subjects)
                    or consent_holder_dids != {consent.holder_did}
                ):
                    consent_violation = True
                    consent_violation_reason = (
                        "Presented credentials do not all belong to the consenting holder"
                    )

            # Check claim minimization intent authorization record
            # (disclosed_claims). The payload is client supplied, so it is only
            # compared with the server-recorded consent and never trusted alone.
            if not consent_violation and disclosed_claims:
                for k, value in disclosed_claims.items():
                    if k in consent.rejected_claims:
                        consent_violation = True
                        consent_violation_reason = (
                            f"Disclosed claim '{k}' was rejected by holder consent."
                        )
                        break
                    if (
                        k not in consent.approved_claims
                        or consent.approved_claims[k] != value
                    ):
                        consent_violation = True
                        consent_violation_reason = (
                            f"Disclosed claim '{k}' does not match the holder's approved value."
                        )
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
        # Revocation / status gate: also blocks if subject is already quarantined
        _revoc_clear = (
            revocation_status_clear
            and quarantine_status_error is None
            and not is_already_quarantined
        )
        _check_revoc = (
            PolicyCheckResult.ok(PolicyCheckName.REVOCATION_STATUS)
            if _revoc_clear
            else PolicyCheckResult.fail(
                PolicyCheckName.REVOCATION_STATUS,
                reason=(
                    "Revoked or locked in quarantine"
                    if is_already_quarantined
                    else (
                        f"Quarantine status unavailable: {quarantine_status_error}"
                        if quarantine_status_error
                        else (
                            status_eval_reason
                            or "Credential revoked or status check failed"
                        )
                    )
                ),
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
        quarantine_anchor = {
            "status": "NOT_REQUESTED",
            "txHash": None,
            "blockNumber": None,
        }

        # Execute quarantine side-effect only when evaluator requests it
        if quarantine_triggered:
            try:
                from app.infrastructure.cache_and_anchor import blockchain_anchor
                if subject_id and hasattr(blockchain_anchor, "anchor_quarantine"):
                    anchor_result = blockchain_anchor.anchor_quarantine(
                        subject_id, quarantine_reason or "High heuristic risk"
                    )
                    if isinstance(anchor_result, dict):
                        quarantine_anchor = {
                            "status": anchor_result.get("status", "UNANCHORED"),
                            "txHash": anchor_result.get("tx_hash"),
                            "blockNumber": anchor_result.get("block_number"),
                        }
            except Exception as error:
                quarantine_anchor["status"] = "UNANCHORED"
                logger.warning(
                    "Quarantine side effect failed (%s)",
                    type(error).__name__,
                )

        # Report what is actually sent in the VP. A Data Integrity VC is shared
        # as a whole; client-provided claim-selection metadata cannot make its
        # signed claims disappear from the presentation.
        credential_subject = target_vc.get("credentialSubject")
        disclosed_keys = (
            [key for key in credential_subject.keys() if key != "id"]
            if isinstance(credential_subject, dict)
            else []
        )
        req_keys = list(session.requested_fields)
        hidden_keys: list[str] = []

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
                "quarantineAnchor": quarantine_anchor,
                "aiRisk": {
                    **ai_risk_evidence,
                    "score": ai_risk_score,
                    "level": policy_result.ai_risk_level.value,
                    "reasons": list(ai_reasons),
                },
                "dataMinimization": {
                    "status": "FULL_CREDENTIAL_DISCLOSED",
                    "requestedFields": req_keys,
                    "disclosedFields": disclosed_keys,
                    "hiddenFields": hidden_keys,
                    "selectiveDisclosureActive": False,
                    "cryptographicSelectiveDisclosure": False,
                    "limitation": "Claim-level cryptographic selective disclosure is not implemented in the current eddsa-jcs-2022 profile.",
                },
                "evaluations": {
                    "credential": "Valid W3C VC 2.0 profile format" if cred_valid else "Credential validation failed",
                    "issuer": f"Trusted in local registry: {issuer_did}" if issuer_trusted else f"Issuer untrusted: {trust_reason_val}",
                    "signature": "Cryptographic proof mathematically valid" if sig_valid else "Cryptographic signature invalid or unverified",
                    "holder_binding": "Holder DID bound to presentation signature" if holder_binding_valid else (holder_binding_reason or "Holder mismatch"),
                    "expiration": "Within active validity window" if expiry_valid else "Expired credential",
                    "revocation": (
                        status_eval_reason
                        or (
                            f"Quarantine status unavailable: {quarantine_status_error}"
                            if quarantine_status_error
                            else (
                                "Credential is locked in quarantine"
                                if is_already_quarantined
                                else (
                                    "Credential status checks passed"
                                    if status_evaluated
                                    else "Credential status not supplied; status-list check not applicable"
                                )
                            )
                        )
                    ),
                    "challenge": "Nonce match confirmed" if challenge_valid else ("Nonce missing from presentation proof" if not challenge_nonce else "Nonce mismatch"),
                    "dcql": "DCQL query criteria fully satisfied" if dcql_satisfied else (dcql_reason or "DCQL satisfaction failed"),
                    "consent": "Authorized by holder consent" if not consent_violation else (consent_violation_reason or "Consent violation"),
                    "ai_fraud": (
                        "Risk assessment unavailable; automatic acceptance denied (RISK_UNAVAILABLE)"
                        if ai_risk_score is None
                        else (
                            "Low fraud risk profile"
                            if policy_result.ai_risk_level.value == "LOW"
                            else f"Elevated threat detected: {policy_result.ai_risk_level.value} ({ai_risk_score}/100)"
                        )
                    ),
                    "quarantine": (
                        f"Process-local policy lockout; optional digest anchor status: {quarantine_anchor['status']}"
                        if (quarantine_triggered or is_already_quarantined)
                        else (
                            f"Unavailable: {quarantine_status_error}"
                            if quarantine_status_error
                            else "Clear"
                        )
                    ),
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
            consent_status=(
                "GRANTED"
                if consent is not None and consent.user_approved
                else session.consent_status
            ),
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
                        "disclosed_field_count": str(len(disclosed_keys)),
                        "hidden_field_count": str(len(hidden_keys)),
                        "disclosure_profile": "FULL_SIGNED_VC",
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
                        "ai_risk_score": (
                            str(ai_risk_score)
                            if ai_risk_score is not None
                            else "UNAVAILABLE"
                        ),
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
                    "ai_risk_score": (
                        str(ai_risk_score)
                        if ai_risk_score is not None
                        else "UNAVAILABLE"
                    ),
                    "ai_risk_level": ai_risk_level,
                    "ai_risk_source": ai_risk_evidence["source"],
                    "ai_risk_model_version": (
                        ai_risk_evidence["modelVersion"] or "UNAVAILABLE"
                    ),
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
                    "ai_risk_score": (
                        ai_risk_score if ai_risk_score is not None else "UNAVAILABLE"
                    ),
                },
            )
        except Exception:
            pass

        return result
