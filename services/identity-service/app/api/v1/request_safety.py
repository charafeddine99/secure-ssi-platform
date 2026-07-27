import json
import re
from typing import Any
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.v1.error_handlers import build_error_response
from app.core.config import (
    MAX_AUTH_REQUEST_BYTES,
    MAX_CREDENTIAL_REQUEST_BYTES,
    MAX_JSON_DEPTH,
    MAX_PRESENTATION_REQUEST_BYTES,
    MAX_REVOCATION_REQUEST_BYTES,
)


_JSON_POST_LIMITS = {
    "/api/v1/credentials/validate": MAX_CREDENTIAL_REQUEST_BYTES,
    "/api/v1/credentials/sign": MAX_CREDENTIAL_REQUEST_BYTES,
    "/api/v1/credentials/verify": MAX_CREDENTIAL_REQUEST_BYTES,
    "/api/v1/auth/token": MAX_AUTH_REQUEST_BYTES,
    "/api/v1/presentations/create": MAX_PRESENTATION_REQUEST_BYTES,
    "/api/v1/presentations/verify": MAX_PRESENTATION_REQUEST_BYTES,
}
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_REVOCATION_PATH_PATTERN = re.compile(
    r"^/api/v1/credentials/[^/]+/revoke$"
)


class _DuplicateJsonProperty(ValueError):
    pass


def _reject_duplicate_properties(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateJsonProperty
        value[key] = item
    return value


def _reject_non_finite_number(value: str) -> None:
    raise ValueError("Non-finite JSON numbers are not allowed.")


def _json_depth(value: Any) -> int:
    maximum = 1
    stack = [(value, 1)]
    while stack:
        item, depth = stack.pop()
        maximum = max(maximum, depth)
        if depth > MAX_JSON_DEPTH:
            return depth
        if isinstance(item, dict):
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)
    return maximum


class JsonRequestSafetyMiddleware:
    """Enforces bounded, unambiguous JSON before request model parsing."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = self._request_id(scope)
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                if not any(
                    key.lower() == b"x-request-id" for key, _ in headers
                ):
                    headers.append(
                        (b"x-request-id", request_id.encode("ascii"))
                    )
                message["headers"] = headers
            await send(message)

        request_limit = _JSON_POST_LIMITS.get(scope["path"])
        if (
            request_limit is None
            and _REVOCATION_PATH_PATTERN.fullmatch(scope["path"])
        ):
            request_limit = MAX_REVOCATION_REQUEST_BYTES
        if scope["method"] != "POST" or request_limit is None:
            await self.app(scope, receive, send_with_request_id)
            return

        content_type = self._header(scope, b"content-type")
        if content_type is None or (
            content_type.decode("latin-1").split(";", 1)[0].strip().lower()
            != "application/json"
        ):
            await self._reject(
                scope,
                receive,
                send_with_request_id,
                request_id=request_id,
                status_code=400,
                code="JSON_CONTENT_TYPE_REQUIRED",
                message="JSON requests must use application/json.",
            )
            return

        content_length = self._header(scope, b"content-length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError:
                declared_length = -1
            if declared_length < 0:
                await self._reject(
                    scope,
                    receive,
                    send_with_request_id,
                    request_id=request_id,
                    status_code=400,
                    code="INVALID_CONTENT_LENGTH",
                    message="The Content-Length header is invalid.",
                )
                return
            if declared_length > request_limit:
                await self._reject(
                    scope,
                    receive,
                    send_with_request_id,
                    request_id=request_id,
                    status_code=413,
                    code="REQUEST_TOO_LARGE",
                    message="The request exceeds the configured size limit.",
                )
                return

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > request_limit:
                await self._reject(
                    scope,
                    receive,
                    send_with_request_id,
                    request_id=request_id,
                    status_code=413,
                    code="REQUEST_TOO_LARGE",
                    message="The request exceeds the configured size limit.",
                )
                return
            if not message.get("more_body", False):
                break

        try:
            parsed = json.loads(
                bytes(body).decode("utf-8"),
                object_pairs_hook=_reject_duplicate_properties,
                parse_constant=_reject_non_finite_number,
            )
        except _DuplicateJsonProperty:
            await self._reject(
                scope,
                receive,
                send_with_request_id,
                request_id=request_id,
                status_code=400,
                code="DUPLICATE_JSON_PROPERTY",
                message="Duplicate JSON properties are not allowed.",
            )
            return
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
            await self._reject(
                scope,
                receive,
                send_with_request_id,
                request_id=request_id,
                status_code=400,
                code="INVALID_JSON",
                message="The request body must be valid UTF-8 JSON.",
            )
            return

        if _json_depth(parsed) > MAX_JSON_DEPTH:
            await self._reject(
                scope,
                receive,
                send_with_request_id,
                request_id=request_id,
                status_code=400,
                code="JSON_TOO_DEEP",
                message="The request JSON exceeds the nesting limit.",
            )
            return

        delivered = False

        async def replay_body() -> Message:
            nonlocal delivered
            if delivered:
                return {"type": "http.request", "body": b"", "more_body": False}
            delivered = True
            return {
                "type": "http.request",
                "body": bytes(body),
                "more_body": False,
            }

        await self.app(scope, replay_body, send_with_request_id)

    @staticmethod
    def _header(scope: Scope, name: bytes) -> bytes | None:
        for key, value in scope.get("headers", []):
            if key.lower() == name:
                return value
        return None

    @classmethod
    def _request_id(cls, scope: Scope) -> str:
        value = cls._header(scope, b"x-request-id")
        if value is not None:
            candidate = value.decode("latin-1")
            if _REQUEST_ID_PATTERN.fullmatch(candidate):
                return candidate
        return uuid4().hex

    @staticmethod
    async def _reject(
        scope: Scope,
        receive: Receive,
        send: Send,
        *,
        request_id: str,
        status_code: int,
        code: str,
        message: str,
    ) -> None:
        response = build_error_response(
            request_id=request_id,
            status_code=status_code,
            code=code,
            message=message,
        )
        await response(scope, receive, send)
