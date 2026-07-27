import pytest

from app.config.mongo_settings import MongoSettings, load_mongo_settings
from app.domain.persistence import PersistenceConfigurationError


def test_mongo_defaults_are_disabled_typed_and_redacted() -> None:
    settings = load_mongo_settings({})

    assert settings.enabled is False
    assert settings.database_name == "secure_identity"
    assert settings.max_pool_size == 50
    assert settings.retry_reads is True
    assert settings.retry_writes is True
    assert "mongodb://" not in repr(settings)
    assert "uri=" not in repr(settings)


def test_mongo_environment_values_are_parsed() -> None:
    settings = load_mongo_settings(
        {
            "IDENTITY_MONGO_ENABLED": "true",
            "IDENTITY_MONGO_URI": (
                "mongodb://app:secret@mongodb:27017/identity"
            ),
            "IDENTITY_MONGO_DATABASE": "identity_test",
            "IDENTITY_MONGO_SERVER_SELECTION_TIMEOUT_MS": "750",
            "IDENTITY_MONGO_CONNECT_TIMEOUT_MS": "800",
            "IDENTITY_MONGO_SOCKET_TIMEOUT_MS": "900",
            "IDENTITY_MONGO_MAX_POOL_SIZE": "20",
            "IDENTITY_MONGO_MIN_POOL_SIZE": "2",
            "IDENTITY_MONGO_RETRY_READS": "false",
            "IDENTITY_MONGO_RETRY_WRITES": "false",
            "IDENTITY_MONGO_APP_NAME": "identity-test",
        }
    )

    assert settings.enabled is True
    assert settings.database_name == "identity_test"
    assert settings.server_selection_timeout_ms == 750
    assert settings.connect_timeout_ms == 800
    assert settings.socket_timeout_ms == 900
    assert settings.max_pool_size == 20
    assert settings.min_pool_size == 2
    assert settings.retry_reads is False
    assert settings.retry_writes is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"uri": "https://mongodb.example.test"},
        {"uri": "mongodb://"},
        {"database_name": "invalid database"},
        {"server_selection_timeout_ms": 99},
        {"max_pool_size": 0},
        {"min_pool_size": 51},
    ],
)
def test_unsafe_mongo_settings_are_rejected(
    overrides: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "enabled": True,
        "uri": "mongodb://localhost:27017/identity",
        "database_name": "identity",
        "max_pool_size": 50,
    }
    values.update(overrides)

    with pytest.raises(PersistenceConfigurationError):
        MongoSettings(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "environment",
    [
        {"IDENTITY_MONGO_ENABLED": "yes"},
        {"IDENTITY_MONGO_MAX_POOL_SIZE": "large"},
    ],
)
def test_invalid_environment_values_fail_closed(
    environment: dict[str, str],
) -> None:
    with pytest.raises(PersistenceConfigurationError):
        load_mongo_settings(environment)
