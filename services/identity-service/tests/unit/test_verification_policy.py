"""WP-08 Unit Tests — Verification Policy Domain & Evaluator.

Covers:
 - PolicyCheckResult domain invariants (frozen, reason required on failure)
 - VerificationPolicyResult invariants (score range, quarantine requires reason)
 - VerificationPolicyEvaluator strict cryptographic failure hierarchy
 - AI risk tier mapping (LOW/MEDIUM/HIGH/CRITICAL thresholds)
 - Quarantine flag is only set at CRITICAL risk when all crypto passes
 - to_audit_dict serialisation
 - Convenience constructors (ok / fail)
"""
from __future__ import annotations

import pytest

from app.domain.verification_policy import (
    AiRiskLevel,
    PolicyCheckName,
    PolicyCheckResult,
    PolicyDecision,
    VerificationPolicyResult,
)
from app.application.services.verification_policy_service import (
    VerificationPolicyEvaluator,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _all_ok() -> dict[str, PolicyCheckResult]:
    """Return a dict of nine passing check results (keyword-ready)."""
    return {
        "credential_valid": PolicyCheckResult.ok(PolicyCheckName.CREDENTIAL_VALID),
        "issuer_trusted": PolicyCheckResult.ok(PolicyCheckName.ISSUER_TRUSTED),
        "signature_valid": PolicyCheckResult.ok(PolicyCheckName.SIGNATURE_VALID),
        "holder_binding": PolicyCheckResult.ok(PolicyCheckName.HOLDER_BINDING),
        "expiration": PolicyCheckResult.ok(PolicyCheckName.EXPIRATION),
        "revocation_status": PolicyCheckResult.ok(PolicyCheckName.REVOCATION_STATUS),
        "session_nonce": PolicyCheckResult.ok(PolicyCheckName.SESSION_NONCE),
        "dcql_satisfaction": PolicyCheckResult.ok(PolicyCheckName.DCQL_SATISFACTION),
        "consent_compliance": PolicyCheckResult.ok(PolicyCheckName.CONSENT_COMPLIANCE),
    }


def _evaluate(**overrides: PolicyCheckResult | int) -> VerificationPolicyResult:
    """Call VerificationPolicyEvaluator.evaluate with all-OK defaults, plus overrides."""
    kwargs = _all_ok()
    ai_score = overrides.pop("ai_risk_score", 10)
    kwargs.update(overrides)  # type: ignore[arg-type]
    return VerificationPolicyEvaluator.evaluate(**kwargs, ai_risk_score=ai_score)


# ---------------------------------------------------------------------------
# PolicyCheckResult domain invariants
# ---------------------------------------------------------------------------


class TestPolicyCheckResult:
    def test_ok_factory_sets_passed(self) -> None:
        r = PolicyCheckResult.ok(PolicyCheckName.CREDENTIAL_VALID)
        assert r.passed is True
        assert r.name is PolicyCheckName.CREDENTIAL_VALID

    def test_fail_factory_sets_reason(self) -> None:
        r = PolicyCheckResult.fail(PolicyCheckName.SIGNATURE_VALID, reason="Bad sig")
        assert r.passed is False
        assert r.reason == "Bad sig"

    def test_fail_without_reason_raises(self) -> None:
        with pytest.raises(ValueError, match="no reason"):
            PolicyCheckResult(name=PolicyCheckName.SIGNATURE_VALID, passed=False, reason="")

    def test_frozen_immutability(self) -> None:
        r = PolicyCheckResult.ok(PolicyCheckName.CREDENTIAL_VALID)
        with pytest.raises((AttributeError, TypeError)):
            r.passed = False  # type: ignore[misc]

    def test_ok_can_carry_custom_reason(self) -> None:
        r = PolicyCheckResult.ok(PolicyCheckName.EXPIRATION, reason="Active until 2030")
        assert "2030" in r.reason


# ---------------------------------------------------------------------------
# VerificationPolicyResult invariants
# ---------------------------------------------------------------------------


class TestVerificationPolicyResult:
    def _minimal_result(
        self,
        *,
        score: int = 10,
        decision: PolicyDecision = PolicyDecision.ACCEPTED,
    ) -> VerificationPolicyResult:
        checks = tuple(
            PolicyCheckResult.ok(name) for name in PolicyCheckName
        )
        return VerificationPolicyResult(
            decision=decision,
            crypto_checks=checks,
            ai_risk_level=AiRiskLevel.LOW,
            ai_risk_score=score,
        )

    def test_score_out_of_range_raises(self) -> None:
        checks = tuple(PolicyCheckResult.ok(n) for n in PolicyCheckName)
        with pytest.raises(ValueError, match="ai_risk_score must be in"):
            VerificationPolicyResult(
                decision=PolicyDecision.REJECTED,
                crypto_checks=checks,
                ai_risk_level=AiRiskLevel.LOW,
                ai_risk_score=101,
            )

    def test_quarantine_without_reason_raises(self) -> None:
        checks = tuple(PolicyCheckResult.ok(n) for n in PolicyCheckName)
        with pytest.raises(ValueError, match="quarantine_triggered=True requires"):
            VerificationPolicyResult(
                decision=PolicyDecision.REJECTED,
                crypto_checks=checks,
                ai_risk_level=AiRiskLevel.CRITICAL,
                ai_risk_score=90,
                quarantine_triggered=True,
                quarantine_reason=None,
            )

    def test_accepted_property(self) -> None:
        r = self._minimal_result(decision=PolicyDecision.ACCEPTED)
        assert r.accepted is True

    def test_rejected_property(self) -> None:
        r = self._minimal_result(decision=PolicyDecision.REJECTED)
        assert r.accepted is False

    def test_check_lookup_by_name(self) -> None:
        r = self._minimal_result()
        c = r.check(PolicyCheckName.CREDENTIAL_VALID)
        assert c is not None
        assert c.passed is True

    def test_check_returns_none_for_missing(self) -> None:
        # Edge: empty crypto_checks tuple
        r = VerificationPolicyResult(
            decision=PolicyDecision.REJECTED,
            crypto_checks=(),
            ai_risk_level=AiRiskLevel.LOW,
            ai_risk_score=5,
        )
        assert r.check(PolicyCheckName.CREDENTIAL_VALID) is None

    def test_all_crypto_passed_true_when_all_ok(self) -> None:
        r = self._minimal_result()
        assert r.all_crypto_passed is True

    def test_all_crypto_passed_false_when_one_fails(self) -> None:
        ok_checks = list(PolicyCheckResult.ok(n) for n in PolicyCheckName)
        # Replace one with a failure
        ok_checks[2] = PolicyCheckResult.fail(PolicyCheckName.SIGNATURE_VALID, reason="Bad")
        r = VerificationPolicyResult(
            decision=PolicyDecision.REJECTED,
            crypto_checks=tuple(ok_checks),
            ai_risk_level=AiRiskLevel.LOW,
            ai_risk_score=5,
            first_failure=ok_checks[2],
        )
        assert r.all_crypto_passed is False

    def test_to_audit_dict_shape(self) -> None:
        r = self._minimal_result()
        d = r.to_audit_dict()
        assert d["decision"] == "ACCEPTED"
        assert d["allCryptoPassed"] is True
        assert d["aiRiskLevel"] == "LOW"
        assert isinstance(d["checks"], list)
        assert len(d["checks"]) == len(list(PolicyCheckName))
        assert d["firstFailure"] is None


# ---------------------------------------------------------------------------
# VerificationPolicyEvaluator — AI risk tier mapping
# ---------------------------------------------------------------------------


class TestAiRiskLevelMapping:
    @pytest.mark.parametrize("score,expected", [
        (0, AiRiskLevel.LOW),
        (15, AiRiskLevel.LOW),
        (39, AiRiskLevel.LOW),
        (40, AiRiskLevel.MEDIUM),
        (55, AiRiskLevel.MEDIUM),
        (69, AiRiskLevel.MEDIUM),
        (70, AiRiskLevel.HIGH),
        (84, AiRiskLevel.HIGH),
        (85, AiRiskLevel.CRITICAL),
        (100, AiRiskLevel.CRITICAL),
    ])
    def test_score_to_level(self, score: int, expected: AiRiskLevel) -> None:
        level = VerificationPolicyEvaluator.ai_risk_level_from_score(score)
        assert level is expected


# ---------------------------------------------------------------------------
# VerificationPolicyEvaluator — cryptographic failure hierarchy
# ---------------------------------------------------------------------------


class TestCryptographicFailureHierarchy:
    """Invariant: AI cannot override any cryptographic gate failure."""

    @pytest.mark.parametrize("gate_name,reason", [
        (PolicyCheckName.CREDENTIAL_VALID, "Format invalid"),
        (PolicyCheckName.ISSUER_TRUSTED, "Not in registry"),
        (PolicyCheckName.SIGNATURE_VALID, "Bad signature"),
        (PolicyCheckName.HOLDER_BINDING, "Holder mismatch"),
        (PolicyCheckName.EXPIRATION, "Expired"),
        (PolicyCheckName.REVOCATION_STATUS, "Revoked"),
        (PolicyCheckName.SESSION_NONCE, "Nonce mismatch"),
        (PolicyCheckName.DCQL_SATISFACTION, "Query not satisfied"),
        (PolicyCheckName.CONSENT_COMPLIANCE, "Consent violated"),
    ])
    def test_each_gate_failure_rejects_even_at_zero_ai_risk(
        self, gate_name: PolicyCheckName, reason: str
    ) -> None:
        result = _evaluate(
            **{gate_name.value: PolicyCheckResult.fail(gate_name, reason=reason)},
            ai_risk_score=0,
        )
        assert result.decision is PolicyDecision.REJECTED, (
            f"Gate '{gate_name}' failed but decision was not REJECTED"
        )
        assert result.first_failure is not None
        assert result.first_failure.name is gate_name

    def test_ai_score_zero_cannot_override_signature_failure(self) -> None:
        result = _evaluate(
            signature_valid=PolicyCheckResult.fail(PolicyCheckName.SIGNATURE_VALID, reason="Bad"),
            ai_risk_score=0,
        )
        assert result.decision is PolicyDecision.REJECTED
        assert result.quarantine_triggered is False

    def test_ai_score_zero_cannot_override_expiration_failure(self) -> None:
        result = _evaluate(
            expiration=PolicyCheckResult.fail(PolicyCheckName.EXPIRATION, reason="Expired"),
            ai_risk_score=0,
        )
        assert result.decision is PolicyDecision.REJECTED

    def test_all_pass_low_risk_is_accepted(self) -> None:
        result = _evaluate(ai_risk_score=15)
        assert result.decision is PolicyDecision.ACCEPTED
        assert result.first_failure is None
        assert result.all_crypto_passed is True


# ---------------------------------------------------------------------------
# VerificationPolicyEvaluator — AI gate (all crypto pass)
# ---------------------------------------------------------------------------


class TestAiGate:
    def test_low_risk_accepted(self) -> None:
        result = _evaluate(ai_risk_score=39)
        assert result.decision is PolicyDecision.ACCEPTED

    def test_medium_risk_rejected(self) -> None:
        result = _evaluate(ai_risk_score=40)
        assert result.decision is PolicyDecision.REJECTED
        assert result.quarantine_triggered is False

    def test_high_risk_rejected(self) -> None:
        result = _evaluate(ai_risk_score=70)
        assert result.decision is PolicyDecision.REJECTED
        assert result.quarantine_triggered is False

    def test_critical_risk_rejected_and_quarantined(self) -> None:
        result = _evaluate(ai_risk_score=85)
        assert result.decision is PolicyDecision.REJECTED
        assert result.quarantine_triggered is True
        assert result.quarantine_reason is not None
        assert "85" in result.quarantine_reason

    def test_critical_100_quarantine_reason_carries_score(self) -> None:
        result = _evaluate(ai_risk_score=100)
        assert result.quarantine_triggered is True
        assert "100" in (result.quarantine_reason or "")

    def test_medium_risk_does_not_set_quarantine(self) -> None:
        result = _evaluate(ai_risk_score=69)
        assert result.quarantine_triggered is False

    def test_high_risk_does_not_set_quarantine(self) -> None:
        result = _evaluate(ai_risk_score=84)
        assert result.quarantine_triggered is False


# ---------------------------------------------------------------------------
# VerificationPolicyEvaluator — quarantine only when all crypto pass
# ---------------------------------------------------------------------------


class TestQuarantineNotSetWhenCryptoFails:
    def test_critical_ai_with_crypto_failure_does_not_quarantine(self) -> None:
        """Even at CRITICAL AI risk, crypto failure must not set quarantine_triggered."""
        result = _evaluate(
            signature_valid=PolicyCheckResult.fail(
                PolicyCheckName.SIGNATURE_VALID, reason="Invalid"
            ),
            ai_risk_score=95,
        )
        # Must be REJECTED for crypto reasons, quarantine NOT triggered
        assert result.decision is PolicyDecision.REJECTED
        assert result.quarantine_triggered is False


# ---------------------------------------------------------------------------
# VerificationPolicyEvaluator — score clamping
# ---------------------------------------------------------------------------


class TestScoreClamping:
    def test_score_above_100_is_clamped_to_100(self) -> None:
        result = _evaluate(ai_risk_score=200)
        assert result.ai_risk_score == 100
        assert result.ai_risk_level is AiRiskLevel.CRITICAL

    def test_score_below_0_is_clamped_to_0(self) -> None:
        result = _evaluate(ai_risk_score=-5)
        assert result.ai_risk_score == 0
        assert result.ai_risk_level is AiRiskLevel.LOW


# ---------------------------------------------------------------------------
# VerificationPolicyEvaluator — ordered check tuple
# ---------------------------------------------------------------------------


class TestOrderedChecks:
    def test_nine_checks_in_result(self) -> None:
        result = _evaluate(ai_risk_score=10)
        assert len(result.crypto_checks) == 9

    def test_first_failure_is_earliest_in_canonical_order(self) -> None:
        """When multiple gates fail, first_failure must be the earliest in canonical order."""
        result = _evaluate(
            credential_valid=PolicyCheckResult.fail(
                PolicyCheckName.CREDENTIAL_VALID, reason="Invalid"
            ),
            signature_valid=PolicyCheckResult.fail(
                PolicyCheckName.SIGNATURE_VALID, reason="Also invalid"
            ),
            ai_risk_score=0,
        )
        # credential_valid (gate 1) must be first_failure, not signature (gate 3)
        assert result.first_failure is not None
        assert result.first_failure.name is PolicyCheckName.CREDENTIAL_VALID
