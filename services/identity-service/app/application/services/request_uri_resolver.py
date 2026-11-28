"""Wallet side of OpenID4VP ``request_uri``: turn a scanned link into a request.

Order of checks, all before anything is shown to the holder:

1. The link is ``openid4vp://`` with ``client_id`` and ``request_uri`` and no
   by-value ``request``; ``request_uri_method=post`` is not supported.
2. The request object is read. A ``request_uri`` on this platform's own origin
   is built locally (no network call). Any other one goes through the
   SSRF-safe fetcher.
3. The JWS is verified against the key in ``client_id`` (typ, alg, signature,
   aud, exp, client_id match, response mode).
4. Only requests from this platform's verifier key, for an open session with
   the same nonce and response_uri, are opened. A valid request from another
   verifier is refused with a clear message: this wallet cannot yet post to an
   external ``response_uri``.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit

from app.domain.oid4vp import VerificationSessionStatus
from app.domain.request_object import RequestObjectError, verify_request_object

REQUEST_OBJECT_PATH = re.compile(r"^/api/v1/oid4vp/request-objects/(session_[A-Za-z0-9_-]{8,128})$")
MAX_LINK_LENGTH = 4096


@dataclass(frozen=True)
class ResolvedRequest:
    session_id: str
    client_id: str


def request_uri_for(origin: str, session_id: str) -> str:
    return f"{origin.rstrip('/')}/api/v1/oid4vp/request-objects/{session_id}"


def parse_request_link(link: str) -> tuple[str, str]:
    """Return (client_id, request_uri) from an ``openid4vp://`` link."""
    if not isinstance(link, str) or not link.strip() or len(link) > MAX_LINK_LENGTH:
        raise RequestObjectError("INVALID_LINK", "The link is missing or too long.")
    parts = urlsplit(link.strip())
    if parts.scheme != "openid4vp":
        raise RequestObjectError("INVALID_LINK", "Expected an openid4vp:// request link.")
    params = parse_qs(parts.query, keep_blank_values=True)
    if any(len(values) != 1 for values in params.values()):
        raise RequestObjectError("INVALID_LINK", "A request parameter appears more than once.")
    if "request" in params:
        raise RequestObjectError("INVALID_LINK", "Send either request or request_uri, not both.")
    method = params.get("request_uri_method", ["get"])[0].lower()
    if method != "get":
        raise RequestObjectError("UNSUPPORTED_METHOD", "Only request_uri_method=get is supported.")
    client_id = params.get("client_id", [""])[0]
    request_uri = params.get("request_uri", [""])[0]
    if not client_id or not request_uri:
        raise RequestObjectError("INVALID_LINK", "The link needs client_id and request_uri.")
    return client_id, request_uri


class RequestUriResolver:
    def __init__(
        self,
        *,
        oid4vp_service,
        signer,
        own_origins: Iterable[str],
        fetch: Callable[[str], str],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._service = oid4vp_service
        self._signer = signer
        self._own_origins = {origin.rstrip("/").lower() for origin in own_origins if origin}
        self._fetch = fetch
        self._clock = clock

    def _own_session(self, request_uri: str) -> str | None:
        parts = urlsplit(request_uri)
        origin = f"{parts.scheme}://{parts.netloc}".lower()
        match = REQUEST_OBJECT_PATH.fullmatch(parts.path or "")
        if origin in self._own_origins and match and not parts.query and not parts.fragment:
            return match.group(1)
        return None

    def resolve(self, link: str) -> ResolvedRequest:
        client_id, request_uri = parse_request_link(link)
        local_session = self._own_session(request_uri)
        if local_session is not None:
            token = self._service.request_object(local_session)
        else:
            token = self._fetch(request_uri)
        claims = verify_request_object(token, expected_client_id=client_id, now=self._clock())

        if self._signer is None or client_id != self._signer.client_id:
            raise RequestObjectError(
                "EXTERNAL_VERIFIER_UNSUPPORTED",
                "This request is signed by a verifier outside this platform. "
                "This wallet can only answer verifiers on this platform.",
            )
        session = self._service.get_session(claims["state"])
        if (
            session.status != VerificationSessionStatus.PENDING
            or session.client_id != client_id
            or session.nonce != claims["nonce"]
            or session.response_uri != claims["response_uri"]
        ):
            raise RequestObjectError("REQUEST_NOT_FOUND", "This request is no longer open.")
        return ResolvedRequest(session_id=session.session_id, client_id=client_id)
