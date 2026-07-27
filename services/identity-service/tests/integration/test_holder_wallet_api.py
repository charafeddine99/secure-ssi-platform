from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from app.api.v1.dependencies import (
    get_holder_presentation_service,
    get_holder_wallet_service,
    get_presentation_challenge_service,
    get_presentation_reconciliation_service,
    get_verifier_presentation_service,
)
from app.application.services.audit_outbox_service import (
    AuditOutboxDeliveryService,
)
from app.application.services.credential_issuance_service import (
    CredentialIssuanceService,
)
from app.application.services.holder_wallet_service import (
    HolderWalletService,
    PresentationChallengeService,
)
from app.application.services.internal_metrics import InternalMetrics
from app.application.services.presentation_proof_service import (
    PresentationBuilder,
    PresentationValidator,
)
from app.application.services.presentation_service import (
    HolderPresentationService,
    PresentationReconciliationService,
    VerifierPresentationService,
    build_credential_inspector,
)
from app.config.audit_outbox_settings import AuditOutboxSettings
from app.config.holder_wallet_settings import HolderWalletSettings
from app.config.status_list_settings import StatusListSettings
from app.domain.persistence import AuditEventType
from app.infrastructure.crypto.ed25519_signer import Ed25519CredentialSigner
from app.infrastructure.crypto.jcs_canonicalizer import JcsCanonicalizer
from app.infrastructure.crypto.local_holder_key_provider import (
    LocalDevelopmentHolderSigner,
    LocalHolderKeyProvider,
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
from app.infrastructure.persistence.holder_wallet_repositories import (
    MongoHolderWalletRepository,
    MongoPresentationChallengeRepository,
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


NOW = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)
PASSWORDS = {
    "admin": "Admin-Prototype-2026!",
    "issuer": "Issuer-Prototype-2026!",
    "verifier": "Verifier-Prototype-2026!",
    "holder": "Holder-Prototype-2026!",
}


class HolderWalletRuntime:
    def __init__(self) -> None:
        self.now = NOW
        self.sequence = 0
        self.wallet_sequence = 0
        self.challenge_sequence = 0
        self.credentials = FakeCollection(
            unique_fields=("credentialId",),
            unique_compounds=(("statusListId", "statusListIndex"),),
        )
        self.entries = FakeCollection(
            unique_fields=("credentialId",),
            unique_compounds=(("statusListId", "statusListIndex"),),
        )
        self.wallets = FakeCollection(
            unique_fields=("walletId", "holderDid", "keyReference"),
        )
        self.challenges = FakeCollection(
            unique_fields=("challengeId", "challenge"),
        )
        self.presentations = FakeCollection(
            unique_fields=("presentationId",),
            unique_compounds=(("challenge", "domain"),),
        )
        self.audit_events = FakeCollection()
        self.audit_outbox = FakeCollection()
        self.metrics = InternalMetrics()
        canonicalizer = JcsCanonicalizer()
        signer = Ed25519CredentialSigner()
        self.holder_keys = LocalHolderKeyProvider()
        wallet_repository = MongoHolderWalletRepository(
            cast(Any, self.wallets)
        )
        credential_repository = MongoCredentialRepository(
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
            metrics=self.metrics,
        )
        self.wallet_service = HolderWalletService(
            wallet_repository=wallet_repository,
            credential_repository=credential_repository,
            key_provider=self.holder_keys,
            audit_delivery_service=delivery,
            clock=lambda: self.now,
            storage_id_generator=self.next_id,
            wallet_id_generator=self.next_wallet_id,
            key_reference_generator=self.next_key_reference,
            metrics=self.metrics,
        )
        self.challenge_service = PresentationChallengeService(
            challenge_repository=MongoPresentationChallengeRepository(
                cast(Any, self.challenges)
            ),
            wallet_repository=wallet_repository,
            audit_delivery_service=delivery,
            clock=lambda: self.now,
            storage_id_generator=self.next_id,
            challenge_id_generator=self.next_challenge_id,
            challenge_value_generator=self.next_challenge_value,
            metrics=self.metrics,
        )
        status_settings = StatusListSettings(
            public_base_url="http://testserver/api/v1/status-lists"
        )
        entry_repository = MongoCredentialStatusEntryRepository(
            cast(Any, self.entries),
            cast(Any, self.credentials),
        )
        proof_service = build_local_proof_service(clock=lambda: self.now)
        self.issuance = CredentialIssuanceService(
            validator=CredentialProfileValidator(),
            signer=LocalIssuerSigningService(
                proof_service=proof_service,
                key_provider=LocalIssuerKeyProvider(),
            ),
            issuance_repository=MongoCredentialIssuanceRepository(
                cast(Any, self.credentials)
            ),
            entry_repository=entry_repository,
            canonicalizer=canonicalizer,
            settings=status_settings,
            clock=lambda: self.now,
            id_generator=self.next_id,
            wallet_repository=wallet_repository,
        )
        repository = MongoPresentationRepository(
            cast(Any, self.presentations),
            clock=lambda: self.now,
        )
        self.presentation_repository = repository
        inspector = build_credential_inspector(
            credential_repository=credential_repository,
            entry_repository=entry_repository,
            credential_proof_service=proof_service,
            canonicalizer=canonicalizer,
            status_list_settings=status_settings,
        )
        self.holder_service = HolderPresentationService(
            repository=repository,
            credential_inspector=inspector,
            builder=PresentationBuilder(
                canonicalizer=canonicalizer,
                signer=signer,
                key_provider=self.holder_keys,
                holder_signer=LocalDevelopmentHolderSigner(
                    self.holder_keys
                ),
                key_metadata_provider=self.holder_keys,
            ),
            audit_delivery_service=delivery,
            clock=lambda: self.now,
            id_generator=self.next_id,
            wallet_service=self.wallet_service,
            challenge_service=self.challenge_service,
        )
        self.verifier_service = VerifierPresentationService(
            repository=repository,
            credential_inspector=inspector,
            validator=PresentationValidator(
                canonicalizer=canonicalizer,
                signer=signer,
                key_provider=self.holder_keys,
                did_resolver=CompositeDidResolver(
                    {"key": DidKeyResolver()}
                ),
            ),
            canonicalizer=canonicalizer,
            audit_delivery_service=delivery,
            clock=lambda: self.now,
            challenge_service=self.challenge_service,
        )
        self.reconciliation_service = PresentationReconciliationService(
            repository=repository,
            verifier_service=self.verifier_service,
            challenge_service=self.challenge_service,
            audit_delivery_service=delivery,
            settings=HolderWalletSettings(
                reconciliation_stale_seconds=10
            ),
            clock=lambda: self.now,
            metrics=self.metrics,
            wallet_repository=wallet_repository,
            key_metadata_provider=self.holder_keys,
        )

    def next_id(self) -> str:
        self.sequence += 1
        return f"{self.sequence:024x}"

    def next_wallet_id(self) -> str:
        self.wallet_sequence += 1
        return f"wallet_{self.wallet_sequence:016d}"

    def next_key_reference(self) -> str:
        return f"local-dev:wallet:{self.wallet_sequence + 1:016d}"

    def next_challenge_id(self) -> str:
        self.challenge_sequence += 1
        return f"challenge_{self.challenge_sequence:016d}"

    def next_challenge_value(self) -> str:
        return f"challenge_nonce_{self.challenge_sequence:08d}"

    def issue(self, holder_did: str) -> dict[str, Any]:
        credential = load_unsigned_credential()
        credential["id"] = (
            f"urn:uuid:00000000-0000-4000-8000-{self.sequence + 1:012d}"
        )
        credential["credentialSubject"]["id"] = holder_did
        return self.issuance.issue(credential)


@pytest.fixture
def wallet_client() -> Iterator[tuple[TestClient, HolderWalletRuntime]]:
    runtime = HolderWalletRuntime()
    app.dependency_overrides[get_holder_wallet_service] = (
        lambda: runtime.wallet_service
    )
    app.dependency_overrides[get_presentation_challenge_service] = (
        lambda: runtime.challenge_service
    )
    app.dependency_overrides[get_holder_presentation_service] = (
        lambda: runtime.holder_service
    )
    app.dependency_overrides[get_verifier_presentation_service] = (
        lambda: runtime.verifier_service
    )
    app.dependency_overrides[get_presentation_reconciliation_service] = (
        lambda: runtime.reconciliation_service
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, runtime
    app.dependency_overrides.clear()


def _headers(client: TestClient, role: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/token",
        json={
            "username": f"{role}@example.test",
            "password": PASSWORDS[role],
        },
    )
    assert response.status_code == 200
    return {
        "Authorization": f"Bearer {response.json()['accessToken']}"
    }


def _wallet_and_credential(
    client: TestClient,
    runtime: HolderWalletRuntime,
) -> tuple[dict[str, Any], dict[str, Any]]:
    wallet_response = client.post(
        "/api/v1/wallets",
        json={},
        headers=_headers(client, "holder"),
    )
    assert wallet_response.status_code == 201, wallet_response.text
    wallet = wallet_response.json()
    credential = runtime.issue(wallet["holderDid"])
    return wallet, credential


def _challenge(
    client: TestClient,
    *,
    holder_did: str,
    lifetime_seconds: int = 300,
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/presentation-challenges",
        json={
            "domain": "verifier.example",
            "audience": "secure-ssi-verifier",
            "requestedHolderDid": holder_did,
            "lifetimeSeconds": lifetime_seconds,
        },
        headers=_headers(client, "verifier"),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_presentation(
    client: TestClient,
    *,
    wallet: dict[str, Any],
    credential: dict[str, Any],
    challenge: dict[str, Any],
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/presentations/create",
        json={
            "walletId": wallet["walletId"],
            "challengeId": challenge["challengeId"],
            "credentialIds": [credential["id"]],
            "lifetimeSeconds": 300,
        },
        headers=_headers(client, "holder"),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_wallet_challenge_presentation_flow_and_object_authorization(
    wallet_client: tuple[TestClient, HolderWalletRuntime],
) -> None:
    client, runtime = wallet_client
    wallet, credential = _wallet_and_credential(client, runtime)

    inventory = client.get(
        f"/api/v1/wallets/{wallet['walletId']}/credentials",
        headers=_headers(client, "holder"),
    )
    hidden_wallet = client.get(
        f"/api/v1/wallets/{wallet['walletId']}",
        headers=_headers(client, "admin"),
    )
    challenge = _challenge(client, holder_did=wallet["holderDid"])
    created = _create_presentation(
        client,
        wallet=wallet,
        credential=credential,
        challenge=challenge,
    )
    presentation = created["presentation"]
    hidden_presentation = client.get(
        f"/api/v1/presentations/{presentation['id']}",
        headers=_headers(client, "admin"),
    )
    verifier_read = client.get(
        f"/api/v1/presentations/{presentation['id']}",
        headers=_headers(client, "verifier"),
    )
    verified = client.post(
        "/api/v1/presentations/verify",
        json={"presentation": presentation},
        headers=_headers(client, "verifier"),
    )
    replay = client.post(
        "/api/v1/presentations/create",
        json={
            "walletId": wallet["walletId"],
            "challengeId": challenge["challengeId"],
            "credentialIds": [credential["id"]],
        },
        headers=_headers(client, "holder"),
    )

    assert inventory.status_code == 200
    assert inventory.json()["credentials"][0]["credentialId"] == (
        credential["id"]
    )
    assert hidden_wallet.status_code == 404
    assert hidden_presentation.status_code == 404
    assert verifier_read.status_code == 200
    assert presentation["proof"]["audience"] == "secure-ssi-verifier"
    assert verified.status_code == 200
    assert verified.json()["valid"] is True
    assert replay.status_code == 409
    assert replay.json()["error"]["code"] == (
        "PRESENTATION_CHALLENGE_REPLAY"
    )
    stored_credential = runtime.credentials.documents[0]
    assert stored_credential["walletId"] == wallet["walletId"]
    assert stored_credential["ownerUserId"] == "usr_local_holder"
    assert "privateKey" not in runtime.wallets.documents[0]


def test_locked_wallet_cross_credential_and_admin_reconciliation(
    wallet_client: tuple[TestClient, HolderWalletRuntime],
) -> None:
    client, runtime = wallet_client
    wallet, credential = _wallet_and_credential(client, runtime)
    challenge = _challenge(client, holder_did=wallet["holderDid"])
    created = _create_presentation(
        client,
        wallet=wallet,
        credential=credential,
        challenge=challenge,
    )
    presentation_id = created["presentation"]["id"]
    claimed = runtime.presentation_repository.claim_verification(
        presentation_id,
        expected_version=1,
    )
    assert claimed is not None
    runtime.now += timedelta(seconds=11)

    issuer_denied = client.post(
        f"/api/v1/presentations/{presentation_id}/reconcile",
        headers=_headers(client, "issuer"),
    )
    reconciled = client.post(
        f"/api/v1/presentations/{presentation_id}/reconcile",
        headers=_headers(client, "admin"),
    )
    repeated = client.post(
        f"/api/v1/presentations/{presentation_id}/reconcile",
        headers=_headers(client, "admin"),
    )

    assert issuer_denied.status_code == 403
    assert reconciled.status_code == 200
    assert reconciled.json()["metadata"]["verificationResult"] == "VERIFIED"
    assert reconciled.json()["metadata"]["reconciliationAttempts"] == 1
    assert repeated.status_code == 200
    events = runtime.audit_repository.list_recent(
        event_type=AuditEventType.PRESENTATION_RECONCILED
    )
    assert len(events) == 1
    snapshot = runtime.metrics.snapshot()
    assert snapshot.reconciliation_success_count == 1


def test_reconciliation_rejects_expired_challenge_evidence(
    wallet_client: tuple[TestClient, HolderWalletRuntime],
) -> None:
    client, runtime = wallet_client
    wallet, credential = _wallet_and_credential(client, runtime)
    challenge = _challenge(
        client,
        holder_did=wallet["holderDid"],
        lifetime_seconds=30,
    )
    created = _create_presentation(
        client,
        wallet=wallet,
        credential=credential,
        challenge=challenge,
    )
    presentation_id = created["presentation"]["id"]
    claimed = runtime.presentation_repository.claim_verification(
        presentation_id,
        expected_version=1,
    )
    assert claimed is not None
    runtime.now += timedelta(seconds=31)

    reconciled = client.post(
        f"/api/v1/presentations/{presentation_id}/reconcile",
        headers=_headers(client, "admin"),
    )

    assert reconciled.status_code == 200
    assert reconciled.json()["metadata"]["verificationResult"] == "REJECTED"
    assert reconciled.json()["metadata"]["rejectionCodes"] == [
        "RECONCILIATION_EVIDENCE_INCOMPLETE"
    ]


def test_locked_wallet_and_cross_wallet_credential_are_rejected(
    wallet_client: tuple[TestClient, HolderWalletRuntime],
) -> None:
    client, runtime = wallet_client
    wallet, _credential = _wallet_and_credential(client, runtime)
    other_wallet = runtime.wallet_service.create(
        owner_user_id="usr_other",
        correlation_id="other-wallet-create",
    )
    other_credential = runtime.issue(other_wallet.holder_did)
    challenge = _challenge(client, holder_did=wallet["holderDid"])

    cross_wallet = client.post(
        "/api/v1/presentations/create",
        json={
            "walletId": wallet["walletId"],
            "challengeId": challenge["challengeId"],
            "credentialIds": [other_credential["id"]],
        },
        headers=_headers(client, "holder"),
    )
    runtime.wallet_service.lock(
        wallet["walletId"],
        owner_user_id="usr_local_holder",
        correlation_id="wallet-lock",
    )
    locked = client.post(
        "/api/v1/presentations/create",
        json={
            "walletId": wallet["walletId"],
            "challengeId": challenge["challengeId"],
            "credentialIds": [other_credential["id"]],
        },
        headers=_headers(client, "holder"),
    )

    assert cross_wallet.status_code == 404
    assert cross_wallet.json()["error"]["code"] == (
        "HOLDER_WALLET_NOT_FOUND"
    )
    assert locked.status_code == 409
    assert locked.json()["error"]["code"] == "HOLDER_WALLET_UNAVAILABLE"
    ownership_events = runtime.audit_repository.list_recent(
        event_type=AuditEventType.HOLDER_OWNERSHIP_REJECTED
    )
    assert len(ownership_events) == 1


def test_challenge_binding_confusion_and_incomplete_reconciliation_fail_closed(
    wallet_client: tuple[TestClient, HolderWalletRuntime],
) -> None:
    client, runtime = wallet_client
    wallet, credential = _wallet_and_credential(client, runtime)
    challenge = _challenge(client, holder_did=wallet["holderDid"])

    confused = client.post(
        "/api/v1/presentations/create",
        json={
            "walletId": wallet["walletId"],
            "challengeId": challenge["challengeId"],
            "credentialIds": [credential["id"]],
            "domain": "other.example",
            "audience": "wrong-audience",
        },
        headers=_headers(client, "holder"),
    )
    assert confused.status_code == 409
    assert confused.json()["error"]["code"] == (
        "PRESENTATION_CHALLENGE_REJECTED"
    )

    second_challenge = _challenge(
        client,
        holder_did=wallet["holderDid"],
    )
    created = _create_presentation(
        client,
        wallet=wallet,
        credential=credential,
        challenge=second_challenge,
    )
    presentation_id = created["presentation"]["id"]
    claimed = runtime.presentation_repository.claim_verification(
        presentation_id,
        expected_version=1,
    )
    assert claimed is not None
    runtime.challenges.documents.clear()
    runtime.now += timedelta(seconds=11)

    reconciled = client.post(
        f"/api/v1/presentations/{presentation_id}/reconcile",
        headers=_headers(client, "admin"),
    )

    assert reconciled.status_code == 200
    assert reconciled.json()["metadata"]["verificationResult"] == "REJECTED"
    assert reconciled.json()["metadata"]["rejectionCodes"] == [
        "RECONCILIATION_EVIDENCE_INCOMPLETE"
    ]
    failed = runtime.audit_repository.list_recent(
        event_type=AuditEventType.PRESENTATION_RECONCILIATION_FAILED
    )
    assert len(failed) == 1


def test_wallet_challenge_openapi_contracts_are_authenticated(
    wallet_client: tuple[TestClient, HolderWalletRuntime],
) -> None:
    client, _ = wallet_client
    paths = client.get("/openapi.json").json()["paths"]

    for path, method in (
        ("/api/v1/wallets", "post"),
        ("/api/v1/wallets/{wallet_id}", "get"),
        ("/api/v1/wallets/{wallet_id}/credentials", "get"),
        ("/api/v1/presentation-challenges", "post"),
        (
            "/api/v1/presentation-challenges/{challenge_id}",
            "get",
        ),
        (
            "/api/v1/presentations/{presentation_id}/reconcile",
            "post",
        ),
    ):
        assert paths[path][method]["security"] == [{"BearerAuth": []}]
