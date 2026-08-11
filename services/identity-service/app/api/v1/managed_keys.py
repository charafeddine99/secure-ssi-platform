from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Header,
    Path,
    Query,
    Request,
    status,
)

from app.api.v1.dependencies import (
    get_managed_key_service,
    require_permission,
)
from app.application.services.managed_key_service import ManagedKeyService
from app.domain.auth import AuthenticatedPrincipal
from app.domain.permissions import Permission
from app.schemas.credential_api import ApiErrorResponse
from app.schemas.managed_key_api import (
    ManagedKeyCreateRequest,
    ManagedKeyDestructionRequest,
    ManagedKeyListResponse,
    ManagedKeyReasonRequest,
    ManagedKeyResponse,
    ManagedKeyRotateRequest,
)


router = APIRouter(prefix="/wallets", tags=["managed-keys"])
_WALLET_ID_PATTERN = r"^wallet_[A-Za-z0-9_-]{16,80}$"
_KEY_ID_PATTERN = r"^key_[A-Za-z0-9_-]{16,80}$"
_ERRORS = {
    401: {"model": ApiErrorResponse},
    403: {"model": ApiErrorResponse},
    404: {
        "model": ApiErrorResponse,
        "description": "The wallet or key is absent or hidden.",
    },
    409: {"model": ApiErrorResponse},
    422: {"model": ApiErrorResponse},
    503: {"model": ApiErrorResponse},
}


@router.post(
    "/{wallet_id}/keys",
    response_model=ManagedKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Provision a provider-bound managed key",
    responses=_ERRORS,
)
def create_managed_key(
    wallet_id: Annotated[str, Path(pattern=_WALLET_ID_PATTERN)],
    payload: ManagedKeyCreateRequest,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=8,
            max_length=256,
        ),
    ],
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.WALLET_KEY_CREATE)
    ),
    service: ManagedKeyService = Depends(get_managed_key_service),
) -> ManagedKeyResponse:
    return ManagedKeyResponse.from_domain(
        service.create_for_wallet(
            wallet_id=wallet_id,
            owner_user_id=principal.id,
            purpose=payload.purpose,
            algorithm=payload.algorithm,
            provider_name=payload.provider,
            idempotency_key=idempotency_key,
            correlation_id=request.state.request_id,
        )
    )


@router.get(
    "/{wallet_id}/keys",
    response_model=ManagedKeyListResponse,
    summary="List managed keys owned by a holder wallet",
    responses=_ERRORS,
)
def list_managed_keys(
    wallet_id: Annotated[str, Path(pattern=_WALLET_ID_PATTERN)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    after_key_id: Annotated[
        str | None,
        Query(alias="afterKeyId", pattern=_KEY_ID_PATTERN),
    ] = None,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.WALLET_KEY_READ)
    ),
    service: ManagedKeyService = Depends(get_managed_key_service),
) -> ManagedKeyListResponse:
    keys = service.list_owned(
        wallet_id,
        owner_user_id=principal.id,
        limit=limit,
        after_key_id=after_key_id,
    )
    return ManagedKeyListResponse(
        wallet_id=wallet_id,
        items=[ManagedKeyResponse.from_domain(key) for key in keys],
        next_cursor=keys[-1].key_id if len(keys) == limit else None,
    )


@router.get(
    "/{wallet_id}/keys/{key_id}",
    response_model=ManagedKeyResponse,
    summary="Read managed-key public lifecycle metadata",
    responses=_ERRORS,
)
def get_managed_key(
    wallet_id: Annotated[str, Path(pattern=_WALLET_ID_PATTERN)],
    key_id: Annotated[str, Path(pattern=_KEY_ID_PATTERN)],
    request: Request,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.WALLET_KEY_READ)
    ),
    service: ManagedKeyService = Depends(get_managed_key_service),
) -> ManagedKeyResponse:
    return ManagedKeyResponse.from_domain(
        service.get_owned(
            wallet_id,
            key_id,
            owner_user_id=principal.id,
            correlation_id=request.state.request_id,
        )
    )


@router.post(
    "/{wallet_id}/keys/{key_id}/rotate",
    response_model=ManagedKeyResponse,
    summary="Rotate an active managed key",
    responses=_ERRORS,
)
def rotate_managed_key(
    wallet_id: Annotated[str, Path(pattern=_WALLET_ID_PATTERN)],
    key_id: Annotated[str, Path(pattern=_KEY_ID_PATTERN)],
    _payload: ManagedKeyRotateRequest,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=8,
            max_length=256,
        ),
    ],
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.WALLET_KEY_ROTATE)
    ),
    service: ManagedKeyService = Depends(get_managed_key_service),
) -> ManagedKeyResponse:
    return ManagedKeyResponse.from_domain(
        service.rotate(
            wallet_id,
            key_id,
            owner_user_id=principal.id,
            idempotency_key=idempotency_key,
            correlation_id=request.state.request_id,
        )
    )


@router.post(
    "/{wallet_id}/keys/{key_id}/suspend",
    response_model=ManagedKeyResponse,
    summary="Suspend an owned managed key",
    responses=_ERRORS,
)
def suspend_managed_key(
    wallet_id: Annotated[str, Path(pattern=_WALLET_ID_PATTERN)],
    key_id: Annotated[str, Path(pattern=_KEY_ID_PATTERN)],
    payload: ManagedKeyReasonRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.WALLET_KEY_SUSPEND)
    ),
    service: ManagedKeyService = Depends(get_managed_key_service),
) -> ManagedKeyResponse:
    del payload
    return ManagedKeyResponse.from_domain(
        service.suspend(
            wallet_id,
            key_id,
            owner_user_id=principal.id,
            correlation_id=request.state.request_id,
        )
    )


