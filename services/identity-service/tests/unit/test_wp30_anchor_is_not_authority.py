"""A blockchain anchor can never change a verification or trust decision."""

import inspect

import pytest

from app.application.services.trust_registry_service import TrustRegistryService
from app.application.services.verification_policy_service import (
    VerificationPolicyEvaluator,
)
from app.domain.blockchain_anchor import AnchorEventType

ANCHORABLE = {"DID_DOCUMENT", "STATUS_LIST", "CREDENTIAL_REVOCATION", "QUARANTINE", "AUDIT_EVENT"}


def _names(function) -> list[str]:
    return [name.lower() for name in inspect.signature(function).parameters]


def test_policy_decision_takes_no_anchor_input() -> None:
    names = _names(VerificationPolicyEvaluator.evaluate)
    assert "signature_valid" in names
    assert not [n for n in names if "anchor" in n or "chain" in n]


def test_issuer_trust_takes_no_anchor_input() -> None:
    names = _names(TrustRegistryService.evaluate_issuer_trust)
    assert "issuer_did" in names
    assert not [n for n in names if "anchor" in n or "chain" in n]


def test_only_listed_event_classes_can_be_anchored() -> None:
    assert {event.name for event in AnchorEventType} == ANCHORABLE
    with pytest.raises(ValueError):
        AnchorEventType("RAW_CREDENTIAL")
