from datetime import UTC, datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Path,
    Response,
    Security,
    status,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.v1.dependencies import (
    get_holder_wallet_repository,
    get_managed_key_service,
)
from app.application.ports.holder_wallet import HolderWalletRepository
from app.application.services.managed_key_service import ManagedKeyService
from app.config.recovery_grant_settings import load_recovery_grant_settings
from app.infrastructure.auth.recovery_grant import (
    RecoveryGrantError,
    RecoveryGrantVerifier,
)
from app.schemas.recovery_internal import (
    ManagedKeyRecoveryRequest,
    ManagedKeyRecoveryResponse,
)


router = APIRouter(prefix="/internal/v1/recovery", tags=["internal-recovery"])
_bearer = HTTPBearer(auto_error=False, scheme_name="RecoveryServiceGrant")
_settings = load_recovery_grant_settings()
_verifier = RecoveryGrantVerifier(_settings)
_WALLET_PATTERN = r"^wallet_[A-Za-z0-9_-]{16,80}$"


def _token(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Security(_bearer)
    ],
) -> str:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise HTTPException(status_code=401, detail="Recovery grant is required.")
    return credentials.credentials


@router.get(
    "/wallets/{wallet_id}/owners/{owner_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    include_in_schema=False,
)
def verify_wallet_owner(
    wallet_id: Annotated[str, Path(pattern=_WALLET_PATTERN)],
    owner_user_id: Annotated[str, Path(min_length=1, max_length=128)],
    token: str = Depends(_token),
    wallets: HolderWalletRepository = Depends(get_holder_wallet_repository),
) -> Response:
    try:
        _verifier.verify(
            token,
            scope="wallet:ownership:read",
            wallet_id=wallet_id,
            owner_user_id=owner_user_id,
            checked_at=datetime.now(UTC),
        )
    except RecoveryGrantError as error:
        raise HTTPException(status_code=401, detail="Recovery grant is invalid.") from error
    wallet = wallets.get(wallet_id)
    if wallet is None or wallet.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Wallet was not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/key-rotation",
    response_model=ManagedKeyRecoveryResponse,
    include_in_schema=False,
)
def recover_managed_key(
    payload: ManagedKeyRecoveryRequest,
    token: str = Depends(_token),
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=16, max_length=128)
    ] = "",
    service: ManagedKeyService = Depends(get_managed_key_service),
) -> ManagedKeyRecoveryResponse:
    if idempotency_key != f"recovery:{payload.recovery_request_id}":
        raise HTTPException(status_code=409, detail="Recovery idempotency key is invalid.")
    try:
        _verifier.verify(
            token,
            scope="managed-key:recover",
            wallet_id=payload.wallet_id,
            owner_user_id=payload.owner_user_id,
            request_id=payload.recovery_request_id,
            checked_at=datetime.now(UTC),
        )
    except RecoveryGrantError as error:
        raise HTTPException(status_code=401, detail="Recovery grant is invalid.") from error
    predecessor, successor = service.recover_wallet(
        payload.wallet_id,
        owner_user_id=payload.owner_user_id,
        recovery_request_id=payload.recovery_request_id,
        reason=payload.reason,
        correlation_id=payload.recovery_request_id,
    )
    return ManagedKeyRecoveryResponse(
        predecessor_key_id=predecessor.key_id,
        successor_key_id=successor.key_id,
        predecessor_did=predecessor.holder_did,
        successor_did=successor.holder_did,
        provider=successor.provider,
    )
