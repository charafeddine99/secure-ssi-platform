from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path, Query, status

from app.api.dependencies import (
    get_current_principal,
    get_recovery_service,
    get_step_up_guard,
)
from app.infrastructure.auth.step_up import StepUpGuard
from app.application.services.recovery_service import RecoveryService
from app.domain.auth import RecoveryPrincipal
from app.schemas.recovery_api import (
    ApiError,
    GuardianDecisionRequest,
    RecoveryApprovalResponse,
    RecoveryCreateRequest,
    RecoveryDecisionResponse,
    RecoveryNotificationListResponse,
    RecoveryNotificationResponse,
    RiskReviewRequest,
    RecoveryPolicyResponse,
    RecoveryPolicyUpsertRequest,
    RecoveryOversightCaseResponse,
    RecoveryOversightDetailResponse,
    RecoveryOversightListResponse,
    RecoveryRequestListResponse,
    RecoveryRequestResponse,
    RecoveryTimelineEventResponse,
    RecoveryTimelineResponse,
)
from app.domain.recovery import RecoveryState


router = APIRouter(prefix="/api/v1/recovery", tags=["account-recovery"])
_REQUEST_PATTERN = r"^recovery_[A-Za-z0-9_-]{16,80}$"
_WALLET_PATTERN = r"^wallet_[A-Za-z0-9_-]{16,80}$"
_ERRORS = {code: {"model": ApiError} for code in (401, 403, 404, 409, 422, 503)}


@router.get(
    "/policy", response_model=RecoveryPolicyResponse, responses=_ERRORS
)
def get_policy(
    wallet_id: Annotated[str, Query(alias="walletId", pattern=_WALLET_PATTERN)],
    principal: RecoveryPrincipal = Depends(get_current_principal),
    service: RecoveryService = Depends(get_recovery_service),
) -> RecoveryPolicyResponse:
    return RecoveryPolicyResponse.from_domain(
        service.get_policy(principal, wallet_id=wallet_id)
    )


@router.put(
    "/policy", response_model=RecoveryPolicyResponse, responses=_ERRORS
)
def put_policy(
    payload: RecoveryPolicyUpsertRequest,
    principal: RecoveryPrincipal = Depends(get_current_principal),
    service: RecoveryService = Depends(get_recovery_service),
    step_up_token: Annotated[str | None, Header(alias="X-Step-Up-Token")] = None,
    step_up: StepUpGuard = Depends(get_step_up_guard),
) -> RecoveryPolicyResponse:
    step_up.require(
        principal,
        step_up_token,
        action="recovery.policy.update",
        resource=payload.wallet_id,
    )
    return RecoveryPolicyResponse.from_domain(
        service.put_policy(principal, **payload.model_dump())
    )


@router.post(
    "/requests",
    response_model=RecoveryRequestResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
)
def create_request(
    payload: RecoveryCreateRequest,
    principal: RecoveryPrincipal = Depends(get_current_principal),
    service: RecoveryService = Depends(get_recovery_service),
    step_up_token: Annotated[str | None, Header(alias="X-Step-Up-Token")] = None,
    step_up: StepUpGuard = Depends(get_step_up_guard),
) -> RecoveryRequestResponse:
    step_up.require(
        principal,
        step_up_token,
        action="recovery.request.create",
        resource=payload.wallet_id,
    )
    return RecoveryRequestResponse.from_domain(
        service.create_request(
            principal, wallet_id=payload.wallet_id, reason=payload.reason
        )
    )


@router.get(
    "/requests", response_model=RecoveryRequestListResponse, responses=_ERRORS
)
def list_requests(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    principal: RecoveryPrincipal = Depends(get_current_principal),
    service: RecoveryService = Depends(get_recovery_service),
) -> RecoveryRequestListResponse:
    return RecoveryRequestListResponse(
        items=[
            RecoveryRequestResponse.from_domain(item)
            for item in service.list_requests(principal, limit=limit)
        ]
    )


@router.get(
    "/requests/{request_id}",
    response_model=RecoveryRequestResponse,
    responses=_ERRORS,
)
def get_request(
    request_id: Annotated[str, Path(pattern=_REQUEST_PATTERN)],
    principal: RecoveryPrincipal = Depends(get_current_principal),
    service: RecoveryService = Depends(get_recovery_service),
) -> RecoveryRequestResponse:
    return RecoveryRequestResponse.from_domain(
        service.get_request(principal, request_id)
    )


@router.get(
    "/requests/{request_id}/timeline",
    response_model=RecoveryTimelineResponse,
    responses=_ERRORS,
)
def get_request_timeline(
    request_id: Annotated[str, Path(pattern=_REQUEST_PATTERN)],
    principal: RecoveryPrincipal = Depends(get_current_principal),
    service: RecoveryService = Depends(get_recovery_service),
) -> RecoveryTimelineResponse:
    return RecoveryTimelineResponse(
        request_id=request_id,
        items=[
            RecoveryTimelineEventResponse.from_domain(event)
            for event in service.get_timeline(principal, request_id)
        ],
    )


