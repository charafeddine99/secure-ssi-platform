from dataclasses import replace

import pytest

from app.domain.recovery import RecoveryConflictError, RecoveryReason
from app.infrastructure.persistence.indexes import (
    APPROVAL_INDEXES,
    GUARDIAN_INDEXES,
    POLICY_INDEXES,
    REQUEST_INDEXES,
    SHARE_INDEXES,
)
from app.infrastructure.persistence.mappers import (
    guardian_from_document,
    guardian_to_document,
    policy_from_document,
    policy_to_document,
    request_from_document,
    request_to_document,
    share_from_document,
    share_to_document,
)
from tests.support import WALLET_ID, build_runtime, configure_guardians


def test_domain_mappers_round_trip_recovery_documents() -> None:
    runtime = build_runtime()
    guardian_ids = configure_guardians(runtime)
    request = runtime.service.create_request(
        runtime.owner, wallet_id=WALLET_ID, reason=RecoveryReason.KEY_LOSS
    )
    guardian = runtime.repository.get_guardian(guardian_ids[0])
    policy = runtime.repository.get_policy(WALLET_ID)
    share = next(iter(runtime.repository.shares.values()))
    assert guardian is not None and policy is not None

    assert guardian_from_document(guardian_to_document(guardian)) == guardian
    assert policy_from_document(policy_to_document(policy)) == policy
    assert request_from_document(request_to_document(request)) == request
    assert share_from_document(share_to_document(share)) == share


def test_memory_repository_enforces_optimistic_versions() -> None:
    runtime = build_runtime()
    guardian_ids = configure_guardians(runtime)
    guardian = runtime.repository.get_guardian(guardian_ids[0])
    assert guardian is not None
    with pytest.raises(RecoveryConflictError):
        runtime.repository.update_guardian(
            replace(guardian, display_name="Lost update", version=2),
            expected_version=99,
        )


def test_required_mongo_indexes_cover_uniqueness_and_due_work() -> None:
    names = {
        index.document["name"]
        for index in (
            *GUARDIAN_INDEXES,
            *POLICY_INDEXES,
            *REQUEST_INDEXES,
            *APPROVAL_INDEXES,
            *SHARE_INDEXES,
        )
    }
    assert {
        "uq_guardians_wallet_user_active",
        "uq_recovery_policy_wallet",
        "uq_recovery_active_wallet",
        "uq_recovery_approval_guardian",
        "uq_recovery_share_request_guardian",
        "ix_recovery_timelock_due",
        "ix_recovery_stale_execution",
    }.issubset(names)
