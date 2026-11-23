"""Recovery events use the wallet subject, and a blind production check is not LOW."""

from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest

from app.infrastructure.risk.fraud_gateway import (
    FraudRecoveryRiskGateway,
    RecoveryRiskUnavailableError,
)
from app.infrastructure.risk.security_event_forwarder import to_security_event, wallet_subject

KEY = b"k" * 32


def _gateway(environment, body):
    client = SimpleNamespace(post=lambda *_a, **_k: httpx.Response(200, json=body, request=httpx.Request("POST", "http://f")))
    settings = SimpleNamespace(fraud_service_token="t" * 32, environment=environment, fraud_base_url="http://f", fraud_timeout_seconds=1)
    return FraudRecoveryRiskGateway(settings, client=client)


def test_production_refuses_a_low_with_no_history():
    with pytest.raises(RecoveryRiskUnavailableError):
        _gateway("production", {"risk_level": "LOW", "data_quality": "NOT_CONFIGURED"}).assess_recovery(wallet_id="w", reason="r")


def test_production_accepts_a_low_built_on_history():
    assert _gateway("production", {"risk_level": "LOW", "data_quality": "PLATFORM_HISTORY"}).assess_recovery(wallet_id="w", reason="r") == "LOW"


def test_development_may_run_without_the_store():
    assert _gateway("development", {"risk_level": "LOW", "data_quality": "NOT_CONFIGURED"}).assess_recovery(wallet_id="w", reason="r") == "LOW"


def test_event_uses_the_risk_subject_and_no_raw_identifier():
    document = {
        "_id": "recovery_audit_" + "a" * 64, "eventType": "GUARDIAN_PROOF_REJECTED", "aggregateId": "req-1",
        "actorId": "user-raw", "occurredAt": datetime(2026, 11, 5, tzinfo=UTC), "metadata": {"guardianId": "g-raw"},
    }
    event = to_security_event(document, key=KEY, origin="OPERATIONAL", wallet_id="wallet-raw")
    assert event["resource_ref"] == wallet_subject("wallet-raw")
    assert event["event_type"] == "recovery.proof_rejected"
    text = str(event)
    assert "user-raw" not in text and "g-raw" not in text and "wallet-raw" not in text


def test_unmapped_events_are_not_forwarded():
    document = {"_id": "x", "eventType": "RECOVERY_RECONCILED", "occurredAt": datetime(2026, 11, 5, tzinfo=UTC)}
    assert to_security_event(document, key=KEY, origin="OPERATIONAL", wallet_id=None) is None
