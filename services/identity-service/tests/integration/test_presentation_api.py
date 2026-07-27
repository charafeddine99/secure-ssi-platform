import copy
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from app.api.v1.dependencies import (
    get_clock,
    get_holder_presentation_service,
    get_verifier_presentation_service,
)
from app.application.services.audit_outbox_service import (
    AuditOutboxDeliveryService,
)
from app.application.services.credential_issuance_service import (
    CredentialIssuanceService,
)
from app.application.services.presentation_proof_service import (
    PresentationBuilder,
    PresentationValidator,
)
from app.application.services.presentation_service import (
    HolderPresentationService,
    VerifierPresentationService,
    build_credential_inspector,
)
from app.config.audit_outbox_settings import AuditOutboxSettings
from app.config.status_list_settings import StatusListSettings
from app.domain.persistence import AuditEventType
from app.infrastructure.crypto.ed25519_signer import Ed25519CredentialSigner
from app.infrastructure.crypto.jcs_canonicalizer import JcsCanonicalizer
from app.infrastructure.crypto.local_holder_key_provider import (
    LocalHolderKeyProvider,
    SYNTHETIC_HOLDER_DID,
)
from app.infrastructure.crypto.local_issuer_key_provider import (
    LocalIssuerKeyProvider,
)
from app.infrastructure.crypto.local_issuer_signing_service import (
    LocalIssuerSigningService,
)
from app.infrastructure.fixtures.signed_credentials import (
    build_local_proof_service,
    load_unsigned_credential,
)
from app.infrastructure.persistence.audit_outbox_repository import (
    MongoAuditOutboxRepository,
)
from app.infrastructure.persistence.issuance_repository import (
    MongoCredentialIssuanceRepository,
)
from app.infrastructure.persistence.presentation_repository import (
    MongoPresentationRepository,
)
from app.infrastructure.persistence.repositories import (
    MongoAuditEventRepository,
    MongoCredentialRepository,
)
from app.infrastructure.persistence.status_list_repositories import (
    MongoCredentialStatusEntryRepository,
)
from app.main import app
from app.services.credential_validator import CredentialProfileValidator
from app.services.did_resolver import CompositeDidResolver, DidKeyResolver
from tests.support.fake_mongo import FakeCollection


NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
PASSWORDS = {
    "holder": "Holder-Prototype-2026!",
    "verifier": "Verifier-Prototype-2026!",
}


