from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.v1.dependencies import (
    get_audit_event_repository,
    get_auth_settings,
    get_credential_issuance_api_service,
    get_trust_registry_service,
    get_user_repository,
    require_permission,
)
from app.application.ports.repositories import (
    AuditEventRepository,
    UserRepository,
)
from app.application.services.credential_api_service import CredentialApiService
from app.application.services.trust_registry_service import TrustRegistryService
from app.config.auth_settings import AuthSettings
from app.domain.auth import AuthenticatedPrincipal
from app.domain.exceptions import PermissionDeniedError
from app.domain.permissions import Permission, Role
from app.domain.persistence import (
    AuditEvent,
    AuditEventType,
    EntityNotFoundError,
    OptimisticLockError,
    PersistenceUnavailableError,
    PersistedUser,
)
from app.domain.trust_registry import TrustRole, TrustStatus
from app.infrastructure.persistence.mappers import new_object_id
from app.schemas.admin_user_api import (
    AdminUserResponse,
    IssuerScopeOptionResponse,
    UpdateIssuerScopeRequest,
)

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


def _require_persistent_users(settings: AuthSettings) -> None:
    if settings.user_provider != "mongodb":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "User administration requires the MongoDB authentication "
                "provider; synthetic fixture accounts are read-only."
            ),
        )


def _to_response(
    user: PersistedUser,
    trust_registry: TrustRegistryService,
) -> AdminUserResponse:
    organization_name = None
    if user.issuer_did:
        trust_record = trust_registry.get_trust_record(user.issuer_did)
        if trust_record is not None:
            organization_name = trust_record.organization_name
    return AdminUserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        roles=[role.value for role in user.roles],
        enabled=user.enabled,
        issuer_did=user.issuer_did,
        issuer_organization_name=organization_name,
        version=user.version,
    )


@router.get(
    "",
    response_model=list[AdminUserResponse],
    summary="List persistent platform users",
)
def list_admin_users(
    limit: int = Query(default=100, ge=1, le=100),
    skip: int = Query(default=0, ge=0),
    _principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.ADMIN_USERS_READ)
    ),
    settings: AuthSettings = Depends(get_auth_settings),
    users: UserRepository = Depends(get_user_repository),
    trust_registry: TrustRegistryService = Depends(get_trust_registry_service),
) -> list[AdminUserResponse]:
    _require_persistent_users(settings)
    try:
        records = users.list_all(limit=limit, skip=skip)
    except PersistenceUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Persistent user directory is unavailable.",
        ) from error
    return [_to_response(record, trust_registry) for record in records]


@router.get(
    "/issuer-options",
    response_model=list[IssuerScopeOptionResponse],
    summary="List active, trusted issuers with configured signing keys",
)
def list_issuer_scope_options(
    _principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.ADMIN_USERS_READ)
    ),
    settings: AuthSettings = Depends(get_auth_settings),
    trust_registry: TrustRegistryService = Depends(get_trust_registry_service),
    issuance: CredentialApiService = Depends(
        get_credential_issuance_api_service
    ),
) -> list[IssuerScopeOptionResponse]:
    _require_persistent_users(settings)
    now = datetime.now(UTC)
    options = []
    for record in trust_registry.list_trust_records(
        status=TrustStatus.ACTIVE,
        limit=500,
        skip=0,
    ):
        if TrustRole.ISSUER not in record.roles or not record.is_valid_at(now):
            continue
        if not trust_registry.evaluate_issuer_trust(
            issuer_did=record.issuer_did,
            at_time=now,
        ).is_trusted:
            continue
        if not issuance.supports_issuer(record.issuer_did):
            continue
        options.append(
            IssuerScopeOptionResponse(
                issuer_did=record.issuer_did,
                organization_name=record.organization_name,
            )
        )
    return sorted(options, key=lambda option: option.organization_name.casefold())


@router.put(
    "/{user_id}/issuer-scope",
    response_model=AdminUserResponse,
    summary="Assign or remove an Issuer account's institution scope",
)
def update_issuer_scope(
    user_id: str,
    payload: UpdateIssuerScopeRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.ADMIN_USERS_WRITE)
    ),
    settings: AuthSettings = Depends(get_auth_settings),
    users: UserRepository = Depends(get_user_repository),
    trust_registry: TrustRegistryService = Depends(get_trust_registry_service),
    issuance: CredentialApiService = Depends(
        get_credential_issuance_api_service
    ),
    audit_events: AuditEventRepository = Depends(get_audit_event_repository),
) -> AdminUserResponse:
    _require_persistent_users(settings)
    current = users.get_by_id(user_id)
    if current is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User was not found.",
        )
    if Role.ISSUER not in current.roles:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Institution scope can only be assigned to an Issuer account.",
        )
    if current.version != payload.expected_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User changed since it was loaded; refresh and try again.",
        )

    issuer_did = (
        payload.issuer_did.strip()
        if payload.issuer_did is not None
        else None
    )
    if payload.issuer_did is not None and not issuer_did:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="issuerDid must be null or a non-empty DID.",
        )
    organization_name = None
    if issuer_did is not None:
        record = trust_registry.get_trust_record(issuer_did)
        now = datetime.now(UTC)
        if (
            record is None
            or TrustRole.ISSUER not in record.roles
            or not record.is_valid_at(now)
            or not trust_registry.evaluate_issuer_trust(
                issuer_did=issuer_did,
                at_time=now,
            ).is_trusted
        ):
            raise PermissionDeniedError(
                "Issuer scope must match a currently trusted Issuer record."
            )
        if not issuance.supports_issuer(issuer_did):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The selected institution has no configured signing key.",
            )
        organization_name = record.organization_name

    if issuer_did == current.issuer_did:
        return _to_response(current, trust_registry)

    try:
        updated = users.update(
            replace(current, issuer_did=issuer_did),
            expected_version=payload.expected_version,
        )
    except (ValueError, PermissionDeniedError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except OptimisticLockError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User changed since it was loaded; refresh and try again.",
        ) from error
    except EntityNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User was not found.",
        ) from error
    except PersistenceUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Persistent user directory is unavailable.",
        ) from error

    now = datetime.now(UTC)
    metadata = {
        "action": "assigned" if issuer_did is not None else "removed",
        "version": str(updated.version),
    }
    if current.issuer_did is not None:
        metadata["previousIssuerDid"] = current.issuer_did
    if issuer_did is not None:
        metadata["issuerDid"] = issuer_did
        metadata["organizationName"] = organization_name or issuer_did
    audit_events.append(
        AuditEvent(
            id=new_object_id(),
            event_type=AuditEventType.USER_ISSUER_SCOPE_UPDATED,
            subject_id=updated.id,
            actor_id=principal.id,
            correlation_id=getattr(request.state, "request_id", None),
            metadata=metadata,
            created_at=now,
            updated_at=now,
            version=1,
        )
    )
    return _to_response(updated, trust_registry)
