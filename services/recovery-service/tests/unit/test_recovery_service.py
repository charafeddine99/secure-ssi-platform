from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta

import pytest

from app.domain.auth import RecoveryPrincipal
from app.domain.recovery import (
    GuardianStatus,
    RecoveryAuditEventType,
    RecoveryConflictError,
    RecoveryNotFoundError,
    RecoveryReason,
    RecoveryState,
    RecoveryValidationError,
)
from tests.support import (
    WALLET_ID,
    build_runtime,
    configure_guardians,
)


def test_guardian_create_duplicate_list_suspend_resume_revoke_and_remove() -> None:
    runtime = build_runtime()
    guardian = runtime.service.create_guardian(
        runtime.owner,
        wallet_id=WALLET_ID,
        guardian_user_id=runtime.guardians[0].user_id,
        guardian_did="did:key:zGuardianLifecycle01",
        display_name="Guardian One",
        verification_method="did:key:zGuardianLifecycle01#zGuardianLifecycle01",
    )

    with pytest.raises(RecoveryConflictError):
        runtime.service.create_guardian(
            runtime.owner,
            wallet_id=WALLET_ID,
            guardian_user_id=runtime.guardians[0].user_id,
            guardian_did="did:key:zGuardianLifecycleDuplicate",
            display_name="Duplicate",
            verification_method=(
                "did:key:zGuardianLifecycleDuplicate#zGuardianLifecycleDuplicate"
            ),
        )
    assert runtime.service.list_guardians(runtime.owner) == (guardian,)
    assert runtime.service.list_guardians(runtime.guardians[0]) == (guardian,)
    suspended = runtime.service.update_guardian(
        runtime.owner, guardian.guardian_id, status=GuardianStatus.SUSPENDED
    )
    assert not suspended.can_approve
    resumed = runtime.service.update_guardian(
        runtime.owner, guardian.guardian_id, status=GuardianStatus.ACTIVE
    )
    assert resumed.can_approve
    revoked = runtime.service.update_guardian(
        runtime.owner, guardian.guardian_id, status=GuardianStatus.REVOKED
    )
    assert revoked.status is GuardianStatus.REVOKED
    removed = runtime.service.remove_guardian(runtime.owner, guardian.guardian_id)
    assert removed.status is GuardianStatus.REMOVED


def test_guardian_multi_field_update_advances_one_optimistic_version() -> None:
    runtime = build_runtime()
    guardian = runtime.service.create_guardian(
        runtime.owner,
        wallet_id=WALLET_ID,
        guardian_user_id=runtime.guardians[0].user_id,
        guardian_did="did:key:zGuardianVersion01",
        display_name="Guardian One",
        verification_method="did:key:zGuardianVersion01#zGuardianVersion01",
    )

    updated = runtime.service.update_guardian(
        runtime.owner,
        guardian.guardian_id,
        display_name="Guardian One Updated",
        verification_method="did:key:zGuardianVersion01#rotated",
        status=GuardianStatus.SUSPENDED,
    )

    assert updated.version == guardian.version + 1
    assert updated.display_name == "Guardian One Updated"
    assert updated.status is GuardianStatus.SUSPENDED


def test_guardian_self_assignment_foreign_wallet_and_foreign_mutation_denied() -> None:
    runtime = build_runtime()
    with pytest.raises(RecoveryValidationError):
        runtime.service.create_guardian(
            runtime.owner,
            wallet_id=WALLET_ID,
            guardian_user_id=runtime.owner.user_id,
            guardian_did="did:key:zSelfGuardianDenied",
            display_name="Self",
            verification_method="did:key:zSelfGuardianDenied#zSelfGuardianDenied",
        )
    with pytest.raises(RecoveryNotFoundError):
        runtime.service.create_guardian(
            runtime.owner,
            wallet_id="wallet_foreignabcdefghij",
            guardian_user_id=runtime.guardians[0].user_id,
            guardian_did="did:key:zForeignWalletGuardian",
            display_name="Foreign",
            verification_method="did:key:zForeignWalletGuardian#zForeignWalletGuardian",
        )
    guardian_ids = configure_guardians(runtime)
    with pytest.raises(RecoveryNotFoundError):
        runtime.service.update_guardian(
            runtime.guardians[0],
            guardian_ids[1],
            status=GuardianStatus.SUSPENDED,
        )


