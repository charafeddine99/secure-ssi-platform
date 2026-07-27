from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.application.services.credential_revocation_service import (
    CredentialRevocationService,
)
from app.domain.audit_outbox import AuditOutboxRecord
from app.domain.bitstring_status_list import (
    CredentialStatusEntry,
    StatusPurpose,
    generate_status_list_id,
)
from app.domain.credential_status import (
    CredentialAlreadyRevokedError,
    CredentialNotFoundError,
    CredentialStatus,
)
from app.domain.persistence import (
    AuditEvent,
    AuditEventType,
    DuplicateEntityError,
    PersistedCredential,
    PersistenceUnavailableError,
)


NOW = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)


def credential(
    *,
    status: CredentialStatus = CredentialStatus.ACTIVE,
    expiration_date: datetime | None = None,
) -> PersistedCredential:
    revoked = status is CredentialStatus.REVOKED
    return PersistedCredential(
        id="64b64c0f0123456789abcdef",
        credential_id="urn:uuid:credential-1",
        issuer_did="did:web:issuer.example.test",
        holder_did="did:key:zholder",
        credential_type=("VerifiableCredential",),
        issuance_date=NOW - timedelta(days=1),
        expiration_date=expiration_date,
        credential_hash="a" * 64,
        status=status,
        raw_credential={"id": "urn:uuid:credential-1"},
        created_at=NOW - timedelta(days=1),
        updated_at=NOW - timedelta(days=1),
        revoked_at=NOW if revoked else None,
        revoked_by="usr_local_issuer" if revoked else None,
        revocation_reason="Affiliation ended" if revoked else None,
        version=2 if revoked else 1,
    )


class FakeRevocationRepository:
    def __init__(self, stored: PersistedCredential | None) -> None:
        self.stored = stored
        self.last_outbox: AuditOutboxRecord | None = None

    def get_by_credential_id(
        self,
        credential_id: str,
    ) -> PersistedCredential | None:
        if self.stored is None or self.stored.credential_id != credential_id:
            return None
        return self.stored

    def revoke(
        self,
        credential_id: str,
        *,
        revoked_at: datetime,
        revoked_by: str,
        revocation_reason: str,
        expected_version: int,
        status_entry: CredentialStatusEntry,
        audit_outbox: AuditOutboxRecord,
    ) -> PersistedCredential:
        assert self.stored is not None
        if self.stored.status is CredentialStatus.REVOKED:
            raise CredentialAlreadyRevokedError
        assert credential_id == self.stored.credential_id
        assert expected_version == self.stored.version
        self.last_outbox = audit_outbox
        self.stored = replace(
            self.stored,
            status=CredentialStatus.REVOKED,
            revoked_at=revoked_at,
            revoked_by=revoked_by,
            revocation_reason=revocation_reason,
            status_list_id=status_entry.status_list_id,
            status_list_index=status_entry.status_list_index,
            updated_at=revoked_at,
            version=expected_version + 1,
        )
        return self.stored

    def mark_expired(
        self,
        credential_id: str,
        *,
        expired_at: datetime,
        expected_version: int,
    ) -> PersistedCredential:
        assert self.stored is not None
        assert credential_id == self.stored.credential_id
        assert expected_version == self.stored.version
        self.stored = replace(
            self.stored,
            status=CredentialStatus.EXPIRED,
            updated_at=expired_at,
            version=expected_version + 1,
        )
        return self.stored


class FakeAuditRepository:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []
        self.fail_next = False

    def append(self, event: AuditEvent) -> AuditEvent:
        if self.fail_next:
            self.fail_next = False
            raise PersistenceUnavailableError("Temporary audit failure.")
        if any(existing.id == event.id for existing in self.events):
            raise DuplicateEntityError("Duplicate audit id.")
        self.events.append(event)
        return event

    def get_by_id(self, event_id: str) -> AuditEvent | None:
        return next(
            (event for event in self.events if event.id == event_id),
            None,
        )

    def list_recent(
        self,
        *,
        event_type: AuditEventType | None = None,
        limit: int = 100,
    ) -> tuple[AuditEvent, ...]:
        events = (
            self.events
            if event_type is None
            else [
                event
                for event in self.events
                if event.event_type is event_type
            ]
        )
        return tuple(reversed(events[-limit:]))


class FakeStatusListService:
    def ensure_entry(
        self,
        stored: PersistedCredential,
    ) -> CredentialStatusEntry:
        return CredentialStatusEntry(
            id="100000000000000000000001",
            credential_id=stored.credential_id,
            issuer_did=stored.issuer_did,
            status_list_id=generate_status_list_id(stored.issuer_did),
            status_list_index=7,
            status_purpose=StatusPurpose.REVOCATION,
            created_at=NOW,
            updated_at=NOW,
        )


