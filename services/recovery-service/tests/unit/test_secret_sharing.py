from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.application.ports.secret_sharing import SecretSharingContext
from app.domain.recovery import SecretShareError
from app.infrastructure.secret_sharing.pycryptodome_provider import (
    PyCryptodomeSecretSharingProvider,
)


NOW = datetime(2026, 8, 12, tzinfo=UTC)
SECRET = b"sixteen-byte-key"
GUARDIANS = tuple(f"guardian_{index:016d}" for index in range(1, 6))
CONTEXT = SecretSharingContext(
    recovery_request_id="recovery_0000000000000001",
    policy_id="policy_0000000000000001",
    policy_version=4,
    share_version=2,
)


def provider() -> PyCryptodomeSecretSharingProvider:
    return PyCryptodomeSecretSharingProvider(b"K" * 32)


def test_split_reconstructs_with_exact_threshold_and_more_than_threshold() -> None:
    adapter = provider()
    split = adapter.split(
        SECRET,
        threshold=3,
        guardian_ids=GUARDIANS,
        context=CONTEXT,
        created_at=NOW,
    )

    assert len(split.shares) == 5
    assert adapter.combine(
        split.shares[:3],
        threshold=3,
        context=CONTEXT,
        expected_commitment=split.commitment,
    ) == SECRET
    assert adapter.combine(
        split.shares[:4],
        threshold=3,
        context=CONTEXT,
        expected_commitment=split.commitment,
    ) == SECRET


def test_insufficient_and_duplicate_shares_are_rejected() -> None:
    adapter = provider()
    split = adapter.split(
        SECRET,
        threshold=3,
        guardian_ids=GUARDIANS,
        context=CONTEXT,
        created_at=NOW,
    )

    with pytest.raises(SecretShareError):
        adapter.combine(
            split.shares[:2],
            threshold=3,
            context=CONTEXT,
            expected_commitment=split.commitment,
        )
    with pytest.raises(SecretShareError, match="Duplicate"):
        adapter.combine(
            (split.shares[0], split.shares[0], split.shares[2]),
            threshold=3,
            context=CONTEXT,
            expected_commitment=split.commitment,
        )


def test_malformed_tampered_and_wrong_version_shares_are_rejected() -> None:
    adapter = provider()
    split = adapter.split(
        SECRET,
        threshold=3,
        guardian_ids=GUARDIANS,
        context=CONTEXT,
        created_at=NOW,
    )
    share = split.shares[0]

    with pytest.raises(SecretShareError):
        adapter.validate_share(
            replace(share, encrypted_envelope="not-base64!"), context=CONTEXT
        )
    changed = (
        "A" if share.encrypted_envelope[0] != "A" else "B"
    ) + share.encrypted_envelope[1:]
    with pytest.raises(SecretShareError):
        adapter.validate_share(
            replace(share, encrypted_envelope=changed), context=CONTEXT
        )
    with pytest.raises(SecretShareError, match="policy version"):
        adapter.validate_share(
            share, context=replace(CONTEXT, policy_version=5)
        )


def test_share_from_another_recovery_and_wrong_commitment_are_rejected() -> None:
    adapter = provider()
    split = adapter.split(
        SECRET,
        threshold=3,
        guardian_ids=GUARDIANS,
        context=CONTEXT,
        created_at=NOW,
    )

    with pytest.raises(SecretShareError, match="policy version"):
        adapter.validate_share(
            split.shares[0],
            context=replace(
                CONTEXT, recovery_request_id="recovery_0000000000000002"
            ),
        )
    with pytest.raises(SecretShareError, match="commitment"):
        adapter.combine(
            split.shares[:3],
            threshold=3,
            context=CONTEXT,
            expected_commitment="0" * 64,
        )


def test_share_content_is_redacted_and_not_logged(caplog) -> None:
    adapter = provider()
    split = adapter.split(
        SECRET,
        threshold=2,
        guardian_ids=GUARDIANS[:3],
        context=CONTEXT,
        created_at=NOW,
    )

    representation = repr(split.shares[0])
    assert split.shares[0].encrypted_envelope not in representation
    assert split.shares[0].integrity_digest not in representation
    assert SECRET.decode() not in caplog.text


@pytest.mark.parametrize("threshold,count", [(2, 3), (3, 5), (4, 7)])
def test_supported_generic_thresholds(threshold: int, count: int) -> None:
    adapter = provider()
    guardian_ids = tuple(f"guardian_{index:016d}" for index in range(count))
    split = adapter.split(
        SECRET,
        threshold=threshold,
        guardian_ids=guardian_ids,
        context=CONTEXT,
        created_at=NOW,
    )
    assert adapter.combine(
        split.shares[:threshold],
        threshold=threshold,
        context=CONTEXT,
        expected_commitment=split.commitment,
    ) == SECRET
