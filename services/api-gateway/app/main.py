from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.health import router as health_router
from app.api.routes.proxy import router as proxy_router
from app.core.config import APP_VERSION, SERVICE_NAME, CORS_ORIGINS
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
app.add_middleware(SecurityHeadersMiddleware)

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
    allow_headers=["Accept", "Authorization", "Content-Type", "X-Correlation-ID", "X-SSI-Client"],
    expose_headers=["X-Correlation-ID", "Retry-After"]
)

app.include_router(health_router)
app.include_router(proxy_router)

