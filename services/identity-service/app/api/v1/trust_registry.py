from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.api.v1.dependencies import (
    get_step_up_service,
    get_trust_registry_service,
    require_permission,
)
from app.application.services.step_up_service import StepUpService
from app.application.services.trust_registry_service import TrustRegistryService
from app.domain.auth import AuthenticatedPrincipal
from app.domain.permissions import Permission
from app.domain.persistence import DuplicateEntityError, OptimisticLockError
from app.domain.trust_registry import TrustRecord, TrustRole, TrustStatus
from app.schemas.trust_registry_api import (
    ReasonRequest,
    RegisterTrustedIssuerRequest,
    TrustEvaluationRequest,
    TrustEvaluationResponse,
    TrustRecordResponse,
    UpdateTrustRecordRequest,
)

router = APIRouter(prefix="/trust-registry", tags=["trust-registry"])


def _to_response(record: TrustRecord) -> TrustRecordResponse:
    return TrustRecordResponse(
        id=record.id,
        issuer_did=record.issuer_did,
        organization_name=record.organization_name,
        trust_status=record.trust_status.value,
        roles=[r.value for r in record.roles],
        permitted_credential_types=list(record.permitted_credential_types),
        valid_from=record.valid_from.isoformat(),
        valid_until=record.valid_until.isoformat() if record.valid_until else None,
        trust_source=record.trust_source,
        trust_anchor=record.trust_anchor,
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
        created_by=record.created_by,
        audit_metadata=dict(record.audit_metadata),
        version=record.version,
    )


@router.get(
    "/issuers",
    response_model=list[TrustRecordResponse],
    summary="List Trust Registry Records",
    description="Retrieve list of registered trusted issuers and their accreditation status.",
)
def list_trusted_issuers(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    skip: int = Query(default=0, ge=0),
    service: TrustRegistryService = Depends(get_trust_registry_service),
) -> list[TrustRecordResponse]:
    t_status = None
    if status_filter:
        try:
            t_status = TrustStatus(status_filter.lower())
        except ValueError:
            pass
    records = service.list_trust_records(status=t_status, limit=limit, skip=skip)
    return [_to_response(r) for r in records]


@router.get(
    "/issuers/{issuer_did:path}",
    response_model=TrustRecordResponse,
    summary="Get Trust Record by Issuer DID",
    description="Fetch authoritative Trust Registry record for an exact issuer DID.",
)
def get_trusted_issuer(
    issuer_did: str,
    service: TrustRegistryService = Depends(get_trust_registry_service),
) -> TrustRecordResponse:
    record = service.get_trust_record(issuer_did)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issuer '{issuer_did}' is not registered in the Trust Registry.",
        )
    return _to_response(record)


@router.post(
    "/issuers",
    response_model=TrustRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Trusted Issuer (Admin Only)",
    description="Add an authorized accredited issuer to the platform's local authoritative Trust Registry.",
)
def register_trusted_issuer(
    payload: RegisterTrustedIssuerRequest,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.TRUST_REGISTRY_WRITE)
    ),
    service: TrustRegistryService = Depends(get_trust_registry_service),
    step_up_token: Annotated[str | None, Header(alias="X-Step-Up-Token")] = None,
    step_up: StepUpService = Depends(get_step_up_service),
) -> TrustRecordResponse:
    step_up.require(principal, step_up_token, action="trust.registry.write", resource=payload.issuer_did)
    roles = tuple(TrustRole(r) for r in payload.roles if r in TrustRole._value2member_map_)
    now = datetime.now(UTC)
    v_until = now + timedelta(days=payload.valid_days)
    try:
        record = service.register_trusted_issuer(
            actor_id=principal.id,
            issuer_did=payload.issuer_did,
            organization_name=payload.organization_name,
            roles=roles or (TrustRole.ISSUER,),
            permitted_credential_types=tuple(payload.permitted_credential_types),
            valid_from=now,
            valid_until=v_until,
            trust_source=payload.trust_source,
            trust_anchor=payload.trust_anchor,
            audit_metadata={"notes": payload.notes} if payload.notes else None,
        )
        return _to_response(record)
    except DuplicateEntityError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.put(
    "/issuers/{record_id}",
    response_model=TrustRecordResponse,
    summary="Update Trust Record (Admin Only)",
    description="Modify organization name, permitted credential types, or validity window.",
)
def update_trust_record(
    record_id: str,
    payload: UpdateTrustRecordRequest,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.TRUST_REGISTRY_WRITE)
    ),
    service: TrustRegistryService = Depends(get_trust_registry_service),
    step_up_token: Annotated[str | None, Header(alias="X-Step-Up-Token")] = None,
    step_up: StepUpService = Depends(get_step_up_service),
) -> TrustRecordResponse:
    step_up.require(principal, step_up_token, action="trust.registry.write", resource=record_id)
    t_status = None
    if payload.trust_status:
        try:
            t_status = TrustStatus(payload.trust_status.lower())
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid trust status: {payload.trust_status}",
            ) from error

    roles = None
    if payload.roles is not None:
        roles = tuple(TrustRole(r) for r in payload.roles if r in TrustRole._value2member_map_)

    v_until = None
    if payload.valid_days_extended is not None:
        v_until = datetime.now(UTC) + timedelta(days=payload.valid_days_extended)

    types = tuple(payload.permitted_credential_types) if payload.permitted_credential_types is not None else None

    try:
        updated = service.update_trust_record(
            actor_id=principal.id,
            record_id=record_id,
            organization_name=payload.organization_name,
            trust_status=t_status,
            roles=roles,
            permitted_credential_types=types,
            valid_until=v_until,
            audit_metadata={"notes": payload.notes} if payload.notes else None,
        )
        return _to_response(updated)
    except OptimisticLockError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error