@pytest.mark.parametrize("threshold,count", [(2, 3), (3, 5), (4, 7)])
def test_policy_supports_generic_m_of_n(threshold: int, count: int) -> None:
    runtime = build_runtime()
    configure_guardians(runtime, count=count, threshold=threshold)
    policy = runtime.service.get_policy(runtime.owner, wallet_id=WALLET_ID)
    assert policy.minimum_approvals == threshold
    assert policy.maximum_guardians == count


@pytest.mark.parametrize("threshold,count", [(0, 3), (4, 3)])
def test_invalid_policy_threshold_is_rejected(threshold: int, count: int) -> None:
    runtime = build_runtime()
    with pytest.raises(RecoveryValidationError):
        runtime.service.put_policy(
            runtime.owner,
            wallet_id=WALLET_ID,
            minimum_approvals=threshold,
            maximum_guardians=count,
            approval_window_seconds=300,
            time_lock_seconds=10,
            recovery_expiration_seconds=1200,
            maximum_attempts=3,
            cooldown_seconds=0,
            allow_cancellation=True,
        )


def test_invalid_policy_timelock_is_rejected() -> None:
    runtime = build_runtime()
    with pytest.raises(RecoveryValidationError):
        runtime.service.put_policy(
            runtime.owner,
            wallet_id=WALLET_ID,
            minimum_approvals=2,
            maximum_guardians=3,
            approval_window_seconds=300,
            time_lock_seconds=-1,
            recovery_expiration_seconds=1200,
            maximum_attempts=3,
            cooldown_seconds=0,
            allow_cancellation=True,
        )


def test_request_creation_persists_snapshot_but_no_plaintext_share() -> None:
    runtime = build_runtime()
    guardian_ids = configure_guardians(runtime)
    request = runtime.service.create_request(
        runtime.owner,
        wallet_id=WALLET_ID,
        reason=RecoveryReason.ACCOUNT_COMPROMISE,
    )

    assert request.session.state is RecoveryState.PENDING_APPROVALS
    assert request.policy.minimum_approvals == 3
    assert request.policy.guardian_ids == guardian_ids
    assert request.challenge.value != request.nonce.value
    assert len(runtime.repository.shares) == 5
    assert all(
        share.recovery_request_id == request.request_id
        and share.encrypted_envelope
        and "sixteen" not in share.encrypted_envelope
        for share in runtime.repository.shares.values()
    )
    with pytest.raises(RecoveryConflictError):
        runtime.service.create_request(
            runtime.owner,
            wallet_id=WALLET_ID,
            reason=RecoveryReason.KEY_LOSS,
        )


def test_three_of_five_reaches_one_quorum_and_duplicate_is_idempotent() -> None:
    runtime = build_runtime()
    guardian_ids = configure_guardians(runtime)
    request = runtime.service.create_request(
        runtime.owner,
        wallet_id=WALLET_ID,
        reason=RecoveryReason.LOST_ACCESS,
    )

    first, current = runtime.service.approve(
        runtime.guardians[0],
        request.request_id,
        guardian_id=guardian_ids[0],
        challenge=request.challenge.value,
    )
    repeated, repeated_request = runtime.service.approve(
        runtime.guardians[0],
        request.request_id,
        guardian_id=guardian_ids[0],
        challenge=request.challenge.value,
    )
    assert repeated == first
    assert repeated_request == current
    runtime.service.approve(
        runtime.guardians[1],
        request.request_id,
        guardian_id=guardian_ids[1],
        challenge=request.challenge.value,
    )
    _, reached = runtime.service.approve(
        runtime.guardians[2],
        request.request_id,
        guardian_id=guardian_ids[2],
        challenge=request.challenge.value,
    )
    assert reached.session.state is RecoveryState.WAITING_TIMELOCK
    assert reached.session.quorum.approvals == 3
    events = runtime.repository.list_audit_events(request.request_id)
    assert sum(
        event.event_type is RecoveryAuditEventType.RECOVERY_QUORUM_REACHED
        for event in events
    ) == 1
    with pytest.raises(RecoveryConflictError):
        runtime.service.approve(
            runtime.guardians[3],
            request.request_id,
            guardian_id=guardian_ids[3],
            challenge=request.challenge.value,
        )


