"""Sprint 19: Security Hardening Verification Suite (Live & Integration).

Tests defensive security headers, multi-tier rate limiting with standard RFC headers,
JSON nesting depth attack defense, payload size bounds, token revocation / blacklisting,
and sensitive credential/key leakage masking across the unified API Gateway facade.
"""

import sys
import json
import urllib.request
import urllib.error
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from packages.shared.security.masking import (
    sanitize_sensitive_data,
    mask_connection_string,
    SENSITIVE_FIELD_NAMES,
)

GATEWAY_BASE_URL = "http://127.0.0.1:8000"


def is_gateway_online():
    try:
        req = urllib.request.Request(f"{GATEWAY_BASE_URL}/health")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


class TestMaskingSecurityLogic:
    """Verifies credential, seed, and key masking logic without network dependency."""

    def test_mask_connection_string(self):
        uri = "mongodb://ssi_admin:superSecretP@ssw0rd!@127.0.0.1:27017/secure_identity"
        masked = mask_connection_string(uri)
        assert "superSecretP@ssw0rd!" not in masked
        assert masked == "mongodb://ssi_admin:***REDACTED***@127.0.0.1:27017/secure_identity"

    def test_sanitize_sensitive_data_structures(self):
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


@pytest.mark.skipif(not is_gateway_online(), reason="API Gateway daemon is not running on port 8000")
class TestLiveGatewaySecurityHardening:
    """Verifies security controls on the running API Gateway."""

    def test_live_defensive_security_headers(self):
        req = urllib.request.Request(f"{GATEWAY_BASE_URL}/health")
        with urllib.request.urlopen(req, timeout=3) as resp:
            assert resp.status == 200
            headers = resp.headers
            assert headers.get("X-Content-Type-Options") == "nosniff"
            assert headers.get("X-Frame-Options") == "DENY"
            assert headers.get("X-XSS-Protection") == "1; mode=block"
            assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
            assert "default-src 'self'" in headers.get("Content-Security-Policy", "")
            assert "max-age=31536000" in headers.get("Strict-Transport-Security", "")

    def test_live_rate_limiting_headers(self):
        req = urllib.request.Request(f"{GATEWAY_BASE_URL}/api/v1/fraud/stats")
        with urllib.request.urlopen(req, timeout=3) as resp:
            assert resp.status == 200
            assert "X-RateLimit-Limit" in resp.headers
            assert "X-RateLimit-Remaining" in resp.headers
            assert "X-RateLimit-Reset" in resp.headers

    def test_live_json_depth_bomb_defense(self):
        # 20-level nested JSON object
        nested = {"leaf": "data"}
        for i in range(20, 0, -1):
            nested = {f"k_{i}": nested}

        req = urllib.request.Request(
            f"{GATEWAY_BASE_URL}/api/v1/identity/credentials/validate",
            data=json.dumps(nested).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                pytest.fail("Expected 400 Bad Request for JSON depth bomb, got 200")
        except urllib.error.HTTPError as err:
            assert err.code == 400
            data = json.loads(err.read().decode("utf-8"))
            assert data["error"]["code"] == "JSON_DEPTH_EXCEEDED"
