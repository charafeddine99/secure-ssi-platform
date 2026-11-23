"""WP-29 P0-3: attack paths against Guardian recovery (prompt section 6.9)."""

import base64
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from threading import Barrier, Thread

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.application.services.recovery_service import RecoveryService
from app.core.config import RecoveryConfigurationError, load_settings
from app.domain.auth import RecoveryPrincipal
from app.domain.recovery import (
    GuardianStatus,
    RecoveryAuthorizationError,
    RecoveryConflictError,
    RecoveryNotFoundError,
    RecoveryReason,
    RecoveryState,
    RecoveryValidationError,
    RiskHoldStatus,
)
from app.infrastructure.auth.step_up import (
    STEP_UP_AUDIENCE,
    StepUpGuard,
    StepUpRequiredError,
)
from app.infrastructure.persistence.mappers import (
    guardian_from_document,
    guardian_to_document,
    policy_from_document,
)
from app.infrastructure.persistence.memory_repository import (
    MemoryRecoveryRepository,
)
from app.infrastructure.risk.fraud_gateway import (
    FraudRecoveryRiskGateway,
    RecoveryRiskUnavailableError,
)
from app.infrastructure.secret_sharing.pycryptodome_provider import (
    PyCryptodomeSecretSharingProvider,
)
from app.schemas.recovery_api import RecoveryPolicyUpsertRequest
from tests.support import (
    OWNER,
    WALLET_ID,
    FakeManagedKeyGateway,
    FakeRiskGateway,
    MutableClock,
    Sequence,
    build_runtime,
    configure_guardians,
    enroll_guardian,
)
from app.application.services.metrics import RecoveryMetrics


def floors_service(runtime, **overrides) -> RecoveryService:
    settings = replace(
        load_settings({}),
        minimum_approvals_floor=2,
        time_lock_floor_seconds=86400,
        guardian_change_delay_seconds=86400,
        **overrides,
    )
    return RecoveryService(
        repository=runtime.repository,
        secret_sharing=PyCryptodomeSecretSharingProvider(b"R" * 32),
        managed_keys=runtime.gateway,
        settings=settings,
        metrics=runtime.metrics,
        clock=runtime.clock,
        id_generator=runtime.service._ids,
        worker_id="worker",
        risk=runtime.risk,
    )


def policy_args(**overrides) -> dict:
    values = dict(
        wallet_id=WALLET_ID,
        minimum_approvals=2,
        maximum_guardians=3,
        approval_window_seconds=3600,
        time_lock_seconds=86400,
        recovery_expiration_seconds=200000,
        maximum_attempts=3,
        cooldown_seconds=0,
        allow_cancellation=True,
    )
    values.update(overrides)
    return values


def open_request(runtime):
    return runtime.service.create_request(
        runtime.owner,
        wallet_id=WALLET_ID,
        reason=RecoveryReason.ACCOUNT_COMPROMISE,
    )


def approve(runtime, index, guardian_ids, request):
    return runtime.service.approve(
        runtime.guardians[index],
        request.request_id,
        guardian_id=guardian_ids[index],
        challenge=request.challenge.value,
    )


# -- self guardian ---------------------------------------------------------


def test_allow_self_guardian_is_rejected_by_the_api_schema() -> None:
    with pytest.raises(ValueError):
        RecoveryPolicyUpsertRequest(
            walletId=WALLET_ID,
            minimumApprovals=2,
            maximumGuardians=3,
            approvalWindowSeconds=60,
            timeLockSeconds=60,
            recoveryExpirationSeconds=120,
            maximumAttempts=1,
            cooldownSeconds=0,
            allowCancellation=True,
            allowSelfGuardian=True,
        )


def test_allow_self_guardian_cannot_reach_the_service() -> None:
    runtime = build_runtime()
    with pytest.raises(TypeError):
        runtime.service.put_policy(
            runtime.owner, **policy_args(), allow_self_guardian=True
        )


