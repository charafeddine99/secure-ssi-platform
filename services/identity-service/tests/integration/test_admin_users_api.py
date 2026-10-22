from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.v1.dependencies import (
    get_audit_event_repository,
    get_auth_settings,
    get_credential_issuance_api_service,
    get_current_principal,
    get_trust_registry_service,
    get_user_repository,
)
from app.application.services.trust_registry_service import TrustRegistryService
from app.config.auth_settings import AuthSettings
from app.domain.auth import AuthenticatedPrincipal, User
from app.domain.permissions import Role
from app.domain.persistence import AuditEventType, PersistedUser
from app.infrastructure.crypto.local_issuer_key_provider import (
    SYNTHETIC_ISSUER_DID,
)
from app.infrastructure.persistence.repositories import (
    MongoAuditEventRepository,
    MongoUserRepository,
)
from app.infrastructure.persistence.trust_registry_repository import (
    MongoTrustRegistryRepository,
)
from app.main import app
from tests.support.fake_mongo import FakeDatabase


NOW = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
ARGON_HASH = "$argon2id$v=19$m=19456,t=2,p=1$salt$hash"
ADMIN_ID = "64b64c0f0123456789abcdef"
ISSUER_ID = "74b64c0f0123456789abcdef"


class FakeIssuanceService:
    def __init__(self, supported_issuer: str = SYNTHETIC_ISSUER_DID) -> None:
        self.supported_issuer = supported_issuer

    def supports_issuer(self, issuer_did: str) -> bool:
        return issuer_did == self.supported_issuer


