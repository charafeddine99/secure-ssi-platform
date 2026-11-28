from fastapi import APIRouter, Depends, Response

from app.api.v1.dependencies import (
    get_clock,
    get_key_providers,
    get_mongo_connection_manager,
    get_revocation_ledger,
    get_revocation_ledger_settings,
    get_signing_trust,
    get_step_up_settings,
    require_permission,
)
from app.api.v1.platform_backups import (
    build_platform_backup_service,
    get_platform_backup_settings,
)
from app.application.services.readiness_service import (
    ReadinessReport,
    evaluate_readiness,
)
from app.domain.auth import AuthenticatedPrincipal
from app.domain.permissions import Permission
from app.schemas.credential_api import ApiModel


public_router = APIRouter(tags=["readiness"])
router = APIRouter(prefix="/admin", tags=["readiness"])


class ReadinessResponse(ApiModel):
    environment: str
    ready: bool
    blockers: list[str]
    warnings: list[str]
    details: dict


def _report(manager, ledger, clock, signing, holders, ledger_settings, step_up) -> ReadinessReport:
    settings = get_platform_backup_settings()
    backup = (
        build_platform_backup_service(manager, settings=settings)
        if settings.enabled and manager.is_connected
        else None
    )
    return evaluate_readiness(
        environment=ledger_settings.environment,
        signing_uses_development_keys=signing.uses_development_keys,
        signing_providers=(signing.credential_provider, signing.status_provider),
        holder_providers=holders.values(),
        ledger=ledger,
        ledger_settings=ledger_settings,
        backup=backup,
        backup_settings=settings,
        step_up_required=step_up.required,
        clock=clock,
    )


@public_router.get("/ready")
def ready(
    response: Response,
    manager=Depends(get_mongo_connection_manager),
    ledger=Depends(get_revocation_ledger),
    clock=Depends(get_clock),
    signing=Depends(get_signing_trust),
    holders=Depends(get_key_providers),
    ledger_settings=Depends(get_revocation_ledger_settings),
    step_up=Depends(get_step_up_settings),
) -> dict[str, str]:
    """Status only. The reasons need an administrator, see /admin/readiness."""
    report = _report(
        manager, ledger, clock, signing, holders, ledger_settings, step_up
    )
    if not report.ready:
        response.status_code = 503
    return {"status": "READY" if report.ready else "NOT_READY"}


@router.get("/readiness", response_model=ReadinessResponse)
def readiness_detail(
    _principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.ADMIN_BACKUP_READ)
    ),
    manager=Depends(get_mongo_connection_manager),
    ledger=Depends(get_revocation_ledger),
    clock=Depends(get_clock),
    signing=Depends(get_signing_trust),
    holders=Depends(get_key_providers),
    ledger_settings=Depends(get_revocation_ledger_settings),
    step_up=Depends(get_step_up_settings),
) -> ReadinessResponse:
    report = _report(
        manager, ledger, clock, signing, holders, ledger_settings, step_up
    )
    return ReadinessResponse(
        environment=report.environment,
        ready=report.ready,
        blockers=list(report.blockers),
        warnings=list(report.warnings),
        details=report.details,
    )
