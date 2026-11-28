import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.fraud import router as fraud_router
from app.api.routes.fraud_detection import router as fraud_detection_router
from app.api.routes.intelligence import router as intelligence_router
from app.core.config import APP_VERSION, CORS_ORIGINS, SERVICE_NAME

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

app = FastAPI(
    title=SERVICE_NAME,
    version=APP_VERSION,
    description="Deterministic, advisory risk heuristics for synthetic SSI prototype events; no trained model is deployed."
)

# Browser access is limited to explicitly configured local frontend origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Correlation-ID"],
)

# Register routes
app.include_router(health_router)
app.include_router(fraud_router)
app.include_router(fraud_detection_router)
app.include_router(intelligence_router)


# Sample block at the bottom to run the uvicorn server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8002, reload=True)
