import os
from collections.abc import Mapping
from dataclasses import dataclass

from app.domain.persistence import PersistenceConfigurationError


@dataclass(frozen=True)
class HolderWalletSettings:
    challenge_lifetime_seconds: int = 300
    reconciliation_enabled: bool = True
    reconciliation_stale_seconds: int = 60
    reconciliation_poll_interval_ms: int = 1_000
    reconciliation_batch_size: int = 100

    def __post_init__(self) -> None:
        if not 30 <= self.challenge_lifetime_seconds <= 3_600:
            raise PersistenceConfigurationError(
                "Challenge lifetime is outside the supported range."
            )
        if not 10 <= self.reconciliation_stale_seconds <= 86_400:
            raise PersistenceConfigurationError(
                "Presentation reconciliation timeout is invalid."
            )
        if not 100 <= self.reconciliation_poll_interval_ms <= 60_000:
            raise PersistenceConfigurationError(
                "Presentation reconciliation interval is invalid."
            )
        if not 1 <= self.reconciliation_batch_size <= 500:
            raise PersistenceConfigurationError(
                "Presentation reconciliation batch size is invalid."
            )


def load_holder_wallet_settings(
    environ: Mapping[str, str] | None = None,
) -> HolderWalletSettings:
    values = os.environ if environ is None else environ
    return HolderWalletSettings(
        challenge_lifetime_seconds=_parse_int(
            values.get(
                "IDENTITY_PRESENTATION_CHALLENGE_LIFETIME_SECONDS",
                "300",
            ),
            name="IDENTITY_PRESENTATION_CHALLENGE_LIFETIME_SECONDS",
        ),
        reconciliation_enabled=_parse_bool(
            values.get(
                "IDENTITY_PRESENTATION_RECONCILIATION_ENABLED",
                "true",
            ),
            name="IDENTITY_PRESENTATION_RECONCILIATION_ENABLED",
        ),
        reconciliation_stale_seconds=_parse_int(
            values.get(
                "IDENTITY_PRESENTATION_RECONCILIATION_STALE_SECONDS",
                "60",
            ),
            name="IDENTITY_PRESENTATION_RECONCILIATION_STALE_SECONDS",
        ),
        reconciliation_poll_interval_ms=_parse_int(
            values.get(
                "IDENTITY_PRESENTATION_RECONCILIATION_POLL_INTERVAL_MS",
                "1000",
            ),
            name="IDENTITY_PRESENTATION_RECONCILIATION_POLL_INTERVAL_MS",
        ),
        reconciliation_batch_size=_parse_int(
            values.get(
                "IDENTITY_PRESENTATION_RECONCILIATION_BATCH_SIZE",
                "100",
            ),
            name="IDENTITY_PRESENTATION_RECONCILIATION_BATCH_SIZE",
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
