import time
import uuid
from collections import OrderedDict
from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Assigns or preserves a unique X-Correlation-ID header across requests
    for distributed request tracing and telemetry.
    """
    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("x-correlation-id") or str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        response: Response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response


class PathSafetyMiddleware(BaseHTTPMiddleware):
    """
    Rejects dot-segment and backslash paths before routing (OWASP API8/API9:2023).

    Proxy routes build upstream URLs from the path; an un-normalised '..' (raw or
    %2e/%2f-encoded, which Starlette decodes) would otherwise escape the
    /api/v1/<service>/ prefix and reach internal service routes.
    """
    async def dispatch(self, request: Request, call_next):
        path = request.scope.get("path", "")
        segments = path.split("/")
        if "\\" in path or any(segment in (".", "..") for segment in segments):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": {"code": "PATH_REJECTED", "message": "The request path is not allowed."}},
            )
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Injects enterprise defensive HTTP security headers according to OWASP guidelines.
    """
    def __init__(self, app, *, hsts_enabled: bool = False):
        super().__init__(app)
        self.hsts_enabled = hsts_enabled

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self';"
        # HSTS is an operator opt-in: only enable it when a verified HTTPS
        # reverse-proxy boundary serves the public application. Do not emit
        # preload/includeSubDomains policy for localhost or unknown domains.
        if self.hsts_enabled:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Sliding-window rate limiter to protect microservice APIs from DoS
    and brute-force credential stuffing.
    - Standard endpoints: 180 requests per minute.
    - Sensitive endpoints (auth, credentials, recovery): 30 requests per minute.
    """
    def __init__(
        self,
        app,
        max_requests: int = 180,
        window_seconds: int = 60,
        sensitive_requests: int = 30,
        max_clients: int = 10_000,
    ):
        super().__init__(app)
        if max_clients < 1:
            raise ValueError("max_clients must be greater than zero")
        self.max_requests = max_requests
        self.sensitive_requests = sensitive_requests
        self.window_seconds = window_seconds
        self.max_clients = max_clients
        self.clients: OrderedDict[str, list[float]] = OrderedDict()

    def _is_sensitive_path(self, path: str) -> bool:
        sensitive_prefixes = (
            "/api/v1/auth/login",
            "/api/v1/identity/auth/login",
            "/api/v1/identity/auth/token",
            "/api/v1/oid4vci/token",
            "/api/v1/oid4vci/credential",
            "/api/v1/identity/credentials/sign",
            "/api/v1/recovery/request",
            "/api/v1/fraud/quarantine",
        )
        return any(path.startswith(prefix) for prefix in sensitive_prefixes)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "127.0.0.1"
        now = time.time()
        path = request.url.path

        # Exclude health and root discovery from rate limiting
        if path in ("/health", "/api/v1/system/status", "/docs", "/openapi.json"):
            return await call_next(request)

        is_sensitive = self._is_sensitive_path(path)
        effective_limit = self.sensitive_requests if is_sensitive else self.max_requests
        rate_key = f"{client_ip}:{'sensitive' if is_sensitive else 'standard'}"

        if rate_key not in self.clients and len(self.clients) >= self.max_clients:
            # Bound per-process memory even if requests arrive with many client IPs.
            self.clients.popitem(last=False)

        # Clean timestamps older than the sliding window
        timestamps = self.clients.get(rate_key, [])
        timestamps = [t for t in timestamps if now - t < self.window_seconds]

        reset_time = int(timestamps[0] + self.window_seconds) if timestamps else int(now + self.window_seconds)
        remaining = max(0, effective_limit - len(timestamps))

        if len(timestamps) >= effective_limit:
            correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
            retry_after = int(self.window_seconds - (now - timestamps[0]))
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Rate limit of {effective_limit} requests per minute exceeded for this endpoint tier.",
                        "correlation_id": correlation_id,
                        "retry_after": retry_after
                    }
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(effective_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                }
            )

        timestamps.append(now)
        self.clients[rate_key] = timestamps
        self.clients.move_to_end(rate_key)

        response: Response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(effective_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining - 1 if remaining > 0 else 0)
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        return response
