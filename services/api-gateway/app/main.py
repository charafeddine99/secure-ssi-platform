from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.health import router as health_router
from app.api.routes.proxy import router as proxy_router
from app.api.routes.iot_door import router as iot_door_router
from app.core.config import APP_VERSION, SERVICE_NAME, CORS_ORIGINS

app = FastAPI(
    title=SERVICE_NAME,
    version=APP_VERSION,
    description="Secure SSI Platform - Merkezi API Gateway, Reverse-Proxy ve IoT Kapı Köprüsü"
)

# CORS Middleware (React Web3 Arayüzü için)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(proxy_router)
app.include_router(iot_door_router)
