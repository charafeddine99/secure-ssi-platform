from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from app.api.v1.dependencies import (
    get_audit_event_repository,
    get_credential_repository,
    get_holder_wallet_repository,
    get_presentation_challenge_repository,
    get_presentation_repository,
    get_revocation_repository,
    get_user_repository,
)
from app.domain.credential_status import (
    CredentialAlreadyRevokedError,
    CredentialStatus,
)
from app.domain.audit_outbox import AuditOutboxRecord, AuditOutboxSource
from app.domain.bitstring_status_list import (
    CredentialStatusEntry,
    StatusPurpose,
    generate_status_list_id,
)
from app.domain.permissions import Role
from app.domain.persistence import (
    AuditEvent,
    AuditEventType,
    DuplicateEntityError,
    OptimisticLockError,
    PersistedCredential,
    PersistedUser,
)
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
    ensure_mongo_indexes,
)
from app.infrastructure.persistence.mongo_user_provider import (
    MongoUserProvider,
)
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
from tests.support.fake_mongo import FakeCollection, FakeDatabase


NOW = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(minutes=1)
ARGON_HASH = "$argon2id$v=19$m=19456,t=2,p=1$salt$hash"


def user(
    *,
    user_id: str = "64b64c0f0123456789abcdef",
    username: str = "issuer@example.test",
) -> PersistedUser:
    return PersistedUser(
        id=user_id,
        username=username,
        display_name="Issuer",
        roles=(Role.ISSUER,),
        enabled=True,
        password_hash=ARGON_HASH,
        created_at=NOW,
        updated_at=NOW,
    )


def credential(
    *,
    storage_id: str,
    credential_id: str,
    created_at: datetime = NOW,
) -> PersistedCredential:
    return PersistedCredential(
        id=storage_id,
        credential_id=credential_id,
        issuer_did="did:web:issuer.example.test",
        holder_did="did:key:zholder",
        credential_type=("VerifiableCredential",),
        issuance_date=NOW,
        expiration_date=NOW + timedelta(days=365),
        credential_hash="a" * 64,
        status=CredentialStatus.ACTIVE,
        raw_credential={"id": credential_id},
        created_at=created_at,
        updated_at=created_at,
    )


def audit_event(
    *,
    event_id: str,
    event_type: AuditEventType,
    created_at: datetime,
) -> AuditEvent:
    return AuditEvent(
        id=event_id,
        event_type=event_type,
        subject_id="subject-1",
        actor_id="actor-1",
        correlation_id="request-1",
        metadata={"result": "accepted"},
        created_at=created_at,
        updated_at=created_at,
    )


def revocation_records(
    stored: PersistedCredential,
) -> tuple[CredentialStatusEntry, AuditOutboxRecord]:
    status_entry = CredentialStatusEntry(
        id="84b64c0f0123456789abcdef",
        credential_id=stored.credential_id,
        issuer_did=stored.issuer_did,
        status_list_id=generate_status_list_id(stored.issuer_did),
        status_list_index=17,
        status_purpose=StatusPurpose.REVOCATION,
        created_at=LATER,
        updated_at=LATER,
    )
    event = AuditEvent(
        id="94b64c0f0123456789abcdef",
        event_type=AuditEventType.CREDENTIAL_REVOKED,
        subject_id=stored.credential_id,
        actor_id="usr_local_issuer",
        correlation_id="request-revoke",
        metadata={"status": "REVOKED"},
        created_at=LATER,
        updated_at=LATER,
    )
    return status_entry, AuditOutboxRecord.pending(
        event=event,
        aggregate_type="credential",
        aggregate_id=stored.credential_id,
        source=AuditOutboxSource.CREDENTIAL,
    )


def test_user_repository_crud_optimistic_lock_and_soft_delete() -> None:
    collection = FakeCollection(unique_fields=("username",))
    repository = MongoUserRepository(
        cast(Any, collection),
        clock=lambda: LATER,
    )
    original = repository.add(user())

    assert repository.get_by_id(original.id) == original
    assert repository.get_by_username(" ISSUER@EXAMPLE.TEST ") == original

    updated = repository.update(
        replace(original, display_name="Updated Issuer"),
        expected_version=1,
    )
    assert updated.version == 2
    assert updated.updated_at == LATER
    assert repository.get_by_id(original.id) == updated

    with pytest.raises(OptimisticLockError):
        repository.update(original, expected_version=1)

    repository.soft_delete(original.id, expected_version=2)
    assert repository.get_by_id(original.id) is None
    assert collection.documents[0]["deletedAt"] == LATER
    assert collection.documents[0]["enabled"] is False
    assert collection.documents[0]["version"] == 3


def test_user_repository_translates_unique_constraint() -> None:
    repository = MongoUserRepository(
        cast(Any, FakeCollection(unique_fields=("username",)))
    )
    repository.add(user())

    with pytest.raises(DuplicateEntityError):
        repository.add(
            user(user_id="74b64c0f0123456789abcdef")
        )


