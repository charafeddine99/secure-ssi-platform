import base64

import pytest

from app.core.config import RecoveryConfigurationError, load_settings


def test_recovery_configuration_validates_security_boundaries() -> None:
    with pytest.raises(RecoveryConfigurationError):
        load_settings(
            {
                "RECOVERY_DEFAULT_MINIMUM_APPROVALS": "4",
                "RECOVERY_DEFAULT_MAXIMUM_GUARDIANS": "3",
            }
        )
    with pytest.raises(RecoveryConfigurationError):
        load_settings({"RECOVERY_IDENTITY_GRANT_LIFETIME_SECONDS": "121"})
    with pytest.raises(RecoveryConfigurationError):
        load_settings(
            {
                "RECOVERY_DEFAULT_APPROVAL_WINDOW_SECONDS": "3600",
                "RECOVERY_DEFAULT_TIME_LOCK_SECONDS": "300",
                "RECOVERY_DEFAULT_EXPIRATION_SECONDS": "3600",
            }
        )


def test_production_requires_explicit_valid_secrets() -> None:
    with pytest.raises(RecoveryConfigurationError):
        load_settings({"RECOVERY_ENVIRONMENT": "production"})
    settings = load_settings(
        {
            "RECOVERY_ENVIRONMENT": "production",
            "RECOVERY_AUTH_JWT_SECRET": "J" * 32,
            "RECOVERY_IDENTITY_GRANT_SECRET": "G" * 32,
            "RECOVERY_SHARE_ENVELOPE_KEY_BASE64": base64.b64encode(
                b"E" * 32
            ).decode(),
            "RECOVERY_STEP_UP_SECRET": "S" * 32,
            "FRAUD_INTERNAL_SERVICE_TOKEN": "F" * 32,
        }
    )
    assert settings.environment == "production"
    assert settings.step_up_required is True
    assert "S" * 32 not in repr(settings)
    assert "J" * 32 not in repr(settings)
    assert "G" * 32 not in repr(settings)


@pytest.mark.parametrize("environment", ["prd", "qa", "uat", "docker"])
def test_unknown_environment_names_fail_closed(environment: str) -> None:
    # Only explicitly named development/test environments may use fallbacks.
    with pytest.raises(RecoveryConfigurationError):
        load_settings({"RECOVERY_ENVIRONMENT": environment})


def test_published_development_secrets_are_rejected_in_production() -> None:
    from app.core.config import _DEVELOPMENT_GRANT_SECRET, _DEVELOPMENT_JWT_SECRET

    with pytest.raises(RecoveryConfigurationError):
        load_settings(
            {
                "RECOVERY_ENVIRONMENT": "production",
                "RECOVERY_AUTH_JWT_SECRET": _DEVELOPMENT_JWT_SECRET,
                "RECOVERY_IDENTITY_GRANT_SECRET": _DEVELOPMENT_GRANT_SECRET,
                "RECOVERY_SHARE_ENVELOPE_KEY_BASE64": base64.b64encode(b"k" * 32).decode(),
            }
        )