@router.post(
    "/{wallet_id}/keys/{key_id}/resume",
    response_model=ManagedKeyResponse,
    summary="Resume an owned suspended key",
    responses=_ERRORS,
)
def resume_managed_key(
    wallet_id: Annotated[str, Path(pattern=_WALLET_ID_PATTERN)],
    key_id: Annotated[str, Path(pattern=_KEY_ID_PATTERN)],
    payload: ManagedKeyReasonRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.WALLET_KEY_RESUME)
    ),
    service: ManagedKeyService = Depends(get_managed_key_service),
) -> ManagedKeyResponse:
    del payload
    return ManagedKeyResponse.from_domain(
        service.resume(
            wallet_id,
            key_id,
            owner_user_id=principal.id,
            correlation_id=request.state.request_id,
        )
    )


@router.post(
    "/{wallet_id}/keys/{key_id}/compromise",
    response_model=ManagedKeyResponse,
    summary="Administratively mark a managed key compromised",
    responses=_ERRORS,
)
def compromise_managed_key(
    wallet_id: Annotated[str, Path(pattern=_WALLET_ID_PATTERN)],
    key_id: Annotated[str, Path(pattern=_KEY_ID_PATTERN)],
    payload: ManagedKeyReasonRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.WALLET_KEY_COMPROMISE)
    ),
    service: ManagedKeyService = Depends(get_managed_key_service),
) -> ManagedKeyResponse:
    return ManagedKeyResponse.from_domain(
        service.mark_compromised(
            wallet_id,
            key_id,
            actor_id=principal.id,
            reason=payload.reason,
            correlation_id=request.state.request_id,
            administrative=True,
        )
    )


@router.post(
    "/{wallet_id}/keys/{key_id}/revoke",
    response_model=ManagedKeyResponse,
    summary="Irreversibly revoke an owned managed key",
    responses=_ERRORS,
)
def revoke_managed_key(
    wallet_id: Annotated[str, Path(pattern=_WALLET_ID_PATTERN)],
    key_id: Annotated[str, Path(pattern=_KEY_ID_PATTERN)],
    payload: ManagedKeyReasonRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.WALLET_KEY_REVOKE)
    ),
    service: ManagedKeyService = Depends(get_managed_key_service),
) -> ManagedKeyResponse:
    return ManagedKeyResponse.from_domain(
        service.revoke(
            wallet_id,
            key_id,
            owner_user_id=principal.id,
            reason=payload.reason,
            correlation_id=request.state.request_id,
        )
    )


@router.post(
    "/{wallet_id}/keys/{key_id}/schedule-destruction",
    response_model=ManagedKeyResponse,
    summary="Administratively schedule delayed provider deletion",
    responses=_ERRORS,
)
def schedule_managed_key_destruction(
    wallet_id: Annotated[str, Path(pattern=_WALLET_ID_PATTERN)],
    key_id: Annotated[str, Path(pattern=_KEY_ID_PATTERN)],
    payload: ManagedKeyDestructionRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.WALLET_KEY_DESTROY)
    ),
    service: ManagedKeyService = Depends(get_managed_key_service),
) -> ManagedKeyResponse:
    return ManagedKeyResponse.from_domain(
        service.schedule_destruction(
            wallet_id,
            key_id,
            actor_id=principal.id,
            reason=payload.reason,
            confirmation=payload.confirmation,
            correlation_id=request.state.request_id,
            administrative=True,
        )
    )


@router.post(
    "/{wallet_id}/keys/{key_id}/cancel-destruction",
    response_model=ManagedKeyResponse,
    summary="Administratively cancel pending provider deletion",
    responses=_ERRORS,
)
def cancel_managed_key_destruction(
    wallet_id: Annotated[str, Path(pattern=_WALLET_ID_PATTERN)],
    key_id: Annotated[str, Path(pattern=_KEY_ID_PATTERN)],
    payload: ManagedKeyReasonRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.WALLET_KEY_DESTROY)
    ),
    service: ManagedKeyService = Depends(get_managed_key_service),
) -> ManagedKeyResponse:
    return ManagedKeyResponse.from_domain(
        service.cancel_destruction(
            wallet_id,
            key_id,
            actor_id=principal.id,
            reason=payload.reason,
            correlation_id=request.state.request_id,
            administrative=True,
        )
    )


@router.post(
    "/{wallet_id}/keys/{key_id}/reconcile",
    response_model=ManagedKeyResponse,
    summary="Administratively reconcile provider and local key state",
    responses=_ERRORS,
)
def reconcile_managed_key(
    wallet_id: Annotated[str, Path(pattern=_WALLET_ID_PATTERN)],
    key_id: Annotated[str, Path(pattern=_KEY_ID_PATTERN)],
    payload: ManagedKeyReasonRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.ADMIN_KEY_RECONCILE)
    ),
    service: ManagedKeyService = Depends(get_managed_key_service),
) -> ManagedKeyResponse:
    del payload
    return ManagedKeyResponse.from_domain(
        service.reconcile_authorized(
            wallet_id,
            key_id,
            actor_id=principal.id,
            correlation_id=request.state.request_id,
            administrative=True,
        )
    )
