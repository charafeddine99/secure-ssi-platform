from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast
import pytest

from app.domain.oid4vp import (
    VerificationSession,
    VerificationSessionStatus,
    NinePointVerificationResult,
    SessionNotFoundError,
    SessionAlreadyConsumedError,
)
from app.domain.persistence import AuditEvent, AuditEventType
from app.infrastructure.persistence.oid4vp_repository import (
    VerificationSessionDocumentMapper,
    MongoVerificationSessionRepository,
)
from app.application.services.oid4vp_service import Oid4vpService
from app.application.services.trust_registry_service import TrustRegistryService
from app.infrastructure.crypto.local_holder_key_provider import SYNTHETIC_HOLDER_DID
from app.infrastructure.persistence.trust_registry_repository import (
    InMemoryTrustRegistryRepository,
)
from app.infrastructure.fixtures.signed_credentials import (
    build_local_proof_service,
    build_signed_presentation,
)
from tests.support.fake_mongo import FakeCollection


class FakeAuditRepository:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> AuditEvent:
        self.events.append(event)
        return event


class DummyCredentialProofResult:
    is_valid = True
    verified = True

class DummyCredentialProofService:
    def verify_credential(self, *args, **kwargs):
        return DummyCredentialProofResult()

class DummyCredentialInspector:
    def __init__(self):
        self._proofs = DummyCredentialProofService()

class DummyVerifierPresentationService:
    def __init__(self):
        self._credentials = DummyCredentialInspector()

    def verify_presentation(self, *args, **kwargs):
        return NinePointVerificationResult(
            credential_valid=True,
            issuer_trusted=True,
            signature_valid=True,
            holder_binding_valid=True,
            expiration_valid=True,
            revocation_status_clear=True,
            challenge_valid=True,
            ai_risk_level="LOW",
            ai_risk_score=15,
            blockchain_anchored=True,
            final_policy_result="ACCEPTED",
            details={},
        )



class DummyStatusListService:
    def check_credential_status(self, *args, **kwargs):
        return {"status": "VALID", "revoked": False}


def _create_sample_session(
    session_id: str = "session_consent_000000000001",
    status: VerificationSessionStatus = VerificationSessionStatus.PENDING,
    consent_status: str = "PENDING",
    rejection_reason: str | None = None,
    requested_fields: tuple[str, ...] = ("name", "degree", "programCode"),
) -> VerificationSession:
    now = datetime.now(UTC)
    return VerificationSession(
        id="507f1f77bcf86cd799439011",
        session_id=session_id,
        verifier_did="did:web:verifier.example.com",
        client_id="https://verifier.example.com/callback",
        response_uri="https://verifier.example.com/post",
        nonce="challenge_nonce_xyz123",
        presentation_definition={"id": "pres_def_1"},
        purpose="Verify student qualifications",
        status=status,
        created_at=now,
        expires_at=now + timedelta(minutes=10),
        consent_status=consent_status,
        rejection_reason=rejection_reason,
        requested_fields=requested_fields,
    )


def test_mapper_preserves_consent_and_selective_disclosure_fields():
    session = _create_sample_session(
        requested_fields=("affiliation", "degree", "gpa"),
    )
    doc = VerificationSessionDocumentMapper.to_document(session)
    assert doc["consentStatus"] == "PENDING"
    assert doc["rejectionReason"] is None
    assert doc["requestedFields"] == ["affiliation", "degree", "gpa"]

    restored = VerificationSessionDocumentMapper.from_document(doc)
    assert restored.consent_status == "PENDING"
    assert restored.rejection_reason is None
    assert restored.requested_fields == ("affiliation", "degree", "gpa")


def test_mapper_preserves_rejected_consent_state():
    session = _create_sample_session(
        status=VerificationSessionStatus.REJECTED,
        consent_status="REJECTED",
        rejection_reason="Holder declined to disclose GPA",
    )

    doc = VerificationSessionDocumentMapper.to_document(session)
    assert doc["status"] == "REJECTED"
    assert doc["consentStatus"] == "REJECTED"
    assert doc["rejectionReason"] == "Holder declined to disclose GPA"

    restored = VerificationSessionDocumentMapper.from_document(doc)
    assert restored.status == VerificationSessionStatus.REJECTED
    assert restored.consent_status == "REJECTED"
    assert restored.rejection_reason == "Holder declined to disclose GPA"