class FakeAuditDelivery:
    def __init__(
        self,
        repository: FakeAuditRepository,
        revocations: FakeRevocationRepository,
    ) -> None:
        self.repository = repository
        self.revocations = revocations
        self.records: dict[str, AuditOutboxRecord] = {}

    def enqueue(self, record: AuditOutboxRecord) -> AuditOutboxRecord:
        self.records.setdefault(record.event.id, record)
        return self.records[record.event.id]

    def ensure(self, record: AuditOutboxRecord) -> AuditOutboxRecord:
        return self.enqueue(record)

    def deliver_event(self, event_id: str) -> bool:
        record = self.records.get(event_id)
        if (
            record is None
            and self.revocations.last_outbox is not None
            and self.revocations.last_outbox.event.id == event_id
        ):
            record = self.revocations.last_outbox
        if record is None:
            return False
        try:
            self.repository.append(record.event)
        except PersistenceUnavailableError:
            return False
        except DuplicateEntityError:
            return True
        return True


def service(
    stored: PersistedCredential | None,
) -> tuple[
    CredentialRevocationService,
    FakeRevocationRepository,
    FakeAuditRepository,
]:
    repository = FakeRevocationRepository(stored)
    audit_repository = FakeAuditRepository()
    delivery = FakeAuditDelivery(audit_repository, repository)
    value = CredentialRevocationService(
        revocation_repository=repository,
        status_list_service=FakeStatusListService(),
        audit_delivery_service=delivery,
        clock=lambda: NOW,
        event_id_generator=lambda: (
            f"{len(audit_repository.events) + 1:024x}"
        ),
    )
    return value, repository, audit_repository


def test_revoke_records_permanent_metadata_and_audit_event() -> None:
    application, repository, audit = service(credential())

    snapshot = application.revoke(
        "urn:uuid:credential-1",
        reason="  Affiliation ended  ",
        revoked_by="usr_local_issuer",
        correlation_id="request-1",
    )

    assert snapshot.status is CredentialStatus.REVOKED
    assert snapshot.revoked is True
    assert snapshot.revocation_reason == "Affiliation ended"
    assert repository.stored is not None
    assert repository.stored.version == 2
    assert len(audit.events) == 1
    assert audit.events[0].event_type is AuditEventType.CREDENTIAL_REVOKED
    assert audit.events[0].subject_id == snapshot.credential_id
    assert audit.events[0].actor_id == "usr_local_issuer"
    assert audit.events[0].metadata == {"status": "REVOKED"}


def test_revoke_is_rejected_after_first_success() -> None:
    application, _, audit = service(
        credential(status=CredentialStatus.REVOKED)
    )

    with pytest.raises(CredentialAlreadyRevokedError):
        application.revoke(
            "urn:uuid:credential-1",
            reason="Second attempt",
            revoked_by="usr_local_admin",
            correlation_id="request-2",
        )

    assert len(audit.events) == 1
    assert audit.events[0].event_type is AuditEventType.CREDENTIAL_REVOKED


def test_status_lookup_retries_durable_audit_after_transient_failure() -> None:
    application, repository, audit = service(credential())
    audit.fail_next = True

    snapshot = application.revoke(
        "urn:uuid:credential-1",
        reason="Affiliation ended",
        revoked_by="usr_local_issuer",
        correlation_id="request-failed-audit",
    )

    assert snapshot.status is CredentialStatus.REVOKED
    assert repository.stored is not None
    assert repository.stored.status is CredentialStatus.REVOKED
    snapshot = application.get_status(
        "urn:uuid:credential-1",
        correlation_id="request-repair-audit",
    )

    assert snapshot.status is CredentialStatus.REVOKED
    assert [event.event_type for event in audit.events] == [
        AuditEventType.CREDENTIAL_REVOKED,
        AuditEventType.STATUS_CHECKED,
    ]


def test_status_check_persists_expiration_and_audits() -> None:
    application, repository, audit = service(
        credential(expiration_date=NOW)
    )

    snapshot = application.get_status(
        "urn:uuid:credential-1",
        correlation_id="request-3",
    )

    assert snapshot.status is CredentialStatus.EXPIRED
    assert repository.stored is not None
    assert repository.stored.version == 2
    assert audit.events[0].event_type is AuditEventType.STATUS_CHECKED
    assert audit.events[0].metadata == {"status": "EXPIRED"}


def test_missing_credential_does_not_create_an_audit_event() -> None:
    application, _, audit = service(None)

    with pytest.raises(CredentialNotFoundError):
        application.get_status(
            "urn:uuid:missing",
            correlation_id="request-4",
        )

    assert audit.events == []
