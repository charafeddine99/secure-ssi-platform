"""Gateway security telemetry.

The gateway has no database, so this buffer is bounded and in memory: a restart
loses what is queued, and an overflow is counted and reported as `dropped`.
Requests are reported as per-minute counts, which give rates their denominator.
"""

import asyncio
import hashlib
import hmac
import logging
import os
import socket
import time
import uuid
from collections import Counter, deque
from datetime import UTC, datetime
from typing import Any

import httpx
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

MAX_QUEUE = 2000
FLUSH_SECONDS = 5.0
BATCH_SIZE = 200
_ROUTE_GROUPS = (
    ("/api/v1/identity/auth/token", "login"),
    ("/api/v1/auth/login", "login"),
    ("/api/v1/identity/auth/login", "login"),
    ("/api/v1/oid4vci/token", "oid4vci_token"),
    ("/api/v1/oid4vci/credential", "oid4vci_credential"),
    ("/api/v1/oid4vci", "oid4vci"),
    ("/api/v1/oid4vp", "oid4vp"),
    ("/api/v1/recovery", "recovery"),
    ("/api/v1/guardians", "recovery"),
    ("/api/v1/fraud", "fraud"),
    ("/api/v1/identity", "identity"),
)


_proxy_cache: tuple[float, str | None] = (0.0, None)


def _trusted_proxy_address() -> str | None:
    """Resolved, not hard-coded: a container's address changes when it is recreated."""
    global _proxy_cache
    host = os.getenv("GATEWAY_TRUSTED_PROXY_HOST", "")
    if not host:
        return None
    expires, address = _proxy_cache
    if time.time() >= expires:
        try:
            address = socket.gethostbyname(host)
        except OSError:
            address = None
        _proxy_cache = (time.time() + 30, address)
    return address


def client_address(request: Any) -> str:
    """X-Real-IP counts only from the configured proxy; anyone else could forge it."""
    peer = request.client.host if request.client else "unknown"
    if peer == _trusted_proxy_address():
        return request.headers.get("x-real-ip", peer)
    return peer


def route_group(path: str) -> str:
    return next((group for prefix, group in _ROUTE_GROUPS if path.startswith(prefix)), "other")


def classify(group: str, status_code: int) -> str | None:
    if status_code == 429:
        return "api.rate_limited"
    if status_code == 401:
        return "gateway.login.rejected" if group == "login" else "auth.session.rejected"
    if status_code == 403:
        return "authz.denied"
    if 400 <= status_code < 500 and status_code != 404:
        return {
            "oid4vci_token": "oid4vci.token.failure",
            "oid4vci_credential": "oid4vci.credential.failure",
            "oid4vp": "oid4vp.request.failure",
        }.get(group)
    return None


class TelemetryBuffer:
    def __init__(self, *, url: str, token: str, key: bytes, origin: str, environment: str, client: httpx.AsyncClient | None = None) -> None:
        self._url = f"{url.rstrip('/')}/api/v1/fraud/intel/ingest"
        self._token = token
        self._key = key
        self._origin = origin
        self._environment = environment
        self._client = client
        self._queue: deque[dict[str, Any]] = deque()
        self._minute: Counter[tuple[int, str]] = Counter()
        self._task: asyncio.Task[None] | None = None
        self.instance = uuid.uuid4().hex[:12]
        self.dropped = 0
        self.failures = 0

    def _source_ref(self, client_ip: str) -> str:
        digest = hmac.new(self._key, client_ip.encode(), hashlib.sha256).hexdigest()
        return f"src:{digest[:40]}"

    def _enqueue(self, event: dict[str, Any]) -> None:
        if len(self._queue) >= MAX_QUEUE:
            self.dropped += 1
            return
        self._queue.append(event)

    def _event(self, event_id: str, event_type: str, occurred: datetime, **fields: Any) -> dict[str, Any]:
        return {
            "event_id": event_id,
            "occurred_at": occurred.isoformat(),
            "source_service": "api-gateway",
            "source_component": "telemetry-middleware",
            "event_type": event_type,
            "origin": self._origin,
            **fields,
        }

    def record(self, path: str, status_code: int, client_ip: str) -> None:
        group = route_group(path)
        self._minute[(int(time.time() // 60), group)] += 1
        event_type = classify(group, status_code)
        if event_type:
            self._enqueue(self._event(
                f"gw:{self.instance}:{uuid.uuid4().hex}",
                event_type,
                datetime.now(UTC),
                source_ref=self._source_ref(client_ip),
                attributes={"route_group": group, "http_status": str(status_code)},
            ))

    def _roll_minutes(self, *, everything: bool = False) -> None:
        current = int(time.time() // 60)
        for (minute, group), count in list(self._minute.items()):
            if everything or minute < current:
                del self._minute[(minute, group)]
                self._enqueue(self._event(
                    f"gw:{self.instance}:{minute}:{group}",
                    "api.request",
                    datetime.fromtimestamp(minute * 60, UTC),
                    count=count,
                    attributes={"route_group": group},
                ))

    async def flush(self) -> None:
        self._roll_minutes()
        events = [self._queue.popleft() for _ in range(min(BATCH_SIZE, len(self._queue)))]
        client = self._client or httpx.AsyncClient(timeout=5.0)
        try:
            response = await client.post(
                self._url,
                headers={"X-Internal-Service-Token": self._token},
                json={
                    "source": "api-gateway",
                    "environment": self._environment,
                    "stats": {"backlog": len(self._queue), "dropped": self.dropped, "delivery_failures": self.failures},
                    "events": events,
                },
            )
            response.raise_for_status()
        except Exception as error:
            self.failures += 1
            self._queue.extendleft(reversed(events))
            while len(self._queue) > MAX_QUEUE:
                self._queue.pop()
                self.dropped += 1
            logger.warning("Gateway telemetry delivery failed (%s)", type(error).__name__)
        finally:
            if self._client is None:
                await client.aclose()

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(FLUSH_SECONDS)
            await self.flush()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop(), name="gateway-telemetry")


def build_buffer() -> TelemetryBuffer | None:
    token = os.getenv("FRAUD_INTERNAL_SERVICE_TOKEN", "")
    key = os.getenv("SECURITY_EVENT_PSEUDONYM_KEY", "")
    if len(token) < 32 or len(key) < 32:
        return None
    return TelemetryBuffer(
        url=os.getenv("FRAUD_SERVICE_URL", "http://fraud-service:8000"),
        token=token,
        key=key.encode(),
        origin=os.getenv("SECURITY_EVENT_ORIGIN", "OPERATIONAL"),
        environment=os.getenv("GATEWAY_ENVIRONMENT", "development"),
    )


class SecurityTelemetryMiddleware(BaseHTTPMiddleware):
    """Outermost, so it also sees requests the rate limiter refuses."""

    def __init__(self, app: Any, buffer: TelemetryBuffer | None = None) -> None:
        super().__init__(app)
        self.buffer = buffer if buffer is not None else build_buffer()

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path
        if self.buffer is not None and path.startswith("/api/"):
            self.buffer.start()
            self.buffer.record(path, response.status_code, client_address(request))
        return response