def test_repository_reject_session_updates_atomically():
    collection = FakeCollection(unique_fields=("sessionId",))
    repo = MongoVerificationSessionRepository(cast(Any, collection))

    session = _create_sample_session("session_to_reject_0000000001")
    repo.add(session)

    rejected = repo.reject_session("session_to_reject_0000000001", reason="Holder rejected verification", expected_version=1)
    assert rejected.status == VerificationSessionStatus.REJECTED
    assert rejected.consent_status == "REJECTED"
    assert rejected.rejection_reason == "Holder rejected verification"

    # Reload from repo
    loaded = repo.get_by_session_id("session_to_reject_0000000001")
    assert loaded is not None
    assert loaded.status == VerificationSessionStatus.REJECTED
    assert loaded.consent_status == "REJECTED"
    assert loaded.rejection_reason == "Holder rejected verification"


def test_repository_reject_session_fails_if_not_found():
    collection = FakeCollection(unique_fields=("sessionId",))
    repo = MongoVerificationSessionRepository(cast(Any, collection))

    with pytest.raises(SessionNotFoundError):
        repo.reject_session("session_non_existent_000000001", reason="Some reason", expected_version=1)


def test_repository_reject_session_fails_if_already_consumed():
    collection = FakeCollection(unique_fields=("sessionId",))
    repo = MongoVerificationSessionRepository(cast(Any, collection))

    session = _create_sample_session("session_consumed_00000000001")
    repo.add(session)

    repo.reject_session("session_consumed_00000000001", reason="First rejection", expected_version=1)

    with pytest.raises(SessionAlreadyConsumedError):
        repo.reject_session("session_consumed_00000000001", reason="Duplicate rejection", expected_version=2)


def test_oid4vp_service_reject_session_records_audit_event():
    collection = FakeCollection(unique_fields=("sessionId",))
    session_repo = MongoVerificationSessionRepository(cast(Any, collection))
    audit_repo = FakeAuditRepository()

    service = Oid4vpService(
        session_repository=session_repo,
        credential_repository=None,  # type: ignore[arg-type]
        audit_repository=audit_repo,  # type: ignore[arg-type]
        verifier_presentation_service=DummyVerifierPresentationService(),  # type: ignore[arg-type]
        status_list_service=DummyStatusListService(),  # type: ignore[arg-type]
    )

    session = _create_sample_session("session_service_reject_00001")
    session_repo.add(session)

    rejected = service.reject_session(
        session_id="session_service_reject_00001",
        reason="Holder opted out of selective disclosure",
        actor_id="did:key:z6MkuHolder123",
    )

    assert rejected.status == VerificationSessionStatus.REJECTED
    assert rejected.consent_status == "REJECTED"
    assert rejected.rejection_reason == "Holder opted out of selective disclosure"

    # Assert audit event appended
    assert len(audit_repo.events) == 1
    event = audit_repo.events[0]
    assert event.event_type is AuditEventType.CONSENT_REJECTED
    assert event.metadata["session_id"] == "session_service_reject_00001"
    assert event.metadata["reason"] == "Holder opted out of selective disclosure"
    assert event.actor_id == "did:key:z6MkuHolder123"


