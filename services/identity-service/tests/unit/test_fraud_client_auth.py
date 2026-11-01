from __future__ import annotations

import pytest

from app.infrastructure.clients import fraud_client as fraud_client_module
from app.infrastructure.clients.fraud_client import (
    FraudRiskClient,
    FraudRiskUnavailableError,
)


def test_identity_fraud_client_uses_internal_service_credential(monkeypatch):
    service_secret = "identity-to-fraud-test-secret-32-bytes"
    monkeypatch.setenv("FRAUD_INTERNAL_SERVICE_TOKEN", service_secret)
    requests = []

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "risk_score": 0.2,
                "risk_level": "LOW",
                "is_anomaly": False,
                "recommended_action": "ALLOW",
                "reasons": [],
                "model_version": "rule-heuristic-v1",
                "risk_signals": [],
                "advisory_only": True,
            }

    class FakeHttpClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def post(self, url, *, json, headers):
            requests.append((url, headers))
            return FakeResponse()

    monkeypatch.setattr(fraud_client_module.httpx, "Client", FakeHttpClient)
    client = FraudRiskClient(base_url="http://fraud-service:8000")

    result = client.evaluate_presentation_risk(did="did:key:holder")
    client.report_event(event_type="LOGIN", did="did:key:holder")

    assert result["source"] == "fraud_service"
    assert len(requests) == 2
    assert requests[0][0].endswith("/api/v1/fraud/evaluate")
    assert requests[1][0].endswith("/api/v1/fraud/events")
    assert all(
        headers == {"X-Internal-Service-Token": service_secret}
        for _, headers in requests
    )


def test_identity_fraud_client_omits_unconfigured_internal_credential(monkeypatch):
    monkeypatch.delenv("FRAUD_INTERNAL_SERVICE_TOKEN", raising=False)
    monkeypatch.setattr(fraud_client_module, "FRAUD_INTERNAL_SERVICE_TOKEN", "")
    requests = []

    class FakeResponse:
        status_code = 401

    class FakeHttpClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def post(self, url, **kwargs):
            requests.append((url, kwargs.get("headers", {})))
            return FakeResponse()

    monkeypatch.setattr(fraud_client_module.httpx, "Client", FakeHttpClient)
    client = FraudRiskClient(base_url="http://fraud-service:8000")

    with pytest.raises(FraudRiskUnavailableError) as exc_info:
        client.evaluate_presentation_risk(did="did:key:holder")

    assert exc_info.value.code == "RISK_UNAVAILABLE"
    assert requests
    assert all("X-Internal-Service-Token" not in headers for _, headers in requests)


def test_identity_fraud_client_rejects_malformed_or_non_advisory_response(monkeypatch):
    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "risk_score": 0.2,
                "risk_level": "LOW",
                "reasons": [],
                "risk_signals": [],
                "model_version": "rule-heuristic-v1",
                "advisory_only": False,
            }

    class FakeHttpClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def post(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr(fraud_client_module.httpx, "Client", FakeHttpClient)
    client = FraudRiskClient(base_url="http://fraud-service:8000")

    with pytest.raises(FraudRiskUnavailableError, match="RISK_UNAVAILABLE"):
        client.evaluate_presentation_risk(did="did:key:holder")
