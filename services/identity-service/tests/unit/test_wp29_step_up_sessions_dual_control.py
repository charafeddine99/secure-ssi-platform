"""WP-29: TOTP step-up, durable session revocation, two-person control."""

from datetime import UTC, datetime, timedelta

import jwt
import pyotp
import pytest
from pymongo.errors import PyMongoError

from app.application.services.dual_control_service import (
    KEY_DESTRUCTION,
    PLATFORM_RESTORE,
    DualControlError,
    DualControlService,
)
from app.application.services.step_up_service import (
    STEP_UP_AUDIENCE,
    StepUpLockedError,
    StepUpRequiredError,
    StepUpService,
)
from app.config.step_up_settings import StepUpSettings, load_step_up_settings
from app.domain.auth import AuthenticatedPrincipal
from app.domain.permissions import Role
from app.domain.persistence import PersistenceConfigurationError
from app.infrastructure.auth.durable_token_revocation import (
    MongoTokenRevocationStore,
)
from app.infrastructure.persistence.memory_db import MemoryCollection


ISSUER = "secure-ssi-identity-service"
SECRET = "t" * 40


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


def principal(session: str = "session-1", user: str = "user-1"):
    return AuthenticatedPrincipal(
        id=user,
        username=user,
        display_name=user,
        roles=(Role.HOLDER,),
        permissions=(),
        authentication_source="test",
        session_id=session,
    )


def service(clock=None, *, required=True, factors=None, tokens=None, key=None):
    clock = clock or Clock()
    return (
        StepUpService(
            factors=factors if factors is not None else MemoryCollection(),
            tokens=tokens if tokens is not None else MemoryCollection(),
            settings=StepUpSettings(
                environment="test",
                required=required,
                dual_control_required=False,
                token_secret=SECRET,
                factor_key=key or b"f" * 32,
            ),
            issuer=ISSUER,
            clock=clock,
        ),
        clock,
    )


def enrolled(clock=None, **options):
    step_up, clock = service(clock, **options)
    enrollment = step_up.begin_enrollment(principal(), current_code=None)
    totp = pyotp.TOTP(enrollment.secret)
    step_up.confirm_enrollment(principal(), code=totp.at(clock()))
    clock.advance(30)
    return step_up, clock, totp


def test_enrollment_is_not_active_until_a_code_is_confirmed() -> None:
    step_up, _ = service()
    step_up.begin_enrollment(principal(), current_code=None)
    assert step_up.status("user-1")["enrolled"] is False
    with pytest.raises(StepUpRequiredError):
        step_up.issue_token(
            principal(), action="a.b", resource="r", code="000000"
        )


def test_factor_secret_is_encrypted_at_rest() -> None:
    factors = MemoryCollection()
    step_up, _ = service(factors=factors)
    enrollment = step_up.begin_enrollment(principal(), current_code=None)
    assert enrollment.secret not in str(factors.documents)


def test_factor_secret_cannot_be_moved_to_another_user() -> None:
    factors = MemoryCollection()
    step_up, clock, totp = enrolled(factors=factors)
    factors.documents[0]["userId"] = "user-2"
    with pytest.raises(Exception):
        step_up.issue_token(
            principal(user="user-2"),
            action="a.b",
            resource="r",
            code=totp.at(clock()),
        )


def test_valid_code_issues_a_token_scoped_to_session_action_and_resource() -> None:
    step_up, clock, totp = enrolled()
    token, lifetime = step_up.issue_token(
        principal(), action="wallet.key.rotate", resource="key_1", code=totp.at(clock())
    )
    claims = jwt.decode(
        token,
        SECRET,
        algorithms=["HS256"],
        audience=STEP_UP_AUDIENCE,
        options={"verify_exp": False, "verify_iat": False},
    )
    assert lifetime == 120
    assert claims["sid"] == "session-1"
    assert claims["act"] == "wallet.key.rotate"
    assert claims["res"] == "key_1"
    assert claims["amr"] == ["otp"]


def test_a_used_code_cannot_be_replayed() -> None:
    step_up, clock, totp = enrolled()
    code = totp.at(clock())
    step_up.issue_token(principal(), action="a.b", resource="r", code=code)
    with pytest.raises(StepUpRequiredError):
        step_up.issue_token(principal(), action="a.b", resource="r", code=code)