class PresentationRuntime:
    def __init__(self) -> None:
        self.now = NOW
        self.sequence = 0
        self.credentials = FakeCollection(
            unique_fields=("credentialId",),
            unique_compounds=(("statusListId", "statusListIndex"),),
        )
        self.entries = FakeCollection(
            unique_fields=("credentialId",),
            unique_compounds=(("statusListId", "statusListIndex"),),
        )
        self.presentations = FakeCollection(
            unique_fields=("presentationId",),
            unique_compounds=(("challenge", "domain"),),
        )
        self.audit_events = FakeCollection()
        self.audit_outbox = FakeCollection()
        canonicalizer = JcsCanonicalizer()
        signer = Ed25519CredentialSigner()
        issuer_keys = LocalIssuerKeyProvider()
        holder_keys = LocalHolderKeyProvider()
        self.status_settings = StatusListSettings(
            public_base_url="http://testserver/api/v1/status-lists"
        )
        self.entry_repository = MongoCredentialStatusEntryRepository(
            cast(Any, self.entries),
            cast(Any, self.credentials),
        )
        proof_service = build_local_proof_service(
            clock=lambda: self.now
        )
        issuance = CredentialIssuanceService(
            validator=CredentialProfileValidator(),
            signer=LocalIssuerSigningService(
                proof_service=proof_service,
                key_provider=issuer_keys,
            ),
            issuance_repository=MongoCredentialIssuanceRepository(
                cast(Any, self.credentials)
            ),
            entry_repository=self.entry_repository,
            canonicalizer=canonicalizer,
            settings=self.status_settings,
            clock=lambda: self.now,
            id_generator=self.next_id,
        )
        self.issued = tuple(
            issuance.issue(self._unsigned(index))
            for index in (1, 2)
        )
        self.credential_repository = MongoCredentialRepository(
            cast(Any, self.credentials)
        )
        self.audit_repository = MongoAuditEventRepository(
            cast(Any, self.audit_events)
        )
        delivery = AuditOutboxDeliveryService(
            outbox_repository=MongoAuditOutboxRepository(
                cast(Any, self.audit_outbox),
                cast(Any, self.credentials),
            ),
            audit_repository=self.audit_repository,
            settings=AuditOutboxSettings(),
            clock=lambda: self.now,
        )
        repository = MongoPresentationRepository(
            cast(Any, self.presentations),
            clock=lambda: self.now,
        )
        inspector = build_credential_inspector(
            credential_repository=self.credential_repository,
            entry_repository=self.entry_repository,
            credential_proof_service=proof_service,
            canonicalizer=canonicalizer,
            status_list_settings=self.status_settings,
        )
        self.holder_service = HolderPresentationService(
            repository=repository,
            credential_inspector=inspector,
            builder=PresentationBuilder(
                canonicalizer=canonicalizer,
                signer=signer,
                key_provider=holder_keys,
            ),
            audit_delivery_service=delivery,
            clock=lambda: self.now,
            id_generator=self.next_id,
        )
        self.verifier_service = VerifierPresentationService(
            repository=repository,
            credential_inspector=inspector,
            validator=PresentationValidator(
                canonicalizer=canonicalizer,
                signer=signer,
                key_provider=holder_keys,
                did_resolver=CompositeDidResolver(
                    {"key": DidKeyResolver()}
                ),
            ),
            canonicalizer=canonicalizer,
            audit_delivery_service=delivery,
            clock=lambda: self.now,
        )

    def next_id(self) -> str:
        self.sequence += 1
        return f"{self.sequence:024x}"

    @staticmethod
    def _unsigned(index: int) -> dict[str, Any]:
        credential = load_unsigned_credential()
        credential["id"] = (
            f"urn:uuid:00000000-0000-4000-8000-{index:012d}"
        )
        credential["credentialSubject"]["id"] = SYNTHETIC_HOLDER_DID
        return credential

    def revoke(self, credential_id: str) -> None:
        document = self.credentials.find_one(
            {"credentialId": credential_id}
        )
        assert document is not None
        document["status"] = "REVOKED"
        document["revokedAt"] = self.now
        document["revokedBy"] = "usr_local_issuer"
        document["revocationReason"] = "Test revocation"
        document["updatedAt"] = self.now
        document["version"] += 1
        index = next(
            index
            for index, item in enumerate(self.credentials.documents)
            if item["credentialId"] == credential_id
        )
        self.credentials.documents[index] = document


