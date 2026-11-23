"""Signed OpenID4VP authorization requests (OpenID4VP 1.0 Final with RFC 9101 JAR).

The verifier publishes each request as a JWS at an HTTPS ``request_uri``. The
QR or link then carries only ``client_id`` and ``request_uri``.

Client identifier prefix: ``decentralized_identifier:`` with a ``did:jwk`` DID.
The DID carries the public key, so a wallet needs no network fetch to get it.
A did:jwk proves the request was signed by that key and not changed on the way;
it does not prove who runs the key. Trust in the verifier is a separate
decision (see ``RequestObjectTrust``).
"""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

REQUEST_OBJECT_TYP = "oauth-authz-req+jwt"
REQUEST_OBJECT_MEDIA_TYPE = "application/oauth-authz-req+jwt"
CLIENT_ID_PREFIX = "decentralized_identifier:"
# OpenID4VP 1.0 §5.8: static audience for a request object sent to a wallet.
WALLET_AUDIENCE = "https://self-issued.me/v2"
ALLOWED_ALGORITHMS = ("EdDSA",)
MAX_REQUEST_OBJECT_BYTES = 32_768
MAX_LIFETIME = timedelta(minutes=10)
CLOCK_SKEW = timedelta(seconds=60)


class RequestObjectError(ValueError):
    """A request object that must not be acted on. ``code`` is safe to show."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def did_jwk_for(public_key: Ed25519PublicKey) -> str:
    raw = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    jwk = {"crv": "Ed25519", "kty": "OKP", "x": _b64url(raw)}
    # did:jwk encodes the JWK as compact JSON with sorted members.
    encoded = json.dumps(jwk, separators=(",", ":"), sort_keys=True).encode()
    return f"did:jwk:{_b64url(encoded)}"


def public_key_from_did_jwk(did: str) -> Ed25519PublicKey:
    if not did.startswith("did:jwk:") or len(did) > 512:
        raise RequestObjectError("UNSUPPORTED_CLIENT_ID", "Only did:jwk verifier keys are supported.")
    try:
        jwk = json.loads(_b64url_decode(did[len("did:jwk:"):]))
    except (ValueError, json.JSONDecodeError) as error:
        raise RequestObjectError("INVALID_CLIENT_ID", "The verifier key cannot be read.") from error
    if not isinstance(jwk, dict) or "d" in jwk:
        raise RequestObjectError("INVALID_CLIENT_ID", "The verifier key is not a public key.")
    if jwk.get("kty") != "OKP" or jwk.get("crv") != "Ed25519" or not isinstance(jwk.get("x"), str):
        raise RequestObjectError("UNSUPPORTED_CLIENT_ID", "Only Ed25519 verifier keys are supported.")
    try:
        raw = _b64url_decode(jwk["x"])
    except ValueError as error:
        raise RequestObjectError("INVALID_CLIENT_ID", "The verifier key cannot be read.") from error
    if len(raw) != 32:
        raise RequestObjectError("INVALID_CLIENT_ID", "The verifier key has the wrong length.")
    return Ed25519PublicKey.from_public_bytes(raw)


def client_id_for(public_key: Ed25519PublicKey) -> str:
    return CLIENT_ID_PREFIX + did_jwk_for(public_key)


def did_from_client_id(client_id: str) -> str:
    if not client_id.startswith(CLIENT_ID_PREFIX):
        raise RequestObjectError(
            "UNSUPPORTED_CLIENT_ID",
            "Signed requests need a decentralized_identifier client_id.",
        )
    return client_id[len(CLIENT_ID_PREFIX):]


@dataclass(frozen=True)
class RequestObjectSigner:
    """The verifier's request-signing key."""

    private_key: Ed25519PrivateKey

    @property
    def client_id(self) -> str:
        return client_id_for(self.private_key.public_key())

    @property
    def did(self) -> str:
        return did_jwk_for(self.private_key.public_key())

    def sign(
        self,
        *,
        response_uri: str,
        nonce: str,
        state: str,
        dcql_query: Mapping[str, Any],
        session_expires_at: datetime,
        now: datetime,
    ) -> str:
        expires = min(session_expires_at, now + MAX_LIFETIME)
        claims = {
            "iss": self.client_id,
            "aud": WALLET_AUDIENCE,
            "client_id": self.client_id,
            "response_type": "vp_token",
            "response_mode": "direct_post",
            "response_uri": response_uri,
            "nonce": nonce,
            "state": state,
            "dcql_query": dict(dcql_query),
            "iat": int(now.timestamp()),
            "exp": int(expires.timestamp()),
        }
        headers = {"typ": REQUEST_OBJECT_TYP, "kid": f"{self.did}#0"}
        return jwt.encode(claims, self.private_key, algorithm="EdDSA", headers=headers)


