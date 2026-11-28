"""WP-28 Holder Wallet Backup & Restore API (owner-scoped)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path, Response, status
from pydantic import Field

from app.api.v1.dependencies import (
    get_step_up_service,
    get_wallet_backup_service,
    require_permission,
)
from app.application.services.step_up_service import StepUpService
from app.application.services.wallet_backup_service import (
    MAX_PAYLOAD_CHARACTERS,
    RestoreItemPlan,
    RestoreJob,
    RestorePlan,
    WalletBackupRecord,
    WalletBackupService,
)
from app.domain.auth import AuthenticatedPrincipal
from app.domain.permissions import Permission
from app.schemas.credential_api import ApiErrorResponse, ApiModel


router = APIRouter(prefix="/wallets", tags=["holder-wallet-backup"])
_WALLET_ID_PATTERN = r"^wallet_[A-Za-z0-9_-]{16,80}$"
_BACKUP_ID_PATTERN = r"^wbk_[A-Za-z0-9_-]{16,64}$"
_RESTORE_ID_PATTERN = r"^wrs_[A-Za-z0-9_-]{16,64}$"
_ERRORS = {
    code: {"model": ApiErrorResponse} for code in (401, 403, 404, 409, 413, 422, 503)
}


class WalletBackupResponse(ApiModel):
    backup_id: str
    wallet_id: str
    holder_did: str
    format_version: int
    item_count: int
    content_digest: str
    created_at: datetime

    @classmethod
    def from_domain(cls, value: WalletBackupRecord) -> "WalletBackupResponse":
        return cls(
            backup_id=value.backup_id,
            wallet_id=value.wallet_id,
            holder_did=value.holder_did,
            format_version=value.format_version,
            item_count=value.item_count,
            content_digest=value.content_digest,
            created_at=value.created_at,
        )


class WalletBackupCreatedResponse(ApiModel):
    backup: WalletBackupResponse
    # Canonical plaintext for client-side encryption. Never stored by the service.
    payload: str


class WalletBackupListResponse(ApiModel):
    items: list[WalletBackupResponse]


class WalletRestoreRequest(ApiModel):
    payload: Annotated[str, Field(min_length=2, max_length=MAX_PAYLOAD_CHARACTERS)]


class RestoreItemResponse(ApiModel):
    credential_id: str
    outcome: str
    credential_types: list[str]

    @classmethod
    def from_domain(cls, value: RestoreItemPlan) -> "RestoreItemResponse":
        return cls(
            credential_id=value.credential_id,
            outcome=value.outcome,
            credential_types=list(value.credential_types),
        )


class WalletRestorePreviewResponse(ApiModel):
    backup: WalletBackupResponse
    total: int
    restorable: int
    already_present: int
    not_restorable: int
    items: list[RestoreItemResponse]

    @classmethod
    def from_domain(cls, plan: RestorePlan) -> "WalletRestorePreviewResponse":
        restorable = plan.count("RESTORABLE")
        present = plan.count("ALREADY_PRESENT")
        return cls(
            backup=WalletBackupResponse.from_domain(plan.backup),
            total=len(plan.items),
            restorable=restorable,
            already_present=present,
            not_restorable=len(plan.items) - restorable - present,
            items=[RestoreItemResponse.from_domain(item) for item in plan.items],
        )


class WalletRestoreJobResponse(ApiModel):
    restore_id: str
    backup_id: str
    wallet_id: str
    status: str
    restored: int
    already_present: int
    rejected: int
    failure_code: str | None
    items: list[RestoreItemResponse]
    created_at: datetime

    @classmethod
    def from_domain(cls, value: RestoreJob) -> "WalletRestoreJobResponse":
        return cls(
            restore_id=value.restore_id,
            backup_id=value.backup_id,
            wallet_id=value.wallet_id,
            status=value.status,
            restored=value.restored,
            already_present=value.already_present,
            rejected=value.rejected,
            failure_code=value.failure_code,
            items=[RestoreItemResponse.from_domain(item) for item in value.items],
            created_at=value.created_at,
        )


@router.post(
    "/{wallet_id}/backups",
    response_model=WalletBackupCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a wallet backup payload for client-side encryption",
    responses=_ERRORS,
)
def create_wallet_backup(
    wallet_id: Annotated[str, Path(pattern=_WALLET_ID_PATTERN)],
    response: Response,
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.WALLETS_BACKUP)),
    service: WalletBackupService = Depends(get_wallet_backup_service),
    step_up_token: Annotated[str | None, Header(alias="X-Step-Up-Token")] = None,
    step_up: StepUpService = Depends(get_step_up_service),
) -> WalletBackupCreatedResponse:
    step_up.require(
        principal,
        step_up_token,
        action="wallet.backup.create",
        resource=wallet_id,
    )
    record, payload = service.create_backup(wallet_id, owner_user_id=principal.id)
    response.headers["Cache-Control"] = "no-store"
    return WalletBackupCreatedResponse(
        backup=WalletBackupResponse.from_domain(record), payload=payload
    )


@router.get(
    "/{wallet_id}/backups",
    response_model=WalletBackupListResponse,
    summary="List backup metadata recorded for an owned wallet",
    responses=_ERRORS,
)
def list_wallet_backups(
    wallet_id: Annotated[str, Path(pattern=_WALLET_ID_PATTERN)],
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.WALLETS_BACKUP)),
    service: WalletBackupService = Depends(get_wallet_backup_service),
) -> WalletBackupListResponse:
    return WalletBackupListResponse(
        items=[
            WalletBackupResponse.from_domain(item)
            for item in service.list_backups(wallet_id, owner_user_id=principal.id)
        ]
    )


@router.post(
    "/{wallet_id}/backups/{backup_id}/preview",
    response_model=WalletRestorePreviewResponse,
    summary="Validate a decrypted backup and preview its restore impact",
    responses=_ERRORS,
)
def preview_wallet_restore(
    wallet_id: Annotated[str, Path(pattern=_WALLET_ID_PATTERN)],
    backup_id: Annotated[str, Path(pattern=_BACKUP_ID_PATTERN)],
    payload: WalletRestoreRequest,
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.WALLETS_RESTORE)),
    service: WalletBackupService = Depends(get_wallet_backup_service),
) -> WalletRestorePreviewResponse:
    return WalletRestorePreviewResponse.from_domain(
        service.preview(
            wallet_id, backup_id, owner_user_id=principal.id, payload=payload.payload
        )
    )


@router.post(
    "/{wallet_id}/backups/{backup_id}/restore",
    response_model=WalletRestoreJobResponse,
    summary="Restore verified, non-revoked credentials that are missing from the wallet",
    responses=_ERRORS,
)
def restore_wallet_backup(
    wallet_id: Annotated[str, Path(pattern=_WALLET_ID_PATTERN)],
    backup_id: Annotated[str, Path(pattern=_BACKUP_ID_PATTERN)],
    payload: WalletRestoreRequest,
    response: Response,
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=16, max_length=128)
    ],
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.WALLETS_RESTORE)),
    service: WalletBackupService = Depends(get_wallet_backup_service),
    step_up_token: Annotated[str | None, Header(alias="X-Step-Up-Token")] = None,
    step_up: StepUpService = Depends(get_step_up_service),
) -> WalletRestoreJobResponse:
    step_up.require(
        principal,
        step_up_token,
        action="wallet.backup.restore",
        resource=wallet_id,
    )
    job, created = service.restore(
        wallet_id,
        backup_id,
        owner_user_id=principal.id,
        payload=payload.payload,
        idempotency_key=idempotency_key,
    )
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return WalletRestoreJobResponse.from_domain(job)


@router.get(
    "/{wallet_id}/restore-jobs/{restore_id}",
    response_model=WalletRestoreJobResponse,
    summary="Read an owned wallet restore job",
    responses=_ERRORS,
)
def get_wallet_restore_job(
    wallet_id: Annotated[str, Path(pattern=_WALLET_ID_PATTERN)],
    restore_id: Annotated[str, Path(pattern=_RESTORE_ID_PATTERN)],
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.WALLETS_RESTORE)),
    service: WalletBackupService = Depends(get_wallet_backup_service),
) -> WalletRestoreJobResponse:
    return WalletRestoreJobResponse.from_domain(
        service.get_restore_job(wallet_id, restore_id, owner_user_id=principal.id)
    )