@pytest.fixture
def presentation_client() -> Iterator[
    tuple[TestClient, PresentationRuntime]
]:
    runtime = PresentationRuntime()
    app.dependency_overrides[get_clock] = lambda: (lambda: runtime.now)
    app.dependency_overrides[get_holder_presentation_service] = (
        lambda: runtime.holder_service
    )
    app.dependency_overrides[get_verifier_presentation_service] = (
        lambda: runtime.verifier_service
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, runtime
    app.dependency_overrides.clear()


def _headers(client: TestClient, role: str) -> dict[str, str]:
    token = client.post(
        "/api/v1/auth/token",
        json={
            "username": f"{role}@example.test",
            "password": PASSWORDS[role],
        },
    )
    assert token.status_code == 200
    return {"Authorization": f"Bearer {token.json()['accessToken']}"}


def _create(
    client: TestClient,
    runtime: PresentationRuntime,
    *,
    count: int = 1,
    challenge: str = "challenge_nonce_00000001",
    lifetime_seconds: int = 300,
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/presentations/create",
        json={
            "credentialIds": [
                credential["id"]
                for credential in runtime.issued[:count]
            ],
            "challenge": challenge,
            "domain": "verifier.example",
            "lifetimeSeconds": lifetime_seconds,
        },
        headers={
            **_headers(client, "holder"),
            "x-request-id": "presentation-create-1",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_verify_get_and_audit_multi_credential_presentation(
    presentation_client: tuple[TestClient, PresentationRuntime],
) -> None:
    client, runtime = presentation_client
    created = _create(client, runtime, count=2)
    presentation = created["presentation"]
    presentation_id = presentation["id"]

    verified = client.post(
        "/api/v1/presentations/verify",
        json={
            "presentation": presentation,
            "expectedChallenge": "challenge_nonce_00000001",
            "expectedDomain": "verifier.example",
        },
        headers={
            **_headers(client, "verifier"),
            "x-request-id": "presentation-verify-1",
        },
    )
    fetched = client.get(
        f"/api/v1/presentations/{presentation_id}",
        headers=_headers(client, "verifier"),
    )

    assert verified.status_code == 200
    assert verified.json()["valid"] is True
    assert verified.json()["errors"] == []
    assert len(verified.json()["credentialIds"]) == 2
    assert fetched.status_code == 200
    assert fetched.json()["metadata"]["verificationResult"] == "VERIFIED"
    assert fetched.json()["metadata"]["version"] == 3
    assert presentation["holder"] == SYNTHETIC_HOLDER_DID
    assert presentation["proof"]["challenge"] == (
        "challenge_nonce_00000001"
    )
    events = runtime.audit_repository.list_recent()
    assert {event.event_type for event in events} == {
        AuditEventType.PRESENTATION_CREATED,
        AuditEventType.PRESENTATION_VERIFIED,
    }
    assert all(event.subject_id == presentation_id for event in events)


def test_replay_is_rejected_after_one_verification(
    presentation_client: tuple[TestClient, PresentationRuntime],
) -> None:
    client, runtime = presentation_client
    created = _create(client, runtime)
    payload = {
        "presentation": created["presentation"],
        "expectedChallenge": "challenge_nonce_00000001",
        "expectedDomain": "verifier.example",
    }
    headers = _headers(client, "verifier")

    first = client.post(
        "/api/v1/presentations/verify",
        json=payload,
        headers=headers,
    )
    replay = client.post(
        "/api/v1/presentations/verify",
        json=payload,
        headers=headers,
    )

    assert first.status_code == 200
    assert replay.status_code == 409
    assert replay.json()["error"]["code"] == (
        "PRESENTATION_REPLAY_DETECTED"
    )
    assert len(
        runtime.audit_repository.list_recent(
            event_type=AuditEventType.PRESENTATION_VERIFIED
        )
    ) == 1


def test_wrong_challenge_consumes_nonce_and_records_rejection(
    presentation_client: tuple[TestClient, PresentationRuntime],
) -> None:
    client, runtime = presentation_client
    created = _create(client, runtime)

    response = client.post(
        "/api/v1/presentations/verify",
        json={
            "presentation": created["presentation"],
            "expectedChallenge": "wrong_challenge_00000001",
            "expectedDomain": "verifier.example",
        },
        headers=_headers(client, "verifier"),
    )

    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert "CHALLENGE_MISMATCH" in response.json()["errors"]
    rejected = runtime.audit_repository.list_recent(
        event_type=AuditEventType.PRESENTATION_REJECTED
    )
    assert len(rejected) == 1


def test_tampered_proof_and_holder_binding_are_rejected(
    presentation_client: tuple[TestClient, PresentationRuntime],
) -> None:
    client, runtime = presentation_client
    created = _create(client, runtime)
    tampered = copy.deepcopy(created["presentation"])
    tampered["verifiableCredential"][0]["credentialSubject"]["id"] = (
        "did:key:zTamperedHolder"
    )

    response = client.post(
        "/api/v1/presentations/verify",
        json={
            "presentation": tampered,
            "expectedChallenge": "challenge_nonce_00000001",
            "expectedDomain": "verifier.example",
        },
        headers=_headers(client, "verifier"),
    )

    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert "PRESENTATION_CONTENT_MISMATCH" in response.json()["errors"]
    assert "CREDENTIAL_CONTENT_MISMATCH" in response.json()["errors"]


def test_revoked_credential_is_rejected_at_verification(
    presentation_client: tuple[TestClient, PresentationRuntime],
) -> None:
    client, runtime = presentation_client
    created = _create(client, runtime)
    runtime.revoke(runtime.issued[0]["id"])

    response = client.post(
        "/api/v1/presentations/verify",
        json={
            "presentation": created["presentation"],
            "expectedChallenge": "challenge_nonce_00000001",
            "expectedDomain": "verifier.example",
        },
        headers=_headers(client, "verifier"),
    )

    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert "CREDENTIAL_REVOKED" in response.json()["errors"]


def test_expired_presentation_is_rejected(
    presentation_client: tuple[TestClient, PresentationRuntime],
) -> None:
    client, runtime = presentation_client
    created = _create(client, runtime, lifetime_seconds=30)
    runtime.now += timedelta(seconds=31)

    response = client.post(
        "/api/v1/presentations/verify",
        json={
            "presentation": created["presentation"],
            "expectedChallenge": "challenge_nonce_00000001",
            "expectedDomain": "verifier.example",
        },
        headers=_headers(client, "verifier"),
    )

    assert response.status_code == 200
    assert "PRESENTATION_EXPIRED" in response.json()["errors"]


def test_rbac_validation_and_openapi_contract(
    presentation_client: tuple[TestClient, PresentationRuntime],
) -> None:
    client, runtime = presentation_client
    verifier_create = client.post(
        "/api/v1/presentations/create",
        json={
            "credentialIds": [runtime.issued[0]["id"]],
            "challenge": "challenge_nonce_00000001",
            "domain": "verifier.example",
        },
        headers=_headers(client, "verifier"),
    )
    invalid_challenge = client.post(
        "/api/v1/presentations/create",
        json={
            "credentialIds": [runtime.issued[0]["id"]],
            "challenge": "short",
            "domain": "verifier.example",
        },
        headers=_headers(client, "holder"),
    )
    created = _create(
        client,
        runtime,
        challenge="challenge_nonce_00000002",
    )
    holder_verify = client.post(
        "/api/v1/presentations/verify",
        json={
            "presentation": created["presentation"],
            "expectedChallenge": "challenge_nonce_00000002",
            "expectedDomain": "verifier.example",
        },
        headers=_headers(client, "holder"),
    )
    paths = client.get("/openapi.json").json()["paths"]

    assert verifier_create.status_code == 403
    assert invalid_challenge.status_code == 422
    assert holder_verify.status_code == 403
    assert paths["/api/v1/presentations/create"]["post"]["security"] == [
        {"BearerAuth": []}
    ]
    assert paths["/api/v1/presentations/verify"]["post"]["security"] == [
        {"BearerAuth": []}
    ]
    assert paths[
        "/api/v1/presentations/{presentation_id}"
    ]["get"]["security"] == [{"BearerAuth": []}]


def test_missing_credential_and_unsafe_transport_are_rejected(
    presentation_client: tuple[TestClient, PresentationRuntime],
) -> None:
    client, _ = presentation_client
    holder_headers = {
        **_headers(client, "holder"),
        "content-type": "application/json",
    }
    missing = client.post(
        "/api/v1/presentations/create",
        json={
            "credentialIds": ["urn:uuid:missing"],
            "challenge": "challenge_nonce_00000001",
            "domain": "verifier.example",
        },
        headers=holder_headers,
    )
    duplicate = client.post(
        "/api/v1/presentations/create",
        content=(
            '{"credentialIds":["urn:uuid:missing"],'
            '"challenge":"challenge_nonce_00000001",'
            '"challenge":"challenge_nonce_00000002",'
            '"domain":"verifier.example"}'
        ),
        headers=holder_headers,
    )
    oversized = client.post(
        "/api/v1/presentations/verify",
        content=b"x" * 69_633,
        headers={
            **_headers(client, "verifier"),
            "content-type": "application/json",
        },
    )

    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == (
        "PRESENTATION_CREDENTIAL_REJECTED"
    )
    assert duplicate.status_code == 400
    assert duplicate.json()["error"]["code"] == "DUPLICATE_JSON_PROPERTY"
    assert oversized.status_code == 413
    assert oversized.json()["error"]["code"] == "REQUEST_TOO_LARGE"
