from fastapi import FastAPI
from app.api.routes.health import router as health_router
from app.core.config import APP_VERSION, SERVICE_NAME
app = FastAPI(title=SERVICE_NAME, version=APP_VERSION)
app.include_router(health_router)
