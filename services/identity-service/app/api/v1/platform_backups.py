"""WP-28 Admin Platform Backup & Disaster Recovery API.

Admin-only. There is intentionally no restore-execution endpoint: restores run
only through the CLI drill (``python -m app.tools.platform_restore_drill``)
into an empty ``restore_drill_*`` database. Live cutover is not automated.
"""

import os
from datetime import datetime
from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Path
from pydantic import Field
from pymongo import MongoClient

from app.api.v1.dependencies import (
    get_audit_event_repository,
    get_key_management_settings,
    get_mongo_connection_manager,
    get_revocation_ledger_settings,
    get_step_up_service,
    require_permission,
    revocation_ledger_collection,
)
from app.application.services.step_up_service import StepUpService
from app.infrastructure.key_management.backup_key_wrapper import (
    RemoteBackupKeyWrapper,
)
from app.infrastructure.key_management.signing_trust import build_remote_adapter
from app.application.services.platform_backup_service import (
    LEDGER_COMPONENT,
    RECOVERY_COMPONENT,
    CollectionSummary,
    PlatformBackupDisabledError,
    PlatformBackupRecord,
    PlatformBackupService,
    PlatformBackupSettings,
    load_platform_backup_settings,
)
from app.core.config import APP_VERSION
from app.domain.auth import AuthenticatedPrincipal
from app.domain.permissions import Permission
from app.infrastructure.persistence.connection import MongoConnectionManager
from app.schemas.credential_api import ApiErrorResponse, ApiModel


router = APIRouter(prefix="/admin/platform-backups", tags=["platform-backup"])
_BACKUP_ID_PATTERN = r"^pbk_[A-Za-z0-9_-]{16,64}$"
_ERRORS = {code: {"model": ApiErrorResponse} for code in (401, 403, 404, 409, 422, 503)}


@lru_cache(maxsize=1)
def get_platform_backup_settings() -> PlatformBackupSettings:
    return load_platform_backup_settings()


_RECOVERY_CLIENT: MongoClient[dict[str, Any]] | None = None


def _additional_sources(
    manager: MongoConnectionManager,
    settings: PlatformBackupSettings,
) -> dict[str, Any]:
    """Recovery needs its own read-only principal. A dedicated ledger joins the
    archive as a component; otherwise it is already inside the identity data."""
    global _RECOVERY_CLIENT
    sources: dict[str, Any] = {}
    if settings.recovery_uri is not None:
        if _RECOVERY_CLIENT is None:
            _RECOVERY_CLIENT = MongoClient(
                settings.recovery_uri,
                serverSelectionTimeoutMS=3_000,
                appname="secure-ssi-platform-backup",
            )
        sources[RECOVERY_COMPONENT] = _RECOVERY_CLIENT[settings.recovery_database]
    if get_revocation_ledger_settings().separate_authority:
        sources[LEDGER_COMPONENT] = revocation_ledger_collection(manager).database
    return sources


def _key_wrapper(settings: PlatformBackupSettings) -> Any:
    if settings.kms_key_reference is None:
        return None
    return RemoteBackupKeyWrapper(
        build_remote_adapter(
            get_key_management_settings(),
            token_environment_variable=os.environ.get(
                "IDENTITY_PLATFORM_BACKUP_KMS_AUTH_TOKEN_ENV"
            ),
            client_purpose="backup-key-wrapping",
        ),
        settings.kms_key_reference,
    )


def build_platform_backup_service(
    manager: MongoConnectionManager,
    *,
    settings: PlatformBackupSettings,
    audits: Any = None,
) -> PlatformBackupService:
    return PlatformBackupService(
        database=manager.database,
        settings=settings,
        audits=audits or _NoAudit(),
        app_version=APP_VERSION,
        additional_sources=_additional_sources(manager, settings),
        key_wrapper=_key_wrapper(settings),
    )


class _NoAudit:
    def append(self, event: Any) -> Any:
        return event


