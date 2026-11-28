"""Authenticator enrollment, step-up tokens and two-person approvals."""

import logging
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Path, Response
from pydantic import Field

from app.api.v1.dependencies import (
    get_audit_event_repository,
    get_authentication_service,
    get_current_principal,
    get_dual_control_service,
    get_step_up_service,
    require_permission,
)
from app.application.services.authentication_service import (
    AuthenticationService,
)
from app.application.services.dual_control_service import (
    DualControlOperation,
    DualControlService,
)
from app.application.services.step_up_service import (
    StepUpRequiredError,
    StepUpService,
)
from app.domain.auth import AuthenticatedPrincipal
from app.domain.exceptions import InvalidCredentialsError
from app.application.ports.repositories import AuditEventRepository
from app.domain.persistence import AuditEvent, AuditEventType
from app.infrastructure.persistence.mappers import new_object_id
from app.domain.permissions import Permission
from app.schemas.credential_api import ApiModel


_LOGGER = logging.getLogger(__name__)

router = APIRouter(tags=["step-up-authentication"])
_CODE = r"^[0-9]{6}$"


class MfaStatusResponse(ApiModel):
    required: bool
    enrolled: bool
    method: str | None


class TotpEnrollRequest(ApiModel):
    password: str = Field(min_length=1, max_length=1024)
    current_code: str | None = Field(default=None, pattern=_CODE)


class TotpEnrollResponse(ApiModel):
    secret: str
    otpauth_uri: str


class TotpConfirmRequest(ApiModel):
    code: str = Field(pattern=_CODE)


class StepUpRequest(ApiModel):
    action: str = Field(min_length=3, max_length=64)
    resource: str = Field(min_length=1, max_length=256)
    code: str = Field(pattern=_CODE)


class StepUpResponse(ApiModel):
    step_up_token: str
    expires_in: int


class DualControlRequest(ApiModel):
    operation_type: Literal[
        "KEY_COMPROMISE",
        "KEY_DESTRUCTION",
        "PLATFORM_RESTORE",
        "BACKUP_KEY_ROTATION",
    ]
    target: str = Field(min_length=3, max_length=512)
    reason: str = Field(min_length=3, max_length=500)


class DualControlResponse(ApiModel):
    operation_id: str
    operation_type: str
    target: str
    requested_by: str
    approved_by: str | None
    status: str
    expires_at: str

    @classmethod
    def from_domain(cls, value: DualControlOperation) -> "DualControlResponse":
        return cls(
            operation_id=value.operation_id,
            operation_type=value.operation_type,
            target=value.target,
            requested_by=value.requested_by,
            approved_by=value.approved_by,
            status=value.status,
            expires_at=value.expires_at.isoformat(),
        )


class DualControlApprovalResponse(ApiModel):
    operation: DualControlResponse
    execution_token: str


class DualControlListResponse(ApiModel):
    items: list[DualControlResponse]


@router.get("/auth/mfa", response_model=MfaStatusResponse)
def mfa_status(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    service: StepUpService = Depends(get_step_up_service),
) -> MfaStatusResponse:
    return MfaStatusResponse(**service.status(principal.id))


@router.post("/auth/mfa/totp", response_model=TotpEnrollResponse)
def begin_totp_enrollment(
    payload: TotpEnrollRequest,
    response: Response,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    authentication: AuthenticationService = Depends(
        get_authentication_service
    ),
    service: StepUpService = Depends(get_step_up_service),
) -> TotpEnrollResponse:
    # A stolen session alone must not be able to enroll its own authenticator.
    # Not a 401: the gateway ends the session on 401, and a mistyped password
    # here should not sign the person out.
    try:
        authentication.authenticate(
            username=principal.username,
            password=payload.password,
        )
    except InvalidCredentialsError as error:
        raise StepUpRequiredError("The password is not correct.") from error
    enrollment = service.begin_enrollment(
        principal,
        current_code=payload.current_code,
    )
    response.headers["Cache-Control"] = "no-store"
    return TotpEnrollResponse(
        secret=enrollment.secret,
        otpauth_uri=enrollment.otpauth_uri,
    )


@router.post("/auth/mfa/totp/confirm", response_model=MfaStatusResponse)
def confirm_totp_enrollment(
    payload: TotpConfirmRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    service: StepUpService = Depends(get_step_up_service),
) -> MfaStatusResponse:
    service.confirm_enrollment(principal, code=payload.code)
    return MfaStatusResponse(**service.status(principal.id))


