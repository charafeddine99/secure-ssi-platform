import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from bson import ObjectId

from app.config.mongo_settings import MongoSettings
from app.domain.audit_outbox import AuditOutboxRecord, AuditOutboxSource
from app.domain.bitstring_status_list import (
    StatusPurpose,
    generate_status_list_id,
)
from app.domain.credential_status import (
    CredentialAlreadyRevokedError,
    CredentialStatus,
)
from app.domain.permissions import Role
from app.domain.managed_key import (
    KeyAlgorithm,
    KeyPurpose,
    ManagedKey,
    ManagedKeyState,
)
from app.domain.holder_wallet import HolderWallet, WalletStatus
from app.domain.presentation_challenge import (
    ChallengeStatus,
    PresentationChallenge,
)
from app.domain.persistence import (
    AuditEvent,
    AuditEventType,
    OptimisticLockError,
    PersistedCredential,
    PersistedUser,
)
from app.infrastructure.persistence.connection import MongoConnectionManager
from app.infrastructure.persistence.indexes import (
    AUDIT_EVENTS_COLLECTION,
    AUDIT_OUTBOX_COLLECTION,
    CREDENTIALS_COLLECTION,
    HOLDER_WALLETS_COLLECTION,
    PRESENTATION_CHALLENGES_COLLECTION,
    PRESENTATIONS_COLLECTION,
    STATUS_LIST_ENTRIES_COLLECTION,
    STATUS_LISTS_COLLECTION,
    USERS_COLLECTION,
    MANAGED_KEYS_COLLECTION,
    ensure_mongo_indexes,
)
from app.infrastructure.key_management.development_provider import (
    DevelopmentExternalKeyProvider,
)
from app.infrastructure.persistence.managed_key_repository import (
    MongoManagedKeyRepository,
)
from app.infrastructure.persistence.mappers import new_object_id
from app.infrastructure.persistence.repositories import (
    MongoAuditEventRepository,
    MongoCredentialRepository,
    MongoRevocationRepository,
    MongoUserRepository,
)
from app.infrastructure.persistence.presentation_repository import (
    MongoPresentationRepository,
)
from app.infrastructure.persistence.holder_wallet_repositories import (
    MongoHolderWalletRepository,
    MongoPresentationChallengeRepository,
)
from app.domain.presentation import (
    PersistedPresentation,
    PresentationVerificationState,
)
from app.infrastructure.persistence.status_list_repositories import (
    MongoCredentialStatusEntryRepository,
)


NOW = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
ARGON_HASH = "$argon2id$v=19$m=19456,t=2,p=1$salt$hash"


@pytest.fixture(scope="module")
def mongo_database() -> Any:
    uri = os.environ.get("IDENTITY_TEST_MONGODB_URI")
    if not uri:
        pytest.skip(
            "Set IDENTITY_TEST_MONGODB_URI to run real MongoDB integration."
        )
    database_name = f"secure_identity_test_{ObjectId()}"
    assert database_name.startswith("secure_identity_test_")
    manager = MongoConnectionManager(
        MongoSettings(
            enabled=True,
            uri=uri,
            database_name=database_name,
            server_selection_timeout_ms=2_000,
            connect_timeout_ms=2_000,
            socket_timeout_ms=3_000,
            max_pool_size=5,
        )
    )
    manager.connect()
    database = manager.database
    ensure_mongo_indexes(database)
    try:
        yield database
    finally:
        database.client.drop_database(database_name)
        manager.close()


