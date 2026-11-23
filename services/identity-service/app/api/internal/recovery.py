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
import jwt

from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.dependencies import (
    get_authentication_service,
    get_holder_wallet_repository,
    get_managed_key_repository,
    get_managed_key_service,
)
from app.application.ports.key_management import ManagedKeyRepository
from app.application.services.authentication_service import (
    AuthenticationService,
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


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class SessionCheckRequest(_Strict):
    session_id: str = Field(alias="sessionId", min_length=1, max_length=256)
    issued_at: int = Field(alias="issuedAt", ge=0)


class DidCustodyRequest(_Strict):
    did: str = Field(min_length=8, max_length=2048)


def _subject_of(token: str, *, scope: str) -> str:
    """Reads the grant's subject, then verifies the grant for that subject."""
    try:
        subject = str(
            jwt.decode(token, options={"verify_signature": False})["sub"]
        )
        _verifier.verify(
            token,
            scope=scope,
            wallet_id="",
            owner_user_id=subject,
            checked_at=datetime.now(UTC),
        )
    except (KeyError, jwt.PyJWTError, RecoveryGrantError) as error:
        raise HTTPException(
            status_code=401, detail="Recovery grant is invalid."
        ) from error
    return subject


@router.post("/sessions/check", include_in_schema=False)
def check_session(
    payload: SessionCheckRequest,
    token: str = Depends(_token),
    authentication: AuthenticationService = Depends(
        get_authentication_service
    ),
) -> dict[str, bool]:
    return {
        "active": authentication.is_session_active(
            user_id=_subject_of(token, scope="session:read"),
            session_id=payload.session_id,
            issued_at=datetime.fromtimestamp(payload.issued_at, UTC),
        )
    }


@router.post("/dids/custody", include_in_schema=False)
def did_custody(
    payload: DidCustodyRequest,
    token: str = Depends(_token),
    keys: ManagedKeyRepository = Depends(get_managed_key_repository),
) -> dict[str, bool]:
    _subject_of(token, scope="did:custody:read")
    multibase = payload.did.removeprefix("did:key:")
    method = f"{payload.did}#{multibase}"
    return {"managed": keys.get_by_verification_method(method) is not None}


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
    authentication: AuthenticationService = Depends(
        get_authentication_service
    ),
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
    # Whoever held the old key may still hold a session: end them all.
    authentication.revoke_subject(
        payload.owner_user_id,
        reason="guardian_recovery_completed",
    )
    return ManagedKeyRecoveryResponse(
        predecessor_key_id=predecessor.key_id,
        successor_key_id=successor.key_id,
        predecessor_did=predecessor.holder_did,
        successor_did=successor.holder_did,
        provider=successor.provider,
    )
