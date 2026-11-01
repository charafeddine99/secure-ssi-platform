from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def synthetic_fraud_service_for_identity_integration(monkeypatch: pytest.MonkeyPatch):
    """Keep in-process integration journeys deterministic and network isolated.

    These tests exercise Identity's end-to-end policy path, not the external
    Fraud Service transport. Transport success, malformed response, and outage
    are covered separately by fraud-client tests and the explicit outage case.
    """
    from app.application.services.oid4vp_service import fraud_client

    monkeypatch.setattr(
        fraud_client,
        "evaluate_presentation_risk",
        lambda **_kwargs: {
            "risk_score": 15,
            "risk_level": "LOW",
            "is_anomaly": False,
            "recommended_action": "ALLOW",
            "reasons": ["synthetic isolated integration signal"],
            "model_version": "test-rule-heuristic-v1",
            "risk_signals": ["synthetic_test_signal"],
            "advisory_only": True,
            "source": "fraud_service",
        },
    )
