import base64
import binascii
import hashlib
import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from app.config.environment_policy import is_production_like
from app.domain.persistence import PersistenceConfigurationError


_DEVELOPMENT_STEP_UP_SECRET = (
    "local-step-up-token-secret-not-for-production-2026-only"
)
_DEVELOPMENT_FACTOR_KEY = hashlib.sha256(
    b"secure-ssi-development-mfa-factor-key"
).digest()


@dataclass(frozen=True)
class StepUpSettings:
    environment: str
    required: bool
    dual_control_required: bool
    token_secret: str = field(repr=False)
    factor_key: bytes = field(repr=False)
    token_lifetime_seconds: int = 120
    max_failed_attempts: int = 5
    lockout_seconds: int = 300
    totp_issuer: str = "Secure SSI"


def load_step_up_settings(
    environ: Mapping[str, str] | None = None,
) -> StepUpSettings:
    values = os.environ if environ is None else environ
    environment = values.get("IDENTITY_ENVIRONMENT", "development")
    production = is_production_like(environment)
    secret = values.get("IDENTITY_STEP_UP_SECRET", "").strip()
    encoded = values.get("IDENTITY_MFA_FACTOR_KEY_BASE64", "").strip()
    if production and (
        not secret
        or secret == _DEVELOPMENT_STEP_UP_SECRET
        or len(secret) < 32
        or not encoded
    ):
        raise PersistenceConfigurationError(
            "Production-like environments need a step-up secret and an MFA "
            "factor key."
        )
    factor_key = _DEVELOPMENT_FACTOR_KEY
    if encoded:
        try:
            factor_key = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as error:
            raise PersistenceConfigurationError(
                "The MFA factor key is not valid base64."
            ) from error
        if len(factor_key) != 32:
            raise PersistenceConfigurationError(
                "The MFA factor key must be 32 bytes."
            )
    return StepUpSettings(
        environment=environment,
        required=production or _flag(values, "IDENTITY_STEP_UP_REQUIRED"),
        dual_control_required=(
            production or _flag(values, "IDENTITY_DUAL_CONTROL_REQUIRED")
        ),
        token_secret=secret or _DEVELOPMENT_STEP_UP_SECRET,
        factor_key=factor_key,
    )


def _flag(values: Mapping[str, str], name: str) -> bool:
    return values.get(name, "false").strip().casefold() == "true"
