"""Test sensitive field masking and PII leakage prevention."""

from packages.shared.security.masking import (
    sanitize_sensitive_data,
    mask_connection_string,
    SENSITIVE_FIELD_NAMES,
)


def test_mask_connection_string():
    uri = "mongodb://ssi_admin:superSecretP@ssw0rd!@127.0.0.1:27017/secure_identity"
    masked = mask_connection_string(uri)
    assert "superSecretP@ssw0rd!" not in masked
    assert masked == "mongodb://ssi_admin:***REDACTED***@127.0.0.1:27017/secure_identity"


def test_sanitize_sensitive_data_structures():
    payload = {
        "user": "alice",
        "private_key": "308184020100300506032b657004220420..",
        "seed": "1234567890abcdef",
        "password": "my_secret_password",
        "metadata": {
            "jwt_secret": "sensitive-signing-key",
            "nested_list": [
                {"authorization_secret": "shamir-share-secret", "public_id": "pub-123"}
            ]
        }
    }
    sanitized = sanitize_sensitive_data(payload)
    assert sanitized["user"] == "alice"
    assert sanitized["private_key"] == "***REDACTED***"
    assert sanitized["seed"] == "***REDACTED***"
    assert sanitized["password"] == "***REDACTED***"
    assert sanitized["metadata"]["jwt_secret"] == "***REDACTED***"
    assert sanitized["metadata"]["nested_list"][0]["authorization_secret"] == "***REDACTED***"
    assert sanitized["metadata"]["nested_list"][0]["public_id"] == "pub-123"
