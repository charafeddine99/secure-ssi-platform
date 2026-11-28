"""Fetch a verifier's request object from a ``request_uri`` without SSRF.

The URI comes from a scanned QR, so it is attacker-controlled input:

- HTTPS only, default port only, no user info, no fragment, at most 2048 chars;
- the host is resolved once and every address must be globally routable
  (no loopback, private, link-local, reserved, multicast); the connection is
  pinned to that vetted address so DNS rebinding cannot swap it, while TLS is
  still checked against the original host name (SNI);
- redirects are not followed;
- 3 s connect / 5 s read timeouts, 32 KiB body limit;
- the response must be ``application/oauth-authz-req+jwt``.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from urllib.parse import urlsplit

import httpx

from app.domain.request_object import (
    MAX_REQUEST_OBJECT_BYTES,
    REQUEST_OBJECT_MEDIA_TYPE,
    RequestObjectError,
)

MAX_REQUEST_URI_LENGTH = 2048
Resolver = Callable[[str], list[str]]


def _system_resolver(host: str) -> list[str]:
    infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    return sorted({info[4][0] for info in infos})


def check_request_uri(uri: str) -> tuple[str, str]:
    """Return (host, path_and_query) for an acceptable URI, or raise."""
    if not isinstance(uri, str) or not uri or len(uri) > MAX_REQUEST_URI_LENGTH:
        raise RequestObjectError("INVALID_REQUEST_URI", "The request_uri is missing or too long.")
    try:
        parts = urlsplit(uri)
        port = parts.port
    except ValueError as error:
        raise RequestObjectError("INVALID_REQUEST_URI", "The request_uri is not a valid URL.") from error
    if parts.scheme != "https":
        raise RequestObjectError("INSECURE_REQUEST_URI", "The request_uri must use HTTPS.")
    if parts.username or parts.password or parts.fragment or not parts.hostname:
        raise RequestObjectError("INVALID_REQUEST_URI", "The request_uri is not a plain HTTPS URL.")
    if port not in (None, 443):
        raise RequestObjectError("INVALID_REQUEST_URI", "The request_uri must use the default HTTPS port.")
    host = parts.hostname.lower()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise RequestObjectError("BLOCKED_REQUEST_URI", "The request_uri must name a host, not an address.")
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    return host, path


def vetted_address(host: str, resolver: Resolver = _system_resolver) -> str:
    try:
        addresses = resolver(host)
    except OSError as error:
        raise RequestObjectError("UNREACHABLE_REQUEST_URI", "The request_uri host cannot be resolved.") from error
    if not addresses:
        raise RequestObjectError("UNREACHABLE_REQUEST_URI", "The request_uri host cannot be resolved.")
    for address in addresses:
        if not ipaddress.ip_address(address.split("%", 1)[0]).is_global:
            raise RequestObjectError("BLOCKED_REQUEST_URI", "The request_uri points to a private network.")
    return addresses[0]


def fetch_request_object(
    uri: str,
    *,
    resolver: Resolver = _system_resolver,
    transport: httpx.BaseTransport | None = None,
) -> str:
    host, path = check_request_uri(uri)
    address = vetted_address(host, resolver)
    literal = f"[{address}]" if ":" in address else address
    timeout = httpx.Timeout(5.0, connect=3.0)
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False, transport=transport) as client:
            with client.stream(
                "GET",
                f"https://{literal}{path}",
                headers={"Host": host, "Accept": REQUEST_OBJECT_MEDIA_TYPE},
                extensions={"sni_hostname": host},
            ) as response:
                if 300 <= response.status_code < 400:
                    raise RequestObjectError("REDIRECT_REFUSED", "The request_uri redirected; redirects are not followed.")
                if response.status_code in (404, 410):
                    raise RequestObjectError("REQUEST_NOT_FOUND", "The verifier no longer has this request.")
                if response.status_code != 200:
                    raise RequestObjectError("REQUEST_URI_FAILED", "The verifier could not return the request.")
                media = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                if media != REQUEST_OBJECT_MEDIA_TYPE:
                    raise RequestObjectError("WRONG_CONTENT_TYPE", "The request_uri did not return a request object.")
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_REQUEST_OBJECT_BYTES:
                        raise RequestObjectError("REQUEST_TOO_LARGE", "The request object is too large.")
    except httpx.TimeoutException as error:
        raise RequestObjectError("REQUEST_URI_TIMEOUT", "The verifier did not answer in time.") from error
    except httpx.RequestError as error:
        raise RequestObjectError("UNREACHABLE_REQUEST_URI", "The verifier could not be reached.") from error
    try:
        return body.decode("ascii").strip()
    except UnicodeDecodeError as error:
        raise RequestObjectError("INVALID_REQUEST_OBJECT", "The request object is not a compact JWS.") from error
