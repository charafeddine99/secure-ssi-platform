import os
from collections.abc import Mapping
from dataclasses import dataclass

from app.domain.audit_outbox import AuditRetryPolicy
from app.domain.persistence import PersistenceConfigurationError


@dataclass(frozen=True)
class AuditOutboxSettings:
    enabled: bool = True
    poll_interval_ms: int = 1_000
    batch_size: int = 100
    base_retry_seconds: int = 1
    max_retry_seconds: int = 300
    lease_seconds: int = 30

    def __post_init__(self) -> None:
        if not 100 <= self.poll_interval_ms <= 60_000:
            raise PersistenceConfigurationError(
                "Audit outbox poll interval is outside the supported range."
            )
        if not 1 <= self.batch_size <= 500:
            raise PersistenceConfigurationError(
                "Audit outbox batch size is outside the supported range."
            )
        try:
            AuditRetryPolicy(
                base_delay_seconds=self.base_retry_seconds,
                max_delay_seconds=self.max_retry_seconds,
                lease_seconds=self.lease_seconds,
            )
        except ValueError as error:
            raise PersistenceConfigurationError(
                "Audit outbox retry settings are invalid."
            ) from error

    @property
    def retry_policy(self) -> AuditRetryPolicy:
        return AuditRetryPolicy(
            base_delay_seconds=self.base_retry_seconds,
            max_delay_seconds=self.max_retry_seconds,
            lease_seconds=self.lease_seconds,
        )


def load_audit_outbox_settings(
    environ: Mapping[str, str] | None = None,
) -> AuditOutboxSettings:
    values = os.environ if environ is None else environ
    return AuditOutboxSettings(
        enabled=_parse_bool(
            values.get("IDENTITY_AUDIT_OUTBOX_ENABLED", "true"),
            name="IDENTITY_AUDIT_OUTBOX_ENABLED",
        ),
        poll_interval_ms=_parse_int(
            values.get("IDENTITY_AUDIT_OUTBOX_POLL_INTERVAL_MS", "1000"),
            name="IDENTITY_AUDIT_OUTBOX_POLL_INTERVAL_MS",
        ),
        batch_size=_parse_int(
            values.get("IDENTITY_AUDIT_OUTBOX_BATCH_SIZE", "100"),
            name="IDENTITY_AUDIT_OUTBOX_BATCH_SIZE",
        ),
        base_retry_seconds=_parse_int(
            values.get("IDENTITY_AUDIT_OUTBOX_BASE_RETRY_SECONDS", "1"),
            name="IDENTITY_AUDIT_OUTBOX_BASE_RETRY_SECONDS",
        ),
        max_retry_seconds=_parse_int(
            values.get("IDENTITY_AUDIT_OUTBOX_MAX_RETRY_SECONDS", "300"),
            name="IDENTITY_AUDIT_OUTBOX_MAX_RETRY_SECONDS",
        ),
        lease_seconds=_parse_int(
            values.get("IDENTITY_AUDIT_OUTBOX_LEASE_SECONDS", "30"),
            name="IDENTITY_AUDIT_OUTBOX_LEASE_SECONDS",
        ),
    )


def _parse_bool(value: str, *, name: str) -> bool:
    normalized = value.strip().casefold()
    if normalized not in {"true", "false"}:
        raise PersistenceConfigurationError(f"{name} must be true or false.")
    return normalized == "true"


def _parse_int(value: str, *, name: str) -> int:
    try:
        return int(value)
    except ValueError as error:
        raise PersistenceConfigurationError(
            f"{name} must be an integer."
        ) from error
