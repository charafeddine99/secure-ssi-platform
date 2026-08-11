import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domain.managed_key import (
    KeyAlgorithm,
    KeyPolicyError,
    KeyPurpose,
    ManagedKey,
)
from app.domain.persistence import PersistenceConfigurationError


_PRODUCTION_LIKE = frozenset({"production", "prod", "staging"})


@dataclass(frozen=True)
class KeyManagementSettings:
    environment: str = "development"
    enabled_providers: tuple[str, ...] = ("development",)
    default_provider: str = "development"
    allowed_algorithms: tuple[KeyAlgorithm, ...] = (
        KeyAlgorithm.ED25519,
    )
    development_provider_enabled: bool = True
    prohibit_development_in_production: bool = True
    remote_provider_name: str = "remote-kms"
    remote_base_url: str | None = None
    remote_auth_token_env: str | None = None
    connect_timeout_seconds: float = 2.0
    request_timeout_seconds: float = 5.0
    retry_count: int = 2
    retry_backoff_ms: int = 100
    tls_verify: bool = True
    client_certificate_path: str | None = None
    client_key_path: str | None = None
    circuit_failure_threshold: int = 5
    circuit_reset_seconds: int = 30
    rotation_interval_days: int = 90
    rotation_grace_seconds: int = 0
    destruction_delay_hours: int = 24
    reconciliation_enabled: bool = True
    reconciliation_interval_ms: int = 1_000
    reconciliation_batch_size: int = 100
    stale_operation_seconds: int = 60
    reconciliation_lease_seconds: int = 30
    reconciliation_retry_limit: int = 5

    def __post_init__(self) -> None:
        environment = self.environment.strip().casefold()
        providers = tuple(
            provider.strip().casefold()
            for provider in self.enabled_providers
            if provider.strip()
        )
        if not providers or len(set(providers)) != len(providers):
            raise PersistenceConfigurationError(
                "Enabled key providers must be a non-empty unique list."
            )
        if self.default_provider.casefold() not in providers:
            raise PersistenceConfigurationError(
                "Default key provider must be enabled."
            )
        if not self.allowed_algorithms:
            raise PersistenceConfigurationError(
                "At least one key algorithm must be allowed."
            )
        if (
            "development" in providers
            and not self.development_provider_enabled
        ):
            raise PersistenceConfigurationError(
                "Development key provider is enabled but prohibited."
            )
        if (
            environment in _PRODUCTION_LIKE
            and self.prohibit_development_in_production
            and (
                self.default_provider.casefold() == "development"
                or providers == ("development",)
            )
        ):
            raise PersistenceConfigurationError(
                "Production cannot use development-only key custody."
            )
        if any(
            provider != "development"
            and provider != self.remote_provider_name.casefold()
            for provider in providers
        ):
            raise PersistenceConfigurationError(
                "An enabled key provider has no configured adapter."
            )
        if (
            self.remote_provider_name.casefold() in providers
            and not self.remote_base_url
        ):
            raise PersistenceConfigurationError(
                "Remote KMS base URL is required."
            )
        if (
            environment in _PRODUCTION_LIKE
            and self.remote_provider_name.casefold() in providers
            and not self.tls_verify
        ):
            raise PersistenceConfigurationError(
                "Production remote KMS requires TLS verification."
            )
        if not 0.1 <= self.connect_timeout_seconds <= 60:
            raise PersistenceConfigurationError(
                "KMS connection timeout is invalid."
            )
        if not 0.1 <= self.request_timeout_seconds <= 120:
            raise PersistenceConfigurationError(
                "KMS request timeout is invalid."
            )
        if not 0 <= self.retry_count <= 10:
            raise PersistenceConfigurationError("KMS retry count is invalid.")
        if not 0 <= self.retry_backoff_ms <= 60_000:
            raise PersistenceConfigurationError(
                "KMS retry backoff is invalid."
            )
        if not 1 <= self.circuit_failure_threshold <= 100:
            raise PersistenceConfigurationError(
                "KMS circuit failure threshold is invalid."
            )
        if not 1 <= self.circuit_reset_seconds <= 3_600:
            raise PersistenceConfigurationError(
                "KMS circuit reset interval is invalid."
            )
        if not 1 <= self.rotation_interval_days <= 3_650:
            raise PersistenceConfigurationError(
                "Key rotation interval is invalid."
            )
        if not 0 <= self.rotation_grace_seconds <= 604_800:
            raise PersistenceConfigurationError(
                "Key rotation grace period is invalid."
            )
        if not 1 <= self.destruction_delay_hours <= 8_760:
            raise PersistenceConfigurationError(
                "Key destruction delay is invalid."
            )
        if not 100 <= self.reconciliation_interval_ms <= 60_000:
            raise PersistenceConfigurationError(
                "Key reconciliation interval is invalid."
            )
        if not 1 <= self.reconciliation_batch_size <= 500:
            raise PersistenceConfigurationError(
                "Key reconciliation batch size is invalid."
            )
        if not 10 <= self.stale_operation_seconds <= 86_400:
            raise PersistenceConfigurationError(
                "Stale key operation threshold is invalid."
            )
        if not 5 <= self.reconciliation_lease_seconds <= 3_600:
            raise PersistenceConfigurationError(
                "Key reconciliation lease is invalid."
            )
        if not 1 <= self.reconciliation_retry_limit <= 100:
            raise PersistenceConfigurationError(
                "Key reconciliation retry limit is invalid."
            )
        if bool(self.client_certificate_path) != bool(self.client_key_path):
            raise PersistenceConfigurationError(
                "Both KMS client certificate references are required."
            )
        object.__setattr__(self, "environment", environment)
        object.__setattr__(self, "enabled_providers", providers)
        object.__setattr__(
            self,
            "default_provider",
            self.default_provider.casefold(),
        )
        object.__setattr__(
            self,
            "remote_provider_name",
            self.remote_provider_name.casefold(),
        )


