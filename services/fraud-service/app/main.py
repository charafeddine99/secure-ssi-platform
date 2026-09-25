import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.fraud import router as fraud_router
from app.api.routes.fraud_detection import router as fraud_detection_router
from app.core.config import APP_VERSION, SERVICE_NAME

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

app = FastAPI(
    title=SERVICE_NAME,
    version=APP_VERSION,
    description="AI-powered Fraud Detection & Anomaly Engine for Decentralized Identity (DID) Systems (XGBoost + Autoencoder)"
)

# Enable CORS for frontend & API gateway access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(health_router)
app.include_router(fraud_router)
app.include_router(fraud_detection_router)


# Sample block at the bottom to run the uvicorn server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8002, reload=True)
