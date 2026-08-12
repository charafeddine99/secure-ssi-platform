from datetime import UTC, datetime
from typing import Any

import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import RecoverySettings
from app.domain.auth import RecoveryPrincipal
from app.domain.recovery import RecoveryAuthorizationError


_REQUIRED = ["iss", "sub", "aud", "iat", "nbf", "exp", "jti", "roles", "token_use"]


class RecoveryJwtAuthenticator:
    def __init__(self, settings: RecoverySettings) -> None:
        self._settings = settings

    def authenticate(self, token: str, *, checked_at: datetime) -> RecoveryPrincipal:
        if not token or len(token) > 8192:
            raise RecoveryAuthorizationError("Bearer access token is invalid.")
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != self._settings.jwt_algorithm:
                raise RecoveryAuthorizationError("Bearer algorithm is not allowed.")
            payload: dict[str, Any] = jwt.decode(
                token,
                self._settings.jwt_secret,
                algorithms=[self._settings.jwt_algorithm],
                audience=self._settings.jwt_audience,
                issuer=self._settings.jwt_issuer,
                leeway=self._settings.jwt_clock_skew_seconds,
                options={"require": _REQUIRED, "strict_aud": True},
            )
        except (InvalidTokenError, ValueError) as error:
            raise RecoveryAuthorizationError("Bearer access token is invalid.") from error
        if payload.get("token_use") != "access":
            raise RecoveryAuthorizationError("Bearer token use is invalid.")
        subject = payload.get("sub")
        roles = payload.get("roles")
        if (
            not isinstance(subject, str)
            or not subject
            or len(subject) > 128
            or not isinstance(roles, list)
            or not all(isinstance(role, str) for role in roles)
        ):
            raise RecoveryAuthorizationError("Bearer claims are invalid.")
        if checked_at.tzinfo is None or checked_at.utcoffset() is None:
            raise RecoveryAuthorizationError("Authentication clock is invalid.")
        return RecoveryPrincipal.from_claims(subject, tuple(roles))

    def __repr__(self) -> str:
        return (
            "RecoveryJwtAuthenticator(algorithm='HS256', "
            f"issuer={self._settings.jwt_issuer!r}, secret=<redacted>)"
        )


def utc_now() -> datetime:
    return datetime.now(UTC)
