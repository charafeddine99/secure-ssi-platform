"""Browser session cookie for the web app (OWASP Session Management / CSRF cheat sheets).

The web app never stores the access token in JavaScript-readable storage.
When a request carries ``X-SSI-Client: web`` the gateway:

- moves the token from a successful sign-in response into an HttpOnly,
  SameSite=Strict cookie (``__Host-`` prefixed when Secure) and removes it
  from the JSON body;
- turns that cookie back into an ``Authorization`` header for upstream
  services, only when the request has no explicit ``Authorization`` header;
- clears the cookie on sign-out and when an upstream service rejects it.

CSRF defence for cookie-authenticated requests (defence in depth): the custom
``X-SSI-Client`` header (forces a CORS preflight), an allowlisted ``Origin``
when one is sent, and ``Sec-Fetch-Site`` must not be ``cross-site``.
API clients that send their own Bearer token are unaffected.
"""

import os
from collections.abc import Iterable

from fastapi import Request, Response

CLIENT_HEADER = "x-ssi-client"
CLIENT_HEADER_VALUE = "web"
DEFAULT_MAX_AGE_SECONDS = 900
MAX_COOKIE_AGE_SECONDS = 86_400

_raw_secure = os.getenv("GATEWAY_SESSION_COOKIE_SECURE", "true").strip().lower()
if _raw_secure not in {"true", "false"}:
    raise RuntimeError("GATEWAY_SESSION_COOKIE_SECURE must be true or false.")
SESSION_COOKIE_SECURE = _raw_secure == "true"
# The __Host- prefix requires Secure, Path=/ and no Domain attribute.
SESSION_COOKIE_NAME = "__Host-ssi_session" if SESSION_COOKIE_SECURE else "ssi_session"


def is_web_client(request: Request) -> bool:
    return request.headers.get(CLIENT_HEADER, "").strip().lower() == CLIENT_HEADER_VALUE


def session_token(request: Request) -> str | None:
    token = request.cookies.get(SESSION_COOKIE_NAME, "").strip()
    return token or None


def csrf_rejection(request: Request, allowed_origins: Iterable[str]) -> str | None:
    """Return a reason when a cookie-authenticated request fails the CSRF checks."""
    if not is_web_client(request):
        return "The session cookie is accepted only with the X-SSI-Client header."
    origin = request.headers.get("origin")
    if origin is not None and origin not in set(allowed_origins):
        return "The request origin is not allowed to use the session cookie."
    if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
        return "Cross-site requests cannot use the session cookie."
    return None


def set_session_cookie(response: Response, token: str, max_age: object) -> None:
    age = max_age if isinstance(max_age, int) and not isinstance(max_age, bool) and max_age > 0 else DEFAULT_MAX_AGE_SECONDS
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=min(age, MAX_COOKIE_AGE_SECONDS),
        path="/",
        secure=SESSION_COOKIE_SECURE,
        httponly=True,
        samesite="strict",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        secure=SESSION_COOKIE_SECURE,
        httponly=True,
        samesite="strict",
    )
