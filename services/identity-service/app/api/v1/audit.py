"""Audit Trail and Administrative Log API Endpoints.

Provides unified querying across MongoDB append-only AuditEventRepository
and SQLite legacy audit storage for the Admin Console and compliance inspection.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.v1.dependencies import get_audit_event_repository, require_permission
from app.application.ports.repositories import AuditEventRepository
from app.domain.auth import AuthenticatedPrincipal
from app.domain.permissions import Permission
from app.domain.persistence import AuditEventType
from app.database import db_get_audit_logs

logger = logging.getLogger(__name__)

router = APIRouter(tags=["audit"])


class AuditLogEntry(BaseModel):
    id: Any
    event_type: str
    actor_did: str = ""
    target_wallet: str | None = None
    risk_score: int = 5
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class AuditLogListResponse(BaseModel):
    status: str = "SUCCESS"
    count: int
    audit_logs: list[AuditLogEntry]


@router.get("/audit/logs", response_model=AuditLogListResponse, operation_id="list_audit_logs")
def list_audit_logs(
    audit_repo: Annotated[AuditEventRepository, Depends(get_audit_event_repository)],
    _principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.ADMIN_OPERATIONS_READ))],
    event_type: str | None = Query(None, description="Filter by event type"),
    limit: int = Query(100, ge=1, le=500, description="Max logs to return"),
) -> AuditLogListResponse:
    entries: list[AuditLogEntry] = []

    # 1. Try Mongo AuditEventRepository
    try:
        filter_enum = None
        if event_type:
            try:
                filter_enum = AuditEventType(event_type)
            except ValueError:
                filter_enum = None

        mongo_events = audit_repo.list_recent(event_type=filter_enum, limit=limit)
        for ev in mongo_events:
            metadata_dict = dict(ev.metadata)
            risk = 5
            try:
                risk = int(metadata_dict.get("riskScore", metadata_dict.get("risk_score", 5)))
            except (ValueError, TypeError):
                risk = 5

            entries.append(
                AuditLogEntry(
                    id=ev.id,
                    event_type=ev.event_type.value,
                    actor_did=ev.actor_id or "did:ssi:platform:system",
                    target_wallet=ev.subject_id,
                    risk_score=risk,
                    details=metadata_dict,
                    created_at=ev.created_at.isoformat(),
                )
            )
    except Exception as exc:
        logger.debug(f"Mongo audit repository query skipped/failed: {exc}")

    # 2. Merge / Fallback to SQLite audit logs
    try:
        sqlite_logs = db_get_audit_logs(limit=limit)
        for row in sqlite_logs:
            ev_type = row.get("event_type", "SECURITY_EVENT")
            if event_type and event_type.upper() not in ev_type.upper():
                continue

            entries.append(
                AuditLogEntry(
                    id=row.get("id", 0),
                    event_type=ev_type,
                    actor_did=row.get("actor_did") or "did:ssi:platform:system",
                    target_wallet=row.get("target_wallet"),
                    risk_score=row.get("risk_score", 5),
                    details=row.get("details", {}),
                    created_at=row.get("created_at", ""),
                )
            )
    except Exception as exc:
        logger.debug(f"SQLite audit logs fallback failed: {exc}")

    # Sort descending by creation timestamp or ID
    return AuditLogListResponse(
        status="SUCCESS",
        count=len(entries),
        audit_logs=entries[:limit],
    )


@router.get("/audit_logs", response_model=AuditLogListResponse, operation_id="list_audit_logs_legacy_alias", include_in_schema=False)
def list_audit_logs_alias(
    audit_repo: Annotated[AuditEventRepository, Depends(get_audit_event_repository)],
    _principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.ADMIN_OPERATIONS_READ))],
    event_type: str | None = Query(None, description="Filter by event type"),
    limit: int = Query(100, ge=1, le=500, description="Max logs to return"),
) -> AuditLogListResponse:
    return list_audit_logs(
        audit_repo=audit_repo,
        _principal=_principal,
        event_type=event_type,
        limit=limit,
    )


@router.get("/audit/stats")
def get_audit_stats(
    audit_repo: Annotated[AuditEventRepository, Depends(get_audit_event_repository)],
    _principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.ADMIN_OPERATIONS_READ))],
) -> dict[str, Any]:
    logs = list_audit_logs(audit_repo=audit_repo, limit=200).audit_logs
    type_counts: dict[str, int] = {}
    for l in logs:
        type_counts[l.event_type] = type_counts.get(l.event_type, 0) + 1

    return {
        "status": "SUCCESS",
        "total_events_sampled": len(logs),
        "event_type_breakdown": type_counts,
    }
