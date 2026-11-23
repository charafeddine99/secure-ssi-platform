"""Gateway telemetry: classification, privacy and bounded memory."""

import asyncio

import httpx
import pytest

from app.core import telemetry
from app.core.telemetry import TelemetryBuffer, classify, route_group


class Client:
    def __init__(self, status=202):
        self.status = status
        self.bodies = []

    async def post(self, url, headers, json):
        self.bodies.append(json)
        return httpx.Response(self.status, request=httpx.Request("POST", url))


def buffer(client=None):
    return TelemetryBuffer(url="http://fraud", token="t" * 32, key=b"k" * 32, origin="SYNTHETIC_TEST", environment="test", client=client or Client())


@pytest.mark.parametrize(("group", "status", "expected"), [
    ("login", 401, "gateway.login.rejected"),
    ("identity", 401, "auth.session.rejected"),
    ("identity", 403, "authz.denied"),
    ("identity", 429, "api.rate_limited"),
    ("oid4vci_token", 400, "oid4vci.token.failure"),
    ("oid4vci_credential", 400, "oid4vci.credential.failure"),
    ("oid4vp", 409, "oid4vp.request.failure"),
    ("identity", 400, None),
    ("oid4vp", 404, None),
    ("identity", 200, None),
    ("identity", 500, None),
])
def test_only_named_statuses_become_security_signals(group, status, expected):
    assert classify(group, status) == expected


def test_route_groups_hold_no_identifiers():
    assert route_group("/api/v1/identity/wallets/wallet_123/keys") == "identity"
    assert route_group("/api/v1/oid4vp/requests/session_abc/holder-request") == "oid4vp"


def test_ip_and_path_are_not_sent():
    client = Client()
    target = buffer(client)
    target.record("/api/v1/identity/wallets/wallet_123", 403, "203.0.113.9")
    asyncio.run(target.flush())
    text = str(client.bodies[0])
    assert "203.0.113.9" not in text and "wallet_123" not in text
    assert client.bodies[0]["events"][0]["source_ref"].startswith("src:")


def test_requests_become_per_minute_counts(monkeypatch):
    client = Client()
    target = buffer(client)
    monkeypatch.setattr(telemetry.time, "time", lambda: 6000.0)
    for _ in range(3):
        target.record("/api/v1/identity/auth/me", 200, "203.0.113.9")
    monkeypatch.setattr(telemetry.time, "time", lambda: 6060.0)
    asyncio.run(target.flush())
    event = client.bodies[0]["events"][0]
    assert event["event_type"] == "api.request" and event["count"] == 3


def test_overflow_is_counted_not_hidden():
    target = buffer()
    for _ in range(telemetry.MAX_QUEUE + 5):
        target.record("/api/v1/identity/x", 403, "203.0.113.9")
    assert target.dropped == 5


def test_failed_delivery_keeps_events_and_reports_it():
    target = buffer(Client(status=503))
    target.record("/api/v1/identity/x", 403, "203.0.113.9")
    asyncio.run(target.flush())
    assert target.failures == 1 and len(target._queue) == 1
