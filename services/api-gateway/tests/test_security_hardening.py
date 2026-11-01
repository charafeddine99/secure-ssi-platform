"""Sprint 19 Security Hardening Tests for API Gateway.

Validates defensive security headers (CSP, HSTS, X-Content-Type-Options, X-Frame-Options),
sliding-window rate limiting with standard RFC headers, sensitive endpoint protection,
JSON nesting depth limits, payload size bounds, and CORS lockdown.
"""

from typing import Any
import json
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import CORS_ORIGINS, parse_boolean
from app.core.middleware import RateLimiterMiddleware, SecurityHeadersMiddleware


client = TestClient(app)


def test_defensive_security_headers():
    resp = client.get("/health")
    assert resp.status_code == 200

    headers = resp.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-XSS-Protection") == "1; mode=block"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "camera=()" in headers.get("Permissions-Policy", "")
    assert "default-src 'self'" in headers.get("Content-Security-Policy", "")
    assert "Strict-Transport-Security" not in headers


def test_hsts_is_opt_in_for_verified_tls_termination():
    tls_edge_app = FastAPI()
    tls_edge_app.add_middleware(SecurityHeadersMiddleware, hsts_enabled=True)

    @tls_edge_app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "healthy"}

    response = TestClient(tls_edge_app).get("/health")
    assert response.headers.get("Strict-Transport-Security") == "max-age=31536000"


def test_hsts_setting_rejects_ambiguous_values():
    assert parse_boolean("false", name="GATEWAY_HSTS_ENABLED") is False
    assert parse_boolean("TRUE", name="GATEWAY_HSTS_ENABLED") is True
    try:
        parse_boolean("yes", name="GATEWAY_HSTS_ENABLED")
    except RuntimeError as error:
        assert "GATEWAY_HSTS_ENABLED" in str(error)
    else:
        raise AssertionError("Ambiguous HSTS configuration must fail closed.")


def test_cors_origins_lockdown():
    # Wildcard origin with credentials must not be allowed
    assert "*" not in CORS_ORIGINS
    assert "http://localhost:5173" in CORS_ORIGINS
    assert "http://127.0.0.1:5173" in CORS_ORIGINS


def test_standard_endpoint_rate_limit_headers():
    resp = client.get("/api/v1/fraud/stats")
    assert "X-RateLimit-Limit" in resp.headers
    assert resp.headers.get("X-RateLimit-Limit") == "180"
    assert "X-RateLimit-Remaining" in resp.headers
    assert "X-RateLimit-Reset" in resp.headers


def test_sensitive_endpoint_rate_limit_tier():
    resp = client.post("/api/v1/identity/auth/login", json={})
    assert "X-RateLimit-Limit" in resp.headers
    assert resp.headers.get("X-RateLimit-Limit") == "30"


def test_rate_limit_exceeded_returns_429():
    # Artificially small limiter to test 429 and Retry-After
    limiter_app = RateLimiterMiddleware(app, max_requests=2, window_seconds=60, sensitive_requests=1)
    test_client = TestClient(limiter_app)

    for _ in range(2):
        r = test_client.get("/api/v1/fraud/stats")

    # 3rd request fails
    r_exceeded = test_client.get("/api/v1/fraud/stats")
    assert r_exceeded.status_code == 429
    assert "Retry-After" in r_exceeded.headers
    assert r_exceeded.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


def test_rate_limiter_bounds_client_state_and_ignores_forwarded_ip():
    class TestClientAddress:
        """Set ASGI client metadata without relying on a Starlette-only kwarg."""

        def __init__(self, inner_app):
            self.inner_app = inner_app

        async def __call__(self, scope, receive, send):
            if scope["type"] == "http":
                test_ip = dict(scope.get("headers", [])).get(b"x-test-client-ip")
                if test_ip:
                    scope = {**scope, "client": (test_ip.decode("ascii"), 50000)}
            await self.inner_app(scope, receive, send)

    limiter_app = RateLimiterMiddleware(app, max_requests=20, max_clients=2)
    scoped_app = TestClientAddress(limiter_app)

    with TestClient(scoped_app) as test_client:
        for client_ip in ("192.0.2.1", "192.0.2.2", "192.0.2.3"):
            response = test_client.get(
                "/api/v1/unknown-rate-limit-probe",
                headers={
                    "X-Test-Client-IP": client_ip,
                    "X-Forwarded-For": "198.51.100.99",
                },
            )
            assert response.status_code == 404

    assert len(limiter_app.clients) == 2
    assert set(limiter_app.clients) == {
        "192.0.2.2:standard",
        "192.0.2.3:standard",
    }


def test_payload_size_limit():
    large_payload = b"X" * (1024 * 1024 + 10)  # > 1 MB
    res = client.post("/api/v1/identity/credentials", content=large_payload)
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_json_depth_bomb_defense():
    # Build 20-level nested JSON object
    nested: dict[str, Any] = {"leaf": "data"}
    for i in range(20, 0, -1):
        nested = {f"k_{i}": nested}

    res = client.post(
        "/api/v1/identity/credentials",
        content=json.dumps(nested).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "JSON_DEPTH_EXCEEDED"


def test_invalid_utf8_encoding_defense():
    bad_utf8 = b'{"msg": "\xff\xfe\xfd"}'
    res = client.post(
        "/api/v1/identity/credentials",
        content=bad_utf8,
        headers={"Content-Type": "application/json"}
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_ENCODING"
