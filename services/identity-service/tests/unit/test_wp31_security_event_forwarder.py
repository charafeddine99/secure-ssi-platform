"""Audit rows become minimal, pseudonymous events, and an outage loses nothing."""

from datetime import UTC, datetime

import httpx
import pytest

from app.application.services.security_event_forwarder import (
    DEVELOPMENT_KEY,
    SecurityEventForwarder,
    build_forwarder,
    to_security_event,
)
from tests.support.fake_mongo import FakeDatabase

KEY = b"k" * 32
NOW = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)


def audit(number, event_type="PRESENTATION_REJECTED", **fields):
    return {
        "_id": f"{number:024x}", "eventType": event_type, "subjectId": "did:example:holder-raw",
        "actorId": "user-raw", "correlationId": "corr-raw", "metadata": {}, "createdAt": NOW,
        "chainSeq": number, **fields,
    }


class Transport:
    def __init__(self, status=202):
        self.status = status
        self.bodies = []

    def post(self, url, headers, json):
        self.bodies.append(json)
        return httpx.Response(self.status, request=httpx.Request("POST", url))


def forwarder(database, transport):
    return SecurityEventForwarder(
        database, base_url="http://fraud", token="t" * 32, key=KEY,
        origin="SYNTHETIC_TEST", environment="test", client=transport,
    )


def test_raw_identifiers_and_free_metadata_do_not_leave():
    event = to_security_event(
        audit(1, metadata={"reason": "secret text with spaces", "policy_result": "REJECTED", "claims": "x"}),
        key=KEY, origin="OPERATIONAL",
    )
    text = str(event)
    assert "did:example" not in text and "user-raw" not in text and "corr-raw" not in text
    assert "claims" not in text and "secret text" not in text
    assert event["attributes"] == {"policy_result": "REJECTED"}
    assert event["event_type"] == "presentation.rejected"


def test_sign_in_events_share_one_reference_across_success_and_failure():
    failure = to_security_event(audit(1, "LOGIN_FAILURE", subjectId="login:abc", actorId=None), key=KEY, origin="OPERATIONAL")
    success = to_security_event(audit(2, "LOGIN_SUCCESS", subjectId="login:abc"), key=KEY, origin="OPERATIONAL")
    assert failure["actor_ref"] == success["actor_ref"] is not None


def test_unmapped_audit_types_are_not_forwarded():
    assert to_security_event(audit(1, "STATUS_CHECKED"), key=KEY, origin="OPERATIONAL") is None


def test_cursor_advances_only_after_acceptance():
    database = FakeDatabase()
    database["audit_events"].documents.extend([audit(1), audit(2)])
    down = Transport(status=503)
    with pytest.raises(httpx.HTTPStatusError):
        forwarder(database, down).deliver_once()
    assert database["security_event_forwarder"].documents == []
    up = Transport()
    assert forwarder(database, up).deliver_once() == 2
    assert [e["event_id"] for e in up.bodies[0]["events"]] == [f"audit:{1:024x}", f"audit:{2:024x}"]
    assert forwarder(database, up).deliver_once() == 0
    assert up.bodies[1]["events"] == []


def test_an_empty_cycle_still_reports_liveness():
    transport = Transport()
    forwarder(FakeDatabase(), transport).deliver_once()
    assert transport.bodies[0]["source"] == "identity-service"


def test_forwarder_refuses_development_secrets_in_production(monkeypatch):
    monkeypatch.setenv("FRAUD_INTERNAL_SERVICE_TOKEN", "t" * 32)
    monkeypatch.setenv("SECURITY_EVENT_PSEUDONYM_KEY", DEVELOPMENT_KEY)
    assert build_forwarder(FakeDatabase(), "production") is None
    assert build_forwarder(FakeDatabase(), "development") is not None


def test_forwarder_is_off_without_a_key(monkeypatch):
    monkeypatch.setenv("FRAUD_INTERNAL_SERVICE_TOKEN", "t" * 32)
    monkeypatch.delenv("SECURITY_EVENT_PSEUDONYM_KEY", raising=False)
    assert build_forwarder(FakeDatabase(), "development") is None
