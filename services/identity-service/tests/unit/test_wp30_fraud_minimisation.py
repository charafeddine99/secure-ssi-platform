"""Identity sends the fraud service only what its rules use."""

from hashlib import sha256

import pytest

from app.infrastructure.clients import fraud_client as module
from app.infrastructure.clients.fraud_client import FraudRiskClient

DID = "did:example:holder-wp30"
IP = "203.0.113.9"
AGENT = "Synthetic Browser 1.0"
FINGERPRINT = "synthetic-device-fingerprint"


@pytest.fixture
def sent(monkeypatch):
    calls = []

    class Response:
        status_code = 200

        def json(self):
            return {"risk_score": 0.1, "risk_level": "LOW", "advisory_only": True, "reasons": [], "model_version": "x", "risk_signals": []}

    class Client:
        def __init__(self, **_):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def post(self, _url, json, headers):
            calls.append(json)
            return Response()

    monkeypatch.setenv("FRAUD_INTERNAL_SERVICE_TOKEN", "identity-to-fraud-test-secret-32-bytes")
    monkeypatch.setattr(module.httpx, "Client", Client)
    return calls


def _no_raw_identifier(payload) -> None:
    text = str(payload)
    assert DID not in text and IP not in text and AGENT not in text and FINGERPRINT not in text
    assert "client_ip" not in payload and "user_agent" not in payload
    assert payload["did"] == "subject:" + sha256(DID.encode()).hexdigest()


def test_risk_call_sends_no_raw_identifier(sent) -> None:
    FraudRiskClient(base_url="http://fraud-service:8000").evaluate_presentation_risk(
        did=DID, client_ip=IP, user_agent=AGENT, device_fingerprint=FINGERPRINT
    )
    _no_raw_identifier(sent[0])
    assert "device_fingerprint" not in sent[0]


def test_event_report_sends_no_raw_identifier(sent) -> None:
    FraudRiskClient(base_url="http://fraud-service:8000").report_event(
        event_type="CREDENTIAL_PRESENTED", did=DID, client_ip=IP, user_agent=AGENT, device_fingerprint=FINGERPRINT
    )
    _no_raw_identifier(sent[0])
    assert sent[0]["device_fingerprint"] == sha256(FINGERPRINT.encode()).hexdigest()
