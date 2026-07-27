from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, status

from app.api.v1.dependencies import (
    get_holder_wallet_service,
    require_permission,
)
from app.application.services.holder_wallet_service import (
    HolderWalletService,
)
from app.domain.auth import AuthenticatedPrincipal
from app.domain.permissions import Permission
from app.schemas.credential_api import ApiErrorResponse
from app.schemas.holder_wallet_api import (
    HolderWalletCreateRequest,
    HolderWalletResponse,
    WalletCredentialInventoryResponse,
    WalletCredentialResponse,
)


router = APIRouter(prefix="/wallets", tags=["holder-wallets"])
_WALLET_ID_PATTERN = r"^wallet_[A-Za-z0-9_-]{16,80}$"
_ERRORS = {
    401: {"model": ApiErrorResponse},
    403: {"model": ApiErrorResponse},
    404: {
        "model": ApiErrorResponse,
        "description": "The wallet is absent or hidden from this user.",
    },
    409: {"model": ApiErrorResponse},
    422: {"model": ApiErrorResponse},
    503: {"model": ApiErrorResponse},
}


@router.post(
    "",
    response_model=HolderWalletResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an authenticated holder wallet",
    responses=_ERRORS,
)
def create_wallet(
    _payload: HolderWalletCreateRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.WALLETS_CREATE)
    ),
    service: HolderWalletService = Depends(get_holder_wallet_service),
) -> HolderWalletResponse:
    return HolderWalletResponse.from_domain(
        service.create(
            owner_user_id=principal.id,
            correlation_id=request.state.request_id,
        )
    )


@router.get(
    "/{wallet_id}",
    response_model=HolderWalletResponse,
    summary="Read an owned holder wallet",
    responses=_ERRORS,
)
def get_wallet(
    wallet_id: Annotated[str, Path(pattern=_WALLET_ID_PATTERN)],
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.WALLETS_READ)
    ),
    service: HolderWalletService = Depends(get_holder_wallet_service),
) -> HolderWalletResponse:
    return HolderWalletResponse.from_domain(
        service.get_owned(wallet_id, owner_user_id=principal.id)
    )


@router.get(
    "/{wallet_id}/credentials",
    response_model=WalletCredentialInventoryResponse,
    summary="List credentials owned by a holder wallet",
    responses=_ERRORS,
)
def list_wallet_credentials(
    wallet_id: Annotated[str, Path(pattern=_WALLET_ID_PATTERN)],
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.WALLETS_CREDENTIALS_READ)
    ),
    service: HolderWalletService = Depends(get_holder_wallet_service),
) -> WalletCredentialInventoryResponse:
    records = service.list_credentials(
        wallet_id,
        owner_user_id=principal.id,
    )
    return WalletCredentialInventoryResponse(
        wallet_id=wallet_id,
        credentials=[
            WalletCredentialResponse.from_domain(record)
            for record in records
        ],
    )
