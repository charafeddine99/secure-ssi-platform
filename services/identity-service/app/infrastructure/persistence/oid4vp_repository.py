from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Mapping
from bson import ObjectId
from pymongo import DESCENDING
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.application.ports.oid4vp_repository import VerificationSessionRepository
from app.domain.oid4vp import (
    VerificationSession,
    VerificationSessionStatus,
    NinePointVerificationResult,
    SessionNotFoundError,
    SessionAlreadyConsumedError,
    ConsentDecision,
    ConsentAction,
)
from app.domain.persistence import (
    DuplicateEntityError,
    OptimisticLockError,
    PersistenceUnavailableError,
)
from app.infrastructure.persistence.mappers import to_object_id

class VerificationSessionDocumentMapper:
    @staticmethod
    def to_document(session: VerificationSession) -> dict[str, Any]:
        result_dict = session.verification_result.to_dict() if session.verification_result else None
        return {
            "_id": to_object_id(session.id),
            "sessionId": session.session_id,
            "verifierDid": session.verifier_did,
            "ownerUserId": session.owner_user_id,
            "clientId": session.client_id,
            "responseUri": session.response_uri,
            "nonce": session.nonce,
            "dcqlQuery": deepcopy(dict(session.dcql_query)),
            "presentationDefinition": deepcopy(dict(session.presentation_definition)),
            "purpose": session.purpose,
            "status": session.status.value,
            "createdAt": session.created_at,
            "expiresAt": session.expires_at,
            "presentationId": session.presentation_id,
            "verificationResult": result_dict,
            "disclosedClaims": deepcopy(dict(session.disclosed_claims)) if session.disclosed_claims else None,
            "consentStatus": session.consent_status,
            "rejectionReason": session.rejection_reason,
            "requestedFields": list(session.requested_fields),
            "consentDecision": session.consent_decision.to_dict() if session.consent_decision else None,
            "approvedCredentials": list(session.approved_credentials),
            "approvedClaims": deepcopy(dict(session.approved_claims)) if session.approved_claims else None,
            "rejectedClaims": list(session.rejected_claims),
            "version": session.version,
        }

    @staticmethod
    def from_document(doc: dict[str, Any]) -> VerificationSession:
        v_result = None
        raw_res = doc.get("verificationResult")
        if raw_res:
            v_result = NinePointVerificationResult(
                credential_valid=raw_res["credentialValid"],
                issuer_trusted=raw_res["issuerTrusted"],
                signature_valid=raw_res["signatureValid"],
                holder_binding_valid=raw_res["holderBindingValid"],
                expiration_valid=raw_res["expirationValid"],
                revocation_status_clear=raw_res["revocationStatusClear"],
                challenge_valid=raw_res["challengeValid"],
                ai_risk_level=raw_res["aiRiskLevel"],
                ai_risk_score=raw_res["aiRiskScore"],
                blockchain_anchored=raw_res["blockchainAnchored"],
                final_policy_result=raw_res["finalPolicyResult"],
                details=deepcopy(raw_res.get("details", {})),
            )

        dcql_data = doc.get("dcqlQuery")
        legacy_pe = doc.get("presentationDefinition", {})
        if not dcql_data and legacy_pe:
            from app.application.services.dcql_engine import convert_legacy_presentation_definition_to_dcql
            try:
                dcql_data = convert_legacy_presentation_definition_to_dcql(legacy_pe).to_dict()
            except Exception:
                dcql_data = {}

        consent_dec_doc = doc.get("consentDecision")
        consent_dec = None
        if isinstance(consent_dec_doc, dict):
            c_created = consent_dec_doc.get("createdAt")
            if isinstance(c_created, str):
                try:
                    c_created = datetime.fromisoformat(c_created.replace("Z", "+00:00"))
                except Exception:
                    c_created = doc["createdAt"]
            c_expires = consent_dec_doc.get("expiresAt")
            if isinstance(c_expires, str):
                try:
                    c_expires = datetime.fromisoformat(c_expires.replace("Z", "+00:00"))
                except Exception:
                    c_expires = doc["expiresAt"]
            dec_raw = consent_dec_doc.get("decision", "APPROVE")
            dec_action = ConsentAction.REJECT if str(dec_raw).upper() == "REJECT" else ConsentAction.APPROVE
            consent_dec = ConsentDecision(
                session_id=consent_dec_doc.get("sessionId", doc["sessionId"]),
                verifier_did=consent_dec_doc.get("verifierDid", doc["verifierDid"]),
                client_id=consent_dec_doc.get("clientId", doc["clientId"]),
                purpose=consent_dec_doc.get("purpose", doc.get("purpose", "")),
                nonce=consent_dec_doc.get("nonce", doc["nonce"]),
                holder_did=consent_dec_doc.get("holderDid", ""),
                decision=dec_action,
                approved_credentials=tuple(consent_dec_doc.get("approvedCredentials", ())),
                requested_claims=tuple(consent_dec_doc.get("requestedClaims", ())),
                approved_claims=deepcopy(consent_dec_doc.get("approvedClaims", {})),
                rejected_claims=tuple(consent_dec_doc.get("rejectedClaims", ())),
                created_at=c_created or doc["createdAt"],
                expires_at=c_expires or doc["expiresAt"],
                dcql_query_hash=consent_dec_doc.get("dcqlQueryHash"),
            )

        return VerificationSession(
            id=str(doc["_id"]),
            session_id=doc["sessionId"],
            verifier_did=doc["verifierDid"],
            owner_user_id=doc.get("ownerUserId"),
            client_id=doc["clientId"],
            response_uri=doc["responseUri"],
            nonce=doc["nonce"],
            dcql_query=deepcopy(dcql_data or {}),
            presentation_definition=deepcopy(legacy_pe),
            purpose=doc.get("purpose", "Verification of digital credentials"),
            status=VerificationSessionStatus(doc["status"]),
            created_at=doc["createdAt"],
            expires_at=doc["expiresAt"],
            presentation_id=doc.get("presentationId"),
            verification_result=v_result,
            disclosed_claims=deepcopy(doc.get("disclosedClaims")),
            consent_status=doc.get("consentStatus", "PENDING"),
            rejection_reason=doc.get("rejectionReason"),
            requested_fields=tuple(doc.get("requestedFields", ())),
            consent_decision=consent_dec,
            approved_credentials=tuple(doc.get("approvedCredentials", ())),
            approved_claims=deepcopy(doc.get("approvedClaims")),
            rejected_claims=tuple(doc.get("rejectedClaims", ())),
            version=doc.get("version", 1),
        )

