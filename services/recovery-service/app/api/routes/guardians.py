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
    GuardianBindingRequest,
    GuardianCreateRequest,
    GuardianInvitationListResponse,
    GuardianInvitationResponse,
    GuardianListResponse,
    GuardianResponse,
    GuardianUpdateRequest,
)


router = APIRouter(prefix="/api/v1/guardians", tags=["guardians"])
_GUARDIAN_PATTERN = r"^guardian_[A-Za-z0-9_-]{16,80}$"
_WALLET_PATTERN = r"^wallet_[A-Za-z0-9_-]{16,80}$"
_ERRORS = {code: {"model": ApiError} for code in (401, 403, 404, 409, 422, 503)}


@router.post(
    "",
    response_model=GuardianResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
)
def create_guardian(
    payload: GuardianCreateRequest,
    principal: RecoveryPrincipal = Depends(get_current_principal),
    service: RecoveryService = Depends(get_recovery_service),
    step_up_token: Annotated[str | None, Header(alias="X-Step-Up-Token")] = None,
    step_up: StepUpGuard = Depends(get_step_up_guard),
) -> GuardianResponse:
    step_up.require(
        principal,
        step_up_token,
        action="recovery.guardian.manage",
        resource=payload.wallet_id,
    )
    return GuardianResponse.from_domain(
        service.create_guardian(
            principal,
            wallet_id=payload.wallet_id,
            guardian_user_id=payload.guardian_user_id,
            display_name=payload.display_name,
        )
    )


@router.get(
    "/invitations",
    response_model=GuardianInvitationListResponse,
    responses=_ERRORS,
)
def list_invitations(
    principal: RecoveryPrincipal = Depends(get_current_principal),
    service: RecoveryService = Depends(get_recovery_service),
) -> GuardianInvitationListResponse:
    return GuardianInvitationListResponse(
        items=[
            GuardianInvitationResponse.from_domain(item)
            for item in service.list_invitations(principal)
        ]
    )


@router.post(
    "/{guardian_id}/accept",
    response_model=GuardianResponse,
    responses=_ERRORS,
)
def accept_invitation(
    guardian_id: Annotated[str, Path(pattern=_GUARDIAN_PATTERN)],
    payload: GuardianBindingRequest,
    principal: RecoveryPrincipal = Depends(get_current_principal),
    service: RecoveryService = Depends(get_recovery_service),
    step_up_token: Annotated[str | None, Header(alias="X-Step-Up-Token")] = None,
    step_up: StepUpGuard = Depends(get_step_up_guard),
) -> GuardianResponse:
    step_up.require(
        principal,
        step_up_token,
        action="recovery.guardian.accept",
        resource=guardian_id,
    )
    return GuardianResponse.from_domain(
        service.accept_invitation(
            principal,
            guardian_id,
            guardian_did=payload.guardian_did,
            verification_method=payload.verification_method,
            proof=payload.proof,
        )
    )


@router.post(
    "/{guardian_id}/rebind",
    response_model=GuardianInvitationResponse,
    responses=_ERRORS,
)
def start_rebind(
    guardian_id: Annotated[str, Path(pattern=_GUARDIAN_PATTERN)],
    principal: RecoveryPrincipal = Depends(get_current_principal),
    service: RecoveryService = Depends(get_recovery_service),
) -> GuardianInvitationResponse:
    return GuardianInvitationResponse.from_domain(
        service.start_rebind(principal, guardian_id)
    )


@router.put(
    "/{guardian_id}/rebind",
    response_model=GuardianResponse,
    responses=_ERRORS,
)
def complete_rebind(
    guardian_id: Annotated[str, Path(pattern=_GUARDIAN_PATTERN)],
    payload: GuardianBindingRequest,
    principal: RecoveryPrincipal = Depends(get_current_principal),
    service: RecoveryService = Depends(get_recovery_service),
    step_up_token: Annotated[str | None, Header(alias="X-Step-Up-Token")] = None,
    step_up: StepUpGuard = Depends(get_step_up_guard),
) -> GuardianResponse:
    step_up.require(
        principal,
        step_up_token,
        action="recovery.guardian.rebind",
        resource=guardian_id,
    )
    return GuardianResponse.from_domain(
        service.complete_rebind(
            principal,
            guardian_id,
            guardian_did=payload.guardian_did,
            verification_method=payload.verification_method,
            proof=payload.proof,
        )
    )


@router.get("", response_model=GuardianListResponse, responses=_ERRORS)
def list_guardians(
    wallet_id: Annotated[
        str | None, Query(alias="walletId", pattern=_WALLET_PATTERN)
    ] = None,
    principal: RecoveryPrincipal = Depends(get_current_principal),
    service: RecoveryService = Depends(get_recovery_service),
) -> GuardianListResponse:
    return GuardianListResponse(
        items=[
            GuardianResponse.from_domain(item)
            for item in service.list_guardians(principal, wallet_id=wallet_id)
        ]
    )


@router.get(
    "/{guardian_id}", response_model=GuardianResponse, responses=_ERRORS
)
def get_guardian(
    guardian_id: Annotated[str, Path(pattern=_GUARDIAN_PATTERN)],
    principal: RecoveryPrincipal = Depends(get_current_principal),
    service: RecoveryService = Depends(get_recovery_service),
) -> GuardianResponse:
    return GuardianResponse.from_domain(
        service.get_guardian(principal, guardian_id)
    )


@router.patch(
    "/{guardian_id}", response_model=GuardianResponse, responses=_ERRORS
)
def update_guardian(
    guardian_id: Annotated[str, Path(pattern=_GUARDIAN_PATTERN)],
    payload: GuardianUpdateRequest,
    principal: RecoveryPrincipal = Depends(get_current_principal),
    service: RecoveryService = Depends(get_recovery_service),
    step_up_token: Annotated[str | None, Header(alias="X-Step-Up-Token")] = None,
    step_up: StepUpGuard = Depends(get_step_up_guard),
) -> GuardianResponse:
    step_up.require(
        principal,
        step_up_token,
        action="recovery.guardian.manage",
        resource=guardian_id,
    )
    return GuardianResponse.from_domain(
        service.update_guardian(
            principal,
            guardian_id,
            display_name=payload.display_name,
            status=payload.status,
        )
    )


@router.delete(
    "/{guardian_id}", response_model=GuardianResponse, responses=_ERRORS
)
def remove_guardian(
    guardian_id: Annotated[str, Path(pattern=_GUARDIAN_PATTERN)],
    principal: RecoveryPrincipal = Depends(get_current_principal),
    service: RecoveryService = Depends(get_recovery_service),
    step_up_token: Annotated[str | None, Header(alias="X-Step-Up-Token")] = None,
    step_up: StepUpGuard = Depends(get_step_up_guard),
) -> GuardianResponse:
    step_up.require(
        principal,
        step_up_token,
        action="recovery.guardian.manage",
        resource=guardian_id,
    )
    return GuardianResponse.from_domain(
        service.remove_guardian(principal, guardian_id)
    )
