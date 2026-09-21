from fastapi import FastAPI
from app.api.routes.health import router as health_router
from app.api.routes.fraud import router as fraud_router
from app.core.config import APP_VERSION, SERVICE_NAME

app = FastAPI(
    title=SERVICE_NAME,
    version=APP_VERSION,
    description="Secure SSI Platformu - Yapay Zekâ Tabanlı Dolandırıcılık Tespiti ve Anomali Servisi (XGBoost + Autoencoder)"
)

app.include_router(health_router)
app.include_router(fraud_router)