@pytest.mark.parametrize(
    "inactive_status",
    (
        GuardianStatus.SUSPENDED,
        GuardianStatus.REVOKED,
        GuardianStatus.REMOVED,
    ),
)
def test_wrong_challenge_foreign_and_inactive_guardian_rejected(
    inactive_status: GuardianStatus,
) -> None:
    runtime = build_runtime()
    guardian_ids = configure_guardians(runtime)
    request = runtime.service.create_request(
        runtime.owner,
        wallet_id=WALLET_ID,
        reason=RecoveryReason.KEY_LOSS,
    )
    with pytest.raises(RecoveryConflictError):
        runtime.service.approve(
            runtime.guardians[0],
            request.request_id,
            guardian_id=guardian_ids[0],
            challenge="wrong-challenge-value-that-is-long-enough",
        )
    with pytest.raises(RecoveryNotFoundError):
        runtime.service.approve(
            runtime.guardians[1],
            request.request_id,
            guardian_id=guardian_ids[0],
            challenge=request.challenge.value,
        )
    guardian = runtime.repository.get_guardian(guardian_ids[0])
    assert guardian is not None
    inactive = guardian.transition(inactive_status, at=runtime.clock())
    runtime.repository.update_guardian(inactive, expected_version=guardian.version)
    with pytest.raises(RecoveryConflictError):
        runtime.service.approve(
            runtime.guardians[0],
            request.request_id,
            guardian_id=guardian_ids[0],
            challenge=request.challenge.value,
        )


def test_parallel_approvals_are_unique_and_quorum_is_deterministic() -> None:
    runtime = build_runtime()
    guardian_ids = configure_guardians(runtime)
    request = runtime.service.create_request(
        runtime.owner,
        wallet_id=WALLET_ID,
        reason=RecoveryReason.DEVICE_LOSS,
    )

    def approve(index: int):
        try:
            return runtime.service.approve(
                runtime.guardians[index],
                request.request_id,
                guardian_id=guardian_ids[index],
                challenge=request.challenge.value,
            )
        except RecoveryConflictError:
            return None

    with ThreadPoolExecutor(max_workers=5) as executor:
        outcomes = list(executor.map(approve, range(5)))
    current = runtime.repository.get_request(request.request_id)
    assert current is not None
    assert current.session.state is RecoveryState.WAITING_TIMELOCK
    assert current.session.quorum.approvals >= 3
    approvals = runtime.repository.list_approvals(request.request_id)
    assert 3 <= len(approvals) <= 5
    accepted = [outcome for outcome in outcomes if outcome is not None]
    assert len({approval.approval_id for approval, _ in accepted}) == len(accepted)
    assert sum(
        event.event_type is RecoveryAuditEventType.RECOVERY_QUORUM_REACHED
        for event in runtime.repository.list_audit_events(request.request_id)
    ) == 1