def get_platform_backup_service(
    manager: MongoConnectionManager = Depends(get_mongo_connection_manager),
    audits: Any = Depends(get_audit_event_repository),
    settings: PlatformBackupSettings = Depends(get_platform_backup_settings),
) -> PlatformBackupService:
    if not manager.is_connected:
        raise PlatformBackupDisabledError("Authoritative persistence is unavailable.")
    return build_platform_backup_service(manager, settings=settings, audits=audits)


class CollectionSummaryResponse(ApiModel):
    name: str
    documents: int
    indexes: list[str]

    @classmethod
    def from_domain(cls, value: CollectionSummary) -> "CollectionSummaryResponse":
        return cls(name=value.name, documents=value.documents, indexes=list(value.indexes))


class PlatformBackupResponse(ApiModel):
    backup_id: str
    status: str
    source_database: str
    created_by: str
    started_at: datetime
    finished_at: datetime | None
    duration_ms: float | None
    size_bytes: int | None
    archive_sha256: str | None
    schema_version: int
    app_version: str
    consistency: str
    completeness: str
    components: list[str]
    watermark: str | None
    encryption: str = "AES-256-GCM"
    collections: list[CollectionSummaryResponse]
    expires_at: datetime | None
    failure_code: str | None
    last_verified_at: datetime | None
    last_verify_result: str | None

    @classmethod
    def from_domain(cls, value: PlatformBackupRecord) -> "PlatformBackupResponse":
        return cls(
            backup_id=value.backup_id,
            status=value.status,
            source_database=value.source_database,
            created_by=value.created_by,
            started_at=value.started_at,
            finished_at=value.finished_at,
            duration_ms=value.duration_ms,
            size_bytes=value.size_bytes,
            archive_sha256=value.archive_sha256,
            schema_version=value.schema_version,
            app_version=value.app_version,
            consistency=value.consistency,
            completeness=value.completeness,
            components=list(value.components),
            watermark=value.watermark,
            collections=[CollectionSummaryResponse.from_domain(item) for item in value.collections],
            expires_at=value.expires_at,
            failure_code=value.failure_code,
            last_verified_at=value.last_verified_at,
            last_verify_result=value.last_verify_result,
        )


class PlatformBackupListResponse(ApiModel):
    enabled: bool
    disabled_reason: str | None
    retention_seconds: int
    scheduler: str = "NOT_CONFIGURED"
    interval_seconds: int = 0
    offsite: str = "NOT_CONFIGURED"
    immutable: str = "NOT_CONFIGURED"
    point_in_time: str = "NOT_CONFIGURED"
    key_custody: str = "ENVIRONMENT_KEY"
    scope: list[str] = []
    restore_execution: str = "CLI_DRILL_ONLY_DUAL_CONTROL"
    items: list[PlatformBackupResponse]


class PlatformBackupVerifyResponse(ApiModel):
    backup: PlatformBackupResponse
    integrity_verified: bool
    collections: list[CollectionSummaryResponse]


class RestorePreviewRequest(ApiModel):
    target_database: Annotated[str, Field(min_length=1, max_length=64)]


class RestorePreviewResponse(ApiModel):
    backup: PlatformBackupResponse
    target_database: str
    target_name_accepted: bool
    schema_compatible: bool
    integrity_verified: bool
    execution_available: bool = False
    collections: list[CollectionSummaryResponse]
    blocking_reasons: list[str]


class RetentionSweepResponse(ApiModel):
    expired: int


