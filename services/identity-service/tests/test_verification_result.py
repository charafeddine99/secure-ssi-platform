from datetime import UTC, datetime

import pytest

from app.domain.vc import (
    CredentialVerificationResult,
    VerificationCheck,
    VerificationCheckName,
    VerificationCheckStatus,
    VerificationReasonCode,
)


def successful_checks() -> tuple[VerificationCheck, ...]:
    return tuple(
        VerificationCheck(
            name=name,
            status=(
                VerificationCheckStatus.NOT_APPLICABLE
                if name is VerificationCheckName.CREDENTIAL_STATUS
                else VerificationCheckStatus.PASSED
            ),
        )
        for name in VerificationCheckName
    )


def replace_check(
    checks: tuple[VerificationCheck, ...],
    replacement: VerificationCheck,
) -> tuple[VerificationCheck, ...]:
    return tuple(
        replacement if check.name is replacement.name else check
        for check in checks
    )


def test_success_requires_every_security_check() -> None:
    result = CredentialVerificationResult(
        verified_at=datetime(2026, 1, 1, tzinfo=UTC),
        checks=successful_checks(),
    )

    serialized = result.to_dict()

    assert result.verified is True
    assert serialized["verified"] is True
    assert serialized["verifiedAt"] == "2026-01-01T00:00:00Z"
    assert serialized["checks"]["credentialStatus"] == {
        "status": "notApplicable",
        "reasonCode": None,
    }
    assert serialized["reasonCodes"] == []


def test_signature_failure_produces_an_explicit_reason_code() -> None:
    checks = replace_check(
        successful_checks(),
        VerificationCheck(
            name=VerificationCheckName.SIGNATURE,
            status=VerificationCheckStatus.FAILED,
            reason_code=VerificationReasonCode.SIGNATURE_INVALID,
        ),
    )

    result = CredentialVerificationResult(
        verified_at=datetime(2026, 1, 1, tzinfo=UTC),
        checks=checks,
    )

    assert result.verified is False
    assert result.to_dict()["reasonCodes"] == ["SIGNATURE_INVALID"]


def test_unchecked_issuer_trust_prevents_overstating_verification() -> None:
    checks = replace_check(
        successful_checks(),
        VerificationCheck(
            name=VerificationCheckName.ISSUER_TRUST,
            status=VerificationCheckStatus.NOT_CHECKED,
            reason_code=VerificationReasonCode.CHECK_NOT_PERFORMED,
        ),
    )

    result = CredentialVerificationResult(
        verified_at=datetime(2026, 1, 1, tzinfo=UTC),
        checks=checks,
    )

    assert result.verified is False
    assert result.reason_codes == (
        VerificationReasonCode.CHECK_NOT_PERFORMED,
    )


def test_missing_or_duplicate_checks_are_rejected() -> None:
    with pytest.raises(ValueError, match="exactly once"):
        CredentialVerificationResult(
            verified_at=datetime(2026, 1, 1, tzinfo=UTC),
            checks=successful_checks()[:-1],
        )

    with pytest.raises(ValueError, match="unique"):
        CredentialVerificationResult(
            verified_at=datetime(2026, 1, 1, tzinfo=UTC),
            checks=successful_checks() + (successful_checks()[0],),
        )


def test_failed_check_requires_a_reason_code() -> None:
    with pytest.raises(ValueError, match="requires a reason"):
        VerificationCheck(
            name=VerificationCheckName.SIGNATURE,
            status=VerificationCheckStatus.FAILED,
        )


def test_verified_at_must_be_timezone_aware() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        CredentialVerificationResult(
            verified_at=datetime(2026, 1, 1),
            checks=successful_checks(),
        )
