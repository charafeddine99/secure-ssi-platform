from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.v1.error_handlers import install_exception_handlers
from app.api.v1.request_safety import JsonRequestSafetyMiddleware
from app.api.v1.router import router as v1_router
from app.core.config import APP_VERSION, SERVICE_NAME
from app.lifecycle import application_lifespan


app = FastAPI(
    title=SERVICE_NAME,
    version=APP_VERSION,
    description=(
        "Local academic SSI prototype with synthetic Argon2id authentication "
        "and short-lived HS256 access tokens. Credential signing requires "
        "local RBAC; validation, verification, and capabilities remain public. "
        "MongoDB provides atomic status-bound issuance, irreversible "
        "revocation, Bitstring Status List rollover/immutable history, and "
        "durable audit outbox delivery. Authenticated local holders and "
        "verifiers can manage wallet-bound credentials and create/read or "
        "one-time verify short-lived, server-issued "
        "challenge/domain/audience-bound Verifiable Presentations. A bounded "
        "worker reconciles stale verification claims. There is "
        "also a provider-neutral managed-key lifecycle with a non-production "
        "development adapter and configurable generic HTTPS KMS gateway. "
        "Private keys never cross the provider boundary. There is no "
        "registration, refresh token, rate limiting, MFA, external identity "
        "provider, presentation exchange, account recovery, or deployed "
        "vendor-specific HSM integration."
    ),
    lifespan=application_lifespan,
)
app.add_middleware(JsonRequestSafetyMiddleware)
install_exception_handlers(app)
app.include_router(health_router)
app.include_router(v1_router)
