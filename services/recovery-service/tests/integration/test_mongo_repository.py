import os
from typing import Any, cast
from uuid import uuid4

import pytest
from pymongo import MongoClient

from app.application.services.metrics import RecoveryMetrics
from app.application.services.recovery_service import RecoveryService
from app.core.config import load_settings
from app.domain.recovery import RecoveryConflictError, RecoveryReason, RecoveryState
from app.infrastructure.persistence.indexes import ensure_recovery_indexes
from app.infrastructure.persistence.mongo_repository import (
    MongoRecoveryRepository,
)
from tests.fake_mongo import Database
from tests.support import WALLET_ID, Sequence, build_runtime, configure_guardians


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


def test_live_mongo_recovery_decision_and_rotation_survive_repository_restart() -> None:
    uri = os.getenv("RECOVERY_TEST_MONGODB_URI")
    if not uri:
        pytest.skip("Set RECOVERY_TEST_MONGODB_URI to run the live Mongo restart check.")

    database_name = f"secure_ssi_test_recovery_g8_{uuid4().hex}"
    clients: list[MongoClient[dict[str, Any]]] = []
    created_database = False
    try:
        first_client = MongoClient(
            uri,
            serverSelectionTimeoutMS=3000,
            tz_aware=True,
        )
        clients.append(first_client)
        assert first_client.admin.command("ping")["ok"] == 1
        created_database = True
        first_database = first_client[database_name]
        ensure_recovery_indexes(cast(Any, first_database))
        first_repository = MongoRecoveryRepository(cast(Any, first_database))
        runtime = build_runtime(repository=first_repository)
        guardian_ids = configure_guardians(runtime, time_lock_seconds=15)
        request = runtime.service.create_request(
            runtime.owner,
            wallet_id=WALLET_ID,
            reason=RecoveryReason.KEY_LOSS,
        )
        decision_proofs = [
            runtime.sign_decision(
                guardian_id=guardian_ids[index],
                request_id=request.request_id,
                challenge=request.challenge.value,
            )
            for index in range(3)
        ]
        runtime.service.approve(
            runtime.guardians[0],
            request.request_id,
            guardian_id=guardian_ids[0],
            challenge=request.challenge.value,
            proof=decision_proofs[0],
        )
        first_client.close()

        second_client = MongoClient(
            uri,
            serverSelectionTimeoutMS=3000,
            tz_aware=True,
        )
        clients.append(second_client)
        second_database = second_client[database_name]
        second_repository = MongoRecoveryRepository(cast(Any, second_database))
        persisted = second_repository.get_request(request.request_id)
        stored_approvals = second_repository.list_approvals(request.request_id)
        assert persisted is not None
        assert persisted.session.quorum.approvals == 1
        assert len(stored_approvals) == 1
        assert stored_approvals[0].proof_digest is not None

        second_service = RecoveryService(
            repository=second_repository,
            secret_sharing=runtime.service._secret_sharing,
            managed_keys=runtime.gateway,
            settings=load_settings({}),
            metrics=RecoveryMetrics(),
            clock=runtime.clock,
            id_generator=Sequence(),
            worker_id="worker_recovery_live_restart",
        )
        for index in (1, 2):
            second_service.approve(
                runtime.guardians[index],
                request.request_id,
                guardian_id=guardian_ids[index],
                challenge=request.challenge.value,
                proof=decision_proofs[index],
            )
        waiting = second_repository.get_request(request.request_id)
        assert waiting is not None
        assert waiting.session.state is RecoveryState.WAITING_TIMELOCK
        original_deadline = waiting.session.executable_after
        assert original_deadline is not None
        second_client.close()

        third_client = MongoClient(
            uri,
            serverSelectionTimeoutMS=3000,
            tz_aware=True,
        )
        clients.append(third_client)
        third_repository = MongoRecoveryRepository(
            cast(Any, third_client[database_name])
        )
        after_restart = third_repository.get_request(request.request_id)
        assert after_restart is not None
        assert after_restart.session.executable_after == original_deadline
        third_service = RecoveryService(
            repository=third_repository,
            secret_sharing=runtime.service._secret_sharing,
            managed_keys=runtime.gateway,
            settings=load_settings({}),
            metrics=RecoveryMetrics(),
            clock=runtime.clock,
            id_generator=Sequence(),
            worker_id="worker_recovery_live_restart_2",
        )
        runtime.clock.advance(seconds=15)
        succeeded, failed = third_service.reconcile_due()
        completed = third_repository.get_request(request.request_id)
        assert (succeeded, failed) == (1, 0)
        assert completed is not None
        assert completed.session.state is RecoveryState.COMPLETED
        assert completed.session.result is not None
        assert completed.session.result.predecessor_did != (
            completed.session.result.successor_did
        )
        assert len(third_repository.list_approvals(request.request_id)) == 3
    finally:
        if created_database:
            cleanup_client = MongoClient(
                uri,
                serverSelectionTimeoutMS=3000,
                tz_aware=True,
            )
            try:
                cleanup_client.drop_database(database_name)
            finally:
                cleanup_client.close()
        for client in clients:
            client.close()
