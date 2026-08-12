from dataclasses import dataclass
from datetime import datetime
from typing import Any

import jwt
from jwt.exceptions import InvalidTokenError

from app.config.recovery_grant_settings import RecoveryGrantSettings
from app.domain.exceptions import AuthenticationError


class RecoveryGrantError(AuthenticationError):
    pass


@dataclass(frozen=True)
class RecoveryGrantClaims:
    owner_user_id: str
    wallet_id: str
    request_id: str
    scope: str
    jwt_id: str


class RecoveryGrantVerifier:
    def __init__(self, settings: RecoveryGrantSettings) -> None:
        self._settings = settings

    def verify(
        self,
        token: str,
        *,
        scope: str,
        wallet_id: str,
        owner_user_id: str,
        request_id: str | None = None,
        checked_at: datetime,
    ) -> RecoveryGrantClaims:
        if not token or len(token) > 8192:
            raise RecoveryGrantError("Recovery grant is invalid.")
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "HS256":
                raise RecoveryGrantError("Recovery grant algorithm is invalid.")
            payload: dict[str, Any] = jwt.decode(
                token,
                self._settings.secret,
                algorithms=["HS256"],
                audience=self._settings.audience,
                issuer=self._settings.issuer,
                leeway=self._settings.clock_skew_seconds,
                options={
                    "require": [
                        "iss",
                        "sub",
                        "aud",
                        "iat",
                        "nbf",
                        "exp",
                        "jti",
                        "scope",
                        "wallet_id",
                        "request_id",
                    ],
                    "strict_aud": True,
                },
            )
        except (InvalidTokenError, ValueError) as error:
            raise RecoveryGrantError("Recovery grant is invalid.") from error
        expected = {
            "sub": owner_user_id,
            "scope": scope,
            "wallet_id": wallet_id,
        }
        if any(payload.get(name) != value for name, value in expected.items()):
            raise RecoveryGrantError("Recovery grant binding is invalid.")
        if request_id is not None and payload.get("request_id") != request_id:
            raise RecoveryGrantError("Recovery grant request binding is invalid.")
        jwt_id = payload.get("jti")
        grant_request_id = payload.get("request_id")
        issued_at = payload.get("iat")
        expires_at = payload.get("exp")
        if (
            not isinstance(jwt_id, str)
            or not jwt_id
            or not isinstance(grant_request_id, str)
            or not grant_request_id
            or not isinstance(issued_at, int)
            or not isinstance(expires_at, int)
            or not 0 < expires_at - issued_at <= self._settings.lifetime_seconds
            or checked_at.tzinfo is None
            or checked_at.utcoffset() is None
        ):
            raise RecoveryGrantError("Recovery grant claims are invalid.")
        return RecoveryGrantClaims(
            owner_user_id=owner_user_id,
            wallet_id=wallet_id,
            request_id=grant_request_id,
            scope=scope,
            jwt_id=jwt_id,
        )

    def __repr__(self) -> str:
        return (
            "RecoveryGrantVerifier(algorithm='HS256', "
            f"issuer={self._settings.issuer!r}, secret=<redacted>)"
        )
