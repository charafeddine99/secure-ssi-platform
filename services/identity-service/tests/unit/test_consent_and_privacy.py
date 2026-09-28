from __future__ import annotations

from datetime import UTC, datetime, timedelta
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
from tests.support.fake_mongo import FakeCollection


class FakeAuditRepository:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> AuditEvent:
        self.events.append(event)
        return event


class DummyVerifierPresentationService:
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
            blockchain_anchored=True,
            final_policy_result="ACCEPTED",
            details={},
        )


class DummyStatusListService:
    def check_credential_status(self, *args, **kwargs):
        return {"status": "VALID", "revoked": False}


def _create_sample_session(
    session_id: str = "sess_consent_001",
    status: VerificationSessionStatus = VerificationSessionStatus.PENDING,
    consent_status: str = "PENDING",
    requested_fields: tuple[str, ...] = ("name", "degree", "programCode"),
) -> VerificationSession:
    now = datetime.now(UTC)
    return VerificationSession(
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
    session = _create_sample_session()
    session.status = VerificationSessionStatus.REJECTED
    session.consent_status = "REJECTED"
    session.rejection_reason = "Holder declined to disclose GPA"

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
    repo = MongoVerificationSessionRepository(collection)

    session = _create_sample_session("sess_to_reject")
    repo.save(session)

    rejected = repo.reject_session("sess_to_reject", "Holder rejected verification")
    assert rejected.status == VerificationSessionStatus.REJECTED
    assert rejected.consent_status == "REJECTED"
    assert rejected.rejection_reason == "Holder rejected verification"

    # Reload from repo
    loaded = repo.get_by_session_id("sess_to_reject")
    assert loaded is not None
    assert loaded.status == VerificationSessionStatus.REJECTED
    assert loaded.consent_status == "REJECTED"
    assert loaded.rejection_reason == "Holder rejected verification"


def test_repository_reject_session_fails_if_not_found():
    collection = FakeCollection(unique_fields=("sessionId",))
    repo = MongoVerificationSessionRepository(collection)

    with pytest.raises(SessionNotFoundError):
        repo.reject_session("non_existent_sess", "Some reason")


def test_repository_reject_session_fails_if_already_consumed():
    collection = FakeCollection(unique_fields=("sessionId",))
    repo = MongoVerificationSessionRepository(collection)

    session = _create_sample_session("sess_consumed")
    repo.save(session)

    repo.reject_session("sess_consumed", "First rejection")

    with pytest.raises(SessionAlreadyConsumedError):
        repo.reject_session("sess_consumed", "Duplicate rejection")


def test_oid4vp_service_reject_session_records_audit_event():
    collection = FakeCollection(unique_fields=("sessionId",))
    session_repo = MongoVerificationSessionRepository(collection)
    audit_repo = FakeAuditRepository()

    service = Oid4vpService(
        session_repository=session_repo,
        credential_repository=None,  # type: ignore[arg-type]
        audit_repository=audit_repo,  # type: ignore[arg-type]
        verifier_presentation_service=DummyVerifierPresentationService(),  # type: ignore[arg-type]
        status_list_service=DummyStatusListService(),  # type: ignore[arg-type]
    )

    session = _create_sample_session("sess_service_reject")
    session_repo.save(session)

    rejected = service.reject_session(
        session_id="sess_service_reject",
        rejection_reason="Holder opted out of selective disclosure",
        holder_did="did:key:z6MkuHolder123",
    )

    assert rejected.status == VerificationSessionStatus.REJECTED
    assert rejected.consent_status == "REJECTED"
    assert rejected.rejection_reason == "Holder opted out of selective disclosure"

    # Assert audit event appended
    assert len(audit_repo.events) == 1
    event = audit_repo.events[0]
    assert event.event_type is AuditEventType.CONSENT_REJECTED
    assert event.details["sessionId"] == "sess_service_reject"
    assert event.details["rejectionReason"] == "Holder opted out of selective disclosure"
    assert event.details["holderDid"] == "did:key:z6MkuHolder123"


def test_oid4vp_service_direct_post_calculates_data_minimization():
    collection = FakeCollection(unique_fields=("sessionId",))
    session_repo = MongoVerificationSessionRepository(collection)
    audit_repo = FakeAuditRepository()

    service = Oid4vpService(
        session_repository=session_repo,
        credential_repository=None,  # type: ignore[arg-type]
        audit_repository=audit_repo,  # type: ignore[arg-type]
        verifier_presentation_service=DummyVerifierPresentationService(),  # type: ignore[arg-type]
        status_list_service=DummyStatusListService(),  # type: ignore[arg-type]
    )

    session = _create_sample_session(
        session_id="sess_dp_minimization",
        requested_fields=("affiliation", "degree", "programCode", "graduationYear"),
    )
    session_repo.save(session)

    # Disclose only 2 of the 4 requested fields
    disclosed_claims = {
        "affiliation": "student",
        "degree": "BSc Computer Science",
    }

    result = service.process_direct_post(
        session_id="sess_dp_minimization",
        vp_token={"type": ["VerifiablePresentation"], "verifiableCredential": []},
        disclosed_claims=disclosed_claims,
        ai_risk_score=10,
    )

    assert result.final_policy_result == "ACCEPTED"
    data_min = result.details.get("dataMinimization", {})
    assert data_min["status"] == "SELECTIVE_DISCLOSURE_APPLIED"
    assert data_min["requestedFields"] == ["affiliation", "degree", "programCode", "graduationYear"]
    assert set(data_min["disclosedFields"]) == {"affiliation", "degree"}
    assert set(data_min["hiddenFields"]) == {"programCode", "graduationYear"}
    assert data_min["disclosureRatio"] == 0.5

    # Check session updated to GRANTED
    updated_session = session_repo.get_by_session_id("sess_dp_minimization")
    assert updated_session is not None
    assert updated_session.status == VerificationSessionStatus.VERIFIED
    assert updated_session.consent_status == "GRANTED"

    # Check CONSENT_GRANTED audit event
    consent_events = [e for e in audit_repo.events if e.event_type is AuditEventType.CONSENT_GRANTED]
    assert len(consent_events) == 1
    assert consent_events[0].details["sessionId"] == "sess_dp_minimization"
    assert consent_events[0].details["dataMinimization"]["disclosureRatio"] == 0.5
