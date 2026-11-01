"""WP-08: Verification Policy Evaluator — Status & Trust Policy Integration.

This application-layer service assembles the nine pre-computed verification
gate results (produced by the calling service) into a single, immutable
:class:`~app.domain.verification_policy.VerificationPolicyResult`.

Hierarchy of authority (fail-closed)
-------------------------------------
1.  **Cryptographic gate** — any failure here immediately yields ``REJECTED``.
    The nine gates evaluated in order are:

    1. Credential format validity
    2. Issuer trust (trust-registry lookup)
    3. Cryptographic signature
    4. Holder binding (proof-of-possession)
    5. Credential expiration
    6. Revocation / status (Bitstring Status List + persistence)
    7. Session nonce / challenge
    8. DCQL query satisfaction
    9. Consent compliance

2.  **AI risk gate** — only reached when *all* nine cryptographic gates pass:
    - ``LOW`` (0 – 39)    → ``ACCEPTED``
    - ``MEDIUM`` (40 – 69)→ ``REJECTED`` (step-up required)
    - ``HIGH`` (70 – 84)  → ``REJECTED``
    - ``CRITICAL`` (85+)  → ``REJECTED`` + quarantine side-effect

This service is intentionally **stateless** and **side-effect-free** (the
quarantine *side-effect* is delegated to the caller's infrastructure layer;
this service only sets ``quarantine_triggered=True`` in the result).
"""
from __future__ import annotations

from app.domain.verification_policy import (
    AiRiskLevel,
    PolicyCheckName,
    PolicyCheckResult,
    PolicyDecision,
    VerificationPolicyResult,
)


