from fastapi import APIRouter

from app.api.routes.guardians import router as guardians_router
from app.api.routes.health import router as health_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.recovery import router as recovery_router


router = APIRouter()
router.include_router(health_router)
router.include_router(guardians_router)
router.include_router(recovery_router)
router.include_router(metrics_router)
