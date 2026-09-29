from typing import Any
from fastapi import APIRouter, Depends, Response, Security
from fastapi.security import HTTPAuthorizationCredentials

from app.api.v1.dependencies import (
    bearer_scheme,
    get_authentication_service,
    require_permission,
)
from app.application.services.authentication_service import AuthenticationService
from app.domain.auth import AuthenticatedPrincipal
from app.domain.exceptions import AuthenticationRequiredError
from app.domain.permissions import Permission
from app.schemas.auth_api import (
    CurrentUserResponse,
    PublicUserResponse,
    TokenRequest,
    TokenResponse,
    TokenRevokeRequest,
    TokenRevokeResponse,
)
from app.schemas.credential_api import ApiErrorResponse


router = APIRouter(prefix="/auth", tags=["authentication"])
AUTH_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {
        "model": ApiErrorResponse,
        "description": "Authentication failed or the access token is invalid.",
    },
    422: {
        "model": ApiErrorResponse,
        "description": "The strict login request envelope is invalid.",
    },
    500: {
        "model": ApiErrorResponse,
        "description": "Sanitized configuration or server failure.",
    },
    503: {
        "model": ApiErrorResponse,
        "description": "The configured persistence provider is unavailable.",
    },
}


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Create a local access token",
    description=(
        "Authenticates one enabled account from the configured local provider "
        "with Argon2id and returns a short-lived HS256 JWT. This public "
        "local-development "
        "endpoint has no rate limiting, MFA, refresh token, or token-session "
        "persistence. A Mongo user provider is an explicit opt-in."
    ),
    responses=AUTH_ERROR_RESPONSES,
)
def create_access_token(
    request: TokenRequest,
    response: Response,
    service: AuthenticationService = Depends(get_authentication_service),
) -> TokenResponse:
    session = service.authenticate(
        username=request.username,
        password=request.password.get_secret_value(),
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return TokenResponse(
        access_token=session.access_token,
        expires_in=session.expires_in,
        user=PublicUserResponse.from_principal(session.principal),
    )


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="Read the current local user",
    description=(
        "Resolves a Bearer token subject against the current synthetic user "
        "registry and derives current roles and permissions. Raw tokens and "
        "authentication records are never returned."
    ),
    responses={
        401: AUTH_ERROR_RESPONSES[401],
        500: AUTH_ERROR_RESPONSES[500],
        503: AUTH_ERROR_RESPONSES[503],
    },
)
def current_user(
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.AUTH_SELF_READ)
    ),
) -> CurrentUserResponse:
    return CurrentUserResponse.from_principal(principal)


@router.post(
    "/revoke",
    response_model=TokenRevokeResponse,
    summary="Revoke an active access token",
    description=(
        "Immediately revokes a JWT access token, blacklisting its JTI against future API requests."
    ),
    responses={
        401: AUTH_ERROR_RESPONSES[401],
        500: AUTH_ERROR_RESPONSES[500],
    },
)
def revoke_access_token(
    request: TokenRevokeRequest = TokenRevokeRequest(),
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    service: AuthenticationService = Depends(get_authentication_service),
) -> TokenRevokeResponse:
    target_token = request.token
    if not target_token and credentials and credentials.scheme.casefold() == "bearer":
        target_token = credentials.credentials

    if not target_token:
        raise AuthenticationRequiredError(
            "Bearer token or explicit token body required for revocation."
        )

    service.revoke_token(target_token, reason=request.reason)
    return TokenRevokeResponse(status="SUCCESS", message="Token successfully revoked.")