@router.get("", response_model=PlatformBackupListResponse, responses=_ERRORS)
def list_platform_backups(
    _principal: AuthenticatedPrincipal = Depends(require_permission(Permission.ADMIN_BACKUP_READ)),
    service: PlatformBackupService = Depends(get_platform_backup_service),
) -> PlatformBackupListResponse:
    settings = service.settings
    return PlatformBackupListResponse(
        enabled=settings.enabled,
        disabled_reason=settings.disabled_reason,
        retention_seconds=settings.retention_seconds,
        scheduler="ENABLED" if settings.interval_seconds > 0 else "NOT_CONFIGURED",
        interval_seconds=settings.interval_seconds,
        key_custody=(
            "ENVIRONMENT_KEY" if settings.kms_key_reference is None else "REMOTE_KMS"
        ),
        scope=list(service.component_names),
        items=[PlatformBackupResponse.from_domain(item) for item in service.list_backups()],
    )


@router.post("", response_model=PlatformBackupResponse, status_code=201, responses=_ERRORS)
def create_platform_backup(
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.ADMIN_BACKUP_WRITE)),
    service: PlatformBackupService = Depends(get_platform_backup_service),
    step_up_token: Annotated[str | None, Header(alias="X-Step-Up-Token")] = None,
    step_up: StepUpService = Depends(get_step_up_service),
) -> PlatformBackupResponse:
    step_up.require(principal, step_up_token, action="platform.backup.create", resource="platform")
    return PlatformBackupResponse.from_domain(service.create_backup(actor_id=principal.id))


@router.post("/retention-sweep", response_model=RetentionSweepResponse, responses=_ERRORS)
def sweep_platform_backups(
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.ADMIN_BACKUP_WRITE)),
    service: PlatformBackupService = Depends(get_platform_backup_service),
    step_up_token: Annotated[str | None, Header(alias="X-Step-Up-Token")] = None,
    step_up: StepUpService = Depends(get_step_up_service),
) -> RetentionSweepResponse:
    step_up.require(principal, step_up_token, action="platform.backup.sweep", resource="platform")
    return RetentionSweepResponse(expired=service.expire_due(actor_id=principal.id))


@router.get("/{backup_id}", response_model=PlatformBackupResponse, responses=_ERRORS)
def get_platform_backup(
    backup_id: Annotated[str, Path(pattern=_BACKUP_ID_PATTERN)],
    _principal: AuthenticatedPrincipal = Depends(require_permission(Permission.ADMIN_BACKUP_READ)),
    service: PlatformBackupService = Depends(get_platform_backup_service),
) -> PlatformBackupResponse:
    return PlatformBackupResponse.from_domain(service.get(backup_id))


@router.post("/{backup_id}/verify", response_model=PlatformBackupVerifyResponse, responses=_ERRORS)
def verify_platform_backup(
    backup_id: Annotated[str, Path(pattern=_BACKUP_ID_PATTERN)],
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.ADMIN_BACKUP_WRITE)),
    service: PlatformBackupService = Depends(get_platform_backup_service),
) -> PlatformBackupVerifyResponse:
    record, contents = service.verify(backup_id, actor_id=principal.id)
    return PlatformBackupVerifyResponse(
        backup=PlatformBackupResponse.from_domain(record),
        integrity_verified=True,
        collections=[CollectionSummaryResponse.from_domain(item) for item in contents.collections],
    )


@router.post(
    "/{backup_id}/restore-preview", response_model=RestorePreviewResponse, responses=_ERRORS
)
def preview_platform_restore(
    backup_id: Annotated[str, Path(pattern=_BACKUP_ID_PATTERN)],
    payload: RestorePreviewRequest,
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.ADMIN_BACKUP_WRITE)),
    service: PlatformBackupService = Depends(get_platform_backup_service),
) -> RestorePreviewResponse:
    preview = service.preview_restore(
        backup_id, target_database=payload.target_database, actor_id=principal.id
    )
    return RestorePreviewResponse(
        backup=PlatformBackupResponse.from_domain(preview.backup),
        target_database=preview.target_database,
        target_name_accepted=preview.target_name_accepted,
        schema_compatible=preview.schema_compatible,
        integrity_verified=preview.integrity_verified,
        collections=[CollectionSummaryResponse.from_domain(item) for item in preview.collections],
        blocking_reasons=list(preview.blocking_reasons),
    )