def test_mongo_user_provider_adapts_persisted_user_without_hash_leak() -> None:
    repository = MongoUserRepository(
        cast(Any, FakeCollection(unique_fields=("username",)))
    )
    repository.add(user())
    provider = MongoUserProvider(
        repository,
        fallback_password_hash="fallback-hash",
    )

    record = provider.find_by_username("issuer@example.test")

    assert record is not None
    assert record.user.id == "64b64c0f0123456789abcdef"
    assert record.password_hash == ARGON_HASH
    assert ARGON_HASH not in repr(provider)
    assert provider.authentication_source == "mongodb"


def test_credential_repository_queries_updates_and_soft_deletes() -> None:
    collection = FakeCollection(unique_fields=("credentialId",))
    repository = MongoCredentialRepository(
        cast(Any, collection),
        clock=lambda: LATER + timedelta(minutes=1),
    )
    first = credential(
        storage_id="64b64c0f0123456789abcdef",
        credential_id="urn:uuid:credential-1",
    )
    second = credential(
        storage_id="74b64c0f0123456789abcdef",
        credential_id="urn:uuid:credential-2",
        created_at=LATER,
    )
    repository.add(first)
    repository.add(second)

    assert repository.list_by_issuer(first.issuer_did) == (second, first)
    assert repository.list_by_holder(first.holder_did) == (second, first)
    assert repository.list_by_status(CredentialStatus.ACTIVE) == (
        second,
        first,
    )

    updated = repository.update(
        replace(first, status=CredentialStatus.SUSPENDED),
        expected_version=1,
    )
    assert updated.version == 2
    assert repository.list_by_status(CredentialStatus.SUSPENDED) == (updated,)

    repository.soft_delete(first.credential_id, expected_version=2)
    assert repository.get_by_credential_id(first.credential_id) is None


def test_credential_repository_rejects_duplicate_and_stale_version() -> None:
    repository = MongoCredentialRepository(
        cast(Any, FakeCollection(unique_fields=("credentialId",)))
    )
    original = credential(
        storage_id="64b64c0f0123456789abcdef",
        credential_id="urn:uuid:credential-1",
    )
    repository.add(original)

    with pytest.raises(DuplicateEntityError):
        repository.add(
            credential(
                storage_id="74b64c0f0123456789abcdef",
                credential_id=original.credential_id,
            )
        )
    with pytest.raises(OptimisticLockError):
        repository.update(
            replace(original, version=2),
            expected_version=1,
        )


def test_revocation_repository_is_atomic_irreversible_and_versioned() -> None:
    collection = FakeCollection(unique_fields=("credentialId",))
    credential_repository = MongoCredentialRepository(
        cast(Any, collection)
    )
    repository = MongoRevocationRepository(cast(Any, collection))
    original = credential(
        storage_id="64b64c0f0123456789abcdef",
        credential_id="urn:uuid:credential-1",
    )
    credential_repository.add(original)
    status_entry, outbox = revocation_records(original)

    revoked = repository.revoke(
        original.credential_id,
        revoked_at=LATER,
        revoked_by="usr_local_issuer",
        revocation_reason="Affiliation ended",
        expected_version=1,
        status_entry=status_entry,
        audit_outbox=outbox,
    )

    assert revoked.status is CredentialStatus.REVOKED
    assert revoked.revoked_at == LATER
    assert revoked.revoked_by == "usr_local_issuer"
    assert revoked.revocation_reason == "Affiliation ended"
    assert revoked.version == 2
    with pytest.raises(CredentialAlreadyRevokedError):
        repository.revoke(
            original.credential_id,
            revoked_at=LATER,
            revoked_by="usr_local_issuer",
            revocation_reason="Second attempt",
            expected_version=2,
            status_entry=status_entry,
            audit_outbox=outbox,
        )
    with pytest.raises(OptimisticLockError):
        credential_repository.update(
            replace(
                revoked,
                status=CredentialStatus.ACTIVE,
                revoked_at=None,
                revoked_by=None,
                revocation_reason=None,
            ),
            expected_version=2,
        )


def test_revocation_repository_marks_expired_credential_once() -> None:
    collection = FakeCollection(unique_fields=("credentialId",))
    credential_repository = MongoCredentialRepository(
        cast(Any, collection)
    )
    repository = MongoRevocationRepository(cast(Any, collection))
    original = credential(
        storage_id="64b64c0f0123456789abcdef",
        credential_id="urn:uuid:credential-1",
    )
    credential_repository.add(original)

    expired = repository.mark_expired(
        original.credential_id,
        expired_at=LATER,
        expected_version=1,
    )
    same = repository.mark_expired(
        original.credential_id,
        expired_at=LATER + timedelta(minutes=1),
        expected_version=expired.version,
    )

    assert expired.status is CredentialStatus.EXPIRED
    assert expired.version == 2
    assert same == expired


