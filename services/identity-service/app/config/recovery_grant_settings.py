import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from app.domain.exceptions import AuthConfigurationError


_DEVELOPMENT_SECRET = (
    "local-recovery-to-identity-grant-secret-not-for-production-2026"
)
_PRODUCTION = {"production", "prod", "staging"}


@dataclass(frozen=True)
class RecoveryGrantSettings:
    issuer: str
    audience: str
    secret: str = field(repr=False)
    lifetime_seconds: int = 60
    clock_skew_seconds: int = 5

    def __post_init__(self) -> None:
        if not self.issuer or not self.audience or len(self.secret.encode()) < 32:
            raise AuthConfigurationError("Recovery grant settings are invalid.")
        if not 15 <= self.lifetime_seconds <= 120:
            raise AuthConfigurationError("Recovery grant lifetime is invalid.")
        if not 0 <= self.clock_skew_seconds <= 30:
            raise AuthConfigurationError("Recovery grant clock skew is invalid.")


def load_recovery_grant_settings(
    environ: Mapping[str, str] | None = None,
) -> RecoveryGrantSettings:
    values = os.environ if environ is None else environ
    environment = values.get("IDENTITY_ENVIRONMENT", "development").casefold()
    secret = values.get("IDENTITY_RECOVERY_GRANT_SECRET")
    if environment in _PRODUCTION and not secret:
        raise AuthConfigurationError(
            "Identity recovery grant secret is required in production."
        )
    return RecoveryGrantSettings(
        issuer=values.get(
            "IDENTITY_RECOVERY_GRANT_ISSUER", "secure-ssi-recovery-service"
        ),
        audience=values.get(
            "IDENTITY_RECOVERY_GRANT_AUDIENCE", "identity-service-recovery"
        ),
        secret=secret or _DEVELOPMENT_SECRET,
        lifetime_seconds=_int_setting(
            values, "IDENTITY_RECOVERY_GRANT_LIFETIME_SECONDS", "60"
        ),
        clock_skew_seconds=_int_setting(
            values, "IDENTITY_RECOVERY_GRANT_CLOCK_SKEW_SECONDS", "5"
        ),
    )


def _int_setting(
    values: Mapping[str, str], name: str, default: str
) -> int:
    try:
        return int(values.get(name, default))
    except ValueError as error:
        raise AuthConfigurationError(
            "Identity recovery grant integer setting is invalid."
        ) from error
