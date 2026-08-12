from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from app.api.dependencies import get_current_principal, get_recovery_service
from app.application.services.recovery_service import RecoveryService
from app.domain.auth import RecoveryPrincipal
from app.schemas.recovery_api import (
    ApiError,
    GuardianCreateRequest,
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
) -> GuardianResponse:
    return GuardianResponse.from_domain(
        service.create_guardian(
            principal,
            wallet_id=payload.wallet_id,
            guardian_user_id=payload.guardian_user_id,
            guardian_did=payload.guardian_did,
            display_name=payload.display_name,
            verification_method=payload.verification_method,
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
) -> GuardianResponse:
    return GuardianResponse.from_domain(
        service.update_guardian(
            principal,
            guardian_id,
            display_name=payload.display_name,
            verification_method=payload.verification_method,
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
) -> GuardianResponse:
    return GuardianResponse.from_domain(
        service.remove_guardian(principal, guardian_id)
    )