def verify_request_object(
    token: str,
    *,
    expected_client_id: str,
    now: datetime,
) -> dict[str, Any]:
    """Check a request object the way a wallet must before showing it.

    The key comes only from ``expected_client_id`` (the value in the QR), so
    a request object cannot swap in another verifier's key.
    """
    if not isinstance(token, str) or not token or len(token) > MAX_REQUEST_OBJECT_BYTES:
        raise RequestObjectError("INVALID_REQUEST_OBJECT", "The request object is missing or too large.")
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as error:
        raise RequestObjectError("INVALID_REQUEST_OBJECT", "The request object is not a JWS.") from error
    if header.get("typ") != REQUEST_OBJECT_TYP:
        raise RequestObjectError("INVALID_TYP", "The request object has the wrong typ header.")
    if header.get("alg") not in ALLOWED_ALGORITHMS:
        raise RequestObjectError("UNSUPPORTED_ALG", "The request object uses an algorithm that is not accepted.")
    did = did_from_client_id(expected_client_id)
    kid = header.get("kid")
    if kid is not None and (not isinstance(kid, str) or kid.split("#", 1)[0] != did):
        raise RequestObjectError("KEY_MISMATCH", "The request object names a different key.")
    public_key = public_key_from_did_jwk(did)
    try:
        claims = jwt.decode(
            token,
            public_key,
            algorithms=list(ALLOWED_ALGORITHMS),
            audience=WALLET_AUDIENCE,
            # Time is checked below against the caller's clock, not PyJWT's.
            options={"require": ["exp", "iat", "aud"], "verify_iat": False, "verify_exp": False},
        )
    except jwt.InvalidAudienceError as error:
        raise RequestObjectError("INVALID_AUDIENCE", "The request is not addressed to a wallet.") from error
    except jwt.InvalidSignatureError as error:
        raise RequestObjectError("INVALID_SIGNATURE", "The request signature is not valid.") from error
    except jwt.PyJWTError as error:
        raise RequestObjectError("INVALID_REQUEST_OBJECT", "The request object is not valid.") from error

    iat, exp = claims.get("iat"), claims.get("exp")
    if not isinstance(iat, int) or not isinstance(exp, int):
        raise RequestObjectError("INVALID_REQUEST_OBJECT", "The request has no valid times.")
    if datetime.fromtimestamp(exp, tz=now.tzinfo) + CLOCK_SKEW <= now:
        raise RequestObjectError("EXPIRED", "The request has expired.")
    if datetime.fromtimestamp(iat, tz=now.tzinfo) > now + CLOCK_SKEW:
        raise RequestObjectError("INVALID_REQUEST_OBJECT", "The request was issued in the future.")
    if exp - iat > MAX_LIFETIME.total_seconds():
        raise RequestObjectError("INVALID_REQUEST_OBJECT", "The request lives longer than allowed.")
    if claims.get("client_id") != expected_client_id:
        raise RequestObjectError("CLIENT_ID_MISMATCH", "The request names a different client_id than the link.")
    if claims.get("response_type") != "vp_token":
        raise RequestObjectError("UNSUPPORTED_RESPONSE_TYPE", "Only vp_token requests are supported.")
    if claims.get("response_mode") != "direct_post":
        raise RequestObjectError("UNSUPPORTED_RESPONSE_MODE", "Only direct_post requests are supported.")
    for name in ("response_uri", "nonce", "state"):
        value = claims.get(name)
        if not isinstance(value, str) or not value or len(value) > 2048:
            raise RequestObjectError("MISSING_PARAMETER", f"The request has no valid {name}.")
    if not isinstance(claims.get("dcql_query"), dict):
        raise RequestObjectError("MISSING_PARAMETER", "The request has no dcql_query.")
    return claims