def test_wrong_codes_lock_the_factor() -> None:
    step_up, clock, totp = enrolled()
    for _ in range(5):
        with pytest.raises(StepUpRequiredError):
            step_up.issue_token(
                principal(), action="a.b", resource="r", code="000000"
            )
    with pytest.raises(StepUpLockedError):
        step_up.issue_token(
            principal(), action="a.b", resource="r", code=totp.at(clock())
        )
    clock.advance(301)
    step_up.issue_token(
        principal(), action="a.b", resource="r", code=totp.at(clock())
    )


def test_replacing_a_factor_needs_the_current_code() -> None:
    step_up, clock, totp = enrolled()
    with pytest.raises(StepUpRequiredError):
        step_up.begin_enrollment(principal(), current_code=None)
    with pytest.raises(StepUpRequiredError):
        step_up.begin_enrollment(principal(), current_code="123456")
    assert step_up.begin_enrollment(principal(), current_code=totp.at(clock()))


@pytest.mark.parametrize("code", ["", "12345", "1234567", "abcdef", "12 456"])
def test_malformed_codes_are_rejected(code: str) -> None:
    step_up, _, _ = enrolled()
    with pytest.raises(StepUpRequiredError):
        step_up.issue_token(principal(), action="a.b", resource="r", code=code)


def _real_clock_service():
    return enrolled(RealClock())


class RealClock(Clock):
    def __init__(self) -> None:
        # enrolled() moves this forward 30 s, which lands on the present.
        self.value = datetime.now(UTC) - timedelta(seconds=31)


def test_token_is_single_use_and_bound() -> None:
    step_up, clock, totp = _real_clock_service()
    token, _ = step_up.issue_token(
        principal(), action="a.b", resource="r", code=totp.at(clock())
    )
    with pytest.raises(StepUpRequiredError):
        step_up.require(principal(session="other"), token, action="a.b", resource="r")
    with pytest.raises(StepUpRequiredError):
        step_up.require(principal(), token, action="a.c", resource="r")
    with pytest.raises(StepUpRequiredError):
        step_up.require(principal(), token, action="a.b", resource="other")
    step_up.require(principal(), token, action="a.b", resource="r")
    with pytest.raises(StepUpRequiredError):
        step_up.require(principal(), token, action="a.b", resource="r")


@pytest.mark.parametrize("token", [None, "", "true", "mfa_verified=true"])
def test_client_invented_step_up_is_refused(token) -> None:
    step_up, _ = service()
    with pytest.raises(StepUpRequiredError):
        step_up.require(principal(), token, action="a.b", resource="r")


def test_production_forces_step_up_and_dual_control_on() -> None:
    settings = load_step_up_settings(
        {
            "IDENTITY_ENVIRONMENT": "prd",
            "IDENTITY_STEP_UP_REQUIRED": "false",
            "IDENTITY_DUAL_CONTROL_REQUIRED": "false",
            "IDENTITY_STEP_UP_SECRET": "s" * 40,
            "IDENTITY_MFA_FACTOR_KEY_BASE64": "QUFB" * 10 + "QUE=",
        }
    )
    assert settings.required is True
    assert settings.dual_control_required is True
    assert "s" * 40 not in repr(settings)


def test_production_refuses_missing_step_up_secrets() -> None:
    with pytest.raises(PersistenceConfigurationError):
        load_step_up_settings({"IDENTITY_ENVIRONMENT": "production"})


# -- durable session revocation -------------------------------------------


def _store(collection=None, clock=None):
    return MongoTokenRevocationStore(
        collection if collection is not None else MemoryCollection(),
        clock=clock or Clock(),
    )


def test_subject_revocation_kills_older_tokens_and_allows_new_sign_in() -> None:
    clock = Clock()
    store = _store(clock=clock)
    issued_before = clock() - timedelta(minutes=1)
    store.revoke_subject("user-1", reason="guardian_recovery_completed")
    assert store.is_revoked("jti-1", "user-1", issued_before) is True
    assert store.is_revoked("jti-2", "user-1", clock()) is True
    assert store.is_revoked("jti-3", "user-1", clock() + timedelta(seconds=2)) is False