@router.post(
    "/issuers/{record_id}/suspend",
    response_model=TrustRecordResponse,
    summary="Suspend Trusted Issuer (Admin Only)",
    description="Temporarily suspend an issuer's trust accreditation.",
)
def suspend_trusted_issuer(
    record_id: str,
    payload: ReasonRequest,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.TRUST_REGISTRY_WRITE)
    ),
    service: TrustRegistryService = Depends(get_trust_registry_service),
    step_up_token: Annotated[str | None, Header(alias="X-Step-Up-Token")] = None,
    step_up: StepUpService = Depends(get_step_up_service),
) -> TrustRecordResponse:
    step_up.require(principal, step_up_token, action="trust.registry.write", resource=record_id)
    record = service.get_trust_record_by_id(record_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trust record '{record_id}' not found.",
        )
    try:
        updated = service.suspend_issuer(
            actor_id=principal.id,
            issuer_did=record.issuer_did,
            reason=payload.reason,
        )
        return _to_response(updated)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error


@router.post(
    "/issuers/{record_id}/revoke",
    response_model=TrustRecordResponse,
    summary="Revoke Trusted Issuer (Admin Only)",
    description="Permanently revoke an issuer's trust accreditation.",
)
def revoke_trusted_issuer(
    record_id: str,
    payload: ReasonRequest,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.TRUST_REGISTRY_WRITE)
    ),
    service: TrustRegistryService = Depends(get_trust_registry_service),
    step_up_token: Annotated[str | None, Header(alias="X-Step-Up-Token")] = None,
    step_up: StepUpService = Depends(get_step_up_service),
) -> TrustRecordResponse:
    step_up.require(principal, step_up_token, action="trust.registry.write", resource=record_id)
    record = service.get_trust_record_by_id(record_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trust record '{record_id}' not found.",
        )
    try:
        updated = service.revoke_issuer(
            actor_id=principal.id,
            issuer_did=record.issuer_did,
            reason=payload.reason,
        )
        return _to_response(updated)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error


@router.post(
    "/evaluate",
    response_model=TrustEvaluationResponse,
    summary="Evaluate Issuer Trust Policy",
    description="Determine if an issuer identity is authoritative and trusted for specified credential types.",
)
def evaluate_issuer_trust(
    payload: TrustEvaluationRequest,
    service: TrustRegistryService = Depends(get_trust_registry_service),
) -> TrustEvaluationResponse:
    result = service.evaluate_issuer_trust(
        issuer_did=payload.issuer_did,
        credential_types=payload.credential_types,
    )
    return TrustEvaluationResponse(
        is_trusted=result.is_trusted,
        issuer_did=result.issuer_did,
        status=result.status.value if result.status else None,
        reason=result.reason,
        trust_record_id=result.trust_record_id,
        trust_source=result.trust_source,
        matched_types=list(result.matched_types),
    )
