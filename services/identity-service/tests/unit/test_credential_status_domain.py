from datetime import UTC, datetime, timedelta

import pytest

from app.domain.credential_status import (
    CredentialAlreadyRevokedError,
    CredentialStatus,
    CredentialStatusSnapshot,
    InvalidCredentialStatusTransitionError,
    InvalidRevocationReasonError,
    RevocationPolicy,
)


NOW = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)


def test_credential_status_vocabulary_is_stable() -> None:
    assert tuple(status.value for status in CredentialStatus) == (
        "ACTIVE",
        "REVOKED",
        "SUSPENDED",
        "EXPIRED",
    )


def test_revoked_snapshot_requires_complete_metadata() -> None:
    snapshot = CredentialStatusSnapshot(
        credential_id="urn:uuid:credential-1",
        status=CredentialStatus.REVOKED,
        expiration_date=NOW + timedelta(days=1),
        revoked_at=NOW,
        revocation_reason="Affiliation ended",
        revoked_by="usr_local_issuer",
        version=2,
    )

    assert snapshot.revoked is True
    with pytest.raises(ValueError):
        CredentialStatusSnapshot(
            credential_id=snapshot.credential_id,
            status=CredentialStatus.REVOKED,
            expiration_date=snapshot.expiration_date,
            revoked_at=NOW,
            revocation_reason=None,
            revoked_by=snapshot.revoked_by,
            version=2,
        )


@pytest.mark.parametrize("reason", ["", "   ", "invalid\nreason", "x" * 501])
def test_revocation_reason_policy_rejects_invalid_values(
    reason: str,
) -> None:
    with pytest.raises(InvalidRevocationReasonError):
        RevocationPolicy.normalize_reason(reason)


def test_revocation_policy_normalizes_and_is_irreversible() -> None:
    assert RevocationPolicy.normalize_reason("  Affiliation ended  ") == (
        "Affiliation ended"
    )
    RevocationPolicy.require_transition(
        current=CredentialStatus.ACTIVE,
        target=CredentialStatus.REVOKED,
    )
    with pytest.raises(CredentialAlreadyRevokedError):
        RevocationPolicy.require_revocable(CredentialStatus.REVOKED)
    with pytest.raises(InvalidCredentialStatusTransitionError):
        RevocationPolicy.require_transition(
            current=CredentialStatus.REVOKED,
            target=CredentialStatus.ACTIVE,
        )


def test_expiration_never_overrides_revocation() -> None:
    assert RevocationPolicy.effective_status(
        stored_status=CredentialStatus.ACTIVE,
        expiration_date=NOW,
        checked_at=NOW,
    ) is CredentialStatus.EXPIRED
    assert RevocationPolicy.effective_status(
        stored_status=CredentialStatus.REVOKED,
        expiration_date=NOW,
        checked_at=NOW,
    ) is CredentialStatus.REVOKED