def test_revocation_survives_a_process_restart() -> None:
    clock = Clock()
    collection = MemoryCollection()
    _store(collection, clock).revoke_subject("user-1")
    _store(collection, clock).revoke_token("jti-9")
    restarted = _store(collection, clock)
    assert restarted.is_revoked("jti-1", "user-1", clock()) is True
    assert restarted.is_revoked("jti-9") is True


def test_another_instance_sees_the_same_revocation() -> None:
    clock = Clock()
    collection = MemoryCollection()
    first, second = _store(collection, clock), _store(collection, clock)
    first.revoke_subject("user-1")
    assert second.is_revoked("jti-1", "user-1", clock()) is True


class _BrokenCollection:
    def find_one(self, *args, **kwargs):
        raise PyMongoError("down")


def test_revocation_check_fails_closed_when_the_store_is_down() -> None:
    assert _store(_BrokenCollection()).is_revoked("jti-1", "user-1") is True


# -- two-person control ----------------------------------------------------


def dual(clock=None) -> DualControlService:
    return DualControlService(
        operations=MemoryCollection(), clock=clock or Clock()
    )


def _requested(service_, kind=PLATFORM_RESTORE, target="pbk_1:restore_drill_a"):
    return service_.request(
        operation_type=kind,
        target=target,
        reason="scheduled drill",
        requested_by="admin-1",
    )


def test_the_requester_cannot_approve_their_own_operation() -> None:
    service_ = dual()
    operation = _requested(service_)
    with pytest.raises(DualControlError):
        service_.approve(operation.operation_id, approved_by="admin-1")


def test_two_distinct_admins_produce_a_single_use_token() -> None:
    service_ = dual()
    operation = _requested(service_)
    _, token = service_.approve(operation.operation_id, approved_by="admin-2")
    service_.consume(
        operation.operation_id,
        token,
        operation_type=PLATFORM_RESTORE,
        target="pbk_1:restore_drill_a",
    )
    with pytest.raises(DualControlError):
        service_.consume(
            operation.operation_id,
            token,
            operation_type=PLATFORM_RESTORE,
            target="pbk_1:restore_drill_a",
        )


def test_approval_cannot_be_used_for_another_target_or_type() -> None:
    service_ = dual()
    operation = _requested(service_)
    _, token = service_.approve(operation.operation_id, approved_by="admin-2")
    for kind, target in (
        (PLATFORM_RESTORE, "pbk_1:restore_drill_other"),
        (KEY_DESTRUCTION, "pbk_1:restore_drill_a"),
    ):
        with pytest.raises(DualControlError):
            service_.consume(
                operation.operation_id,
                token,
                operation_type=kind,
                target=target,
            )


def test_unapproved_operation_cannot_execute() -> None:
    service_ = dual()
    operation = _requested(service_)
    with pytest.raises(DualControlError):
        service_.consume(
            operation.operation_id,
            "guess",
            operation_type=PLATFORM_RESTORE,
            target="pbk_1:restore_drill_a",
        )


def test_wrong_execution_token_is_refused() -> None:
    service_ = dual()
    operation = _requested(service_)
    service_.approve(operation.operation_id, approved_by="admin-2")
    with pytest.raises(DualControlError):
        service_.consume(
            operation.operation_id,
            "wrong-token",
            operation_type=PLATFORM_RESTORE,
            target="pbk_1:restore_drill_a",
        )


def test_expired_approval_is_refused() -> None:
    clock = Clock()
    service_ = dual(clock)
    operation = _requested(service_)
    _, token = service_.approve(operation.operation_id, approved_by="admin-2")
    clock.advance(1801)
    with pytest.raises(DualControlError):
        service_.consume(
            operation.operation_id,
            token,
            operation_type=PLATFORM_RESTORE,
            target="pbk_1:restore_drill_a",
        )


@pytest.mark.parametrize("operation_id,token", [(None, "x"), ("x", None), ("", "")])
def test_missing_approval_is_refused(operation_id, token) -> None:
    with pytest.raises(DualControlError):
        dual().consume(
            operation_id,
            token,
            operation_type=PLATFORM_RESTORE,
            target="t",
        )


def test_execution_token_is_stored_only_as_a_digest() -> None:
    operations = MemoryCollection()
    service_ = DualControlService(operations=operations, clock=Clock())
    operation = _requested(service_)
    _, token = service_.approve(operation.operation_id, approved_by="admin-2")
    assert token not in str(operations.documents)
