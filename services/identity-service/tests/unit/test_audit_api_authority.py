"""The audit API reads only the authoritative MongoDB store (no SQLite merge, no fake success)."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1 import audit
from app.domain.persistence import AuditEventType, PersistenceUnavailableError


def _event(event_id: str, metadata: dict) -> SimpleNamespace:
    return SimpleNamespace(
        id=event_id,
        event_type=AuditEventType.CREDENTIAL_REVOKED,
        actor_id="usr_issuer",
        subject_id="urn:uuid:1",
        metadata=metadata,
        created_at=datetime(2026, 10, 29, tzinfo=UTC),
    )


class FakeRepo:
    def __init__(self, events=(), error: Exception | None = None):
        self.events = list(events)
        self.error = error
        self.calls = []

    def list_recent(self, *, event_type, limit):
        self.calls.append(event_type)
        if self.error:
            raise self.error
        return self.events


def test_unavailable_store_is_503_not_success():
    repo = FakeRepo(error=PersistenceUnavailableError("down"))
    with pytest.raises(HTTPException) as caught:
        audit._load_entries(repo, None, 10)
    assert caught.value.status_code == 503


def test_risk_score_is_null_when_absent_and_kept_when_present():
    repo = FakeRepo([_event("a", {}), _event("b", {"riskScore": 42})])
    entries = audit._load_entries(repo, None, 10)
    assert [e.risk_score for e in entries] == [None, 42]


def test_unknown_event_type_matches_nothing_instead_of_everything():
    repo = FakeRepo([_event("a", {})])
    assert audit._load_entries(repo, "NOT_A_REAL_EVENT", 10) == []
    assert repo.calls == []


def test_no_sqlite_reader_remains_in_the_audit_route():
    assert not hasattr(audit, "db_get_audit_logs")
