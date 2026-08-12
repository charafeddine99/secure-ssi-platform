from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application.services.metrics import RecoveryMetrics
from app.application.services.recovery_service import RecoveryService
from app.domain.auth import RecoveryPrincipal
from app.domain.recovery import RecoveryAuthorizationError
from app.infrastructure.auth.jwt_authenticator import RecoveryJwtAuthenticator
from app.runtime import RecoveryRuntime


bearer = HTTPBearer(
    auto_error=False,
    scheme_name="BearerAuth",
    bearerFormat="JWT",
    description="Short-lived JWT issued by the local Identity Service.",
)


def get_runtime(request: Request) -> RecoveryRuntime:
    return request.app.state.recovery_runtime


def get_recovery_service(
    runtime: RecoveryRuntime = Depends(get_runtime),
) -> RecoveryService:
    return runtime.service


def get_recovery_metrics(
    runtime: RecoveryRuntime = Depends(get_runtime),
) -> RecoveryMetrics:
    return runtime.metrics


def get_current_principal(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Security(bearer)
    ],
    runtime: RecoveryRuntime = Depends(get_runtime),
) -> RecoveryPrincipal:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer authentication is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return RecoveryJwtAuthenticator(runtime.settings).authenticate(
            credentials.credentials, checked_at=datetime.now(UTC)
        )
    except RecoveryAuthorizationError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer authentication is invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
