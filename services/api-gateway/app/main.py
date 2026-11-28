from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.health import router as health_router
from app.api.routes.proxy import router as proxy_router
from app.core.telemetry import SecurityTelemetryMiddleware
from app.core.config import APP_VERSION, SERVICE_NAME, CORS_ORIGINS, HSTS_ENABLED
from app.core.middleware import (
    CorrelationIdMiddleware,
    PathSafetyMiddleware,
    SecurityHeadersMiddleware,
    RateLimiterMiddleware
)

app = FastAPI(
    title=SERVICE_NAME,
    version=APP_VERSION,
    description="Secure SSI Platform - Enterprise API Gateway, Reverse-Proxy & Security Layer"
)

# 1. Defensive Security Headers
app.add_middleware(SecurityHeadersMiddleware, hsts_enabled=HSTS_ENABLED)

# 2. Distributed Tracing & Correlation ID
app.add_middleware(CorrelationIdMiddleware)

# 3. Sliding-window DoS Rate Limiting
app.add_middleware(RateLimiterMiddleware, max_requests=180, window_seconds=60)

# 3.5 Reject dot-segment / backslash paths before any proxy route builds an upstream URL
app.add_middleware(PathSafetyMiddleware)

# 4. CORS Middleware for Web3 Client Portals
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Authorization", "Content-Type", "X-Correlation-ID", "X-SSI-Client", "X-Step-Up-Token", "X-Dual-Control-Operation", "X-Dual-Control-Token"],
    expose_headers=["X-Correlation-ID", "Retry-After"]
)

# Added last, so it runs first and also sees refused requests.
app.add_middleware(SecurityTelemetryMiddleware)

app.include_router(health_router)
app.include_router(proxy_router)