def test_audit_repository_is_append_only_and_returns_recent_events() -> None:
    repository = MongoAuditEventRepository(
        cast(Any, FakeCollection())
    )
    login = audit_event(
        event_id="64b64c0f0123456789abcdef",
        event_type=AuditEventType.LOGIN_SUCCESS,
        created_at=NOW,
    )
    token = audit_event(
        event_id="74b64c0f0123456789abcdef",
        event_type=AuditEventType.TOKEN_ISSUED,
        created_at=LATER,
    )
    repository.append(login)
    repository.append(token)

    assert repository.get_by_id(login.id) == login
    assert repository.list_recent() == (token, login)
    assert repository.list_recent(
        event_type=AuditEventType.LOGIN_SUCCESS
    ) == (login,)

    with pytest.raises(DuplicateEntityError):
        repository.append(login)


def test_index_manager_creates_stable_named_indexes() -> None:
    database = FakeDatabase()

    ensure_mongo_indexes(cast(Any, database))

    user_names = {
        index.document["name"]
        for index in database[USERS_COLLECTION].indexes
    }
    credential_names = {
        index.document["name"]
        for index in database[CREDENTIALS_COLLECTION].indexes
    }
    audit_names = {
        index.document["name"]
        for index in database[AUDIT_EVENTS_COLLECTION].indexes
    }
    assert user_names == {
        "uq_users_username",
        "ix_users_created_at",
    }
    assert credential_names == {
        "uq_credentials_credential_id",
        "ix_credentials_issuer_did",
        "ix_credentials_holder_did",
        "ix_credentials_status",
            "ix_credentials_created_at",
            "ix_credentials_status_list_status",
        "uq_credentials_status_list_index",
        "ix_credentials_wallet_owner_created_at",
    }
    assert audit_names == {
        "ix_audit_events_created_at",
        "ix_audit_events_type_created_at",
    }
    assert {
        index.document["name"]
        for index in database[STATUS_LIST_ENTRIES_COLLECTION].indexes
    } == {
        "uq_status_entries_credential_id",
        "uq_status_entries_list_index",
        "ix_status_entries_issuer_purpose",
    }
    assert {
        index.document["name"]
        for index in database[STATUS_LISTS_COLLECTION].indexes
    } == {
            "uq_status_lists_status_list_id",
            "ix_status_lists_issuer_purpose",
            "ix_status_lists_updated_at",
    }
    assert {
        index.document["name"]
        for index in database[AUDIT_OUTBOX_COLLECTION].indexes
    } == {
        "ix_audit_outbox_delivery",
        "ix_audit_outbox_aggregate",
    }
    assert {
        index.document["name"]
        for index in database[PRESENTATIONS_COLLECTION].indexes
    } == {
        "uq_presentations_presentation_id",
        "uq_presentations_challenge_domain",
        "ix_presentations_holder_created_at",
        "ix_presentations_verification_result",
        "ix_presentations_expires_at",
        "ix_presentations_wallet_owner",
        "ix_presentations_stale_processing",
    }
    assert {
        index.document["name"]
        for index in database[HOLDER_WALLETS_COLLECTION].indexes
    } == {
        "uq_holder_wallets_wallet_id",
        "uq_holder_wallets_key_reference",
        "uq_holder_wallets_active_holder_did",
        "ix_holder_wallets_owner_status",
    }
    assert {
        index.document["name"]
        for index in database[PRESENTATION_CHALLENGES_COLLECTION].indexes
    } == {
        "uq_presentation_challenges_challenge_id",
        "uq_presentation_challenges_challenge",
        "ix_presentation_challenges_expires_at",
        "ix_presentation_challenges_status_expires",
        "ix_presentation_challenges_issuer_created_at",
    }
    assert next(
        index
        for index in database[USERS_COLLECTION].indexes
        if index.document["name"] == "uq_users_username"
    ).document["unique"] is True


def test_dependency_injection_binds_each_repository_collection() -> None:
    database = FakeDatabase()

    class FakeManager:
        @property
        def database(self) -> FakeDatabase:
            return database

    manager = cast(Any, FakeManager())

    assert isinstance(get_user_repository(manager), MongoUserRepository)
    assert isinstance(
        get_credential_repository(manager),
        MongoCredentialRepository,
    )
    assert isinstance(
        get_revocation_repository(manager),
        MongoRevocationRepository,
    )
    assert isinstance(
        get_audit_event_repository(manager),
        MongoAuditEventRepository,
    )
    assert isinstance(
        get_presentation_repository(manager, lambda: NOW),
        MongoPresentationRepository,
    )
    assert isinstance(
        get_holder_wallet_repository(manager),
        MongoHolderWalletRepository,
    )
    assert isinstance(
        get_presentation_challenge_repository(manager),
        MongoPresentationChallengeRepository,
    )