def test_rejections_make_quorum_impossible() -> None:
    runtime = build_runtime()
    guardian_ids = configure_guardians(runtime)
    request = runtime.service.create_request(
        runtime.owner,
        wallet_id=WALLET_ID,
        reason=RecoveryReason.KEY_LOSS,
    )
    current = request
    for index in range(3):
        _, current = runtime.service.reject(
            runtime.guardians[index],
            request.request_id,
            guardian_id=guardian_ids[index],
            challenge=request.challenge.value,
        )
    assert current.session.state is RecoveryState.REJECTED


def test_timelock_blocks_execution_then_worker_rotates_key_and_did() -> None:
    runtime = build_runtime()
    guardian_ids = configure_guardians(runtime, time_lock_seconds=10)
    old_key = runtime.gateway.active_key
    payload = b"historical-signature"
    old_signature = runtime.gateway.sign(old_key, payload)
    request = runtime.service.create_request(
        runtime.owner,
        wallet_id=WALLET_ID,
        reason=RecoveryReason.ACCOUNT_COMPROMISE,
    )
    for index in range(3):
        runtime.service.approve(
            runtime.guardians[index],
            request.request_id,
            guardian_id=guardian_ids[index],
            challenge=request.challenge.value,
        )
    before = runtime.service.reconcile_request(runtime.admin, request.request_id)
    assert before.session.state is RecoveryState.WAITING_TIMELOCK
    assert runtime.gateway.calls == 0
    runtime.clock.advance(seconds=10)
    succeeded, failed = runtime.service.reconcile_due()
    completed = runtime.repository.get_request(request.request_id)
    assert (succeeded, failed) == (1, 0)
    assert completed is not None
    assert completed.session.state is RecoveryState.COMPLETED
    assert completed.session.result is not None
    assert completed.session.result.predecessor_did != completed.session.result.successor_did
    with pytest.raises(RuntimeError):
        runtime.gateway.sign(old_key, b"new-message")
    new_signature = runtime.gateway.sign(runtime.gateway.active_key, payload)
    assert runtime.gateway.verify(old_key, payload, old_signature)
    assert runtime.gateway.verify(runtime.gateway.active_key, payload, new_signature)


def test_reconciliation_preserves_original_quorum_timelock_deadline() -> None:
    runtime = build_runtime()
    guardian_ids = configure_guardians(runtime, time_lock_seconds=10)
    request = runtime.service.create_request(
        runtime.owner,
        wallet_id=WALLET_ID,
        reason=RecoveryReason.KEY_LOSS,
    )
    current = request
    for index in range(3):
        _, current = runtime.service.approve(
            runtime.guardians[index],
            request.request_id,
            guardian_id=guardian_ids[index],
            challenge=request.challenge.value,
        )
    assert current.session.quorum_reached_at is not None
    quorum_only = replace(
        current,
        session=replace(
            current.session,
            state=RecoveryState.QUORUM_REACHED,
            time_lock_started_at=None,
            executable_after=None,
        ),
        version=current.version + 1,
    )
    runtime.repository.update_request(
        quorum_only, expected_version=current.version
    )

    runtime.clock.advance(seconds=20)
    recovered_wait = runtime.service.reconcile_request(
        runtime.admin, request.request_id
    )
    assert recovered_wait.session.executable_after == (
        recovered_wait.session.quorum_reached_at
        + timedelta(seconds=10)
    )
    completed = runtime.service.reconcile_request(runtime.admin, request.request_id)
    assert completed.session.state is RecoveryState.COMPLETED


def test_cancellation_during_timelock_is_idempotent_and_prevents_execution() -> None:
    runtime = build_runtime()
    guardian_ids = configure_guardians(runtime, time_lock_seconds=10)
    request = runtime.service.create_request(
        runtime.owner,
        wallet_id=WALLET_ID,
        reason=RecoveryReason.LOST_ACCESS,
    )
    for index in range(3):
        runtime.service.approve(
            runtime.guardians[index],
            request.request_id,
            guardian_id=guardian_ids[index],
            challenge=request.challenge.value,
        )
    cancelled = runtime.service.cancel(runtime.owner, request.request_id)
    repeated = runtime.service.cancel(runtime.owner, request.request_id)
    runtime.clock.advance(seconds=20)
    runtime.service.reconcile_due()
    assert repeated == cancelled
    assert cancelled.session.state is RecoveryState.CANCELLED
    assert runtime.gateway.calls == 0