@pytest.fixture
def admin_client() -> Any:
    database = FakeDatabase()
    users = MongoUserRepository(database["users"])  # type: ignore[arg-type]
    audit = MongoAuditEventRepository(database["audit_events"])  # type: ignore[arg-type]
    trust_registry = TrustRegistryService(
        repository=MongoTrustRegistryRepository(database["trust_registry"]),  # type: ignore[arg-type]
        audit_repository=audit,
        clock=lambda: NOW,
    )
    trust_registry.seed_default_demo_issuers()
    current_principal = {
        "value": AuthenticatedPrincipal.from_user(
            User(
                id=ADMIN_ID,
                username="admin@example.test",
                display_name="Platform Admin",
                roles=(Role.ADMIN,),
            ),
            authentication_source="test",
        )
    }
    settings = AuthSettings(
        enabled=True,
        jwt_issuer="test-secure-ssi-identity",
        jwt_audience="identity-service",
        access_token_lifetime_seconds=900,
        jwt_algorithm="HS256",
        jwt_secret="integration-test-jwt-secret-at-least-thirty-two-bytes",
        environment="test",
        user_provider="mongodb",
    )

    app.dependency_overrides[get_current_principal] = (
        lambda: current_principal["value"]
    )
    app.dependency_overrides[get_auth_settings] = lambda: settings
    app.dependency_overrides[get_user_repository] = lambda: users
    app.dependency_overrides[get_audit_event_repository] = lambda: audit
    app.dependency_overrides[get_trust_registry_service] = lambda: trust_registry
    app.dependency_overrides[get_credential_issuance_api_service] = (
        lambda: FakeIssuanceService()
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        yield {
            "client": client,
            "users": users,
            "audit": audit,
            "principal": current_principal,
            "settings": settings,
        }
    app.dependency_overrides.clear()


def add_issuer_user(repository: MongoUserRepository) -> PersistedUser:
    record = PersistedUser(
        id=ISSUER_ID,
        username="issuer@example.test",
        display_name="Issuer account",
        roles=(Role.ISSUER,),
        enabled=True,
        password_hash=ARGON_HASH,
        created_at=NOW,
        updated_at=NOW,
    )
    return repository.add(record)


def test_admin_can_list_persistent_users_without_password_material(
    admin_client: dict[str, Any],
) -> None:
    add_issuer_user(admin_client["users"])

    response = admin_client["client"].get("/api/v1/admin/users")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["username"] == "issuer@example.test"
    assert response.json()[0]["roles"] == ["issuer"]
    assert "passwordHash" not in response.text
    assert "password_hash" not in response.text


def test_admin_can_bind_issuer_only_to_supported_trusted_institution(
    admin_client: dict[str, Any],
) -> None:
    add_issuer_user(admin_client["users"])

    response = admin_client["client"].put(
        f"/api/v1/admin/users/{ISSUER_ID}/issuer-scope",
        json={
            "issuerDid": SYNTHETIC_ISSUER_DID,
            "expectedVersion": 1,
        },
    )

    assert response.status_code == 200
    assert response.json()["issuerDid"] == SYNTHETIC_ISSUER_DID
    assert response.json()["issuerOrganizationName"] == "Demo Technical University"
    assert response.json()["version"] == 2
    persisted = admin_client["users"].get_by_id(ISSUER_ID)
    assert persisted is not None and persisted.issuer_did == SYNTHETIC_ISSUER_DID
    events = admin_client["audit"].list_recent(
        event_type=AuditEventType.USER_ISSUER_SCOPE_UPDATED,
        limit=10,
    )
    assert len(events) == 1
    assert events[0].actor_id == ADMIN_ID
    assert events[0].subject_id == ISSUER_ID


def test_admin_issuer_options_include_only_trusted_configured_signers(
    admin_client: dict[str, Any],
) -> None:
    response = admin_client["client"].get(
        "/api/v1/admin/users/issuer-options"
    )

    assert response.status_code == 200
    assert [option["issuerDid"] for option in response.json()] == [
        SYNTHETIC_ISSUER_DID
    ]


def test_admin_cannot_bind_untrusted_or_unconfigured_issuer(
    admin_client: dict[str, Any],
) -> None:
    add_issuer_user(admin_client["users"])
    empty = admin_client["client"].put(
        f"/api/v1/admin/users/{ISSUER_ID}/issuer-scope",
        json={"issuerDid": "   ", "expectedVersion": 1},
    )
    assert empty.status_code == 422
    untrusted = admin_client["client"].put(
        f"/api/v1/admin/users/{ISSUER_ID}/issuer-scope",
        json={"issuerDid": "did:web:unknown.example", "expectedVersion": 1},
    )
    assert untrusted.status_code == 403

    settings = admin_client["client"].app.dependency_overrides
    settings[get_credential_issuance_api_service] = (
        lambda: FakeIssuanceService(supported_issuer="did:web:other.example")
    )
    unsupported = admin_client["client"].put(
        f"/api/v1/admin/users/{ISSUER_ID}/issuer-scope",
        json={"issuerDid": SYNTHETIC_ISSUER_DID, "expectedVersion": 1},
    )
    assert unsupported.status_code == 409
    persisted = admin_client["users"].get_by_id(ISSUER_ID)
    assert persisted is not None and persisted.issuer_did is None


def test_admin_scope_endpoint_rejects_non_issuer_target_and_stale_version(
    admin_client: dict[str, Any],
) -> None:
    target = PersistedUser(
        id=ISSUER_ID,
        username="holder@example.test",
        display_name="Holder account",
        roles=(Role.HOLDER,),
        enabled=True,
        password_hash=ARGON_HASH,
        created_at=NOW,
        updated_at=NOW,
    )
    admin_client["users"].add(target)
    non_issuer = admin_client["client"].put(
        f"/api/v1/admin/users/{ISSUER_ID}/issuer-scope",
        json={"issuerDid": SYNTHETIC_ISSUER_DID, "expectedVersion": 1},
    )
    assert non_issuer.status_code == 409

    admin_client["users"].update(
        target,
        expected_version=1,
    )
    stale = admin_client["client"].put(
        f"/api/v1/admin/users/{ISSUER_ID}/issuer-scope",
        json={"issuerDid": None, "expectedVersion": 1},
    )
    assert stale.status_code == 409


@pytest.mark.parametrize("role", [Role.ISSUER, Role.VERIFIER, Role.HOLDER])
def test_non_admin_cannot_list_or_change_issuer_scopes(
    admin_client: dict[str, Any],
    role: Role,
) -> None:
    add_issuer_user(admin_client["users"])
    admin_client["principal"]["value"] = AuthenticatedPrincipal.from_user(
        User(
            id=ISSUER_ID,
            username=f"{role.value}@example.test",
            display_name=f"{role.value.title()} account",
            roles=(role,),
        ),
        authentication_source="test",
    )

    listing = admin_client["client"].get("/api/v1/admin/users")
    mutation = admin_client["client"].put(
        f"/api/v1/admin/users/{ISSUER_ID}/issuer-scope",
        json={"issuerDid": SYNTHETIC_ISSUER_DID, "expectedVersion": 1},
    )

    assert listing.status_code == 403
    assert mutation.status_code == 403
    persisted = admin_client["users"].get_by_id(ISSUER_ID)
    assert persisted is not None and persisted.issuer_did is None


def test_synthetic_identity_provider_does_not_expose_fixture_users_for_editing(
    admin_client: dict[str, Any],
) -> None:
    settings = admin_client["client"].app.dependency_overrides
    settings[get_auth_settings] = lambda: AuthSettings(
        enabled=True,
        jwt_issuer="test-secure-ssi-identity",
        jwt_audience="identity-service",
        access_token_lifetime_seconds=900,
        jwt_algorithm="HS256",
        jwt_secret="integration-test-jwt-secret-at-least-thirty-two-bytes",
        environment="test",
        user_provider="synthetic",
    )

    response = admin_client["client"].get("/api/v1/admin/users")

    assert response.status_code == 503
