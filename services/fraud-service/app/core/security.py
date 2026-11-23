"""Authentication and authorization for Fraud Service API operations.

User tokens are checked by Identity Service on every request so current account
status, role changes, and token revocation remain authoritative there. Internal
telemetry uses a separate shared service credential and fails closed when it is
not configured.
"""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import Depends, Header, HTTPException, status


IDENTITY_SERVICE_URL = os.getenv(
    "IDENTITY_SERVICE_URL", "http://127.0.0.1:8001"
).rstrip("/")
FRAUD_INTERNAL_SERVICE_TOKEN = os.getenv("FRAUD_INTERNAL_SERVICE_TOKEN", "")
IDENTITY_AUTH_TIMEOUT_SECONDS = float(
    os.getenv("FRAUD_IDENTITY_AUTH_TIMEOUT_SECONDS", "2")
)


@dataclass(frozen=True)
class FraudPrincipal:
    subject: str
    roles: frozenset[str]
    permissions: frozenset[str]
    internal_service: bool = False


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _service_token_configured() -> str:
    token = FRAUD_INTERNAL_SERVICE_TOKEN
    if len(token) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal service authentication is unavailable.",
        )
    return token


async def _introspect_bearer_token(token: str) -> FraudPrincipal:
    try:
        async with httpx.AsyncClient(
            timeout=IDENTITY_AUTH_TIMEOUT_SECONDS,
            follow_redirects=False,
        ) as client:
            response = await client.get(
                f"{IDENTITY_SERVICE_URL}/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Identity authentication service is unavailable.",
        ) from exc

    if response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN):
        raise _unauthorized()
    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Identity authentication service could not verify the caller.",
        )

    try:
        payload: Any = response.json()
        subject = payload["id"]
        roles = payload["roles"]
        permissions = payload["permissions"]
        if (
            not isinstance(subject, str)
            or not subject
            or not isinstance(roles, list)
            or not all(isinstance(role, str) for role in roles)
            or not isinstance(permissions, list)
            or not all(isinstance(permission, str) for permission in permissions)
        ):
            raise ValueError("invalid identity response shape")
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Identity authentication service returned an invalid response.",
        ) from None

    return FraudPrincipal(
        subject=subject,
        roles=frozenset(roles),
        permissions=frozenset(permissions),
    )


async def authenticate_request(
    authorization: str | None = Header(default=None, alias="Authorization"),
    internal_service_token: str | None = Header(
        default=None, alias="X-Internal-Service-Token"
    ),
) -> FraudPrincipal:
    if internal_service_token is not None:
        expected = _service_token_configured()
        if not hmac.compare_digest(internal_service_token, expected):
            raise _unauthorized()
        return FraudPrincipal(
            subject="identity-service",
            roles=frozenset(),
            permissions=frozenset(),
            internal_service=True,
        )

    if not authorization:
        raise _unauthorized()
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.casefold() != "bearer" or not token.strip():
        raise _unauthorized()
    return await _introspect_bearer_token(token.strip())


async def require_authenticated(
    principal: FraudPrincipal = Depends(authenticate_request),
) -> FraudPrincipal:
    return principal


async def require_authenticated_user(
    principal: FraudPrincipal = Depends(authenticate_request),
) -> FraudPrincipal:
    if principal.internal_service:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A user account is required for this operation.",
        )
    return principal


async def require_internal_service(
    internal_service_token: str | None = Header(
        default=None, alias="X-Internal-Service-Token"
    ),
) -> FraudPrincipal:
    expected = _service_token_configured()
    if internal_service_token is None or not hmac.compare_digest(
        internal_service_token, expected
    ):
        raise _unauthorized()
    return FraudPrincipal(
        subject="identity-service",
        roles=frozenset(),
        permissions=frozenset(),
        internal_service=True,
    )


async def require_incident_writer(
    principal: FraudPrincipal = Depends(require_authenticated_user),
) -> FraudPrincipal:
    if "admin" not in principal.roles or "admin:incidents:write" not in principal.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator permission is required.",
        )
    return principal


async def spend_step_up(authorization: str | None, token: str | None, *, action: str, resource: str) -> None:
    """Identity holds the signing secret, so it checks and consumes the token."""
    headers = {"Authorization": authorization or ""}
    if token:
        headers["X-Step-Up-Token"] = token
    try:
        async with httpx.AsyncClient(timeout=IDENTITY_AUTH_TIMEOUT_SECONDS, follow_redirects=False) as client:
            response = await client.post(
                f"{IDENTITY_SERVICE_URL}/api/v1/auth/step-up/verify",
                headers=headers,
                json={"action": action, "resource": resource},
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Identity authentication service is unavailable.",
        ) from exc
    if response.status_code != status.HTTP_204_NO_CONTENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Fresh authentication is required.")


async def require_admin(
    principal: FraudPrincipal = Depends(require_authenticated_user),
) -> FraudPrincipal:
    if "admin" not in principal.roles or "admin:operations:read" not in principal.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator permission is required.",
        )
    return principal
