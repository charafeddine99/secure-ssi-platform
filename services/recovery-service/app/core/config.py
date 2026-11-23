import base64
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from hashlib import sha256

from app.core.environment_policy import is_production_like


SERVICE_NAME = "recovery-service"
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
_DEVELOPMENT_JWT_SECRET = (
    "local-academic-prototype-jwt-secret-not-for-production-2026-only"
)
_DEVELOPMENT_GRANT_SECRET = (
    "local-recovery-to-identity-grant-secret-not-for-production-2026"
)
_DEVELOPMENT_STEP_UP_SECRET = (
    "local-step-up-token-secret-not-for-production-2026-only"
)
_DEVELOPMENT_ENVELOPE_KEY = sha256(
    b"secure-ssi-recovery-development-envelope-key-2026"
).digest()


_PRODUCTION_MINIMUM_APPROVALS = 2
_PRODUCTION_MINIMUM_DELAY_SECONDS = 24 * 3600


class RecoveryConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class RecoverySettings:
    environment: str
    mongo_enabled: bool
    mongo_uri: str = field(repr=False)
    mongo_database: str
    mongo_timeout_ms: int
    jwt_issuer: str
    jwt_audience: str
    jwt_algorithm: str
    jwt_secret: str = field(repr=False)
    jwt_clock_skew_seconds: int = 10
    identity_base_url: str = "http://identity-service:8000"
    identity_grant_issuer: str = "secure-ssi-recovery-service"
    identity_grant_audience: str = "identity-service-recovery"
    identity_grant_secret: str = field(default="", repr=False)
    identity_grant_lifetime_seconds: int = 60
    identity_timeout_seconds: float = 5.0
    envelope_master_key: bytes = field(default=b"", repr=False)
    default_minimum_approvals: int = 2
    default_maximum_guardians: int = 3
    default_approval_window_seconds: int = 3600
    default_time_lock_seconds: int = 300
    default_expiration_seconds: int = 86400
    default_maximum_attempts: int = 3
    default_cooldown_seconds: int = 3600
    reconciliation_enabled: bool = True
    reconciliation_poll_interval_ms: int = 1000
    reconciliation_batch_size: int = 100
    reconciliation_lease_seconds: int = 30
    reconciliation_stale_seconds: int = 60
    minimum_approvals_floor: int = 2
    time_lock_floor_seconds: int = 60
    guardian_change_delay_seconds: int = 300
    guardian_invitation_ttl_seconds: int = 7 * 24 * 3600
    step_up_required: bool = False
    step_up_secret: str = field(default=_DEVELOPMENT_STEP_UP_SECRET, repr=False)
    fraud_base_url: str = "http://fraud-service:8000"
    fraud_service_token: str = field(default="", repr=False)
    fraud_timeout_seconds: float = 2.0

    def __post_init__(self) -> None:
        if is_production_like(self.environment):
            self._require_production_floors()
        if self.jwt_algorithm != "HS256":
            raise RecoveryConfigurationError("Only HS256 recovery JWTs are supported.")
        if len(self.jwt_secret.encode()) < 32 or len(self.identity_grant_secret.encode()) < 32:
            raise RecoveryConfigurationError("Recovery authentication secrets are too short.")
        if len(self.envelope_master_key) != 32:
            raise RecoveryConfigurationError("Recovery envelope key must be 32 bytes.")
        if not 0 <= self.jwt_clock_skew_seconds <= 60:
            raise RecoveryConfigurationError("Recovery JWT clock skew is invalid.")
        if not 100 <= self.mongo_timeout_ms <= 60000:
            raise RecoveryConfigurationError("Recovery MongoDB timeout is invalid.")
        if not 1 <= self.reconciliation_batch_size <= 1000:
            raise RecoveryConfigurationError("Recovery batch size is invalid.")
        if not 100 <= self.reconciliation_poll_interval_ms <= 60000:
            raise RecoveryConfigurationError("Recovery worker interval is invalid.")
        if not 15 <= self.identity_grant_lifetime_seconds <= 120:
            raise RecoveryConfigurationError("Recovery grant lifetime is invalid.")
        if not (
            1
            <= self.default_minimum_approvals
            <= self.default_maximum_guardians
            <= 32
        ):
            raise RecoveryConfigurationError("Default recovery threshold is invalid.")
        if not 60 <= self.default_approval_window_seconds <= 30 * 24 * 3600:
            raise RecoveryConfigurationError("Default approval window is invalid.")
        if not 0 <= self.default_time_lock_seconds <= 30 * 24 * 3600:
            raise RecoveryConfigurationError("Default time lock is invalid.")
        if not (
            self.default_approval_window_seconds + self.default_time_lock_seconds
            <= self.default_expiration_seconds
            <= 60 * 24 * 3600
        ):
            raise RecoveryConfigurationError("Default recovery expiration is invalid.")
        if not 1 <= self.default_maximum_attempts <= 20:
            raise RecoveryConfigurationError("Default recovery attempts are invalid.")
        if not 0 <= self.default_cooldown_seconds <= 30 * 24 * 3600:
            raise RecoveryConfigurationError("Default recovery cooldown is invalid.")
        if min(
            self.reconciliation_lease_seconds,
            self.reconciliation_stale_seconds,
        ) <= 0:
            raise RecoveryConfigurationError("Recovery lease settings are invalid.")


    def _require_production_floors(self) -> None:
        """Fixed for any production-like value; configuration can only raise."""
        if self.minimum_approvals_floor < _PRODUCTION_MINIMUM_APPROVALS:
            raise RecoveryConfigurationError(
                "Production recovery needs at least two Guardian approvals."
            )
        if (
            min(
                self.time_lock_floor_seconds,
                self.guardian_change_delay_seconds,
                self.default_time_lock_seconds,
            )
            < _PRODUCTION_MINIMUM_DELAY_SECONDS
        ):
            raise RecoveryConfigurationError(
                "Production recovery delays must be at least 24 hours."
            )
        if not self.step_up_required:
            raise RecoveryConfigurationError(
                "Production recovery requires step-up authentication."
            )
        if self.step_up_secret == _DEVELOPMENT_STEP_UP_SECRET:
            raise RecoveryConfigurationError(
                "The published step-up secret cannot be used in production."
            )
        if not self.fraud_service_token:
            raise RecoveryConfigurationError(
                "Production recovery requires the risk service credential."
            )