def test_expiration_prevents_late_approval() -> None:
    runtime = build_runtime()
    guardian_ids = configure_guardians(runtime)
    request = runtime.service.create_request(
        runtime.owner,
        wallet_id=WALLET_ID,
        reason=RecoveryReason.LOST_ACCESS,
    )
    runtime.clock.advance(seconds=301)
    with pytest.raises(RecoveryConflictError):
        runtime.service.approve(
            runtime.guardians[0],
            request.request_id,
            guardian_id=guardian_ids[0],
            challenge=request.challenge.value,
        )
    current = runtime.repository.get_request(request.request_id)
    assert current is not None
    assert current.session.state is RecoveryState.EXPIRED


def test_provider_failure_enters_reconciliation_and_idempotent_retry_completes() -> None:
    runtime = build_runtime()
    guardian_ids = configure_guardians(runtime, time_lock_seconds=0)
    request = runtime.service.create_request(
        runtime.owner,
        wallet_id=WALLET_ID,
        reason=RecoveryReason.ACCOUNT_COMPROMISE,
    )
    for index in range(3):
        runtime.service.approve(
            runtime.guardians[index],
            request.request_id,
            guardian_id=guardian_ids[index],
            challenge=request.challenge.value,
        )
    runtime.gateway.fail = True
    failed = runtime.service.reconcile_request(runtime.admin, request.request_id)
    assert failed.session.state is RecoveryState.RECONCILIATION_REQUIRED
    assert runtime.metrics.snapshot().failures == 1
    runtime.gateway.fail = False
    completed = runtime.service.reconcile_request(runtime.admin, request.request_id)
    assert completed.session.state is RecoveryState.COMPLETED
    assert runtime.gateway.calls == 2
    snapshot = runtime.metrics.snapshot()
    assert snapshot.approvals == 3
    assert snapshot.successes == 1
    assert snapshot.key_rotation_seconds >= 0


def test_rbac_and_object_ownership_are_non_enumerating() -> None:
    runtime = build_runtime()
    configure_guardians(runtime)
    request = runtime.service.create_request(
        runtime.owner,
        wallet_id=WALLET_ID,
        reason=RecoveryReason.KEY_LOSS,
    )
    verifier = RecoveryPrincipal.from_claims("usr_verifier", ("verifier",))
    issuer = RecoveryPrincipal.from_claims("usr_issuer", ("issuer",))
    foreign_holder = RecoveryPrincipal.from_claims("usr_foreign", ("holder",))
    with pytest.raises(Exception):
        runtime.service.create_request(
            verifier, wallet_id=WALLET_ID, reason=RecoveryReason.KEY_LOSS
        )
    with pytest.raises(Exception):
        runtime.service.list_requests(issuer)
    with pytest.raises(RecoveryNotFoundError):
        runtime.service.get_request(foreign_holder, request.request_id)
    assert runtime.service.reconcile_request(runtime.admin, request.request_id) == request


def test_audit_and_metrics_use_safe_aggregate_data() -> None:
    runtime = build_runtime()
    configure_guardians(runtime)
    request = runtime.service.create_request(
        runtime.owner,
        wallet_id=WALLET_ID,
        reason=RecoveryReason.KEY_LOSS,
    )
    events = runtime.repository.list_audit_events(request.request_id)
    snapshot = runtime.metrics.snapshot()
    serialized = repr(events)

    assert snapshot.requests == 1
    assert snapshot.active_guardians == 5
    assert request.challenge.value not in serialized
    assert request.nonce.value not in serialized
    assert all("secret" not in key.casefold() for event in events for key in event.metadata)