def test_legacy_allow_self_guardian_true_is_ignored_on_read() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    policy = policy_from_document(
        {
            "policyId": "policy_1",
            "walletId": WALLET_ID,
            "ownerUserId": OWNER,
            "minimumApprovals": 2,
            "maximumGuardians": 3,
            "approvalWindowSeconds": 60,
            "timeLockSeconds": 60,
            "recoveryExpirationSeconds": 120,
            "maximumAttempts": 1,
            "cooldownSeconds": 0,
            "allowCancellation": True,
            "allowSelfGuardian": True,
            "version": 1,
            "createdAt": now,
            "updatedAt": now,
        }
    )
    assert not hasattr(policy, "allow_self_guardian")


def test_owner_cannot_be_invited_as_their_own_guardian() -> None:
    runtime = build_runtime()
    with pytest.raises(RecoveryValidationError):
        runtime.service.create_guardian(
            runtime.owner,
            wallet_id=WALLET_ID,
            guardian_user_id=runtime.owner.user_id,
            display_name="Me",
        )


def test_owner_cannot_approve_their_own_recovery() -> None:
    runtime = build_runtime()
    guardian_ids = configure_guardians(runtime, count=3, threshold=2)
    request = open_request(runtime)
    with pytest.raises(RecoveryNotFoundError):
        runtime.service.approve(
            runtime.owner,
            request.request_id,
            guardian_id=guardian_ids[0],
            challenge=request.challenge.value,
        )


def test_legacy_self_guardian_record_cannot_approve() -> None:
    """A self-Guardian stored before WP-29 must not count towards quorum."""
    runtime = build_runtime()
    guardian_ids = configure_guardians(runtime, count=3, threshold=2)
    legacy = runtime.repository.get_guardian(guardian_ids[0])
    runtime.repository.guardians[guardian_ids[0]] = replace(
        legacy, guardian_user_id=runtime.owner.user_id
    )
    request = open_request(runtime)
    runtime.guardian_signing_keys[runtime.owner.user_id] = (
        runtime.guardian_signing_keys[runtime.guardians[0].user_id]
    )
    with pytest.raises(RecoveryNotFoundError):
        runtime.service.approve(
            runtime.owner,
            request.request_id,
            guardian_id=guardian_ids[0],
            challenge=request.challenge.value,
        )


# -- quorum and floors -----------------------------------------------------


def test_one_guardian_cannot_satisfy_two_of_three() -> None:
    runtime = build_runtime()
    guardian_ids = configure_guardians(runtime, count=3, threshold=2)
    request = open_request(runtime)
    _, current = approve(runtime, 0, guardian_ids, request)
    assert current.session.state is RecoveryState.PENDING_APPROVALS
    _, again = approve(runtime, 0, guardian_ids, request)
    assert again.session.quorum.approvals == 1


def test_m_equals_one_is_refused_by_the_floor() -> None:
    runtime = build_runtime()
    with pytest.raises(RecoveryValidationError):
        floors_service(runtime).put_policy(
            runtime.owner, **policy_args(minimum_approvals=1)
        )


@pytest.mark.parametrize("seconds", [0, 60, 86399])
def test_short_time_lock_is_refused_by_the_floor(seconds: int) -> None:
    runtime = build_runtime()
    with pytest.raises(RecoveryValidationError):
        floors_service(runtime).put_policy(
            runtime.owner, **policy_args(time_lock_seconds=seconds)
        )


PRODUCTION = {
    "RECOVERY_ENVIRONMENT": "production",
    "RECOVERY_AUTH_JWT_SECRET": "J" * 32,
    "RECOVERY_IDENTITY_GRANT_SECRET": "G" * 32,
    "RECOVERY_SHARE_ENVELOPE_KEY_BASE64": base64.b64encode(b"E" * 32).decode(),
    "RECOVERY_STEP_UP_SECRET": "S" * 32,
    "FRAUD_INTERNAL_SERVICE_TOKEN": "F" * 32,
}


