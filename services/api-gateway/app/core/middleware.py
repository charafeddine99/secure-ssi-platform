import time
import uuid
from typing import Dict, Tuple
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


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Injects enterprise defensive HTTP security headers according to OWASP guidelines.
    """
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Sliding-window token bucket rate limiter to protect microservice APIs from DoS.
    Allows 180 requests per minute per IP address.
    """
    def __init__(self, app, max_requests: int = 180, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.clients: Dict[str, list] = {}

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "127.0.0.1"
        now = time.time()

        # Exclude health checks from rate limiting
        if request.url.path in ("/health", "/api/v1/system/status"):
            return await call_next(request)

        # Clean timestamps older than the sliding window
        timestamps = self.clients.get(client_ip, [])
        timestamps = [t for t in timestamps if now - t < self.window_seconds]
        
        if len(timestamps) >= self.max_requests:
            correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Rate limit of {self.max_requests} requests per minute exceeded.",
                        "correlation_id": correlation_id,
                        "retry_after": int(self.window_seconds - (now - timestamps[0]))
                    }
                },
                headers={"Retry-After": str(int(self.window_seconds - (now - timestamps[0])))}
            )

        timestamps.append(now)
        self.clients[client_ip] = timestamps
        return await call_next(request)
