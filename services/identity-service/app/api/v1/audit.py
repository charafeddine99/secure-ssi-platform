"""Audit Trail and Administrative Log API Endpoints.

Reads the MongoDB append-only AuditEventRepository, the authoritative audit
store. There is no fallback: when persistence is unavailable the API answers
503 instead of mixing in records from another store or reporting success.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.v1.dependencies import get_audit_event_repository, require_permission
from app.application.ports.repositories import AuditEventRepository
from app.domain.auth import AuthenticatedPrincipal
from app.domain.permissions import Permission
from app.domain.persistence import AuditEventType

logger = logging.getLogger(__name__)

router = APIRouter(tags=["audit"])


class AuditLogEntry(BaseModel):
    id: Any
    event_type: str
    actor_did: str = ""
    target_wallet: str | None = None
    # None when the event carries no risk score; never a fabricated default.
    risk_score: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class AuditLogListResponse(BaseModel):
    status: str = "SUCCESS"
    count: int
    audit_logs: list[AuditLogEntry]


def _risk_score(metadata: dict[str, Any]) -> int | None:
    value = metadata.get("riskScore", metadata.get("risk_score"))
    if isinstance(value, bool):
        return None
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _load_entries(
    audit_repo: AuditEventRepository,
    event_type: str | None,
    limit: int,
) -> list[AuditLogEntry]:
    filter_enum: AuditEventType | None = None
    if event_type:
        try:
            filter_enum = AuditEventType(event_type)
        except ValueError:
            # An unknown filter matches nothing; it must not widen to all events.
            return []
    try:
        events = audit_repo.list_recent(event_type=filter_enum, limit=limit)
    except Exception as exc:
        logger.warning("Audit repository unavailable (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The authoritative audit store is unavailable.",
        ) from exc
    entries: list[AuditLogEntry] = []
    for ev in events:
        metadata = dict(ev.metadata)
        entries.append(
            AuditLogEntry(
                id=ev.id,
                event_type=ev.event_type.value,
                actor_did=ev.actor_id or "did:ssi:platform:system",
                target_wallet=ev.subject_id,
                risk_score=_risk_score(metadata),
                details=metadata,
                created_at=ev.created_at.isoformat(),
            )
        )
    return entries[:limit]


@router.get("/audit/logs", response_model=AuditLogListResponse, operation_id="list_audit_logs")
def list_audit_logs(
    audit_repo: Annotated[AuditEventRepository, Depends(get_audit_event_repository)],
    _principal: Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.ADMIN_OPERATIONS_READ))],
    event_type: str | None = Query(None, description="Filter by event type"),
    limit: int = Query(100, ge=1, le=500, description="Max logs to return"),
) -> AuditLogListResponse:
    entries = _load_entries(audit_repo, event_type, limit)
    return AuditLogListResponse(count=len(entries), audit_logs=entries)


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
    logs = _load_entries(audit_repo, None, 200)
    type_counts: dict[str, int] = {}
    for l in logs:
        type_counts[l.event_type] = type_counts.get(l.event_type, 0) + 1

    return {
        "status": "SUCCESS",
        "total_events_sampled": len(logs),
        "event_type_breakdown": type_counts,
    }