def test_oid4vp_service_direct_post_calculates_data_minimization(monkeypatch):
    collection = FakeCollection(unique_fields=("sessionId",))
    session_repo = MongoVerificationSessionRepository(cast(Any, collection))
    audit_repo = FakeAuditRepository()
    trust_registry = TrustRegistryService(
        repository=InMemoryTrustRegistryRepository()
    )
    trust_registry.seed_default_demo_issuers()

    service = Oid4vpService(
        session_repository=session_repo,
        credential_repository=None,  # type: ignore[arg-type]
        audit_repository=audit_repo,  # type: ignore[arg-type]
        verifier_presentation_service=DummyVerifierPresentationService(),  # type: ignore[arg-type]
        status_list_service=DummyStatusListService(),  # type: ignore[arg-type]
        trust_registry_service=trust_registry,
    )

    session = _create_sample_session(
        session_id="session_dp_minimization_0001",
        requested_fields=("affiliation", "degree", "programCode", "graduationYear"),
    )
    session_repo.add(session)

    now = datetime.now(UTC)
    raw_vc = {
        "@context": [
            "https://www.w3.org/ns/credentials/v2",
            "https://secure-ssi.example/contexts/university-affiliation/v1",
        ],
        "id": f"urn:uuid:{uuid.uuid4()}",
        "type": ["VerifiableCredential", "UniversityAffiliationCredential"],
        "issuer": "did:web:issuer.example",
        "validFrom": (now - timedelta(days=30)).isoformat().replace("+00:00", "Z"),
        "validUntil": (now + timedelta(days=365)).isoformat().replace("+00:00", "Z"),
        "credentialSubject": {
            "id": SYNTHETIC_HOLDER_DID,
            "affiliation": "student",
            "degree": "Bachelor of Science",
            "programCode": "SYN-CS-2024",
            "graduationYear": 2025,
        },
    }
    proof_service = build_local_proof_service(clock=lambda: now)
    signed_vc = proof_service.sign_credential(raw_vc)
    signed_vp = build_signed_presentation(
        signed_vc,
        nonce=session.nonce,
        domain=session.client_id,
        holder_did=SYNTHETIC_HOLDER_DID,
    )

    from tests.support.consent import record_holder_approval

    record_holder_approval(session.session_id, signed_vc, SYNTHETIC_HOLDER_DID, repository=session_repo)

    # Legacy selection metadata cannot hide claims from a signed VC.
    disclosed_claims = {
        "affiliation": "student",
        "degree": "Bachelor of Science",
    }

    from app.application.services.oid4vp_service import fraud_client

    monkeypatch.setattr(
        fraud_client,
        "evaluate_presentation_risk",
        lambda **_kwargs: {
            "risk_score": 10,
            "reasons": [],
            "model_version": "test-rule-heuristic-v1",
            "risk_signals": ["synthetic_test_signal"],
            "advisory_only": True,
            "source": "fraud_service",
        },
    )
    result = service.process_direct_post(
        session_id="session_dp_minimization_0001",
        vp_token=signed_vp,
        disclosed_claims=disclosed_claims,
    )


    assert result.final_policy_result == "ACCEPTED"
    data_min = result.details.get("dataMinimization", {})
    assert data_min["status"] == "FULL_CREDENTIAL_DISCLOSED"
    assert data_min["requestedFields"] == ["affiliation", "degree", "programCode", "graduationYear"]
    assert set(data_min["disclosedFields"]) == {
        "affiliation", "degree", "programCode", "graduationYear"
    }
    assert data_min["hiddenFields"] == []
    assert data_min["cryptographicSelectiveDisclosure"] is False

    # Check session updated to GRANTED
    updated_session = session_repo.get_by_session_id("session_dp_minimization_0001")
    assert updated_session is not None
    assert updated_session.status == VerificationSessionStatus.VERIFIED
    assert updated_session.consent_status == "GRANTED"

    # Check CONSENT_GRANTED audit event
    consent_events = [e for e in audit_repo.events if e.event_type is AuditEventType.CONSENT_GRANTED]
    assert len(consent_events) == 1
    assert consent_events[0].metadata["session_id"] == "session_dp_minimization_0001"
    assert consent_events[0].metadata["disclosed_field_count"] == "4"
    assert consent_events[0].metadata["hidden_field_count"] == "0"
    assert consent_events[0].metadata["disclosure_profile"] == "FULL_SIGNED_VC"
    assert not any("affiliation" in value for value in consent_events[0].metadata.values())
