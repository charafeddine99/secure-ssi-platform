import pytest

from app.config.holder_wallet_settings import (
    HolderWalletSettings,
    load_holder_wallet_settings,
)
from app.domain.persistence import PersistenceConfigurationError


def test_holder_wallet_settings_load_typed_reconciliation_policy() -> None:
    settings = load_holder_wallet_settings(
        {
            "IDENTITY_PRESENTATION_CHALLENGE_LIFETIME_SECONDS": "600",
            "IDENTITY_PRESENTATION_RECONCILIATION_ENABLED": "false",
            "IDENTITY_PRESENTATION_RECONCILIATION_STALE_SECONDS": "120",
            "IDENTITY_PRESENTATION_RECONCILIATION_POLL_INTERVAL_MS": "2500",
            "IDENTITY_PRESENTATION_RECONCILIATION_BATCH_SIZE": "25",
        }
    )

    assert settings == HolderWalletSettings(
        challenge_lifetime_seconds=600,
        reconciliation_enabled=False,
        reconciliation_stale_seconds=120,
        reconciliation_poll_interval_ms=2_500,
        reconciliation_batch_size=25,
    )


@pytest.mark.parametrize(
    "values",
    [
        {
            "IDENTITY_PRESENTATION_CHALLENGE_LIFETIME_SECONDS": "29",
        },
        {
            "IDENTITY_PRESENTATION_RECONCILIATION_ENABLED": "yes",
        },
        {
            "IDENTITY_PRESENTATION_RECONCILIATION_BATCH_SIZE": "0",
        },
    ],
)
def test_holder_wallet_settings_fail_closed(
    values: dict[str, str],
) -> None:
    with pytest.raises(PersistenceConfigurationError):
        load_holder_wallet_settings(values)
