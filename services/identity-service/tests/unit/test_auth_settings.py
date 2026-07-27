import pytest

from app.config.auth_settings import AuthSettings, load_auth_settings
from app.domain.exceptions import AuthConfigurationError


TEST_SECRET = "test-only-auth-secret-with-at-least-thirty-two-bytes"


def test_safe_development_defaults_are_typed() -> None:
    settings = load_auth_settings({})

    assert settings.enabled is True
    assert settings.jwt_algorithm == "HS256"
    assert settings.jwt_issuer == "secure-ssi-identity-service"
    assert settings.jwt_audience == "identity-service"
    assert settings.access_token_lifetime_seconds == 900
    assert settings.clock_skew_seconds == 10
    assert settings.local_fixture_users_enabled is True
    assert settings.user_provider == "synthetic"
    assert "jwt_secret=" not in repr(settings)


def test_production_like_environment_requires_explicit_secret() -> None:
    with pytest.raises(AuthConfigurationError):
        load_auth_settings(
            {
                "IDENTITY_ENVIRONMENT": "production",
                "IDENTITY_AUTH_FIXTURE_USERS_ENABLED": "false",
            }
        )


def test_production_like_environment_rejects_fixture_users() -> None:
    with pytest.raises(AuthConfigurationError):
        load_auth_settings(
            {
                "IDENTITY_ENVIRONMENT": "production",
                "IDENTITY_AUTH_JWT_SECRET": TEST_SECRET,
                "IDENTITY_AUTH_FIXTURE_USERS_ENABLED": "true",
            }
        )


def test_mongodb_user_provider_allows_fixture_users_to_be_disabled() -> None:
    settings = load_auth_settings(
        {
            "IDENTITY_ENVIRONMENT": "production",
            "IDENTITY_AUTH_JWT_SECRET": TEST_SECRET,
            "IDENTITY_AUTH_FIXTURE_USERS_ENABLED": "false",
            "IDENTITY_AUTH_USER_PROVIDER": "mongodb",
        }
    )

    assert settings.user_provider == "mongodb"
    assert settings.local_fixture_users_enabled is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"jwt_algorithm": "none"},
        {"jwt_secret": "short"},
        {"access_token_lifetime_seconds": 59},
        {"access_token_lifetime_seconds": 3_601},
        {"clock_skew_seconds": 61},
        {"user_provider": "unknown"},
    ],
)
def test_unsafe_auth_settings_are_rejected(
    overrides: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "enabled": True,
        "jwt_issuer": "test-issuer",
        "jwt_audience": "identity-service",
        "access_token_lifetime_seconds": 900,
        "jwt_algorithm": "HS256",
        "jwt_secret": TEST_SECRET,
        "local_fixture_users_enabled": True,
        "clock_skew_seconds": 10,
        "environment": "test",
    }
    values.update(overrides)

    with pytest.raises(AuthConfigurationError):
        AuthSettings(**values)  # type: ignore[arg-type]