@pytest.mark.parametrize(
    "override",
    [
        {"RECOVERY_MINIMUM_APPROVALS_FLOOR": "1"},
        {"RECOVERY_TIME_LOCK_FLOOR_SECONDS": "0"},
        {"RECOVERY_GUARDIAN_CHANGE_DELAY_SECONDS": "60"},
        {"RECOVERY_DEFAULT_TIME_LOCK_SECONDS": "300"},
        {"FRAUD_INTERNAL_SERVICE_TOKEN": ""},
    ],
)
def test_production_floors_cannot_be_configured_away(override) -> None:
    with pytest.raises(RecoveryConfigurationError):
        load_settings({**PRODUCTION, **override})


def test_step_up_cannot_be_disabled_in_production() -> None:
    settings = load_settings(
        {**PRODUCTION, "RECOVERY_STEP_UP_REQUIRED": "false"}
    )
    assert settings.step_up_required is True


def test_quorum_larger_than_enrolled_guardians_cannot_open_a_request() -> None:
    runtime = build_runtime()
    configure_guardians(runtime, count=2, threshold=2)
    runtime.service.put_policy(
        runtime.owner, **policy_args(minimum_approvals=3, maximum_guardians=5)
    )
    with pytest.raises(RecoveryConflictError):
        open_request(runtime)


# -- delayed changes -------------------------------------------------------


def _delayed_runtime():
    runtime = build_runtime()
    guardian_ids = configure_guardians(
        runtime,
        count=3,
        threshold=2,
        time_lock_seconds=86400,
        expiration_seconds=200000,
    )
    runtime.service = floors_service(runtime)
    return runtime, guardian_ids


def test_policy_reduction_is_scheduled_and_does_not_apply_at_once() -> None:
    runtime, _ = _delayed_runtime()
    current = runtime.repository.get_policy(WALLET_ID)
    scheduled = runtime.service.put_policy(
        runtime.owner,
        **policy_args(
            minimum_approvals=2,
            time_lock_seconds=86400,
            maximum_attempts=9,
        ),
    )
    assert scheduled.maximum_attempts == current.maximum_attempts
    assert scheduled.pending_change["maximumAttempts"] == 9
    runtime.clock.advance(seconds=86401)
    applied = runtime.service.get_policy(runtime.owner, wallet_id=WALLET_ID)
    assert applied.maximum_attempts == 9
    assert applied.pending_change is None


def test_policy_change_cannot_alter_an_open_request() -> None:
    runtime, guardian_ids = _delayed_runtime()
    request = open_request(runtime)
    with pytest.raises(RecoveryConflictError):
        runtime.service.put_policy(runtime.owner, **policy_args())
    stored = runtime.repository.get_request(request.request_id)
    assert stored.policy.minimum_approvals == 2
    assert stored.policy.guardian_ids == request.policy.guardian_ids


def test_scheduled_change_does_not_apply_during_an_open_request() -> None:
    runtime, _ = _delayed_runtime()
    runtime.service.put_policy(
        runtime.owner, **policy_args(maximum_attempts=9)
    )
    open_request(runtime)
    runtime.clock.advance(seconds=86401)
    assert runtime.repository.get_policy(WALLET_ID).pending_change is not None


def test_guardian_removal_is_delayed_once_recovery_is_operational() -> None:
    runtime, guardian_ids = _delayed_runtime()
    scheduled = runtime.service.remove_guardian(runtime.owner, guardian_ids[0])
    assert scheduled.status is GuardianStatus.ACTIVE
    assert scheduled.pending_status is GuardianStatus.REMOVED
    runtime.clock.advance(seconds=86401)
    runtime.service.list_guardians(runtime.owner, wallet_id=WALLET_ID)
    assert (
        runtime.repository.get_guardian(guardian_ids[0]).status
        is GuardianStatus.REMOVED
    )


def test_new_guardian_waits_for_activation_and_cannot_join_quorum_early() -> None:
    runtime, guardian_ids = _delayed_runtime()
    runtime.service.put_policy(
        runtime.owner,
        **policy_args(maximum_guardians=4, approval_window_seconds=300),
    )
    late = enroll_guardian(runtime, runtime.guardians[3], 4)
    assert late.status is GuardianStatus.PENDING_ACTIVATION
    assert late.can_approve is False
    request = open_request(runtime)
    assert late.guardian_id not in request.policy.guardian_ids


