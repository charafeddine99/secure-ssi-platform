from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt.exceptions import (
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidTokenError,
)

from app.config.auth_settings import AuthSettings
from app.domain.auth import AuthenticatedPrincipal, TokenClaims
from app.domain.exceptions import (
    AccessTokenExpiredError,
    AccessTokenInvalidAudienceError,
    AccessTokenInvalidIssuerError,
    AccessTokenInvalidUseError,
    AccessTokenNotActiveError,
    AuthConfigurationError,
    InvalidAccessTokenError,
    InvalidRoleError,
)
from app.domain.permissions import normalize_roles


_REQUIRED_CLAIMS = [
    "iss",
    "sub",
    "aud",
    "iat",
    "nbf",
    "exp",
    "jti",
    "roles",
    "token_use",
]


class JwtAccessTokenService:
    """HS256 JWT adapter pinned to one algorithm, issuer, and audience."""

    def __init__(self, settings: AuthSettings) -> None:
        self._settings = settings

    @property
    def lifetime_seconds(self) -> int:
        return self._settings.access_token_lifetime_seconds

    def issue_access_token(
        self,
        principal: AuthenticatedPrincipal,
        *,
        issued_at: datetime,
        jwt_id: str,
    ) -> str:
        if issued_at.tzinfo is None or issued_at.utcoffset() is None:
            raise AuthConfigurationError(
                "Access-token clock must be timezone-aware."
            )
        if not jwt_id or len(jwt_id) > 128:
            raise AuthConfigurationError("Access-token JTI is invalid.")
        issued_at = issued_at.astimezone(UTC).replace(microsecond=0)
        expires_at = issued_at + timedelta(seconds=self.lifetime_seconds)
        payload = {
            "iss": self._settings.jwt_issuer,
            "sub": principal.id,
            "aud": self._settings.jwt_audience,
            "iat": int(issued_at.timestamp()),
            "nbf": int(issued_at.timestamp()),
            "exp": int(expires_at.timestamp()),
            "jti": jwt_id,
            "roles": [role.value for role in principal.roles],
            "token_use": "access",
        }
        return jwt.encode(
            payload,
            self._settings.jwt_secret,
            algorithm=self._settings.jwt_algorithm,
        )

    def decode_access_token(
        self,
        token: str,
        *,
        checked_at: datetime,
    ) -> TokenClaims:
        if (
            not token
            or len(token) > 8_192
            or checked_at.tzinfo is None
            or checked_at.utcoffset() is None
        ):
            raise InvalidAccessTokenError("Access token input is invalid.")
        try:
            header = jwt.get_unverified_header(token)
        except InvalidTokenError as error:
            raise InvalidAccessTokenError(
                "Access token header is invalid."
            ) from error
        if header.get("alg") != self._settings.jwt_algorithm:
            raise InvalidAccessTokenError(
                "Access token algorithm is not allowed."
            )

        try:
            payload = jwt.decode(
                token,
                self._settings.jwt_secret,
                algorithms=[self._settings.jwt_algorithm],
                audience=self._settings.jwt_audience,
                issuer=self._settings.jwt_issuer,
                options={
                    "require": _REQUIRED_CLAIMS,
                    "strict_aud": True,
                    "verify_exp": False,
                    "verify_iat": False,
                    "verify_nbf": False,
                },
            )
        except InvalidIssuerError as error:
            raise AccessTokenInvalidIssuerError(
                "Access token issuer is invalid."
            ) from error
        except InvalidAudienceError as error:
            raise AccessTokenInvalidAudienceError(
                "Access token audience is invalid."
            ) from error
        except InvalidTokenError as error:
            raise InvalidAccessTokenError(
                "Access token cannot be verified."
            ) from error

        if payload.get("token_use") != "access":
            raise AccessTokenInvalidUseError(
                "Token use is not valid for this operation."
            )

        issued_at = self._timestamp(payload, "iat")
        not_before = self._timestamp(payload, "nbf")
        expires_at = self._timestamp(payload, "exp")
        self._validate_time_window(
            issued_at=issued_at,
            not_before=not_before,
            expires_at=expires_at,
            checked_at=checked_at.astimezone(UTC),
        )

        subject = payload.get("sub")
        jwt_id = payload.get("jti")
        roles_value = payload.get("roles")
        if (
            not isinstance(subject, str)
            or not subject
            or len(subject) > 128
            or not isinstance(jwt_id, str)
            or not jwt_id
            or len(jwt_id) > 128
            or not isinstance(roles_value, list)
            or not all(isinstance(role, str) for role in roles_value)
        ):
            raise InvalidAccessTokenError(
                "Access token claims are malformed."
            )
        try:
            roles = normalize_roles(roles_value)
        except InvalidRoleError as error:
            raise InvalidAccessTokenError(
                "Access token roles are invalid."
            ) from error
        if not roles:
            raise InvalidAccessTokenError("Access token roles are missing.")

        return TokenClaims(
            issuer=self._settings.jwt_issuer,
            subject=subject,
            audience=self._settings.jwt_audience,
            issued_at=issued_at,
            not_before=not_before,
            expires_at=expires_at,
            jwt_id=jwt_id,
            roles=roles,
            token_use="access",
        )

    def _validate_time_window(
        self,
        *,
        issued_at: datetime,
        not_before: datetime,
        expires_at: datetime,
        checked_at: datetime,
    ) -> None:
        leeway = timedelta(seconds=self._settings.clock_skew_seconds)
        if expires_at <= checked_at - leeway:
            raise AccessTokenExpiredError("Access token has expired.")
        if not_before > checked_at + leeway or issued_at > checked_at + leeway:
            raise AccessTokenNotActiveError("Access token is not active.")
        if (
            expires_at <= issued_at
            or not_before > expires_at
            or expires_at - issued_at
            > timedelta(seconds=self.lifetime_seconds)
        ):
            raise InvalidAccessTokenError(
                "Access token time window is invalid."
            )

    @staticmethod
    def _timestamp(payload: dict[str, Any], name: str) -> datetime:
        value = payload.get(name)
        if not isinstance(value, int) or isinstance(value, bool):
            raise InvalidAccessTokenError(
                "Access token time claim is malformed."
            )
        try:
            return datetime.fromtimestamp(value, tz=UTC)
        except (OverflowError, OSError, ValueError) as error:
            raise InvalidAccessTokenError(
                "Access token time claim is outside supported bounds."
            ) from error

    def __repr__(self) -> str:
        return (
            "JwtAccessTokenService("
            f"algorithm={self._settings.jwt_algorithm!r}, "
            f"issuer={self._settings.jwt_issuer!r}, "
            f"audience={self._settings.jwt_audience!r}, secret=<redacted>)"
        )
