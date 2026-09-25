from __future__ import annotations

from copy import deepcopy
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
            "clientId": session.client_id,
            "responseUri": session.response_uri,
            "nonce": session.nonce,
            "presentationDefinition": deepcopy(dict(session.presentation_definition)),
            "purpose": session.purpose,
            "status": session.status.value,
            "createdAt": session.created_at,
            "expiresAt": session.expires_at,
            "presentationId": session.presentation_id,
            "verificationResult": result_dict,
            "disclosedClaims": deepcopy(dict(session.disclosed_claims)) if session.disclosed_claims else None,
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

        return VerificationSession(
            id=str(doc["_id"]),
            session_id=doc["sessionId"],
            verifier_did=doc["verifierDid"],
            client_id=doc["clientId"],
            response_uri=doc["responseUri"],
            nonce=doc["nonce"],
            presentation_definition=deepcopy(doc.get("presentationDefinition", {})),
            purpose=doc.get("purpose", "Verification of digital credentials"),
            status=VerificationSessionStatus(doc["status"]),
            created_at=doc["createdAt"],
            expires_at=doc["expiresAt"],
            presentation_id=doc.get("presentationId"),
            verification_result=v_result,
            disclosed_claims=deepcopy(doc.get("disclosedClaims")),
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