def load_settings(environ: Mapping[str, str] | None = None) -> RecoverySettings:
    values = os.environ if environ is None else environ
    environment = values.get("RECOVERY_ENVIRONMENT", "development").casefold()
    production = is_production_like(environment)
    jwt_secret = values.get("RECOVERY_AUTH_JWT_SECRET")
    grant_secret = values.get("RECOVERY_IDENTITY_GRANT_SECRET")
    envelope_text = values.get("RECOVERY_SHARE_ENVELOPE_KEY_BASE64")
    if production and not all((jwt_secret, grant_secret, envelope_text)):
        raise RecoveryConfigurationError(
            "Production recovery secrets must be explicitly configured."
        )
    if production and (jwt_secret == _DEVELOPMENT_JWT_SECRET or grant_secret == _DEVELOPMENT_GRANT_SECRET):
        raise RecoveryConfigurationError(
            "Published development secrets cannot be used in production."
        )
    envelope_key = _DEVELOPMENT_ENVELOPE_KEY
    if envelope_text:
        try:
            envelope_key = base64.b64decode(envelope_text, validate=True)
        except ValueError as error:
            raise RecoveryConfigurationError("Recovery envelope key is not base64.") from error
    return RecoverySettings(
        environment=environment,
        mongo_enabled=_bool(values.get("RECOVERY_MONGO_ENABLED", "false")),
        mongo_uri=values.get(
            "RECOVERY_MONGO_URI",
            "mongodb://recovery_app:change-me-recovery@mongodb:27017/secure_recovery?authSource=secure_recovery",
        ),
        mongo_database=values.get("RECOVERY_MONGO_DATABASE", "secure_recovery"),
        mongo_timeout_ms=_int(values.get("RECOVERY_MONGO_TIMEOUT_MS", "3000")),
        jwt_issuer=values.get("RECOVERY_AUTH_JWT_ISSUER", "secure-ssi-identity-service"),
        jwt_audience=values.get("RECOVERY_AUTH_JWT_AUDIENCE", "identity-service"),
        jwt_algorithm=values.get("RECOVERY_AUTH_JWT_ALGORITHM", "HS256"),
        jwt_secret=jwt_secret or _DEVELOPMENT_JWT_SECRET,
        jwt_clock_skew_seconds=_int(values.get("RECOVERY_AUTH_CLOCK_SKEW_SECONDS", "10")),
        identity_base_url=values.get(
            "RECOVERY_IDENTITY_BASE_URL", "http://identity-service:8000"
        ).rstrip("/"),
        identity_grant_issuer=values.get(
            "RECOVERY_IDENTITY_GRANT_ISSUER", "secure-ssi-recovery-service"
        ),
        identity_grant_audience=values.get(
            "RECOVERY_IDENTITY_GRANT_AUDIENCE", "identity-service-recovery"
        ),
        identity_grant_secret=grant_secret or _DEVELOPMENT_GRANT_SECRET,
        identity_grant_lifetime_seconds=_int(
            values.get("RECOVERY_IDENTITY_GRANT_LIFETIME_SECONDS", "60")
        ),
        identity_timeout_seconds=_float(
            values.get("RECOVERY_IDENTITY_TIMEOUT_SECONDS", "5")
        ),
        envelope_master_key=envelope_key,
        minimum_approvals_floor=_int(
            values.get(
                "RECOVERY_MINIMUM_APPROVALS_FLOOR",
                "2",
            )
        ),
        time_lock_floor_seconds=_int(
            values.get(
                "RECOVERY_TIME_LOCK_FLOOR_SECONDS",
                "86400" if production else "60",
            )
        ),
        guardian_change_delay_seconds=_int(
            values.get(
                "RECOVERY_GUARDIAN_CHANGE_DELAY_SECONDS",
                "86400" if production else "300",
            )
        ),
        guardian_invitation_ttl_seconds=_int(
            values.get("RECOVERY_GUARDIAN_INVITATION_TTL_SECONDS", "604800")
        ),
        step_up_required=(
            production
            or _bool(values.get("RECOVERY_STEP_UP_REQUIRED", "false"))
        ),
        step_up_secret=(
            values.get("RECOVERY_STEP_UP_SECRET") or _DEVELOPMENT_STEP_UP_SECRET
        ),
        fraud_base_url=values.get(
            "RECOVERY_FRAUD_SERVICE_URL", "http://fraud-service:8000"
        ),
        fraud_service_token=values.get("FRAUD_INTERNAL_SERVICE_TOKEN", ""),
        default_minimum_approvals=_int(
            values.get("RECOVERY_DEFAULT_MINIMUM_APPROVALS", "2")
        ),
        default_maximum_guardians=_int(
            values.get("RECOVERY_DEFAULT_MAXIMUM_GUARDIANS", "3")
        ),
        default_approval_window_seconds=_int(
            values.get("RECOVERY_DEFAULT_APPROVAL_WINDOW_SECONDS", "3600")
        ),
        default_time_lock_seconds=_int(
            values.get(
                "RECOVERY_DEFAULT_TIME_LOCK_SECONDS",
                "86400" if production else "300",
            )
        ),
        default_expiration_seconds=_int(
            values.get(
                "RECOVERY_DEFAULT_EXPIRATION_SECONDS",
                "172800" if production else "86400",
            )
        ),
        default_maximum_attempts=_int(
            values.get("RECOVERY_DEFAULT_MAXIMUM_ATTEMPTS", "3")
        ),
        default_cooldown_seconds=_int(
            values.get("RECOVERY_DEFAULT_COOLDOWN_SECONDS", "3600")
        ),
        reconciliation_enabled=_bool(
            values.get("RECOVERY_RECONCILIATION_ENABLED", "true")
        ),
        reconciliation_poll_interval_ms=_int(
            values.get("RECOVERY_RECONCILIATION_POLL_INTERVAL_MS", "1000")
        ),
        reconciliation_batch_size=_int(
            values.get("RECOVERY_RECONCILIATION_BATCH_SIZE", "100")
        ),
        reconciliation_lease_seconds=_int(
            values.get("RECOVERY_RECONCILIATION_LEASE_SECONDS", "30")
        ),
        reconciliation_stale_seconds=_int(
            values.get("RECOVERY_RECONCILIATION_STALE_SECONDS", "60")
        ),
    )


def _bool(value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized not in {"true", "false"}:
        raise RecoveryConfigurationError("Boolean recovery setting is invalid.")
    return normalized == "true"


def _int(value: str) -> int:
    try:
        return int(value)
    except ValueError as error:
        raise RecoveryConfigurationError("Integer recovery setting is invalid.") from error


def _float(value: str) -> float:
    try:
        result = float(value)
    except ValueError as error:
        raise RecoveryConfigurationError("Float recovery setting is invalid.") from error
    if result <= 0:
        raise RecoveryConfigurationError("Float recovery setting must be positive.")
    return result
