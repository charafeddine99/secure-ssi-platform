from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from app.api.v1.dependencies import (
    get_clock,
    get_credential_revocation_service,
    get_status_list_service,
)
from app.application.services.credential_revocation_service import (
    CredentialRevocationService,
)
from app.application.services.audit_outbox_service import (
    AuditOutboxDeliveryService,
)
from app.application.services.status_list_service import StatusListService
from app.config.audit_outbox_settings import AuditOutboxSettings
from app.config.status_list_settings import StatusListSettings
from app.domain.credential_status import CredentialStatus
from app.domain.bitstring_status_list import generate_status_list_id
from app.domain.persistence import AuditEventType, PersistedCredential
from app.infrastructure.persistence.repositories import (
    MongoAuditEventRepository,
    MongoCredentialRepository,
    MongoRevocationRepository,
)
from app.infrastructure.crypto.ed25519_signer import Ed25519CredentialSigner
from app.infrastructure.crypto.jcs_canonicalizer import JcsCanonicalizer
from app.infrastructure.crypto.local_issuer_key_provider import (
    LocalIssuerKeyProvider,
    SYNTHETIC_ISSUER_DID,
)
from app.infrastructure.persistence.audit_outbox_repository import (
    MongoAuditOutboxRepository,
)
from app.infrastructure.persistence.status_list_repositories import (
    MongoCredentialStatusEntryRepository,
    MongoStatusListRepository,
)
from app.infrastructure.status_list_document_generator import (
    StatusListDocumentGenerator,
)
from app.main import app
from tests.support.fake_mongo import FakeCollection


NOW = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
CREDENTIAL_ID = "urn:uuid:credential-revocation-test"
PASSWORDS = {
    "admin": "Admin-Prototype-2026!",
    "issuer": "Issuer-Prototype-2026!",
    "verifier": "Verifier-Prototype-2026!",
}


class RevocationRuntime:
    def __init__(self) -> None:
        credential_collection = FakeCollection(
            unique_fields=("credentialId",)
        )
        audit_collection = FakeCollection()
        entry_collection = FakeCollection(
            unique_fields=("credentialId",),
            unique_compounds=(("statusListId", "statusListIndex"),),
        )
        status_list_collection = FakeCollection(
            unique_fields=("statusListId",)
        )
        outbox_collection = FakeCollection()
        self.credential_repository = MongoCredentialRepository(
            cast(Any, credential_collection)
        )
        self.revocation_repository = MongoRevocationRepository(
            cast(Any, credential_collection)
        )
        self.audit_repository = MongoAuditEventRepository(
            cast(Any, audit_collection)
        )
        self.event_sequence = 0
        self.status_list_service = StatusListService(
            entry_repository=MongoCredentialStatusEntryRepository(
                cast(Any, entry_collection),
                cast(Any, credential_collection),
            ),
            status_list_repository=MongoStatusListRepository(
                cast(Any, status_list_collection)
            ),
            generator=StatusListDocumentGenerator(
                canonicalizer=JcsCanonicalizer(),
                signer=Ed25519CredentialSigner(),
                key_provider=LocalIssuerKeyProvider(),
            ),
            settings=StatusListSettings(
                public_base_url=(
                    "http://testserver/api/v1/status-lists"
                )
            ),
            clock=lambda: NOW,
            id_generator=self.next_event_id,
        )
        delivery = AuditOutboxDeliveryService(
            outbox_repository=MongoAuditOutboxRepository(
                cast(Any, outbox_collection),
                cast(Any, credential_collection),
            ),
            audit_repository=self.audit_repository,
            settings=AuditOutboxSettings(),
            clock=lambda: NOW,
        )
        self.service = CredentialRevocationService(
            revocation_repository=self.revocation_repository,
            status_list_service=self.status_list_service,
            audit_delivery_service=delivery,
            clock=lambda: NOW,
            event_id_generator=self.next_event_id,
        )
        self.credential_repository.add(
            PersistedCredential(
                id="64b64c0f0123456789abcdef",
                credential_id=CREDENTIAL_ID,
                issuer_did=SYNTHETIC_ISSUER_DID,
                holder_did="did:key:zholder",
                credential_type=(
                    "VerifiableCredential",
                    "UniversityAffiliationCredential",
                ),
                issuance_date=NOW - timedelta(days=1),
                expiration_date=NOW + timedelta(days=365),
                credential_hash="a" * 64,
                status=CredentialStatus.ACTIVE,
                raw_credential={"id": CREDENTIAL_ID},
                created_at=NOW - timedelta(days=1),
                updated_at=NOW - timedelta(days=1),
            )
        )

    def next_event_id(self) -> str:
        self.event_sequence += 1
        return f"{self.event_sequence:024x}"


