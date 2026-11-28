"""WP-32: request_uri + signed request object, end to end through the API."""

from __future__ import annotations

import urllib.parse
from datetime import UTC, datetime

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from app.api.v1 import oid4vp as oid4vp_routes
from app.domain.request_object import RequestObjectSigner, verify_request_object
from app.main import app

client = TestClient(app)
PASSWORDS = {"holder": "Holder-Prototype-2026!", "verifier": "Verifier-Prototype-2026!"}


def _token(role: str) -> dict[str, str]:
    res = client.post(
        "/api/v1/auth/token",
        json={"username": f"{role}@example.test", "password": PASSWORDS[role]},
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['accessToken']}"}


def _new_request() -> dict:
    res = client.post(
        "/api/v1/oid4vp/requests",
        json={
            "purpose": "WP-32 request_uri check",
            "requestedCredentialTypes": ["UniversityAffiliationCredential"],
            "requestedFields": ["affiliation"],
        },
        headers=_token("verifier"),
    )
    assert res.status_code == 201, res.text
    return res.json()


def _params(link: str) -> dict[str, str]:
    return {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlsplit(link).query).items()}


def _resolve(link: str, role: str = "holder"):
    return client.post("/api/v1/oid4vp/wallet/resolve-request", json={"link": link}, headers=_token(role))


def test_the_link_holds_only_client_id_and_request_uri() -> None:
    data = _new_request()
    params = _params(data["deepLinkUri"])
    assert set(params) == {"client_id", "request_uri"}
    assert params["client_id"] == data["clientId"]
    assert params["client_id"].startswith("decentralized_identifier:did:jwk:")
    assert params["request_uri"].endswith(f"/api/v1/oid4vp/request-objects/{data['sessionId']}")
    assert data["nonce"] not in data["deepLinkUri"]


def test_the_request_object_is_public_signed_and_not_cached() -> None:
    data = _new_request()
    res = client.get(f"/api/v1/oid4vp/request-objects/{data['sessionId']}")  # no Authorization header
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/oauth-authz-req+jwt")
    assert res.headers["cache-control"] == "no-store"
    assert jwt.get_unverified_header(res.text)["typ"] == "oauth-authz-req+jwt"
    claims = verify_request_object(res.text, expected_client_id=data["clientId"], now=datetime.now(UTC))
    assert claims["state"] == data["sessionId"]
    assert claims["nonce"] == data["nonce"]
    assert claims["response_uri"] == data["responseUri"]
    # Only the request itself: no owner, holder or credential data.
    assert set(claims) == {
        "iss", "aud", "client_id", "response_type", "response_mode",
        "response_uri", "nonce", "state", "dcql_query", "iat", "exp",
    }


@pytest.mark.parametrize("handle", ["session_doesnotexistdoesnotexist", "not-a-handle", "..%2F..%2Fadmin"])
def test_unknown_or_malformed_handles_answer_404(handle) -> None:
    assert client.get(f"/api/v1/oid4vp/request-objects/{handle}").status_code == 404


def test_holder_resolves_the_link_to_the_same_request() -> None:
    data = _new_request()
    res = _resolve(data["deepLinkUri"])
    assert res.status_code == 200, res.text
    assert res.json() == {"sessionId": data["sessionId"], "clientId": data["clientId"]}


def test_only_a_signed_in_holder_can_resolve() -> None:
    data = _new_request()
    anonymous = client.post("/api/v1/oid4vp/wallet/resolve-request", json={"link": data["deepLinkUri"]})
    assert anonymous.status_code == 401
    assert _resolve(data["deepLinkUri"], role="verifier").status_code == 403


def test_a_link_naming_another_key_is_refused() -> None:
    data = _new_request()
    other = RequestObjectSigner(Ed25519PrivateKey.generate())
    params = _params(data["deepLinkUri"])
    link = "openid4vp://?" + urllib.parse.urlencode({"client_id": other.client_id, "request_uri": params["request_uri"]})
    res = _resolve(link)
    assert res.status_code == 422
    assert "KEY_MISMATCH" in res.text or "INVALID_SIGNATURE" in res.text


def test_a_valid_request_from_an_external_verifier_is_refused_after_verification(monkeypatch) -> None:
    external = RequestObjectSigner(Ed25519PrivateKey.generate())
    token = external.sign(
        response_uri="https://external-verifier.example/response",
        nonce="e" * 32,
        state="external-state-value",
        dcql_query={"credentials": [{"id": "c", "format": "ldp_vc"}]},
        session_expires_at=datetime.now(UTC).replace(microsecond=0) + __import__("datetime").timedelta(minutes=5),
        now=datetime.now(UTC),
    )
    fetched = []
    monkeypatch.setattr(oid4vp_routes, "fetch_request_object", lambda uri: fetched.append(uri) or token)
    link = "openid4vp://?" + urllib.parse.urlencode(
        {"client_id": external.client_id, "request_uri": "https://external-verifier.example/request/1"}
    )
    res = _resolve(link)
    assert fetched == ["https://external-verifier.example/request/1"]
    assert res.status_code == 422
    assert "EXTERNAL_VERIFIER_UNSUPPORTED" in res.text


@pytest.mark.parametrize(
    "request_uri",
    ["http://external-verifier.example/r", "https://127.0.0.1/r", "https://169.254.169.254/latest/meta-data"],
)
def test_unsafe_external_request_uris_are_refused_without_a_connection(request_uri) -> None:
    link = "openid4vp://?" + urllib.parse.urlencode({"client_id": "decentralized_identifier:did:jwk:x", "request_uri": request_uri})
    res = _resolve(link)
    assert res.status_code == 422
    assert any(code in res.text for code in ("INSECURE_REQUEST_URI", "BLOCKED_REQUEST_URI"))


def test_a_closed_request_is_gone() -> None:
    from tests.integration.test_wp07_wallet_consent_presentation_proof import _consent, _flow

    with TestClient(app) as wallet_client:
        flow = _flow(wallet_client)
        session = flow["session"]
        assert _consent(wallet_client, flow, action="REJECT").status_code == 200
        assert wallet_client.get(f"/api/v1/oid4vp/request-objects/{session['sessionId']}").status_code == 410
        resolved = wallet_client.post(
            "/api/v1/oid4vp/wallet/resolve-request",
            json={"link": session["deepLinkUri"]},
            headers=flow["holder_headers"] if "holder_headers" in flow else _token("holder"),
        )
        assert resolved.status_code in (404, 410)
