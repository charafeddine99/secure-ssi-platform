"""Browser session cookie and CSRF checks (OWASP Session Management / CSRF cheat sheets)."""

import json

from fastapi.testclient import TestClient

from app.api.routes import proxy as proxy_routes
from app.core.session import SESSION_COOKIE_NAME
from app.main import app

client = TestClient(app)
WEB = {"X-SSI-Client": "web", "Origin": "http://127.0.0.1:5173"}


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self.content = json.dumps(payload if payload is not None else {}).encode()
        self.headers = {"content-type": "application/json"}


def install(monkeypatch, response=None, error=None):
    captured = []

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def request(self, *, method, url, headers, **_kwargs):
            captured.append({"method": method, "url": url, "headers": {k.lower(): v for k, v in headers.items()}})
            if error is not None:
                raise error
            return response or FakeResponse()

    monkeypatch.setattr(proxy_routes.httpx, "AsyncClient", lambda **_kwargs: FakeClient())
    return captured


def set_cookie_header(response):
    return [value for key, value in response.headers.multi_items() if key.lower() == "set-cookie"]


def test_web_sign_in_moves_token_into_httponly_cookie(monkeypatch):
    install(monkeypatch, FakeResponse(200, {"accessToken": "jwt-value", "expiresIn": 900, "user": {"id": "u1"}}))
    response = client.post("/api/v1/identity/auth/token", json={"username": "a", "password": "b"}, headers=WEB)

    assert response.status_code == 200
    body = response.json()
    assert "accessToken" not in body and "access_token" not in body
    assert body["user"] == {"id": "u1"}
    cookie = set_cookie_header(response)[0]
    assert cookie.startswith(f"{SESSION_COOKIE_NAME}=jwt-value")
    lowered = cookie.lower()
    for attribute in ("httponly", "samesite=strict", "path=/", "max-age=900"):
        assert attribute in lowered
    assert "domain=" not in lowered
    assert response.headers["cache-control"] == "no-store"


def test_api_client_sign_in_keeps_existing_contract(monkeypatch):
    install(monkeypatch, FakeResponse(200, {"accessToken": "jwt-value", "user": {"id": "u1"}}))
    response = client.post("/api/v1/identity/auth/token", json={"username": "a", "password": "b"})

    assert response.json()["accessToken"] == "jwt-value"
    assert not set_cookie_header(response)


def test_cookie_becomes_bearer_and_never_reaches_upstream(monkeypatch):
    captured = install(monkeypatch)
    client.cookies.set(SESSION_COOKIE_NAME, "cookie-jwt")
    try:
        response = client.get("/api/v1/identity/auth/me", headers=WEB)
    finally:
        client.cookies.clear()

    assert response.status_code == 200
    forwarded = captured[0]["headers"]
    assert forwarded["authorization"] == "Bearer cookie-jwt"
    assert "cookie" not in forwarded
    assert "x-ssi-client" not in forwarded


def test_explicit_authorization_wins_over_cookie(monkeypatch):
    captured = install(monkeypatch)
    client.cookies.set(SESSION_COOKIE_NAME, "cookie-jwt")
    try:
        client.post("/api/v1/oid4vci/credential", json={}, headers={**WEB, "Authorization": "Bearer oid4vci-token"})
    finally:
        client.cookies.clear()

    assert captured[0]["headers"]["authorization"] == "Bearer oid4vci-token"


def test_cookie_without_custom_header_is_rejected(monkeypatch):
    captured = install(monkeypatch)
    client.cookies.set(SESSION_COOKIE_NAME, "cookie-jwt")
    try:
        response = client.post("/api/v1/identity/wallets", json={}, headers={"Origin": "http://127.0.0.1:5173"})
    finally:
        client.cookies.clear()

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_REJECTED"
    assert captured == []


def test_cookie_from_unlisted_origin_or_cross_site_is_rejected(monkeypatch):
    captured = install(monkeypatch)
    client.cookies.set(SESSION_COOKIE_NAME, "cookie-jwt")
    try:
        foreign = client.post("/api/v1/identity/wallets", json={}, headers={**WEB, "Origin": "https://attacker.example"})
        cross = client.post("/api/v1/identity/wallets", json={}, headers={**WEB, "Sec-Fetch-Site": "cross-site"})
    finally:
        client.cookies.clear()

    assert foreign.status_code == 403
    assert cross.status_code == 403
    assert captured == []


def test_sign_out_and_rejected_cookie_clear_the_session(monkeypatch):
    install(monkeypatch, FakeResponse(200, {"status": "SUCCESS"}))
    client.cookies.set(SESSION_COOKIE_NAME, "cookie-jwt")
    try:
        revoke = client.post("/api/v1/identity/auth/revoke", json={}, headers=WEB)
    finally:
        client.cookies.clear()
    assert any("max-age=0" in value.lower() for value in set_cookie_header(revoke))

    install(monkeypatch, FakeResponse(401, {"error": {"code": "ACCESS_TOKEN_EXPIRED"}}))
    client.cookies.set(SESSION_COOKIE_NAME, "expired-jwt")
    try:
        expired = client.get("/api/v1/identity/auth/me", headers=WEB)
    finally:
        client.cookies.clear()
    assert expired.status_code == 401
    assert any("max-age=0" in value.lower() for value in set_cookie_header(expired))


def test_unexpected_proxy_errors_do_not_echo_internal_details(monkeypatch):
    install(monkeypatch, error=RuntimeError("boom at http://user:secret@identity-service:8001/internal"))
    response = client.get("/api/v1/fraud/stats")

    assert response.status_code == 502
    text = response.text
    assert "identity-service" not in text and "secret" not in text and "boom" not in text


def test_cors_rejects_unlisted_localhost_ports():
    response = client.options(
        "/api/v1/identity/auth/me",
        headers={"Origin": "http://127.0.0.1:9999", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers.get("access-control-allow-origin") is None


def test_login_and_pin_endpoints_use_the_strict_rate_limit():
    for path in ("/api/v1/identity/auth/token", "/api/v1/oid4vci/token"):
        response = client.post(path, json={})
        assert response.headers.get("X-RateLimit-Limit") == "30", path


def test_dot_segment_paths_never_reach_upstream_services(monkeypatch):
    captured = install(monkeypatch)
    # Raw '../' is normalised by the test client itself; it is covered by the live curl --path-as-is check.
    for path in (
        "/api/v1/identity/..%2F..%2Finternal%2Fv1%2Frecovery%2Fkey-rotation",
        "/api/v1/identity/%2e%2e/%2e%2e/internal/v1/recovery/key-rotation",
        "/api/v1/fraud/..\stats",
    ):
        response = client.post(path, json={})
        assert response.status_code == 400, path
        assert response.json()["error"]["code"] == "PATH_REJECTED"
    assert captured == []


def test_encoded_identifiers_without_dot_segments_still_route(monkeypatch):
    captured = install(monkeypatch)
    response = client.get("/api/v1/identity/credentials/urn%3Auuid%3A1234/status")
    assert response.status_code == 200
    assert captured[0]["url"].endswith("/api/v1/credentials/urn:uuid:1234/status")
