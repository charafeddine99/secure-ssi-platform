from fastapi import APIRouter

from app.core.config import APP_VERSION, SERVICE_NAME
from app.schemas.recovery_api import HealthResponse


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        service=SERVICE_NAME,
        status="healthy",
        version=APP_VERSION,
    )