def test_real_mongo_indexes_are_idempotent(mongo_database: Any) -> None:
    ensure_mongo_indexes(mongo_database)

    user_indexes = mongo_database[USERS_COLLECTION].index_information()
    credential_indexes = mongo_database[
        CREDENTIALS_COLLECTION
    ].index_information()
    audit_indexes = mongo_database[
        AUDIT_EVENTS_COLLECTION
    ].index_information()
    entry_indexes = mongo_database[
        STATUS_LIST_ENTRIES_COLLECTION
    ].index_information()
    status_list_indexes = mongo_database[
        STATUS_LISTS_COLLECTION
    ].index_information()
    outbox_indexes = mongo_database[
        AUDIT_OUTBOX_COLLECTION
    ].index_information()
    presentation_indexes = mongo_database[
        PRESENTATIONS_COLLECTION
    ].index_information()
    wallet_indexes = mongo_database[
        HOLDER_WALLETS_COLLECTION
    ].index_information()
    challenge_indexes = mongo_database[
        PRESENTATION_CHALLENGES_COLLECTION
    ].index_information()
    managed_key_indexes = mongo_database[
        MANAGED_KEYS_COLLECTION
    ].index_information()

    assert user_indexes["uq_users_username"]["unique"] is True
    assert (
        credential_indexes["uq_credentials_credential_id"]["unique"]
        is True
    )
    assert "ix_credentials_issuer_did" in credential_indexes
    assert "ix_credentials_holder_did" in credential_indexes
    assert "ix_credentials_status" in credential_indexes
    assert "ix_audit_events_created_at" in audit_indexes
    assert entry_indexes["uq_status_entries_credential_id"]["unique"] is True
    assert status_list_indexes["uq_status_lists_status_list_id"][
        "unique"
    ] is True
    assert "ix_audit_outbox_delivery" in outbox_indexes
    assert presentation_indexes["uq_presentations_presentation_id"][
        "unique"
    ] is True
    assert presentation_indexes["uq_presentations_challenge_domain"][
        "unique"
    ] is True
    assert wallet_indexes["uq_holder_wallets_wallet_id"]["unique"] is True
    assert wallet_indexes["uq_holder_wallets_active_holder_did"][
        "unique"
    ] is True
    assert challenge_indexes[
        "uq_presentation_challenges_challenge_id"
    ]["unique"] is True
    assert managed_key_indexes["uq_managed_keys_key_id"]["unique"] is True
    assert managed_key_indexes[
        "uq_managed_keys_provider_reference"
    ]["unique"] is True
    assert managed_key_indexes[
        "uq_managed_keys_wallet_purpose_version"
    ]["unique"] is True
    assert managed_key_indexes[
        "uq_managed_keys_active_wallet_purpose"
    ]["unique"] is True


def test_real_mongo_user_repository_enforces_version_and_soft_delete(
    mongo_database: Any,
) -> None:
    repository = MongoUserRepository(
        mongo_database[USERS_COLLECTION],
        clock=lambda: NOW + timedelta(minutes=1),
    )
    user = PersistedUser(
        id=new_object_id(),
        username=f"issuer-{ObjectId()}@example.test",
        display_name="Integration Issuer",
        roles=(Role.ISSUER,),
        enabled=True,
        password_hash=ARGON_HASH,
        created_at=NOW,
        updated_at=NOW,
    )
    repository.add(user)

    updated = repository.update(
        replace(user, display_name="Updated Integration Issuer"),
        expected_version=1,
    )
    assert updated.version == 2
    with pytest.raises(OptimisticLockError):
        repository.update(user, expected_version=1)

    repository.soft_delete(user.id, expected_version=2)
    assert repository.get_by_id(user.id) is None


def test_real_mongo_credential_and_audit_repositories(
    mongo_database: Any,
) -> None:
    credential_repository = MongoCredentialRepository(
        mongo_database[CREDENTIALS_COLLECTION]
    )
    audit_repository = MongoAuditEventRepository(
        mongo_database[AUDIT_EVENTS_COLLECTION]
    )
    credential_id = f"urn:uuid:{ObjectId()}"
    credential = PersistedCredential(
        id=new_object_id(),
        credential_id=credential_id,
        issuer_did="did:web:issuer.example.test",
        holder_did="did:key:zholder",
        credential_type=("VerifiableCredential",),
        issuance_date=NOW,
        expiration_date=NOW + timedelta(days=365),
        credential_hash="a" * 64,
        status=CredentialStatus.ACTIVE,
        raw_credential={"id": credential_id},
        created_at=NOW,
        updated_at=NOW,
    )
    event = AuditEvent(
        id=new_object_id(),
        event_type=AuditEventType.VC_SIGNED,
        subject_id=credential_id,
        actor_id=None,
        correlation_id="integration-request",
        metadata={"result": "stored"},
        created_at=NOW,
        updated_at=NOW,
    )

    credential_repository.add(credential)
    audit_repository.append(event)

    assert (
        credential_repository.get_by_credential_id(credential_id)
        == credential
    )
    assert audit_repository.get_by_id(event.id) == event