def test_every_change_notifies_owner_and_guardians() -> None:
    runtime, guardian_ids = _delayed_runtime()
    runtime.service.put_policy(
        runtime.owner, **policy_args(maximum_attempts=9)
    )
    for principal in (runtime.owner, runtime.guardians[0]):
        events = [
            item.event_type
            for item in runtime.service.list_notifications(principal)
        ]
        assert "RECOVERY_POLICY_CHANGE_SCHEDULED" in events


# -- identity and key binding ----------------------------------------------


def test_invitation_gives_no_authority_until_accepted() -> None:
    runtime = build_runtime()
    invited = runtime.service.create_guardian(
        runtime.owner,
        wallet_id=WALLET_ID,
        guardian_user_id=runtime.guardians[0].user_id,
        display_name="G",
    )
    assert invited.status is GuardianStatus.INVITED
    assert invited.can_approve is False
    assert invited.guardian_did == ""


def test_another_user_cannot_accept_an_invitation() -> None:
    runtime = build_runtime()
    invited = runtime.service.create_guardian(
        runtime.owner,
        wallet_id=WALLET_ID,
        guardian_user_id=runtime.guardians[0].user_id,
        display_name="G",
    )
    did, method, proof = runtime.sign_binding(
        guardian_id=invited.guardian_id,
        key=runtime.guardian_signing_keys[runtime.guardians[1].user_id],
    )
    with pytest.raises(RecoveryNotFoundError):
        runtime.service.accept_invitation(
            runtime.guardians[1],
            invited.guardian_id,
            guardian_did=did,
            verification_method=method,
            proof=proof,
        )


def test_foreign_did_without_its_private_key_is_refused() -> None:
    runtime = build_runtime()
    principal = runtime.guardians[0]
    invited = runtime.service.create_guardian(
        runtime.owner,
        wallet_id=WALLET_ID,
        guardian_user_id=principal.user_id,
        display_name="G",
    )
    victim_did, victim_method, _ = runtime.sign_binding(
        guardian_id=invited.guardian_id,
        key=runtime.guardian_signing_keys[runtime.guardians[5].user_id],
    )
    _, _, attacker_proof = runtime.sign_binding(
        guardian_id=invited.guardian_id,
        key=runtime.guardian_signing_keys[principal.user_id],
    )
    with pytest.raises(RecoveryConflictError):
        runtime.service.accept_invitation(
            principal,
            invited.guardian_id,
            guardian_did=victim_did,
            verification_method=victim_method,
            proof=attacker_proof,
        )


def test_binding_proof_for_a_stale_challenge_is_refused() -> None:
    runtime = build_runtime()
    principal = runtime.guardians[0]
    invited = runtime.service.create_guardian(
        runtime.owner,
        wallet_id=WALLET_ID,
        guardian_user_id=principal.user_id,
        display_name="G",
    )
    did, method, proof = runtime.sign_binding(
        guardian_id=invited.guardian_id,
        key=runtime.guardian_signing_keys[principal.user_id],
        challenge="some-other-challenge-value-0123456789",
    )
    with pytest.raises(RecoveryConflictError):
        runtime.service.accept_invitation(
            principal,
            invited.guardian_id,
            guardian_did=did,
            verification_method=method,
            proof=proof,
        )


def test_expired_invitation_cannot_be_accepted() -> None:
    runtime = build_runtime()
    principal = runtime.guardians[0]
    invited = runtime.service.create_guardian(
        runtime.owner,
        wallet_id=WALLET_ID,
        guardian_user_id=principal.user_id,
        display_name="G",
    )
    did, method, proof = runtime.sign_binding(
        guardian_id=invited.guardian_id,
        key=runtime.guardian_signing_keys[principal.user_id],
    )
    runtime.clock.advance(days=8)
    with pytest.raises(RecoveryConflictError):
        runtime.service.accept_invitation(
            principal,
            invited.guardian_id,
            guardian_did=did,
            verification_method=method,
            proof=proof,
        )


