from typing import Any, cast

import pytest

from app.domain.recovery import RecoveryConflictError, RecoveryReason
from app.infrastructure.persistence.indexes import ensure_recovery_indexes
from app.infrastructure.persistence.mongo_repository import (
    MongoRecoveryRepository,
)
from tests.fake_mongo import Database
from tests.support import WALLET_ID, build_runtime, configure_guardians


def test_mongo_repository_round_trip_indexes_and_compare_and_set() -> None:
    source = build_runtime()
    guardian_ids = configure_guardians(source)
    request = source.service.create_request(
        source.owner, wallet_id=WALLET_ID, reason=RecoveryReason.KEY_LOSS
    )
    source.service.approve(
        source.guardians[0],
        request.request_id,
        guardian_id=guardian_ids[0],
        challenge=request.challenge.value,
    )
    database = Database()
    ensure_recovery_indexes(cast(Any, database))
    ensure_recovery_indexes(cast(Any, database))
    repository = MongoRecoveryRepository(cast(Any, database))

    for guardian_id in guardian_ids:
        guardian = source.repository.get_guardian(guardian_id)
        assert guardian is not None
        repository.add_guardian(guardian)
    policy = source.repository.get_policy(WALLET_ID)
    assert policy is not None
    repository.upsert_policy(policy, expected_version=None)
    repository.save_share_set(tuple(source.repository.shares.values()))
    repository.add_request(request)
    approval = source.repository.list_approvals(request.request_id)[0]
    stored_approval, created = repository.add_approval_idempotently(approval)

    assert created and stored_approval == approval
    assert repository.get_policy(WALLET_ID) == policy
    assert repository.get_request(request.request_id) == request
    assert len(repository.list_guardians(wallet_id=WALLET_ID)) == 5
    assert repository.count_active_guardians() == 5
    assert repository.get_share(
        policy_id=request.policy.policy_id,
        policy_version=request.policy.policy_version,
        share_version=request.policy.share_version,
        guardian_id=guardian_ids[0],
    ) is not None
    assert all(collection.indexes for collection in database.collections.values())
    with pytest.raises(RecoveryConflictError):
        repository.update_request(request, expected_version=999)


def test_mongo_repository_approval_is_idempotent_but_conflicts_on_change() -> None:
    source = build_runtime()
    guardian_ids = configure_guardians(source)
    request = source.service.create_request(
        source.owner, wallet_id=WALLET_ID, reason=RecoveryReason.KEY_LOSS
    )
    approval, _ = source.service.approve(
        source.guardians[0],
        request.request_id,
        guardian_id=guardian_ids[0],
        challenge=request.challenge.value,
    )
    repository = MongoRecoveryRepository(cast(Any, Database()))
    first, created = repository.add_approval_idempotently(approval)
    repeated, repeated_created = repository.add_approval_idempotently(approval)

    assert first == repeated and created and not repeated_created
