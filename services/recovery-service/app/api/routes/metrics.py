from fastapi import APIRouter, Depends

from app.api.dependencies import (
    get_current_principal,
    get_recovery_metrics,
)
from app.application.services.metrics import RecoveryMetrics
from app.domain.auth import Permission, RecoveryPrincipal


router = APIRouter(tags=["internal"])


@router.get("/internal/metrics", include_in_schema=False)
def metrics(
    principal: RecoveryPrincipal = Depends(get_current_principal),
    recovery_metrics: RecoveryMetrics = Depends(get_recovery_metrics),
) -> dict[str, object]:
    principal.require(Permission.RECOVERY_RECONCILE)
    return recovery_metrics.snapshot().as_dict()