def test_platform_held_key_cannot_become_a_guardian_key() -> None:
    """The server-signed proof path: the DID belongs to a managed wallet key."""
    runtime = build_runtime()
    principal = runtime.guardians[0]
    invited = runtime.service.create_guardian(
        runtime.owner,
        wallet_id=WALLET_ID,
        guardian_user_id=principal.user_id,
        display_name="G",
    )
    did, method, proof = runtime.sign_binding(
        guardian_id=invited.guardian_id,
        key=runtime.guardian_signing_keys[principal.user_id],
    )
    runtime.gateway.managed_dids.add(did)
    with pytest.raises(RecoveryConflictError):
        runtime.service.accept_invitation(
            principal,
            invited.guardian_id,
            guardian_did=did,
            verification_method=method,
            proof=proof,
        )


def test_two_guardians_cannot_share_one_key() -> None:
    runtime = build_runtime()
    first = enroll_guardian(runtime, runtime.guardians[0])
    second_principal = runtime.guardians[1]
    invited = runtime.service.create_guardian(
        runtime.owner,
        wallet_id=WALLET_ID,
        guardian_user_id=second_principal.user_id,
        display_name="G2",
    )
    did, method, proof = runtime.sign_binding(
        guardian_id=invited.guardian_id,
        key=runtime.guardian_signing_keys[runtime.guardians[0].user_id],
    )
    assert did == first.guardian_did
    with pytest.raises(RecoveryConflictError):
        runtime.service.accept_invitation(
            second_principal,
            invited.guardian_id,
            guardian_did=did,
            verification_method=method,
            proof=proof,
        )


def test_guardian_rotation_keeps_membership_only_with_a_fresh_proof() -> None:
    runtime = build_runtime()
    guardian_ids = configure_guardians(runtime, count=3, threshold=2)
    principal = runtime.guardians[0]
    runtime.service.start_rebind(principal, guardian_ids[0])
    new_key = Ed25519PrivateKey.generate()
    did, method, proof = runtime.sign_binding(
        guardian_id=guardian_ids[0], key=new_key
    )
    rebound = runtime.service.complete_rebind(
        principal,
        guardian_ids[0],
        guardian_did=did,
        verification_method=method,
        proof=proof,
    )
    assert rebound.guardian_did == did
    assert rebound.status is GuardianStatus.ACTIVE
    assert rebound.guardian_id == guardian_ids[0]


def test_rebind_without_a_challenge_is_refused() -> None:
    runtime = build_runtime()
    guardian_ids = configure_guardians(runtime, count=3, threshold=2)
    key = Ed25519PrivateKey.generate()
    did, method, proof = runtime.sign_binding(
        guardian_id=guardian_ids[0],
        key=key,
        challenge="not-a-challenge-the-server-ever-issued-0",
    )
    with pytest.raises(RecoveryConflictError):
        runtime.service.complete_rebind(
            runtime.guardians[0],
            guardian_ids[0],
            guardian_did=did,
            verification_method=method,
            proof=proof,
        )


def test_invitation_challenge_is_never_serialized_to_the_owner() -> None:
    from app.schemas.recovery_api import GuardianResponse

    runtime = build_runtime()
    invited = runtime.service.create_guardian(
        runtime.owner,
        wallet_id=WALLET_ID,
        guardian_user_id=runtime.guardians[0].user_id,
        display_name="G",
    )
    body = GuardianResponse.from_domain(invited).model_dump_json()
    assert invited.invitation_challenge not in body


def test_guardian_document_round_trip_keeps_binding_state() -> None:
    runtime = build_runtime()
    guardian = enroll_guardian(runtime, runtime.guardians[0])
    assert guardian_from_document(guardian_to_document(guardian)) == guardian


# -- proof binding ---------------------------------------------------------


def _forged_proof(runtime, guardian_id, request, *, policy_hash: str) -> str:
    guardian = runtime.repository.get_guardian(guardian_id)
    key = runtime.guardian_signing_keys[guardian.guardian_user_id]
    issued = int(runtime.clock().timestamp())
    return jwt.encode(
        {
            "iss": guardian.guardian_did,
            "sub": guardian.guardian_id,
            "aud": "secure-ssi-platform:guardian-recovery",
            "requestId": request.request_id,
            "sessionId": request.session.session_id,
            "walletId": request.wallet_id,
            "decision": "APPROVE",
            "challenge": request.challenge.value,
            "policyHash": policy_hash,
            "iat": issued,
            "exp": issued + 120,
            "jti": token_urlsafe(18),
        },
        key,
        algorithm="EdDSA",
        headers={
            "typ": "guardian-recovery+jwt",
            "kid": guardian.verification_method,
        },
    )


