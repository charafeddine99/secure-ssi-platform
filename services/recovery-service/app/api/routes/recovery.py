from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from app.api.dependencies import get_current_principal, get_recovery_service
from app.application.services.recovery_service import RecoveryService
from app.domain.auth import RecoveryPrincipal
from app.schemas.recovery_api import (
    ApiError,
    GuardianDecisionRequest,
    RecoveryApprovalResponse,
    RecoveryCreateRequest,
    RecoveryDecisionResponse,
    RecoveryPolicyResponse,
    RecoveryPolicyUpsertRequest,
    RecoveryRequestListResponse,
    RecoveryRequestResponse,
)


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
) -> RecoveryPolicyResponse:
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
) -> RecoveryRequestResponse:
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
) -> RecoveryDecisionResponse:
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
) -> RecoveryDecisionResponse:
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