def test_real_mongo_presentation_repository_is_single_use(
    mongo_database: Any,
) -> None:
    repository = MongoPresentationRepository(
        mongo_database[PRESENTATIONS_COLLECTION],
        clock=lambda: NOW,
    )
    presentation_id = f"urn:uuid:{ObjectId()}0000-4000-8000-000000000001"
    presentation_id = (
        "urn:uuid:00000000-0000-4000-8000-"
        f"{str(ObjectId())[:12]}"
    )
    presentation = PersistedPresentation(
        id=new_object_id(),
        presentation_id=presentation_id,
        holder_did="did:key:zHolder",
        challenge=f"challenge_{ObjectId()}",
        domain="verifier.example",
        credential_ids=("urn:uuid:credential-real-mongo",),
        document={"id": presentation_id},
        verification_result=PresentationVerificationState.PENDING,
        created_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        updated_at=NOW,
    )

    repository.add(presentation)
    claimed = repository.claim_verification(
        presentation_id,
        expected_version=1,
    )

    assert claimed is not None
    assert claimed.verification_result is (
        PresentationVerificationState.PROCESSING
    )
    assert (
        repository.claim_verification(
            presentation_id,
            expected_version=2,
        )
        is None
    )


def test_real_mongo_revocation_is_atomic_and_irreversible(
    mongo_database: Any,
) -> None:
    credential_repository = MongoCredentialRepository(
        mongo_database[CREDENTIALS_COLLECTION]
    )
    revocation_repository = MongoRevocationRepository(
        mongo_database[CREDENTIALS_COLLECTION]
    )
    credential_id = f"urn:uuid:{ObjectId()}"
    credential = PersistedCredential(
        id=new_object_id(),
        credential_id=credential_id,
        issuer_did="did:web:issuer.example.test",
        holder_did="did:key:zholder",
        credential_type=("VerifiableCredential",),
        issuance_date=NOW,
        expiration_date=NOW + timedelta(days=365),
        credential_hash="b" * 64,
        status=CredentialStatus.ACTIVE,
        raw_credential={"id": credential_id},
        created_at=NOW,
        updated_at=NOW,
    )
    credential_repository.add(credential)
    entry = MongoCredentialStatusEntryRepository(
        mongo_database[STATUS_LIST_ENTRIES_COLLECTION],
        mongo_database[CREDENTIALS_COLLECTION],
    ).ensure(
        credential_id=credential_id,
        issuer_did=credential.issuer_did,
        status_list_id=generate_status_list_id(credential.issuer_did),
        status_purpose=StatusPurpose.REVOCATION,
        candidate_index=17,
        list_length=131_072,
        created_at=NOW + timedelta(minutes=1),
    )
    audit_event = AuditEvent(
        id=new_object_id(),
        event_type=AuditEventType.CREDENTIAL_REVOKED,
        subject_id=credential_id,
        actor_id="usr_local_issuer",
        correlation_id="integration-revoke",
        metadata={"status": "REVOKED"},
        created_at=NOW + timedelta(minutes=1),
        updated_at=NOW + timedelta(minutes=1),
    )
    outbox = AuditOutboxRecord.pending(
        event=audit_event,
        aggregate_type="credential",
        aggregate_id=credential_id,
        source=AuditOutboxSource.CREDENTIAL,
    )

    revoked = revocation_repository.revoke(
        credential_id,
        revoked_at=NOW + timedelta(minutes=1),
        revoked_by="usr_local_issuer",
        revocation_reason="Affiliation ended",
        expected_version=1,
        status_entry=entry,
        audit_outbox=outbox,
    )

    assert revoked.status is CredentialStatus.REVOKED
    assert revoked.version == 2
    with pytest.raises(CredentialAlreadyRevokedError):
        revocation_repository.revoke(
            credential_id,
            revoked_at=NOW + timedelta(minutes=1),
            revoked_by="usr_local_issuer",
            revocation_reason="Second attempt",
            expected_version=2,
            status_entry=entry,
            audit_outbox=outbox,
        )