def test_proof_for_a_different_policy_snapshot_is_refused() -> None:
    runtime = build_runtime()
    guardian_ids = configure_guardians(runtime, count=3, threshold=2)
    request = open_request(runtime)
    with pytest.raises(RecoveryConflictError):
        runtime.service.approve(
            runtime.guardians[0],
            request.request_id,
            guardian_id=guardian_ids[0],
            challenge=request.challenge.value,
            proof=_forged_proof(
                runtime, guardian_ids[0], request, policy_hash="0" * 64
            ),
        )


def test_proof_from_another_request_is_refused() -> None:
    runtime = build_runtime()
    guardian_ids = configure_guardians(runtime, count=3, threshold=2)
    first = open_request(runtime)
    proof = runtime.sign_decision(
        guardian_id=guardian_ids[0],
        request_id=first.request_id,
        challenge=first.challenge.value,
    )
    runtime.service.cancel(runtime.owner, first.request_id)
    second = open_request(runtime)
    with pytest.raises(RecoveryConflictError):
        runtime.service.approve(
            runtime.guardians[0],
            second.request_id,
            guardian_id=guardian_ids[0],
            challenge=second.challenge.value,
            proof=proof,
        )


def test_replayed_proof_cannot_add_a_second_approval() -> None:
    runtime = build_runtime()
    guardian_ids = configure_guardians(runtime, count=3, threshold=2)
    request = open_request(runtime)
    proof = runtime.sign_decision(
        guardian_id=guardian_ids[0],
        request_id=request.request_id,
        challenge=request.challenge.value,
    )
    for _ in range(3):
        runtime.service.approve(
            runtime.guardians[0],
            request.request_id,
            guardian_id=guardian_ids[0],
            challenge=request.challenge.value,
            proof=proof,
        )
    assert (
        runtime.repository.get_request(request.request_id).session.quorum.approvals
        == 1
    )


