"""WP-08: Verification Policy Domain — Status & Trust Policy Integration.

This module provides the domain value objects that make the verifier's final
acceptance decision **explicit, auditable, and fail-closed**.  Every check is a
named :class:`PolicyCheckResult`.  The aggregated :class:`VerificationPolicyResult`
carries the definitive ``decision`` (ACCEPTED / REJECTED) together with a
structured audit trail.

Design invariants
-----------------
- All dataclasses are **frozen** (immutable once created).
- :class:`~app.application.services.verification_policy_service.VerificationPolicyEvaluator`
  is the **only** place that constructs a :class:`VerificationPolicyResult`.
- ``ACCEPTED`` is only reachable when *every* cryptographic check passes **and**
  the AI risk level is ``LOW``.
- A single ``False`` in any cryptographic gate yields ``REJECTED`` — period.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class PolicyDecision(StrEnum):
    """Final policy outcome for a single verification session."""

    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class PolicyCheckName(StrEnum):
    """Canonical names of the nine verification gates used in WP-08 policy."""

    CREDENTIAL_VALID = "credential_valid"
    ISSUER_TRUSTED = "issuer_trusted"
    SIGNATURE_VALID = "signature_valid"
    HOLDER_BINDING = "holder_binding"
    EXPIRATION = "expiration"
    REVOCATION_STATUS = "revocation_status"
    SESSION_NONCE = "session_nonce"
    DCQL_SATISFACTION = "dcql_satisfaction"
    CONSENT_COMPLIANCE = "consent_compliance"


class AiRiskLevel(StrEnum):
    """Adaptive-AI risk tier used after cryptographic gates all pass."""

    LOW = "LOW"          # 0 – 39  → policy ACCEPTED
    MEDIUM = "MEDIUM"    # 40 – 69 → policy REJECTED (step-up required)
    HIGH = "HIGH"        # 70 – 84 → policy REJECTED
    CRITICAL = "CRITICAL"  # 85 – 100 → policy REJECTED + quarantine
    UNAVAILABLE = "UNAVAILABLE"  # no authoritative risk result → policy REJECTED


# ---------------------------------------------------------------------------
# Single-check value object
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PolicyCheckResult:
    """Result of one named verification gate.

    Args:
        name: Which gate this result represents.
        passed: ``True`` iff the check passed.
        reason: Human-readable explanation; required when ``passed`` is ``False``.
    """

    name: PolicyCheckName
    passed: bool
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.passed and not self.reason:
            raise ValueError(
                f"PolicyCheckResult '{self.name}' is FAILED but carries no reason."
            )

    # ------------------------------------------------------------------
    # Convenience constructors
    # ------------------------------------------------------------------

    @classmethod
    def ok(cls, name: PolicyCheckName, *, reason: str = "Check passed.") -> "PolicyCheckResult":
        """Convenience constructor for a passing check."""
        return cls(name=name, passed=True, reason=reason)

    @classmethod
    def fail(cls, name: PolicyCheckName, *, reason: str) -> "PolicyCheckResult":
        """Convenience constructor for a failing check."""
        return cls(name=name, passed=False, reason=reason)


# ---------------------------------------------------------------------------
# Aggregated policy result (immutable, audit-ready)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerificationPolicyResult:
    """Aggregated, auditable outcome of the nine-gate + AI policy evaluation.

    This is the **authoritative** record produced by
    :class:`~app.application.services.verification_policy_service.VerificationPolicyEvaluator`.

    Attributes:
        decision: Final ``ACCEPTED`` / ``REJECTED`` verdict.
        crypto_checks: Ordered tuple of all nine cryptographic gate results.
        ai_risk_level: Adaptive-AI tier (only used as a *secondary* gate — it
            cannot override a failed cryptographic check).
        ai_risk_score: Raw 0 – 100 score from the fraud engine.
        quarantine_triggered: ``True`` when ``ai_risk_score >= 85`` **and** all
            cryptographic gates passed.
        quarantine_reason: Free-text reason for the quarantine action.
        first_failure: The first failing :class:`PolicyCheckResult`, or ``None``
            if all cryptographic checks passed.
        details: Arbitrary key/value evidence for audit logging.
    """

    decision: PolicyDecision
    crypto_checks: tuple[PolicyCheckResult, ...]
    ai_risk_level: AiRiskLevel
    ai_risk_score: int | None
    quarantine_triggered: bool = False
    quarantine_reason: str | None = None
    first_failure: PolicyCheckResult | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.ai_risk_score is None and self.ai_risk_level is not AiRiskLevel.UNAVAILABLE:
            raise ValueError("A missing risk score requires ai_risk_level=UNAVAILABLE.")
        if self.ai_risk_score is not None and not 0 <= self.ai_risk_score <= 100:
            raise ValueError(
                f"ai_risk_score must be in [0, 100], got {self.ai_risk_score}."
            )
        if self.ai_risk_score is not None and self.ai_risk_level is AiRiskLevel.UNAVAILABLE:
            raise ValueError("ai_risk_level=UNAVAILABLE cannot carry a risk score.")
        if self.quarantine_triggered and not self.quarantine_reason:
            raise ValueError(
                "quarantine_triggered=True requires a quarantine_reason."
            )

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    @property
    def accepted(self) -> bool:
        """Shorthand for ``decision == PolicyDecision.ACCEPTED``."""
        return self.decision is PolicyDecision.ACCEPTED

    @property
    def all_crypto_passed(self) -> bool:
        """True iff every cryptographic gate in ``crypto_checks`` passed."""
        return all(c.passed for c in self.crypto_checks)

    def check(self, name: PolicyCheckName) -> PolicyCheckResult | None:
        """Return the result for a named gate, or ``None`` if not present."""
        for c in self.crypto_checks:
            if c.name is name:
                return c
        return None

    # ------------------------------------------------------------------
    # Serialisation helper (for audit logs and API responses)
    # ------------------------------------------------------------------

    def to_audit_dict(self) -> dict[str, Any]:
        """Return a structured dict suitable for audit log storage."""
        return {
            "decision": self.decision.value,
            "allCryptoPassed": self.all_crypto_passed,
            "aiRiskLevel": self.ai_risk_level.value,
            "aiRiskScore": self.ai_risk_score,
            "riskAssessmentStatus": (
                "AVAILABLE" if self.ai_risk_score is not None else "UNAVAILABLE"
            ),
            "quarantineTriggered": self.quarantine_triggered,
            "quarantineReason": self.quarantine_reason,
            "firstFailure": (
                {
                    "name": self.first_failure.name.value,
                    "reason": self.first_failure.reason,
                }
                if self.first_failure
                else None
            ),
            "checks": [
                {
                    "name": c.name.value,
                    "passed": c.passed,
                    "reason": c.reason,
                }
                for c in self.crypto_checks
            ],
        }
