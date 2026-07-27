from datetime import UTC, datetime, timedelta
from typing import Any, cast

from app.application.services.status_list_service import StatusListService
from app.config.status_list_settings import StatusListSettings
from app.domain.bitstring_status_list import (
    MINIMUM_STATUS_LIST_ENTRIES,
    StatusPurpose,
    generate_status_list_id,
)
from app.domain.credential_status import CredentialStatus
from app.domain.persistence import PersistedCredential
from app.infrastructure.crypto.ed25519_signer import Ed25519CredentialSigner
from app.infrastructure.crypto.jcs_canonicalizer import JcsCanonicalizer
from app.infrastructure.crypto.local_issuer_key_provider import (
    LocalIssuerKeyProvider,
    SYNTHETIC_ISSUER_DID,
)
from app.infrastructure.persistence.repositories import (
    MongoCredentialRepository,
)
from app.infrastructure.persistence.status_list_repositories import (
    MongoCredentialStatusEntryRepository,
    MongoStatusListRepository,
)
from app.infrastructure.status_list_document_generator import (
    StatusListDocumentGenerator,
)
from tests.support.fake_mongo import FakeCollection


NOW = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)


def _credential(
    storage_id: str,
    credential_id: str,
) -> PersistedCredential:
    return PersistedCredential(
        id=storage_id,
        credential_id=credential_id,
        issuer_did=SYNTHETIC_ISSUER_DID,
        holder_did="did:key:zholder",
        credential_type=("VerifiableCredential",),
        issuance_date=NOW - timedelta(days=1),
        expiration_date=NOW + timedelta(days=365),
        credential_hash="a" * 64,
        status=CredentialStatus.ACTIVE,
        raw_credential={"id": credential_id},
        created_at=NOW,
        updated_at=NOW,
    )


def test_status_entry_repository_reserves_collisions_idempotently() -> None:
    entries = FakeCollection(
        unique_fields=("credentialId",),
        unique_compounds=(("statusListId", "statusListIndex"),),
    )
    credentials = FakeCollection(unique_fields=("credentialId",))
    ids = iter(
        (
            "100000000000000000000001",
            "100000000000000000000002",
            "100000000000000000000003",
        )
    )
    repository = MongoCredentialStatusEntryRepository(
        cast(Any, entries),
        cast(Any, credentials),
        id_generator=lambda: next(ids),
    )
    status_list_id = generate_status_list_id(SYNTHETIC_ISSUER_DID)

    first = repository.ensure(
        credential_id="urn:uuid:first",
        issuer_did=SYNTHETIC_ISSUER_DID,
        status_list_id=status_list_id,
        status_purpose=StatusPurpose.REVOCATION,
        candidate_index=5,
        list_length=MINIMUM_STATUS_LIST_ENTRIES,
        created_at=NOW,
    )
    repeated = repository.ensure(
        credential_id="urn:uuid:first",
        issuer_did=SYNTHETIC_ISSUER_DID,
        status_list_id=status_list_id,
        status_purpose=StatusPurpose.REVOCATION,
        candidate_index=99,
        list_length=MINIMUM_STATUS_LIST_ENTRIES,
        created_at=NOW,
    )
    collided = repository.ensure(
        credential_id="urn:uuid:second",
        issuer_did=SYNTHETIC_ISSUER_DID,
        status_list_id=status_list_id,
        status_purpose=StatusPurpose.REVOCATION,
        candidate_index=5,
        list_length=MINIMUM_STATUS_LIST_ENTRIES,
        created_at=NOW,
    )

    assert repeated == first
    assert collided.status_list_index == 6
    assert len(entries.documents) == 2


def test_status_list_publication_is_idempotent_and_versioned_on_change() -> None:
    credentials = FakeCollection(unique_fields=("credentialId",))
    entries = FakeCollection(
        unique_fields=("credentialId",),
        unique_compounds=(("statusListId", "statusListIndex"),),
    )
    publications = FakeCollection(unique_fields=("statusListId",))
    credential_repository = MongoCredentialRepository(
        cast(Any, credentials)
    )
    first_credential = credential_repository.add(
        _credential(
            "200000000000000000000001",
            "urn:uuid:first",
        )
    )
    entry_repository = MongoCredentialStatusEntryRepository(
        cast(Any, entries),
        cast(Any, credentials),
    )
    sequence = iter(
        (
            "300000000000000000000001",
            "300000000000000000000002",
        )
    )
    service = StatusListService(
        entry_repository=entry_repository,
        status_list_repository=MongoStatusListRepository(
            cast(Any, publications)
        ),
        generator=StatusListDocumentGenerator(
            canonicalizer=JcsCanonicalizer(),
            signer=Ed25519CredentialSigner(),
            key_provider=LocalIssuerKeyProvider(),
        ),
        settings=StatusListSettings(
            public_base_url="https://issuer.example/api/v1/status-lists"
        ),
        clock=lambda: NOW,
        id_generator=lambda: next(sequence),
    )
    first_entry = service.ensure_entry(first_credential)

    version_one = service.get_publication(first_entry.status_list_id)
    repeated = service.get_publication(first_entry.status_list_id)
    second_credential = credential_repository.add(
        _credential(
            "200000000000000000000002",
            "urn:uuid:second",
        )
    )
    service.ensure_entry(second_credential)
    version_two = service.get_publication(first_entry.status_list_id)
    credentials.documents[0]["status"] = CredentialStatus.REVOKED.value
    version_three = service.get_publication(first_entry.status_list_id)

    assert repeated == version_one
    assert version_one.version == 1
    assert version_one.assigned_entries == 1
    assert version_one.revoked_entries == 0
    assert version_two.version == 2
    assert version_two.assigned_entries == 2
    assert version_two.revoked_entries == 0
    assert version_three.version == 3
    assert version_three.revoked_entries == 1
    assert version_three.etag != version_two.etag
    history = service.get_history(first_entry.status_list_id)
    assert tuple(item.version for item in history) == (1, 2, 3)
    assert service.get_version(first_entry.status_list_id, 1) == version_one
    assert history[0].document == version_one.document
    assert history[0].etag == version_one.etag
    assert len(publications.documents) == 1
