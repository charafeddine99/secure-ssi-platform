"""Audit 2026-11-21: request_uri must not carry the internal Docker hostname.

Without IDENTITY_PUBLIC_ORIGIN, OID4VP links are built from the address the caller
used, which the gateway passes as X-Forwarded-Host/-Proto.
"""

from starlette.requests import Request

from app.api.v1 import oid4vp
from app.config.public_origin_settings import PublicOriginSettings


def _request(headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "scheme": "http",
        "server": ("identity-service", 8000),
        "path": "/api/v1/oid4vp/requests",
        "root_path": "",
        "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    return Request(scope)


def test_without_public_origin_the_caller_address_is_used(monkeypatch) -> None:
    monkeypatch.setattr(oid4vp, "_PUBLIC_ORIGIN", PublicOriginSettings())
    request = _request({"x-forwarded-host": "localhost:3000", "x-forwarded-proto": "http"})
    assert oid4vp._origin(request) == "http://localhost:3000"


def test_configured_public_origin_always_wins(monkeypatch) -> None:
    monkeypatch.setattr(oid4vp, "_PUBLIC_ORIGIN", PublicOriginSettings(origin="https://wallet.example.test"))
    request = _request({"x-forwarded-host": "other.example", "x-forwarded-proto": "http"})
    assert oid4vp._origin(request) == "https://wallet.example.test"


def test_malformed_forwarded_values_fall_back_to_the_service_address(monkeypatch) -> None:
    monkeypatch.setattr(oid4vp, "_PUBLIC_ORIGIN", PublicOriginSettings())
    for headers in (
        {"x-forwarded-host": "evil.example/path", "x-forwarded-proto": "http"},
        {"x-forwarded-host": "user@evil.example", "x-forwarded-proto": "http"},
        {"x-forwarded-host": "wallet.example", "x-forwarded-proto": "javascript"},
        {},
    ):
        assert oid4vp._origin(_request(headers)) == "http://identity-service:8000"