class VerificationPolicyEvaluator:
    """Converts nine named check results + an AI risk score into a policy outcome.

    Usage::

        from app.application.services.verification_policy_service import (
            VerificationPolicyEvaluator,
        )
        from app.domain.verification_policy import PolicyCheckResult, PolicyCheckName

        result = VerificationPolicyEvaluator.evaluate(
            credential_valid=PolicyCheckResult.ok(PolicyCheckName.CREDENTIAL_VALID),
            issuer_trusted=PolicyCheckResult.ok(PolicyCheckName.ISSUER_TRUSTED),
            signature_valid=PolicyCheckResult.ok(PolicyCheckName.SIGNATURE_VALID),
            holder_binding=PolicyCheckResult.ok(PolicyCheckName.HOLDER_BINDING),
            expiration=PolicyCheckResult.ok(PolicyCheckName.EXPIRATION),
            revocation_status=PolicyCheckResult.ok(PolicyCheckName.REVOCATION_STATUS),
            session_nonce=PolicyCheckResult.ok(PolicyCheckName.SESSION_NONCE),
            dcql_satisfaction=PolicyCheckResult.ok(PolicyCheckName.DCQL_SATISFACTION),
            consent_compliance=PolicyCheckResult.ok(PolicyCheckName.CONSENT_COMPLIANCE),
            ai_risk_score=15,
        )
        assert result.decision == "ACCEPTED"
    """

    # Evaluation order is fixed; do **not** reorder — it matches the canonical
    # nine-point list in the Master Implementation Plan §13.
    _CRYPTO_GATE_ORDER: tuple[PolicyCheckName, ...] = (
        PolicyCheckName.CREDENTIAL_VALID,
        PolicyCheckName.ISSUER_TRUSTED,
        PolicyCheckName.SIGNATURE_VALID,
        PolicyCheckName.HOLDER_BINDING,
        PolicyCheckName.EXPIRATION,
        PolicyCheckName.REVOCATION_STATUS,
        PolicyCheckName.SESSION_NONCE,
        PolicyCheckName.DCQL_SATISFACTION,
        PolicyCheckName.CONSENT_COMPLIANCE,
    )

    @classmethod
    def ai_risk_level_from_score(cls, score: int) -> AiRiskLevel:
        """Map a raw 0-100 risk score to an :class:`AiRiskLevel` tier."""
        if score >= 85:
            return AiRiskLevel.CRITICAL
        if score >= 70:
            return AiRiskLevel.HIGH
        if score >= 40:
            return AiRiskLevel.MEDIUM
        return AiRiskLevel.LOW

    @classmethod
    def evaluate(
        cls,
        *,
        credential_valid: PolicyCheckResult,
        issuer_trusted: PolicyCheckResult,
        signature_valid: PolicyCheckResult,
        holder_binding: PolicyCheckResult,
        expiration: PolicyCheckResult,
        revocation_status: PolicyCheckResult,
        session_nonce: PolicyCheckResult,
        dcql_satisfaction: PolicyCheckResult,
        consent_compliance: PolicyCheckResult,
        ai_risk_score: int | None,
    ) -> VerificationPolicyResult:
        """Evaluate the nine-gate + AI policy and return an immutable result.

        The method is *pure* — it never raises, never writes to any storage,
        and never blocks.  All side-effects (e.g. quarantine anchoring) MUST be
        handled by the caller based on ``result.quarantine_triggered``.

        Args:
            credential_valid: Gate 1 — W3C VC 2.0 format validity.
            issuer_trusted: Gate 2 — Issuer present in the trust registry.
            signature_valid: Gate 3 — Cryptographic signature verification.
            holder_binding: Gate 4 — Proof-of-possession over the VP.
            expiration: Gate 5 — ``validUntil`` / ``expirationDate`` check.
            revocation_status: Gate 6 — Bitstring Status List + DB status.
            session_nonce: Gate 7 — Nonce/challenge bound to the session.
            dcql_satisfaction: Gate 8 — DCQL query criteria are met.
            consent_compliance: Gate 9 — Holder consent is honoured.
            ai_risk_score: 0 – 100 risk score from the fraud engine, or ``None``
                when the authoritative risk service is unavailable.

        Returns:
            :class:`~app.domain.verification_policy.VerificationPolicyResult` —
            always succeeds; never raises.
        """
        # Absence of an authoritative risk response is not a zero/LOW score.
        safe_score = (
            max(0, min(100, ai_risk_score)) if ai_risk_score is not None else None
        )
        ai_level = (
            cls.ai_risk_level_from_score(safe_score)
            if safe_score is not None
            else AiRiskLevel.UNAVAILABLE
        )

        # Ordered crypto-gate tuple (canonical ordering)
        gate_map: dict[PolicyCheckName, PolicyCheckResult] = {
            PolicyCheckName.CREDENTIAL_VALID: credential_valid,
            PolicyCheckName.ISSUER_TRUSTED: issuer_trusted,
            PolicyCheckName.SIGNATURE_VALID: signature_valid,
            PolicyCheckName.HOLDER_BINDING: holder_binding,
            PolicyCheckName.EXPIRATION: expiration,
            PolicyCheckName.REVOCATION_STATUS: revocation_status,
            PolicyCheckName.SESSION_NONCE: session_nonce,
            PolicyCheckName.DCQL_SATISFACTION: dcql_satisfaction,
            PolicyCheckName.CONSENT_COMPLIANCE: consent_compliance,
        }
        ordered_checks = tuple(gate_map[name] for name in cls._CRYPTO_GATE_ORDER)

        # --- Gate 1: cryptographic failure hierarchy ---
        first_failure: PolicyCheckResult | None = None
        for check in ordered_checks:
            if not check.passed:
                first_failure = check
                break

        if first_failure is not None:
            # Fail-closed: any crypto gate failure → REJECTED, period.
            return VerificationPolicyResult(
                decision=PolicyDecision.REJECTED,
                crypto_checks=ordered_checks,
                ai_risk_level=ai_level,
                ai_risk_score=safe_score,
                first_failure=first_failure,
            )

        # --- Gate 2: authoritative risk result (only reachable when all crypto pass) ---
        if safe_score is None:
            return VerificationPolicyResult(
                decision=PolicyDecision.REJECTED,
                crypto_checks=ordered_checks,
                ai_risk_level=AiRiskLevel.UNAVAILABLE,
                ai_risk_score=None,
                details={
                    "riskAssessmentStatus": "UNAVAILABLE",
                    "reason": "RISK_UNAVAILABLE; automatic acceptance is denied.",
                },
            )

        quarantine_triggered = False
        quarantine_reason: str | None = None

        if ai_level is AiRiskLevel.LOW:
            decision = PolicyDecision.ACCEPTED
        elif ai_level is AiRiskLevel.MEDIUM:
            decision = PolicyDecision.REJECTED
        elif ai_level is AiRiskLevel.HIGH:
            decision = PolicyDecision.REJECTED
        else:  # CRITICAL
            decision = PolicyDecision.REJECTED
            quarantine_triggered = True
            quarantine_reason = (
                f"Automated AI threat engine quarantine (Risk Score: {safe_score}/100)"
            )

        return VerificationPolicyResult(
            decision=decision,
            crypto_checks=ordered_checks,
            ai_risk_level=ai_level,
            ai_risk_score=safe_score,
            quarantine_triggered=quarantine_triggered,
            quarantine_reason=quarantine_reason,
        )