def test_real_mongo_wallet_and_challenge_repositories(
    mongo_database: Any,
) -> None:
    wallet_repository = MongoHolderWalletRepository(
        mongo_database[HOLDER_WALLETS_COLLECTION]
    )
    challenge_repository = MongoPresentationChallengeRepository(
        mongo_database[PRESENTATION_CHALLENGES_COLLECTION]
    )
    suffix = str(ObjectId())
    wallet = HolderWallet(
        id=new_object_id(),
        wallet_id=f"wallet_{suffix}",
        owner_user_id="usr_real_mongo_holder",
        holder_did=f"did:key:z{suffix}",
        status=WalletStatus.ACTIVE,
        key_reference=f"local-dev:wallet:{suffix}",
        created_at=NOW,
        updated_at=NOW,
    )
    challenge = PresentationChallenge(
        id=new_object_id(),
        challenge_id=f"challenge_{suffix}",
        challenge=f"challenge_value_{suffix}",
        domain="verifier.example",
        audience="secure-ssi-verifier",
        requested_holder_did=wallet.holder_did,
        issued_by="usr_real_mongo_verifier",
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        consumed_at=None,
        status=ChallengeStatus.ISSUED,
    )

    wallet_repository.add(wallet)
    challenge_repository.add(challenge)
    consumed = challenge_repository.consume(
        challenge.challenge_id,
        consumed_at=NOW + timedelta(seconds=1),
        expected_version=1,
        domain=challenge.domain,
        audience=challenge.audience,
        requested_holder_did=wallet.holder_did,
    )

    assert wallet_repository.get(wallet.wallet_id) == wallet
    assert consumed is not None
    assert consumed.status is ChallengeStatus.CONSUMED
    assert consumed.version == 2


def test_real_mongo_managed_key_repository_uses_optimistic_lifecycle(
    mongo_database: Any,
) -> None:
    repository = MongoManagedKeyRepository(
        mongo_database[MANAGED_KEYS_COLLECTION]
    )
    provider = DevelopmentExternalKeyProvider()
    suffix = str(ObjectId())
    metadata = provider.create_key(
        key_id=f"key_{suffix}",
        algorithm=KeyAlgorithm.ED25519,
        purpose=KeyPurpose.PRESENTATION_SIGNING,
        idempotency_key=f"mongo-managed-key-{suffix}",
    )
    key = ManagedKey(
        id=new_object_id(),
        key_id=f"key_{suffix}",
        wallet_id=f"wallet_{suffix}",
        owner_user_id="usr_real_mongo_holder",
        holder_did=metadata.holder_did,
        provider=metadata.provider,
        provider_key_reference=metadata.provider_key_reference,
        algorithm=metadata.algorithm,
        purpose=KeyPurpose.PRESENTATION_SIGNING,
        state=ManagedKeyState.ACTIVE,
        public_key_multibase=metadata.public_key_multibase,
        fingerprint=metadata.fingerprint,
        verification_method=metadata.verification_method,
        created_at=NOW,
        updated_at=NOW,
        activated_at=NOW,
    )
    repository.add(key)

    claimed = repository.claim_rotation(
        key.key_id,
        rotated_at=NOW + timedelta(minutes=1),
        expected_version=key.version,
    )

    assert claimed.state is ManagedKeyState.ROTATING
    assert repository.get_active(
        wallet_id=key.wallet_id,
        purpose=key.purpose,
    ) is None
    with pytest.raises(OptimisticLockError):
        repository.claim_rotation(
            key.key_id,
            rotated_at=NOW + timedelta(minutes=2),
            expected_version=key.version,
        )