def test_concurrent_decisions_reach_quorum_and_rotate_exactly_once() -> None:
    runtime = build_runtime()
    guardian_ids = configure_guardians(
        runtime, count=5, threshold=3, time_lock_seconds=10
    )
    request = open_request(runtime)
    barrier = Barrier(5)
    errors: list[Exception] = []

    def decide(index: int) -> None:
        barrier.wait()
        try:
            approve(runtime, index, guardian_ids, request)
        except RecoveryConflictError:
            pass
        except Exception as error:  # pragma: no cover - asserted below
            errors.append(error)

    threads = [Thread(target=decide, args=(i,)) for i in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    events = [
        item.event_type.value
        for item in runtime.repository.list_audit_events(request.request_id)
    ]
    assert events.count("RECOVERY_QUORUM_REACHED") == 1
    runtime.service.reconcile_due()
    runtime.clock.advance(seconds=11)
    runtime.service.reconcile_due()
    runtime.service.reconcile_due()
    assert runtime.gateway.calls == 1


# -- risk hold -------------------------------------------------------------


@pytest.mark.parametrize("level", ["MEDIUM", "HIGH", "CRITICAL", "nonsense", ""])
def test_any_non_low_risk_holds_the_rotation(level: str) -> None:
    runtime = build_runtime()
    runtime.risk.level = level
    guardian_ids = configure_guardians(runtime, count=3, threshold=2)
    request = open_request(runtime)
    assert request.risk.status is RiskHoldStatus.ON_HOLD
    _complete_quorum_and_timelock(runtime, guardian_ids, request)
    stored = runtime.repository.get_request(request.request_id)
    assert stored.session.state is RecoveryState.READY_FOR_EXECUTION
    assert runtime.gateway.calls == 0


def _complete_quorum_and_timelock(runtime, guardian_ids, request) -> None:
    approve(runtime, 0, guardian_ids, request)
    approve(runtime, 1, guardian_ids, request)
    runtime.service.reconcile_due()
    runtime.clock.advance(seconds=11)
    runtime.service.reconcile_due()
    runtime.service.reconcile_due()


@pytest.mark.parametrize(
    "failure",
    [TimeoutError("slow"), RecoveryRiskUnavailableError("down"), ValueError("x")],
)
def test_risk_outage_holds_and_never_passes(failure: Exception) -> None:
    runtime = build_runtime()
    runtime.risk.failure = failure
    guardian_ids = configure_guardians(runtime, count=3, threshold=2)
    request = open_request(runtime)
    assert request.risk.level == "UNAVAILABLE"
    assert request.risk.status is RiskHoldStatus.ON_HOLD
    _complete_quorum_and_timelock(runtime, guardian_ids, request)
    assert runtime.gateway.calls == 0


def test_low_risk_is_clear_and_rotates() -> None:
    runtime = build_runtime()
    guardian_ids = configure_guardians(runtime, count=3, threshold=2)
    request = open_request(runtime)
    assert request.risk.status is RiskHoldStatus.CLEAR
    _complete_quorum_and_timelock(runtime, guardian_ids, request)
    assert runtime.gateway.calls == 1


def test_admin_release_lifts_only_the_hold_and_then_rotation_proceeds() -> None:
    runtime = build_runtime()
    runtime.risk.level = "HIGH"
    guardian_ids = configure_guardians(runtime, count=3, threshold=2)
    request = open_request(runtime)
    _complete_quorum_and_timelock(runtime, guardian_ids, request)
    runtime.service.review_risk(
        runtime.admin, request.request_id, decision="RELEASE", reason="checked"
    )
    runtime.service.reconcile_due()
    assert runtime.gateway.calls == 1


def test_admin_release_does_not_replace_quorum() -> None:
    runtime = build_runtime()
    runtime.risk.level = "HIGH"
    configure_guardians(runtime, count=3, threshold=2)
    request = open_request(runtime)
    runtime.service.review_risk(
        runtime.admin, request.request_id, decision="RELEASE", reason="checked"
    )
    runtime.service.reconcile_due()
    stored = runtime.repository.get_request(request.request_id)
    assert stored.session.state is RecoveryState.PENDING_APPROVALS
    assert runtime.gateway.calls == 0


def test_upholding_a_hold_cancels_the_request() -> None:
    runtime = build_runtime()
    runtime.risk.level = "HIGH"
    configure_guardians(runtime, count=3, threshold=2)
    request = open_request(runtime)
    stored = runtime.service.review_risk(
        runtime.admin, request.request_id, decision="UPHOLD", reason="fraud"
    )
    assert stored.session.state is RecoveryState.CANCELLED


def test_holder_cannot_review_a_risk_hold() -> None:
    runtime = build_runtime()
    runtime.risk.level = "HIGH"
    configure_guardians(runtime, count=3, threshold=2)
    request = open_request(runtime)
    with pytest.raises(RecoveryAuthorizationError):
        runtime.service.review_risk(
            runtime.owner, request.request_id, decision="RELEASE", reason="me"
        )


def test_requester_with_admin_role_cannot_review_their_own_hold() -> None:
    runtime = build_runtime()
    runtime.risk.level = "HIGH"
    configure_guardians(runtime, count=3, threshold=2)
    request = open_request(runtime)
    both = RecoveryPrincipal.from_claims(OWNER, ("holder", "admin"))
    with pytest.raises(RecoveryAuthorizationError):
        runtime.service.review_risk(
            both, request.request_id, decision="RELEASE", reason="me"
        )


def test_request_stored_before_risk_existed_stays_held() -> None:
    from app.infrastructure.persistence.mappers import _risk_from_document

    assert _risk_from_document(None).status is RiskHoldStatus.ON_HOLD


class _Client:
    def __init__(self, body=None, error=None) -> None:
        self.body, self.error = body, error
        self.sent = {}

    def post(self, path, headers, json):
        self.sent = json
        if self.error:
            raise self.error

        class Response:
            def raise_for_status(_self):
                return None

            def json(_self):
                return self.body

        return Response()


def test_risk_client_sends_no_wallet_or_did_and_rejects_malformed_answers() -> None:
    settings = replace(load_settings({}), fraud_service_token="T" * 32)
    client = _Client({"risk_level": "LOW"})
    gateway = FraudRecoveryRiskGateway(settings, client=client)
    assert gateway.assess_recovery(wallet_id=WALLET_ID, reason="X") == "LOW"
    assert WALLET_ID not in str(client.sent)
    for body in ({"risk_level": "SAFE"}, {}, []):
        with pytest.raises(RecoveryRiskUnavailableError):
            FraudRecoveryRiskGateway(
                settings, client=_Client(body)
            ).assess_recovery(wallet_id=WALLET_ID, reason="X")


def test_risk_client_without_credentials_is_unavailable() -> None:
    gateway = FraudRecoveryRiskGateway(load_settings({}), client=_Client({}))
    with pytest.raises(RecoveryRiskUnavailableError):
        gateway.assess_recovery(wallet_id=WALLET_ID, reason="X")


# -- step-up ---------------------------------------------------------------


SECRET = "s" * 40


def _guard():
    settings = replace(
        load_settings({}), step_up_required=True, step_up_secret=SECRET
    )
    return StepUpGuard(settings, MemoryRecoveryRepository()), settings


def _token(settings, **overrides) -> str:
    now = datetime.now(UTC)
    claims = {
        "iss": settings.jwt_issuer,
        "sub": "user-1",
        "aud": STEP_UP_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=120)).timestamp()),
        "jti": token_urlsafe(16),
        "sid": "session-1",
        "act": "recovery.decide",
        "res": "recovery_x",
    }
    claims.update(overrides)
    return jwt.encode(claims, overrides.get("_key", SECRET), algorithm="HS256")


