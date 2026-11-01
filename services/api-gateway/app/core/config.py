import os


def parse_boolean(value: str, *, name: str) -> bool:
    normalized = value.strip().casefold()
    if normalized not in {"true", "false"}:
        raise RuntimeError(f"{name} must be true or false.")
    return normalized == "true"

SERVICE_NAME = "api-gateway"
APP_VERSION = os.getenv("APP_VERSION", "0.2.0")
HSTS_ENABLED = parse_boolean(
    os.getenv("GATEWAY_HSTS_ENABLED", "false"),
    name="GATEWAY_HSTS_ENABLED",
)

# Alt mikroservislerin adresleri (Docker içi veya yerel)
IDENTITY_SERVICE_URL = os.getenv("IDENTITY_SERVICE_URL", "http://127.0.0.1:8001")
FRAUD_SERVICE_URL = os.getenv("FRAUD_SERVICE_URL", "http://127.0.0.1:8002")
RECOVERY_SERVICE_URL = os.getenv("RECOVERY_SERVICE_URL", "http://127.0.0.1:8003")

# Strict CORS origins for trusted Web3 client portals
raw_cors = os.getenv("CORS_ORIGINS", "")
if raw_cors:
    CORS_ORIGINS = [origin.strip() for origin in raw_cors.split(",") if origin.strip()]
else:
    CORS_ORIGINS = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:18000",
        "http://127.0.0.1:18000",
        "http://localhost:13000",
        "http://127.0.0.1:13000",
    ]
