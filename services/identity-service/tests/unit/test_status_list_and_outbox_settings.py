import pytest

from app.config.audit_outbox_settings import load_audit_outbox_settings
from app.config.status_list_settings import load_status_list_settings
from app.domain.persistence import PersistenceConfigurationError


def test_status_list_and_outbox_settings_are_typed() -> None:
    status = load_status_list_settings(
        {
            "IDENTITY_STATUS_LIST_PUBLIC_BASE_URL": (
                "https://issuer.example/api/v1/status-lists/"
            ),
            "IDENTITY_STATUS_LIST_LENGTH": "262144",
            "IDENTITY_STATUS_LIST_CAPACITY": "2048",
            "IDENTITY_STATUS_LIST_TTL_SECONDS": "600",
        }
    )
    outbox = load_audit_outbox_settings(
        {
            "IDENTITY_AUDIT_OUTBOX_ENABLED": "false",
            "IDENTITY_AUDIT_OUTBOX_POLL_INTERVAL_MS": "500",
            "IDENTITY_AUDIT_OUTBOX_BATCH_SIZE": "20",
            "IDENTITY_AUDIT_OUTBOX_BASE_RETRY_SECONDS": "2",
            "IDENTITY_AUDIT_OUTBOX_MAX_RETRY_SECONDS": "60",
            "IDENTITY_AUDIT_OUTBOX_LEASE_SECONDS": "15",
        }
    )

    assert status.public_base_url.endswith("/status-lists")
    assert status.list_length == 262_144
    assert status.capacity == 2_048
    assert status.ttl_seconds == 600
    assert outbox.enabled is False
    assert outbox.batch_size == 20
    assert outbox.retry_policy.next_available_at


@pytest.mark.parametrize(
    "values",
    [
        {"IDENTITY_STATUS_LIST_PUBLIC_BASE_URL": "file:///tmp/status"},
        {"IDENTITY_STATUS_LIST_LENGTH": "100"},
        {
            "IDENTITY_STATUS_LIST_LENGTH": "131072",
            "IDENTITY_STATUS_LIST_CAPACITY": "131073",
        },
        {"IDENTITY_STATUS_LIST_TTL_SECONDS": "0"},
    ],
)
def test_invalid_status_list_settings_fail_closed(
    values: dict[str, str],
) -> None:
    with pytest.raises(PersistenceConfigurationError):
        load_status_list_settings(values)


def test_invalid_outbox_retry_settings_fail_closed() -> None:
    with pytest.raises(PersistenceConfigurationError):
        load_audit_outbox_settings(
            {
                "IDENTITY_AUDIT_OUTBOX_ENABLED": "true",
                "IDENTITY_AUDIT_OUTBOX_POLL_INTERVAL_MS": "1000",
                "IDENTITY_AUDIT_OUTBOX_BATCH_SIZE": "100",
                "IDENTITY_AUDIT_OUTBOX_BASE_RETRY_SECONDS": "60",
                "IDENTITY_AUDIT_OUTBOX_MAX_RETRY_SECONDS": "1",
                "IDENTITY_AUDIT_OUTBOX_LEASE_SECONDS": "30",
            }
        )
