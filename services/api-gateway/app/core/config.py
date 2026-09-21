import os

SERVICE_NAME = "api-gateway"
APP_VERSION = os.getenv("APP_VERSION", "0.2.0")

# Alt mikroservislerin adresleri (Docker içi veya yerel)
IDENTITY_SERVICE_URL = os.getenv("IDENTITY_SERVICE_URL", "http://127.0.0.1:8001")
FRAUD_SERVICE_URL = os.getenv("FRAUD_SERVICE_URL", "http://127.0.0.1:8002")
RECOVERY_SERVICE_URL = os.getenv("RECOVERY_SERVICE_URL", "http://127.0.0.1:8003")

# İstemci arayüzü CORS izinleri
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "*"
]