def _principal() -> RecoveryPrincipal:
    return replace(
        RecoveryPrincipal.from_claims("user-1", ("holder",)),
        session_id="session-1",
    )


def test_step_up_token_passes_once_and_only_once() -> None:
    guard, settings = _guard()
    token = _token(settings)
    guard.require(
        _principal(), token, action="recovery.decide", resource="recovery_x"
    )
    with pytest.raises(StepUpRequiredError):
        guard.require(
            _principal(), token, action="recovery.decide", resource="recovery_x"
        )


@pytest.mark.parametrize(
    "claims",
    [
        {"sub": "someone-else"},
        {"sid": "other-session"},
        {"act": "recovery.policy.update"},
        {"res": "recovery_y"},
        {"aud": "secure-ssi-other"},
        {"exp": 1},
    ],
)
def test_step_up_is_bound_to_user_session_action_resource_and_time(claims) -> None:
    guard, settings = _guard()
    with pytest.raises(StepUpRequiredError):
        guard.require(
            _principal(),
            _token(settings, **claims),
            action="recovery.decide",
            resource="recovery_x",
        )


@pytest.mark.parametrize("token", [None, "", "not-a-jwt", "true"])
def test_missing_or_client_invented_step_up_is_refused(token) -> None:
    guard, _ = _guard()
    with pytest.raises(StepUpRequiredError):
        guard.require(
            _principal(), token, action="recovery.decide", resource="recovery_x"
        )


def test_step_up_signed_with_another_key_is_refused() -> None:
    guard, settings = _guard()
    forged = jwt.encode(
        {
            "iss": settings.jwt_issuer,
            "sub": "user-1",
            "aud": STEP_UP_AUDIENCE,
            "iat": 1,
            "exp": 9999999999,
            "jti": "x" * 20,
            "sid": "session-1",
            "act": "recovery.decide",
            "res": "recovery_x",
        },
        "w" * 40,
        algorithm="HS256",
    )
    with pytest.raises(StepUpRequiredError):
        guard.require(
            _principal(), forged, action="recovery.decide", resource="recovery_x"
        )


def test_unused_fixture_helpers_stay_importable() -> None:
    assert FakeManagedKeyGateway and FakeRiskGateway and MutableClock
    assert RecoveryMetrics