def _audit_step_up(
    audit_events: AuditEventRepository,
    event_type: AuditEventType,
    actor_id: str,
) -> None:
    now = datetime.now(UTC)
    try:
        audit_events.append(AuditEvent(
            id=new_object_id(), event_type=event_type, subject_id=actor_id,
            actor_id=actor_id, correlation_id=None, metadata={},
            created_at=now, updated_at=now, version=1,
        ))
    except Exception as error:
        _LOGGER.warning("Step-up audit event was not written (%s)", type(error).__name__)


@router.post("/auth/step-up", response_model=StepUpResponse)
def create_step_up_token(
    payload: StepUpRequest,
    response: Response,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    service: StepUpService = Depends(get_step_up_service),
    audit_events: AuditEventRepository = Depends(get_audit_event_repository),
) -> StepUpResponse:
    try:
        token, lifetime = service.issue_token(
            principal,
            action=payload.action,
            resource=payload.resource,
            code=payload.code,
        )
    except StepUpRequiredError:
        _audit_step_up(audit_events, AuditEventType.STEP_UP_FAILED, principal.id)
        raise
    _audit_step_up(audit_events, AuditEventType.STEP_UP_SUCCEEDED, principal.id)
    response.headers["Cache-Control"] = "no-store"
    return StepUpResponse(step_up_token=token, expires_in=lifetime)


class StepUpCheck(ApiModel):
    action: str = Field(min_length=3, max_length=100)
    resource: str = Field(min_length=1, max_length=512)


@router.post("/auth/step-up/verify", status_code=204)
def verify_step_up_token(
    payload: StepUpCheck,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    service: StepUpService = Depends(get_step_up_service),
    step_up_token: Annotated[str | None, Header(alias="X-Step-Up-Token")] = None,
) -> Response:
    """Lets another service spend a token without holding the signing secret."""
    service.require(principal, step_up_token, action=payload.action, resource=payload.resource)
    return Response(status_code=204)


@router.get(
    "/admin/dual-control",
    response_model=DualControlListResponse,
)
def list_dual_control_operations(
    _principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.ADMIN_BACKUP_READ)
    ),
    service: DualControlService = Depends(get_dual_control_service),
) -> DualControlListResponse:
    return DualControlListResponse(
        items=[
            DualControlResponse.from_domain(item)
            for item in service.list_recent()
        ]
    )


@router.post(
    "/admin/dual-control",
    response_model=DualControlResponse,
    status_code=201,
)
def request_dual_control_operation(
    payload: DualControlRequest,
    step_up_token: Annotated[
        str | None, Header(alias="X-Step-Up-Token")
    ] = None,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.ADMIN_BACKUP_WRITE)
    ),
    service: DualControlService = Depends(get_dual_control_service),
    step_up: StepUpService = Depends(get_step_up_service),
) -> DualControlResponse:
    step_up.require(
        principal,
        step_up_token,
        action="dual-control.request",
        resource=payload.target,
    )
    return DualControlResponse.from_domain(
        service.request(
            operation_type=payload.operation_type,
            target=payload.target,
            reason=payload.reason,
            requested_by=principal.id,
        )
    )


@router.post(
    "/admin/dual-control/{operation_id}/approve",
    response_model=DualControlApprovalResponse,
)
def approve_dual_control_operation(
    operation_id: Annotated[str, Path(pattern=r"^dco_[A-Za-z0-9_-]{16,64}$")],
    response: Response,
    step_up_token: Annotated[
        str | None, Header(alias="X-Step-Up-Token")
    ] = None,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.ADMIN_BACKUP_WRITE)
    ),
    service: DualControlService = Depends(get_dual_control_service),
    step_up: StepUpService = Depends(get_step_up_service),
) -> DualControlApprovalResponse:
    step_up.require(
        principal,
        step_up_token,
        action="dual-control.approve",
        resource=operation_id,
    )
    operation, token = service.approve(operation_id, approved_by=principal.id)
    response.headers["Cache-Control"] = "no-store"
    return DualControlApprovalResponse(
        operation=DualControlResponse.from_domain(operation),
        execution_token=token,
    )
