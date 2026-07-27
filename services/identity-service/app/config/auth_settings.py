import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from app.domain.exceptions import AuthConfigurationError


_DEVELOPMENT_ONLY_JWT_SECRET = (
    "local-academic-prototype-jwt-secret-not-for-production-2026-only"
)
_PRODUCTION_LIKE_ENVIRONMENTS = {"production", "prod", "staging"}


@dataclass(frozen=True)
class AuthSettings:
    enabled: bool
    jwt_issuer: str
    jwt_audience: str
    access_token_lifetime_seconds: int
    jwt_algorithm: str
    jwt_secret: str = field(repr=False)
    local_fixture_users_enabled: bool = True
    clock_skew_seconds: int = 10
    environment: str = "development"
    user_provider: str = "synthetic"

    def __post_init__(self) -> None:
        if self.jwt_algorithm != "HS256":
            raise AuthConfigurationError(
                "Only the pinned local JWT algorithm is supported."
            )
        if len(self.jwt_secret.encode("utf-8")) < 32:
            raise AuthConfigurationError(
                "The JWT secret does not meet the minimum length."
            )
        if not 60 <= self.access_token_lifetime_seconds <= 3600:
            raise AuthConfigurationError(
                "Access-token lifetime is outside the local safety bounds."
            )
        if not 0 <= self.clock_skew_seconds <= 60:
            raise AuthConfigurationError(
                "JWT clock skew is outside the local safety bounds."
            )
        if not self.jwt_issuer or not self.jwt_audience:
            raise AuthConfigurationError(
                "JWT issuer and audience must be configured."
            )
        if self.user_provider not in {"synthetic", "mongodb"}:
            raise AuthConfigurationError(
                "Authentication user provider must be synthetic or mongodb."
            )
        if (
            self.environment in _PRODUCTION_LIKE_ENVIRONMENTS
            and self.local_fixture_users_enabled
        ):
            raise AuthConfigurationError(
                "Synthetic users cannot be enabled in production-like mode."
            )


def load_auth_settings(
    environ: Mapping[str, str] | None = None,
) -> AuthSettings:
    values = os.environ if environ is None else environ
    environment = values.get("IDENTITY_ENVIRONMENT", "development").lower()
    secret = values.get("IDENTITY_AUTH_JWT_SECRET")
    if not secret:
        if environment in _PRODUCTION_LIKE_ENVIRONMENTS:
            raise AuthConfigurationError(
                "A JWT secret is required in production-like mode."
            )
        secret = _DEVELOPMENT_ONLY_JWT_SECRET

    return AuthSettings(
        enabled=_parse_bool(
            values.get("IDENTITY_AUTH_ENABLED", "true"),
            name="IDENTITY_AUTH_ENABLED",
        ),
        jwt_issuer=values.get(
            "IDENTITY_AUTH_JWT_ISSUER",
            "secure-ssi-identity-service",
        ),
        jwt_audience=values.get(
            "IDENTITY_AUTH_JWT_AUDIENCE",
            "identity-service",
        ),
        access_token_lifetime_seconds=_parse_int(
            values.get("IDENTITY_AUTH_ACCESS_TOKEN_SECONDS", "900"),
            name="IDENTITY_AUTH_ACCESS_TOKEN_SECONDS",
        ),
        jwt_algorithm=values.get("IDENTITY_AUTH_JWT_ALGORITHM", "HS256"),
        jwt_secret=secret,
        local_fixture_users_enabled=_parse_bool(
            values.get("IDENTITY_AUTH_FIXTURE_USERS_ENABLED", "true"),
            name="IDENTITY_AUTH_FIXTURE_USERS_ENABLED",
        ),
        clock_skew_seconds=_parse_int(
            values.get("IDENTITY_AUTH_CLOCK_SKEW_SECONDS", "10"),
            name="IDENTITY_AUTH_CLOCK_SKEW_SECONDS",
        ),
        environment=environment,
        user_provider=values.get(
            "IDENTITY_AUTH_USER_PROVIDER",
            "synthetic",
        ).strip().casefold(),
    )


def _parse_bool(value: str, *, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized not in {"true", "false"}:
        raise AuthConfigurationError(f"{name} must be true or false.")
    return normalized == "true"


def _parse_int(value: str, *, name: str) -> int:
    try:
        return int(value)
    except ValueError as error:
        raise AuthConfigurationError(f"{name} must be an integer.") from error
