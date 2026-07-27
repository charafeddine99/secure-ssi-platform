from fastapi import APIRouter
from app.core.config import APP_VERSION, SERVICE_NAME
router = APIRouter()
@router.get("/health")
def health() -> dict[str, str]:
    return {"service": SERVICE_NAME, "status": "healthy", "version": APP_VERSION}