@pytest.fixture
def revocation_client() -> Iterator[tuple[TestClient, RevocationRuntime]]:
    runtime = RevocationRuntime()
    app.dependency_overrides[get_clock] = lambda: (lambda: NOW)
    app.dependency_overrides[get_credential_revocation_service] = (
        lambda: runtime.service
    )
    app.dependency_overrides[get_status_list_service] = (
        lambda: runtime.status_list_service
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, runtime
    app.dependency_overrides.clear()


def auth_headers(client: TestClient, role: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/token",
        json={
            "username": f"{role}@example.test",
            "password": PASSWORDS[role],
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def test_public_status_lookup_returns_required_contract_and_audits(
    revocation_client: tuple[TestClient, RevocationRuntime],
) -> None:
    client, runtime = revocation_client

    response = client.get(
        f"/api/v1/credentials/{CREDENTIAL_ID}/status",
        headers={"x-request-id": "status-request-1"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "credentialId": CREDENTIAL_ID,
        "status": "ACTIVE",
        "revoked": False,
        "revocationReason": None,
        "revokedAt": None,
        "revokedBy": None,
    }
    events = runtime.audit_repository.list_recent()
    assert len(events) == 1
    assert events[0].event_type is AuditEventType.STATUS_CHECKED
    assert events[0].subject_id == CREDENTIAL_ID
    assert events[0].actor_id is None
    assert events[0].correlation_id == "status-request-1"


@pytest.mark.parametrize("role", ["admin", "issuer"])
def test_admin_and_issuer_can_revoke_exactly_once(
    revocation_client: tuple[TestClient, RevocationRuntime],
    role: str,
) -> None:
    client, runtime = revocation_client
    headers = {
        **auth_headers(client, role),
        "x-request-id": f"revoke-{role}-1",
    }

    first = client.post(
        f"/api/v1/credentials/{CREDENTIAL_ID}/revoke",
        json={"reason": "  Affiliation ended  "},
        headers=headers,
    )
    second = client.post(
        f"/api/v1/credentials/{CREDENTIAL_ID}/revoke",
        json={"reason": "Second attempt"},
        headers=auth_headers(client, role),
    )

    assert first.status_code == 200
    assert first.json() == {
        "credentialId": CREDENTIAL_ID,
        "status": "REVOKED",
        "revoked": True,
        "revocationReason": "Affiliation ended",
        "revokedAt": "2026-07-24T12:00:00Z",
        "revokedBy": f"usr_local_{role}",
    }
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "CREDENTIAL_ALREADY_REVOKED"
    stored = runtime.credential_repository.get_by_credential_id(
        CREDENTIAL_ID
    )
    assert stored is not None
    assert stored.status is CredentialStatus.REVOKED
    assert stored.version == 2
    events = runtime.audit_repository.list_recent(
        event_type=AuditEventType.CREDENTIAL_REVOKED
    )
    assert len(events) == 1
    assert events[0].actor_id == f"usr_local_{role}"
    assert events[0].correlation_id == f"revoke-{role}-1"


def test_verifier_and_anonymous_user_cannot_revoke(
    revocation_client: tuple[TestClient, RevocationRuntime],
) -> None:
    client, runtime = revocation_client

    verifier = client.post(
        f"/api/v1/credentials/{CREDENTIAL_ID}/revoke",
        json={"reason": "Not allowed"},
        headers=auth_headers(client, "verifier"),
    )
    anonymous = client.post(
        f"/api/v1/credentials/{CREDENTIAL_ID}/revoke",
        json={"reason": "Not authenticated"},
    )

    assert verifier.status_code == 403
    assert verifier.json()["error"]["code"] == "PERMISSION_DENIED"
    assert anonymous.status_code == 401
    assert anonymous.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    stored = runtime.credential_repository.get_by_credential_id(
        CREDENTIAL_ID
    )
    assert stored is not None
    assert stored.status is CredentialStatus.ACTIVE
    assert runtime.audit_repository.list_recent() == ()


def test_revocation_and_status_missing_credential_return_safe_404(
    revocation_client: tuple[TestClient, RevocationRuntime],
) -> None:
    client, _ = revocation_client

    status_response = client.get(
        "/api/v1/credentials/urn:uuid:missing/status"
    )
    revoke_response = client.post(
        "/api/v1/credentials/urn:uuid:missing/revoke",
        json={"reason": "Missing"},
        headers=auth_headers(client, "issuer"),
    )

    assert status_response.status_code == 404
    assert status_response.json()["error"]["code"] == "CREDENTIAL_NOT_FOUND"
    assert revoke_response.status_code == 404
    assert revoke_response.json()["error"]["code"] == "CREDENTIAL_NOT_FOUND"


@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [
        ({"reason": "   "}, 422),
        ({"reason": "x" * 501}, 422),
        ({"reason": "valid", "unexpected": True}, 422),
    ],
)
def test_revocation_request_is_strictly_validated(
    revocation_client: tuple[TestClient, RevocationRuntime],
    payload: dict[str, object],
    expected_status: int,
) -> None:
    client, _ = revocation_client

    response = client.post(
        f"/api/v1/credentials/{CREDENTIAL_ID}/revoke",
        json=payload,
        headers=auth_headers(client, "issuer"),
    )

    assert response.status_code == expected_status
    assert response.json()["error"]["code"] == "REQUEST_VALIDATION_FAILED"


def test_revocation_transport_rejects_duplicate_and_oversized_json(
    revocation_client: tuple[TestClient, RevocationRuntime],
) -> None:
    client, _ = revocation_client
    headers = {
        **auth_headers(client, "issuer"),
        "content-type": "application/json",
    }

    duplicate = client.post(
        f"/api/v1/credentials/{CREDENTIAL_ID}/revoke",
        content='{"reason":"one","reason":"two"}',
        headers=headers,
    )
    oversized = client.post(
        f"/api/v1/credentials/{CREDENTIAL_ID}/revoke",
        content='{"reason":"' + "x" * 4_100 + '"}',
        headers=headers,
    )

    assert duplicate.status_code == 400
    assert duplicate.json()["error"]["code"] == "DUPLICATE_JSON_PROPERTY"
    assert oversized.status_code == 413
    assert oversized.json()["error"]["code"] == "REQUEST_TOO_LARGE"


def test_openapi_describes_status_contract_security_and_errors(
    revocation_client: tuple[TestClient, RevocationRuntime],
) -> None:
    client, _ = revocation_client
    paths = client.get("/openapi.json").json()["paths"]
    revoke = paths[
        "/api/v1/credentials/{credential_id}/revoke"
    ]["post"]
    status = paths[
        "/api/v1/credentials/{credential_id}/status"
    ]["get"]

    assert revoke["security"] == [{"BearerAuth": []}]
    assert "security" not in status
    assert {
        "200",
        "400",
        "401",
        "403",
        "404",
        "409",
        "413",
        "422",
        "500",
        "503",
    } <= set(revoke["responses"])
    assert {"200", "404", "409", "500", "503"} <= set(
        status["responses"]
    )


def test_revocation_is_published_in_cacheable_status_list(
    revocation_client: tuple[TestClient, RevocationRuntime],
) -> None:
    client, _ = revocation_client
    revoke = client.post(
        f"/api/v1/credentials/{CREDENTIAL_ID}/revoke",
        json={"reason": "Affiliation ended"},
        headers=auth_headers(client, "issuer"),
    )
    assert revoke.status_code == 200
    status_list_id = generate_status_list_id(SYNTHETIC_ISSUER_DID)

    publication = client.get(
        f"/api/v1/status-lists/{status_list_id}"
    )
    metadata = client.get(
        f"/api/v1/status-lists/{status_list_id}/metadata"
    )
    cached = client.get(
        f"/api/v1/status-lists/{status_list_id}",
        headers={"If-None-Match": publication.headers["etag"]},
    )

    assert publication.status_code == 200
    assert publication.headers["content-type"].startswith(
        "application/vc+ld+json"
    )
    document = publication.json()
    assert document["type"] == [
        "VerifiableCredential",
        "BitstringStatusListCredential",
    ]
    assert document["credentialSubject"]["statusPurpose"] == "revocation"
    assert document["credentialSubject"]["encodedList"].startswith("u")
    assert metadata.status_code == 200
    assert metadata.json()["revokedEntries"] == 1
    assert metadata.json()["assignedEntries"] == 1
    assert metadata.json()["capacity"] == 131072
    assert metadata.json()["active"] is True
    assert metadata.json()["utilization"] == pytest.approx(1 / 131072)
    assert metadata.json()["version"] == 1
    assert metadata.headers["etag"] == publication.headers["etag"]
    assert cached.status_code == 304
    assert cached.content == b""


def test_status_list_history_and_immutable_version_are_public(
    revocation_client: tuple[TestClient, RevocationRuntime],
) -> None:
    client, _ = revocation_client
    client.post(
        f"/api/v1/credentials/{CREDENTIAL_ID}/revoke",
        json={"reason": "Affiliation ended"},
        headers=auth_headers(client, "issuer"),
    )
    status_list_id = generate_status_list_id(SYNTHETIC_ISSUER_DID)
    current = client.get(f"/api/v1/status-lists/{status_list_id}")

    history = client.get(
        f"/api/v1/status-lists/{status_list_id}/history"
    )
    version = client.get(
        f"/api/v1/status-lists/{status_list_id}/versions/1"
    )
    missing = client.get(
        f"/api/v1/status-lists/{status_list_id}/versions/2"
    )

    assert history.status_code == 200
    assert history.json()["latestVersion"] == 1
    assert history.json()["versions"][0]["etag"] == current.headers["etag"]
    assert version.status_code == 200
    assert version.json() == current.json()
    assert version.headers["cache-control"].endswith("immutable")
    assert version.headers["x-status-list-version"] == "1"
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == (
        "STATUS_LIST_VERSION_NOT_FOUND"
    )


def test_status_list_openapi_contract_is_public(
    revocation_client: tuple[TestClient, RevocationRuntime],
) -> None:
    client, _ = revocation_client
    paths = client.get("/openapi.json").json()["paths"]
    publication = paths["/api/v1/status-lists/{status_list_id}"]["get"]
    metadata = paths[
        "/api/v1/status-lists/{status_list_id}/metadata"
    ]["get"]
    history = paths[
        "/api/v1/status-lists/{status_list_id}/history"
    ]["get"]
    version = paths[
        "/api/v1/status-lists/{status_list_id}/versions/{version}"
    ]["get"]

    assert "security" not in publication
    assert "security" not in metadata
    assert "security" not in history
    assert "security" not in version
    assert {"200", "304", "404", "409", "500", "503"} <= set(
        publication["responses"]
    )
    assert {"200", "404", "409", "500", "503"} <= set(
        metadata["responses"]
    )
