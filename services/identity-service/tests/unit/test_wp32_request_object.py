"""WP-32: signed OpenID4VP requests (JAR) and the SSRF-safe request_uri fetcher."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.domain.request_object import (
    REQUEST_OBJECT_MEDIA_TYPE,
    WALLET_AUDIENCE,
    RequestObjectError,
    RequestObjectSigner,
    public_key_from_did_jwk,
    verify_request_object,
)
from app.infrastructure.clients.request_uri_fetcher import (
    check_request_uri,
    fetch_request_object,
    vetted_address,
)
from app.application.services.request_uri_resolver import parse_request_link

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
DCQL = {"credentials": [{"id": "c1", "format": "ldp_vc", "meta": {"type_values": ["X"]}}]}


def _signer() -> RequestObjectSigner:
    return RequestObjectSigner(Ed25519PrivateKey.generate())


def _token(signer: RequestObjectSigner, **overrides) -> str:
    return signer.sign(
        response_uri="https://verifier.example/api/v1/oid4vp/response",
        nonce="n" * 32,
        state="session_abcdefghijklmnop",
        dcql_query=DCQL,
        session_expires_at=overrides.pop("expires", NOW + timedelta(minutes=5)),
        now=overrides.pop("now", NOW),
    )


def _forge(signer: RequestObjectSigner, claims: dict, headers: dict | None = None) -> str:
    base = {"typ": "oauth-authz-req+jwt", "kid": f"{signer.did}#0"}
    return jwt.encode(claims, signer.private_key, algorithm="EdDSA", headers={**base, **(headers or {})})


def _claims(signer: RequestObjectSigner, **changes) -> dict:
    claims = jwt.decode(_token(signer), options={"verify_signature": False})
    claims.update(changes)
    return claims


# -- request object ----------------------------------------------------------


def test_a_signed_request_verifies_and_carries_every_parameter() -> None:
    signer = _signer()
    claims = verify_request_object(_token(signer), expected_client_id=signer.client_id, now=NOW)
    assert claims["client_id"] == signer.client_id
    assert claims["aud"] == WALLET_AUDIENCE
    assert claims["response_mode"] == "direct_post"
    assert claims["dcql_query"] == DCQL
    assert jwt.get_unverified_header(_token(signer))["typ"] == "oauth-authz-req+jwt"


def test_client_id_uses_the_decentralized_identifier_prefix_with_a_public_did_jwk() -> None:
    signer = _signer()
    assert signer.client_id.startswith("decentralized_identifier:did:jwk:")
    jwk = json.loads(base64.urlsafe_b64decode(signer.did[8:] + "=="))
    assert set(jwk) == {"crv", "kty", "x"}  # no private member


def test_lifetime_is_capped_by_the_session_and_ten_minutes() -> None:
    signer = _signer()
    short = jwt.decode(_token(signer, expires=NOW + timedelta(seconds=90)), options={"verify_signature": False})
    long = jwt.decode(_token(signer, expires=NOW + timedelta(hours=2)), options={"verify_signature": False})
    assert short["exp"] - short["iat"] == 90
    assert long["exp"] - long["iat"] == 600


def test_another_verifiers_key_cannot_sign_for_this_client_id() -> None:
    real, attacker = _signer(), _signer()
    with pytest.raises(RequestObjectError) as error:
        verify_request_object(_token(attacker), expected_client_id=real.client_id, now=NOW)
    assert error.value.code in {"KEY_MISMATCH", "INVALID_SIGNATURE"}


def test_a_tampered_payload_fails_the_signature() -> None:
    signer = _signer()
    header, payload, signature = _token(signer).split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=="))
    claims["nonce"] = "x" * 32
    forged_payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    with pytest.raises(RequestObjectError) as error:
        verify_request_object(f"{header}.{forged_payload}.{signature}", expected_client_id=signer.client_id, now=NOW)
    assert error.value.code == "INVALID_SIGNATURE"


def test_client_id_in_the_link_must_match_the_request_object() -> None:
    signer = _signer()
    token = _forge(signer, _claims(signer, client_id="decentralized_identifier:did:jwk:other"))
    with pytest.raises(RequestObjectError) as error:
        verify_request_object(token, expected_client_id=signer.client_id, now=NOW)
    assert error.value.code == "CLIENT_ID_MISMATCH"


@pytest.mark.parametrize(
    ("headers", "code"),
    [({"typ": "JWT"}, "INVALID_TYP"), ({"kid": "did:jwk:someoneelse#0"}, "KEY_MISMATCH")],
)
def test_wrong_header_is_refused(headers, code) -> None:
    signer = _signer()
    with pytest.raises(RequestObjectError) as error:
        verify_request_object(_forge(signer, _claims(signer), headers), expected_client_id=signer.client_id, now=NOW)
    assert error.value.code == code


def test_alg_none_is_refused() -> None:
    signer = _signer()
    token = jwt.encode(_claims(signer), key=None, algorithm="none", headers={"typ": "oauth-authz-req+jwt"})
    with pytest.raises(RequestObjectError) as error:
        verify_request_object(token, expected_client_id=signer.client_id, now=NOW)
    assert error.value.code == "UNSUPPORTED_ALG"


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"aud": "https://evil.example"}, "INVALID_AUDIENCE"),
        ({"response_mode": "fragment"}, "UNSUPPORTED_RESPONSE_MODE"),
        ({"response_type": "code"}, "UNSUPPORTED_RESPONSE_TYPE"),
        ({"nonce": ""}, "MISSING_PARAMETER"),
        ({"state": None}, "MISSING_PARAMETER"),
        ({"dcql_query": "x"}, "MISSING_PARAMETER"),
    ],
)
def test_invalid_parameters_are_refused(changes, code) -> None:
    signer = _signer()
    with pytest.raises(RequestObjectError) as error:
        verify_request_object(_forge(signer, _claims(signer, **changes)), expected_client_id=signer.client_id, now=NOW)
    assert error.value.code == code


def test_an_expired_request_is_refused() -> None:
    signer = _signer()
    token = _token(signer, expires=NOW + timedelta(seconds=30))
    with pytest.raises(RequestObjectError) as error:
        verify_request_object(token, expected_client_id=signer.client_id, now=NOW + timedelta(minutes=5))
    assert error.value.code == "EXPIRED"


def test_a_request_from_the_future_is_refused() -> None:
    signer = _signer()
    token = _token(signer, now=NOW + timedelta(hours=1), expires=NOW + timedelta(hours=2))
    with pytest.raises(RequestObjectError):
        verify_request_object(token, expected_client_id=signer.client_id, now=NOW)


def test_a_did_jwk_holding_a_private_key_is_refused() -> None:
    jwk = {"kty": "OKP", "crv": "Ed25519", "x": "A" * 43, "d": "B" * 43}
    did = "did:jwk:" + base64.urlsafe_b64encode(json.dumps(jwk).encode()).rstrip(b"=").decode()
    with pytest.raises(RequestObjectError):
        public_key_from_did_jwk(did)


def test_a_url_client_id_cannot_be_used_for_a_signed_request() -> None:
    signer = _signer()
    with pytest.raises(RequestObjectError) as error:
        verify_request_object(_token(signer), expected_client_id="https://verifier.example", now=NOW)
    assert error.value.code == "UNSUPPORTED_CLIENT_ID"


# -- link parsing --------------------------------------------------------------


def test_link_parsing_needs_client_id_and_request_uri_only() -> None:
    assert parse_request_link("openid4vp://?client_id=a&request_uri=https%3A%2F%2Fv.example%2Fr") == ("a", "https://v.example/r")


@pytest.mark.parametrize(
    "link",
    [
        "https://v.example/?client_id=a&request_uri=b",
        "openid4vp://?client_id=a",
        "openid4vp://?client_id=a&request_uri=b&request=c",
        "openid4vp://?client_id=a&client_id=b&request_uri=c",
        "openid4vp://?client_id=a&request_uri=b&request_uri_method=post",
        "openid4vp://?" + "x" * 5000,
    ],
)
def test_bad_links_are_refused(link) -> None:
    with pytest.raises(RequestObjectError):
        parse_request_link(link)


# -- SSRF-safe fetcher -----------------------------------------------------------


@pytest.mark.parametrize(
    "uri",
    [
        "http://verifier.example/r",
        "file:///etc/passwd",
        "https://user:pw@verifier.example/r",
        "https://verifier.example:8443/r",
        "https://127.0.0.1/r",
        "https://[::1]/r",
        "https://169.254.169.254/latest/meta-data",
        "https://verifier.example/r#frag",
        "https://verifier.example/" + "a" * 3000,
    ],
)
def test_unsafe_request_uris_are_refused_before_any_connection(uri) -> None:
    with pytest.raises(RequestObjectError):
        check_request_uri(uri)


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.5", "192.168.1.2", "169.254.169.254", "::1", "fd00::1", "0.0.0.0"])
def test_hosts_that_resolve_to_private_addresses_are_blocked(address) -> None:
    with pytest.raises(RequestObjectError) as error:
        vetted_address("rebind.example", resolver=lambda _host: [address])
    assert error.value.code == "BLOCKED_REQUEST_URI"


def test_one_private_address_among_public_ones_blocks_the_host() -> None:
    with pytest.raises(RequestObjectError):
        vetted_address("mixed.example", resolver=lambda _host: ["93.184.216.34", "10.1.1.1"])


def _fetch(handler) -> str:
    return fetch_request_object(
        "https://verifier.example/request/1",
        resolver=lambda _host: ["93.184.216.34"],
        transport=httpx.MockTransport(handler),
    )


def test_fetch_is_pinned_to_the_vetted_address_and_sends_the_host_header() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["host"] = str(request.url), request.headers["host"]
        return httpx.Response(200, headers={"content-type": REQUEST_OBJECT_MEDIA_TYPE}, content=b"a.b.c")

    assert _fetch(handler) == "a.b.c"
    assert seen["url"].startswith("https://93.184.216.34/") and seen["host"] == "verifier.example"


@pytest.mark.parametrize(
    ("response", "code"),
    [
        (httpx.Response(302, headers={"location": "http://169.254.169.254/"}), "REDIRECT_REFUSED"),
        (httpx.Response(404), "REQUEST_NOT_FOUND"),
        (httpx.Response(410), "REQUEST_NOT_FOUND"),
        (httpx.Response(500), "REQUEST_URI_FAILED"),
        (httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html>"), "WRONG_CONTENT_TYPE"),
        (httpx.Response(200, headers={"content-type": REQUEST_OBJECT_MEDIA_TYPE}, content=b"a" * 40_000), "REQUEST_TOO_LARGE"),
    ],
)
def test_bad_responses_are_refused(response, code) -> None:
    with pytest.raises(RequestObjectError) as error:
        _fetch(lambda _request: response)
    assert error.value.code == code


def test_a_timeout_is_reported_as_such() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(RequestObjectError) as error:
        _fetch(handler)
    assert error.value.code == "REQUEST_URI_TIMEOUT"


# -- signing key settings ----------------------------------------------------------


def test_production_like_environment_requires_a_signing_key() -> None:
    from app.config.request_object_settings import load_request_object_signer
    from app.domain.persistence import PersistenceConfigurationError

    with pytest.raises(PersistenceConfigurationError):
        load_request_object_signer({"IDENTITY_ENVIRONMENT": "production"})


def test_a_configured_key_is_stable_and_a_bad_one_is_refused() -> None:
    from app.config.request_object_settings import load_request_object_signer
    from app.domain.persistence import PersistenceConfigurationError

    seed = base64.urlsafe_b64encode(bytes(range(32))).rstrip(b"=").decode()
    first = load_request_object_signer({"OID4VP_REQUEST_SIGNING_KEY": seed, "IDENTITY_ENVIRONMENT": "production"})
    second = load_request_object_signer({"OID4VP_REQUEST_SIGNING_KEY": seed})
    assert first.client_id == second.client_id
    with pytest.raises(PersistenceConfigurationError):
        load_request_object_signer({"OID4VP_REQUEST_SIGNING_KEY": "c2hvcnQ"})
