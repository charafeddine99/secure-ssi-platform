from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application.ports.managed_keys import ManagedKeyRecoveryGateway
from app.application.services.metrics import RecoveryMetrics
from app.application.services.recovery_service import RecoveryService
from app.domain.auth import RecoveryPrincipal
from app.domain.recovery import (
    RecoveryAuthorizationError,
    RecoveryPersistenceError,
)
from app.infrastructure.auth.jwt_authenticator import RecoveryJwtAuthenticator
from app.infrastructure.auth.step_up import StepUpGuard
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


def get_step_up_guard(
    runtime: RecoveryRuntime = Depends(get_runtime),
) -> StepUpGuard:
    return StepUpGuard(runtime.settings, runtime.repository)


def get_recovery_metrics(
    runtime: RecoveryRuntime = Depends(get_runtime),
) -> RecoveryMetrics:
    return runtime.metrics


def get_session_gateway(
    runtime: RecoveryRuntime = Depends(get_runtime),
) -> ManagedKeyRecoveryGateway:
    return runtime.gateway


def get_current_principal(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Security(bearer)
    ],
    runtime: RecoveryRuntime = Depends(get_runtime),
    sessions: ManagedKeyRecoveryGateway = Depends(get_session_gateway),
) -> RecoveryPrincipal:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer authentication is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        authenticator = RecoveryJwtAuthenticator(runtime.settings)
        principal = authenticator.authenticate(
            credentials.credentials, checked_at=datetime.now(UTC)
        )
        # Revocation lives in Identity: a signature alone is not enough, and a
        # failed check is treated as a revoked session.
        sessions.require_active_session(
            user_id=principal.user_id,
            session_id=principal.session_id,
            issued_at=int(authenticator.last_claims["iat"]),
        )
        return principal
    except (RecoveryAuthorizationError, RecoveryPersistenceError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer authentication is invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