@dataclass(frozen=True)
class ConfiguredKeyPolicy:
    settings: KeyManagementSettings

    def require_provision_allowed(
        self,
        *,
        provider: str,
        algorithm: KeyAlgorithm,
        purpose: KeyPurpose,
    ) -> None:
        del purpose
        if provider.casefold() not in self.settings.enabled_providers:
            raise KeyPolicyError("The requested key provider is disabled.")
        if algorithm not in self.settings.allowed_algorithms:
            raise KeyPolicyError("The requested key algorithm is prohibited.")

    def require_resume_allowed(self, key: ManagedKey) -> None:
        del key

    def destruction_time(self, *, now: datetime) -> datetime:
        return now + timedelta(hours=self.settings.destruction_delay_hours)

    @property
    def rotation_grace_seconds(self) -> int:
        return self.settings.rotation_grace_seconds


def load_key_management_settings(
    environ: Mapping[str, str] | None = None,
) -> KeyManagementSettings:
    values = os.environ if environ is None else environ
    remote_provider_name = values.get(
        "IDENTITY_KMS_REMOTE_PROVIDER_NAME",
        "remote-kms",
    )
    return KeyManagementSettings(
        environment=values.get("IDENTITY_ENVIRONMENT", "development"),
        enabled_providers=_csv(
            values.get("IDENTITY_KMS_ENABLED_PROVIDERS", "development")
        ),
        default_provider=values.get(
            "IDENTITY_KMS_DEFAULT_PROVIDER",
            "development",
        ),
        allowed_algorithms=tuple(
            _algorithm(value)
            for value in _csv(
                values.get(
                    "IDENTITY_KMS_ALLOWED_ALGORITHMS",
                    KeyAlgorithm.ED25519.value,
                )
            )
        ),
        development_provider_enabled=_bool(
            values.get(
                "IDENTITY_KMS_DEVELOPMENT_PROVIDER_ENABLED",
                "true",
            ),
            name="IDENTITY_KMS_DEVELOPMENT_PROVIDER_ENABLED",
        ),
        prohibit_development_in_production=_bool(
            values.get(
                "IDENTITY_KMS_PROHIBIT_DEVELOPMENT_IN_PRODUCTION",
                "true",
            ),
            name="IDENTITY_KMS_PROHIBIT_DEVELOPMENT_IN_PRODUCTION",
        ),
        remote_provider_name=remote_provider_name,
        remote_base_url=_optional(
            values.get("IDENTITY_KMS_REMOTE_BASE_URL")
        ),
        remote_auth_token_env=_optional(
            values.get("IDENTITY_KMS_REMOTE_AUTH_TOKEN_ENV")
        ),
        connect_timeout_seconds=_float(
            values.get("IDENTITY_KMS_CONNECT_TIMEOUT_SECONDS", "2"),
            name="IDENTITY_KMS_CONNECT_TIMEOUT_SECONDS",
        ),
        request_timeout_seconds=_float(
            values.get("IDENTITY_KMS_REQUEST_TIMEOUT_SECONDS", "5"),
            name="IDENTITY_KMS_REQUEST_TIMEOUT_SECONDS",
        ),
        retry_count=_int(
            values.get("IDENTITY_KMS_RETRY_COUNT", "2"),
            name="IDENTITY_KMS_RETRY_COUNT",
        ),
        retry_backoff_ms=_int(
            values.get("IDENTITY_KMS_RETRY_BACKOFF_MS", "100"),
            name="IDENTITY_KMS_RETRY_BACKOFF_MS",
        ),
        tls_verify=_bool(
            values.get("IDENTITY_KMS_TLS_VERIFY", "true"),
            name="IDENTITY_KMS_TLS_VERIFY",
        ),
        client_certificate_path=_optional(
            values.get("IDENTITY_KMS_CLIENT_CERTIFICATE_PATH")
        ),
        client_key_path=_optional(
            values.get("IDENTITY_KMS_CLIENT_KEY_PATH")
        ),
        circuit_failure_threshold=_int(
            values.get(
                "IDENTITY_KMS_CIRCUIT_FAILURE_THRESHOLD",
                "5",
            ),
            name="IDENTITY_KMS_CIRCUIT_FAILURE_THRESHOLD",
        ),
        circuit_reset_seconds=_int(
            values.get("IDENTITY_KMS_CIRCUIT_RESET_SECONDS", "30"),
            name="IDENTITY_KMS_CIRCUIT_RESET_SECONDS",
        ),
        rotation_interval_days=_int(
            values.get("IDENTITY_KMS_ROTATION_INTERVAL_DAYS", "90"),
            name="IDENTITY_KMS_ROTATION_INTERVAL_DAYS",
        ),
        rotation_grace_seconds=_int(
            values.get("IDENTITY_KMS_ROTATION_GRACE_SECONDS", "0"),
            name="IDENTITY_KMS_ROTATION_GRACE_SECONDS",
        ),
        destruction_delay_hours=_int(
            values.get("IDENTITY_KMS_DESTRUCTION_DELAY_HOURS", "24"),
            name="IDENTITY_KMS_DESTRUCTION_DELAY_HOURS",
        ),
        reconciliation_enabled=_bool(
            values.get("IDENTITY_KMS_RECONCILIATION_ENABLED", "true"),
            name="IDENTITY_KMS_RECONCILIATION_ENABLED",
        ),
        reconciliation_interval_ms=_int(
            values.get(
                "IDENTITY_KMS_RECONCILIATION_INTERVAL_MS",
                "1000",
            ),
            name="IDENTITY_KMS_RECONCILIATION_INTERVAL_MS",
        ),
        reconciliation_batch_size=_int(
            values.get(
                "IDENTITY_KMS_RECONCILIATION_BATCH_SIZE",
                "100",
            ),
            name="IDENTITY_KMS_RECONCILIATION_BATCH_SIZE",
        ),
        stale_operation_seconds=_int(
            values.get(
                "IDENTITY_KMS_STALE_OPERATION_SECONDS",
                "60",
            ),
            name="IDENTITY_KMS_STALE_OPERATION_SECONDS",
        ),
        reconciliation_lease_seconds=_int(
            values.get(
                "IDENTITY_KMS_RECONCILIATION_LEASE_SECONDS",
                "30",
            ),
            name="IDENTITY_KMS_RECONCILIATION_LEASE_SECONDS",
        ),
        reconciliation_retry_limit=_int(
            values.get(
                "IDENTITY_KMS_RECONCILIATION_RETRY_LIMIT",
                "5",
            ),
            name="IDENTITY_KMS_RECONCILIATION_RETRY_LIMIT",
        ),
    )


def _algorithm(value: str) -> KeyAlgorithm:
    normalized = value.strip().casefold()
    if normalized in {"ed25519", "eddsa"}:
        return KeyAlgorithm.ED25519
    raise PersistenceConfigurationError(
        "IDENTITY_KMS_ALLOWED_ALGORITHMS contains an unsupported algorithm."
    )


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _optional(value: str | None) -> str | None:
    normalized = (value or "").strip()
    return normalized or None


def _bool(value: str, *, name: str) -> bool:
    normalized = value.strip().casefold()
    if normalized not in {"true", "false"}:
        raise PersistenceConfigurationError(f"{name} must be true or false.")
    return normalized == "true"


def _int(value: str, *, name: str) -> int:
    try:
        return int(value)
    except ValueError as error:
        raise PersistenceConfigurationError(
            f"{name} must be an integer."
        ) from error


def _float(value: str, *, name: str) -> float:
    try:
        return float(value)
    except ValueError as error:
        raise PersistenceConfigurationError(
            f"{name} must be numeric."
        ) from error