@router.get(
    "/admin/requests",
    response_model=RecoveryOversightListResponse,
    responses=_ERRORS,
)
def list_oversight_cases(
    state: Annotated[RecoveryState | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    principal: RecoveryPrincipal = Depends(get_current_principal),
    service: RecoveryService = Depends(get_recovery_service),
) -> RecoveryOversightListResponse:
    return RecoveryOversightListResponse(
        items=[
            RecoveryOversightCaseResponse.from_domain(item)
            for item in service.list_oversight(
                principal, states=None if state is None else (state,), limit=limit
            )
        ]
    )


@router.get(
    "/admin/requests/{request_id}",
    response_model=RecoveryOversightDetailResponse,
    responses=_ERRORS,
)
def get_oversight_case(
    request_id: Annotated[str, Path(pattern=_REQUEST_PATTERN)],
    principal: RecoveryPrincipal = Depends(get_current_principal),
    service: RecoveryService = Depends(get_recovery_service),
) -> RecoveryOversightDetailResponse:
    request, events = service.get_oversight(principal, request_id)
    return RecoveryOversightDetailResponse(
        case=RecoveryOversightCaseResponse.from_domain(request),
        timeline=[RecoveryTimelineEventResponse.from_domain(item) for item in events],
    )


@router.post(
    "/requests/{request_id}/cancel",
    response_model=RecoveryRequestResponse,
    responses=_ERRORS,
)
def cancel_request(
    request_id: Annotated[str, Path(pattern=_REQUEST_PATTERN)],
    principal: RecoveryPrincipal = Depends(get_current_principal),
    service: RecoveryService = Depends(get_recovery_service),
) -> RecoveryRequestResponse:
    return RecoveryRequestResponse.from_domain(
        service.cancel(principal, request_id)
    )


@router.post(
    "/requests/{request_id}/approve",
    response_model=RecoveryDecisionResponse,
    responses=_ERRORS,
)
def approve_request(
    request_id: Annotated[str, Path(pattern=_REQUEST_PATTERN)],
    payload: GuardianDecisionRequest,
    principal: RecoveryPrincipal = Depends(get_current_principal),
    service: RecoveryService = Depends(get_recovery_service),
    step_up_token: Annotated[str | None, Header(alias="X-Step-Up-Token")] = None,
    step_up: StepUpGuard = Depends(get_step_up_guard),
) -> RecoveryDecisionResponse:
    step_up.require(
        principal,
        step_up_token,
        action="recovery.decide",
        resource=request_id,
    )
    approval, recovery = service.approve(
        principal,
        request_id,
        guardian_id=payload.guardian_id,
        challenge=payload.challenge,
        proof=payload.proof,
    )
    return RecoveryDecisionResponse(
        approval=RecoveryApprovalResponse.from_domain(approval),
        recovery=RecoveryRequestResponse.from_domain(recovery),
    )


@router.post(
    "/requests/{request_id}/reject",
    response_model=RecoveryDecisionResponse,
    responses=_ERRORS,
)
def reject_request(
    request_id: Annotated[str, Path(pattern=_REQUEST_PATTERN)],
    payload: GuardianDecisionRequest,
    principal: RecoveryPrincipal = Depends(get_current_principal),
    service: RecoveryService = Depends(get_recovery_service),
    step_up_token: Annotated[str | None, Header(alias="X-Step-Up-Token")] = None,
    step_up: StepUpGuard = Depends(get_step_up_guard),
) -> RecoveryDecisionResponse:
    step_up.require(
        principal,
        step_up_token,
        action="recovery.decide",
        resource=request_id,
    )
    approval, recovery = service.reject(
        principal,
        request_id,
        guardian_id=payload.guardian_id,
        challenge=payload.challenge,
        proof=payload.proof,
    )
    return RecoveryDecisionResponse(
        approval=RecoveryApprovalResponse.from_domain(approval),
        recovery=RecoveryRequestResponse.from_domain(recovery),
    )


@router.post(
    "/requests/{request_id}/risk-review",
    response_model=RecoveryRequestResponse,
    responses=_ERRORS,
)
def review_risk(
    request_id: Annotated[str, Path(pattern=_REQUEST_PATTERN)],
    payload: RiskReviewRequest,
    principal: RecoveryPrincipal = Depends(get_current_principal),
    service: RecoveryService = Depends(get_recovery_service),
    step_up_token: Annotated[str | None, Header(alias="X-Step-Up-Token")] = None,
    step_up: StepUpGuard = Depends(get_step_up_guard),
) -> RecoveryRequestResponse:
    step_up.require(
        principal,
        step_up_token,
        action="recovery.risk.review",
        resource=request_id,
    )
    return RecoveryRequestResponse.from_domain(
        service.review_risk(
            principal,
            request_id,
            decision=payload.decision,
            reason=payload.reason,
        )
    )


@router.get(
    "/notifications",
    response_model=RecoveryNotificationListResponse,
    responses=_ERRORS,
)
def list_notifications(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    principal: RecoveryPrincipal = Depends(get_current_principal),
    service: RecoveryService = Depends(get_recovery_service),
) -> RecoveryNotificationListResponse:
    return RecoveryNotificationListResponse(
        items=[
            RecoveryNotificationResponse(
                notification_id=item.notification_id,
                event_type=item.event_type,
                aggregate_id=item.aggregate_id,
                wallet_id=item.wallet_id,
                created_at=item.created_at,
                read_at=item.read_at,
            )
            for item in service.list_notifications(principal, limit=limit)
        ]
    )


@router.post(
    "/notifications/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_ERRORS,
)
def mark_notification_read(
    notification_id: Annotated[
        str, Path(pattern=r"^notice_[a-f0-9]{40}$")
    ],
    principal: RecoveryPrincipal = Depends(get_current_principal),
    service: RecoveryService = Depends(get_recovery_service),
) -> None:
    service.mark_notification_read(principal, notification_id)


@router.post(
    "/requests/{request_id}/reconcile",
    response_model=RecoveryRequestResponse,
    responses=_ERRORS,
)
def reconcile_request(
    request_id: Annotated[str, Path(pattern=_REQUEST_PATTERN)],
    principal: RecoveryPrincipal = Depends(get_current_principal),
    service: RecoveryService = Depends(get_recovery_service),
) -> RecoveryRequestResponse:
    return RecoveryRequestResponse.from_domain(
        service.reconcile_request(principal, request_id)
    )