class MongoVerificationSessionRepository(VerificationSessionRepository):
    def __init__(self, collection: Collection[dict[str, Any]]) -> None:
        self._collection = collection

    def add(self, session: VerificationSession) -> VerificationSession:
        try:
            self._collection.insert_one(VerificationSessionDocumentMapper.to_document(session))
            return session
        except DuplicateKeyError as e:
            raise DuplicateEntityError(f"Verification session {session.session_id} already exists.") from e
        except PyMongoError as e:
            raise PersistenceUnavailableError("Failed to persist verification session.") from e

    def get_by_session_id(self, session_id: str) -> VerificationSession | None:
        try:
            doc = self._collection.find_one({"sessionId": session_id})
            return VerificationSessionDocumentMapper.from_document(doc) if doc else None
        except PyMongoError as e:
            raise PersistenceUnavailableError(f"Failed to lookup session {session_id}.") from e

    def get_by_nonce(self, nonce: str) -> VerificationSession | None:
        try:
            doc = self._collection.find_one({"nonce": nonce})
            return VerificationSessionDocumentMapper.from_document(doc) if doc else None
        except PyMongoError as e:
            raise PersistenceUnavailableError("Failed to lookup session by nonce.") from e

    def update_result(
        self,
        session_id: str,
        *,
        status: VerificationSessionStatus,
        presentation_id: str,
        verification_result: NinePointVerificationResult,
        disclosed_claims: Mapping[str, Any] | None,
        expected_version: int,
    ) -> VerificationSession:
        try:
            res = self._collection.update_one(
                {
                    "sessionId": session_id,
                    "version": expected_version,
                    "status": VerificationSessionStatus.PENDING.value,
                },
                {
                    "$set": {
                        "status": status.value,
                        "presentationId": presentation_id,
                        "verificationResult": verification_result.to_dict(),
                        "disclosedClaims": deepcopy(dict(disclosed_claims)) if disclosed_claims else None,
                        "consentStatus": "GRANTED",
                    },
                    "$inc": {"version": 1},
                },
            )
        except PyMongoError as e:
            raise PersistenceUnavailableError(f"Failed to update verification session {session_id}.") from e

        if res.matched_count == 0:
            current = self.get_by_session_id(session_id)
            if current is None:
                raise SessionNotFoundError(f"Session {session_id} not found.")
            if current.status in {VerificationSessionStatus.VERIFIED, VerificationSessionStatus.REJECTED}:
                raise SessionAlreadyConsumedError(f"Session {session_id} has already been evaluated.")
            raise OptimisticLockError(f"Session {session_id} was modified concurrently.")

        updated = self.get_by_session_id(session_id)
        assert updated is not None
        return updated

    def reject_session(
        self,
        session_id: str,
        *,
        reason: str,
        expected_version: int,
    ) -> VerificationSession:
        try:
            res = self._collection.update_one(
                {
                    "sessionId": session_id,
                    "version": expected_version,
                    "status": VerificationSessionStatus.PENDING.value,
                },
                {
                    "$set": {
                        "status": VerificationSessionStatus.REJECTED.value,
                        "consentStatus": "REJECTED",
                        "rejectionReason": reason,
                    },
                    "$inc": {"version": 1},
                },
            )
        except PyMongoError as e:
            raise PersistenceUnavailableError(f"Failed to reject verification session {session_id}.") from e

        if res.matched_count == 0:
            current = self.get_by_session_id(session_id)
            if current is None:
                raise SessionNotFoundError(f"Session {session_id} not found.")
            if current.status in {VerificationSessionStatus.VERIFIED, VerificationSessionStatus.REJECTED}:
                raise SessionAlreadyConsumedError(f"Session {session_id} has already been evaluated or rejected.")
            raise OptimisticLockError(f"Session {session_id} was modified concurrently.")

        updated = self.get_by_session_id(session_id)
        assert updated is not None
        return updated

    def record_consent(
        self,
        session_id: str,
        *,
        consent_decision: ConsentDecision,
        expected_version: int,
    ) -> VerificationSession:
        try:
            status_val = (
                VerificationSessionStatus.REJECTED.value
                if consent_decision.decision == ConsentAction.REJECT
                else VerificationSessionStatus.PENDING.value
            )
            consent_status_val = (
                "REJECTED"
                if consent_decision.decision == ConsentAction.REJECT
                else "APPROVED"
            )
            res = self._collection.update_one(
                {
                    "sessionId": session_id,
                    "version": expected_version,
                    "status": VerificationSessionStatus.PENDING.value,
                },
                {
                    "$set": {
                        "status": status_val,
                        "consentStatus": consent_status_val,
                        "consentDecision": consent_decision.to_dict(),
                        "approvedCredentials": list(consent_decision.approved_credentials),
                        "approvedClaims": deepcopy(dict(consent_decision.approved_claims)),
                        "rejectedClaims": list(consent_decision.rejected_claims),
                    },
                    "$inc": {"version": 1},
                },
            )
        except PyMongoError as e:
            raise PersistenceUnavailableError(f"Failed to record consent for session {session_id}.") from e

        if res.matched_count == 0:
            current = self.get_by_session_id(session_id)
            if current is None:
                raise SessionNotFoundError(f"Session {session_id} not found.")
            if current.status in {VerificationSessionStatus.VERIFIED, VerificationSessionStatus.REJECTED}:
                raise SessionAlreadyConsumedError(f"Session {session_id} has already been evaluated or rejected.")
            raise OptimisticLockError(f"Session {session_id} was modified concurrently.")

        updated = self.get_by_session_id(session_id)
        assert updated is not None
        return updated

    def list_by_verifier(
        self,
        verifier_did: str,
        *,
        limit: int = 50,
    ) -> tuple[VerificationSession, ...]:
        try:
            cursor = (
                self._collection.find({"verifierDid": verifier_did})
                .sort("createdAt", DESCENDING)
                .limit(limit)
            )
            return tuple(VerificationSessionDocumentMapper.from_document(d) for d in cursor)
        except PyMongoError as e:
            raise PersistenceUnavailableError("Failed to list verification sessions.") from e
