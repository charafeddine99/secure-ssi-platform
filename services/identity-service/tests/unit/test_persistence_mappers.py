from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from bson import ObjectId

from app.domain.credential_status import CredentialStatus
from app.domain.permissions import Role
from app.domain.persistence import (
    AuditEvent,
    AuditEventType,
    CredentialStorageStatus,
    DocumentMappingError,
    PersistedCredential,
    PersistedUser,
)
from app.infrastructure.persistence.mappers import (
    AuditEventDocumentMapper,
    CredentialDocumentMapper,
    UserDocumentMapper,
    new_object_id,
    to_object_id,
)


NOW = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
OBJECT_ID = "64b64c0f0123456789abcdef"
ARGON_HASH = "$argon2id$v=19$m=19456,t=2,p=1$salt$hash"


def test_object_id_conversion_is_explicit_and_round_trips() -> None:
    generated = new_object_id()

    assert len(generated) == 24
    assert str(to_object_id(generated)) == generated
    with pytest.raises(DocumentMappingError):
        to_object_id("invalid")


def test_user_mapper_round_trips_bson_without_exposing_hash() -> None:
    user = PersistedUser(
        id=OBJECT_ID,
        username="issuer@example.test",
        display_name="Issuer",
        roles=(Role.ISSUER,),
        enabled=True,
        password_hash=ARGON_HASH,
        created_at=NOW,
        updated_at=NOW,
    )

    document = UserDocumentMapper.to_document(user)
    restored = UserDocumentMapper.from_document(document)

    assert isinstance(document["_id"], ObjectId)
    assert "id" not in document
    assert restored == user
    assert ARGON_HASH not in repr(restored)


def test_credential_mapper_deep_copies_raw_json() -> None:
    raw = {
        "id": "urn:uuid:credential-1",
        "credentialSubject": {"id": "did:key:zholder"},
    }
    credential = PersistedCredential(
        id=OBJECT_ID,
        credential_id=raw["id"],
        issuer_did="did:web:issuer.example.test",
        holder_did="did:key:zholder",
        credential_type=("VerifiableCredential",),
        issuance_date=NOW,
        expiration_date=NOW + timedelta(days=1),
        credential_hash="a" * 64,
        status=CredentialStorageStatus.STORED,
        raw_credential=raw,
        created_at=NOW,
        updated_at=NOW,
        wallet_id="wallet_abcdefghijklmnop",
        owner_user_id="usr_local_holder",
    )

    document = CredentialDocumentMapper.to_document(credential)
    document_copy = deepcopy(document)
    document["rawCredential"]["credentialSubject"]["id"] = "changed"
    restored = CredentialDocumentMapper.from_document(document_copy)

    assert restored.raw_credential == raw
    assert restored.raw_credential is not raw
    assert document_copy["status"] == "ACTIVE"
    assert document_copy["revokedAt"] is None
    assert document_copy["revokedBy"] is None
    assert document_copy["revocationReason"] is None
    assert document_copy["walletId"] == "wallet_abcdefghijklmnop"
    assert document_copy["ownerUserId"] == "usr_local_holder"
    assert restored.wallet_id == "wallet_abcdefghijklmnop"


def test_credential_mapper_round_trips_revocation_metadata() -> None:
    credential = PersistedCredential(
        id=OBJECT_ID,
        credential_id="urn:uuid:credential-1",
        issuer_did="did:web:issuer.example.test",
        holder_did="did:key:zholder",
        credential_type=("VerifiableCredential",),
        issuance_date=NOW,
        expiration_date=NOW + timedelta(days=1),
        credential_hash="a" * 64,
        status=CredentialStatus.REVOKED,
        raw_credential=None,
        created_at=NOW,
        updated_at=NOW + timedelta(hours=1),
        version=2,
        revoked_at=NOW + timedelta(hours=1),
        revoked_by="usr_local_issuer",
        revocation_reason="Affiliation ended",
    )

    document = CredentialDocumentMapper.to_document(credential)
    restored = CredentialDocumentMapper.from_document(document)

    assert document["status"] == "REVOKED"
    assert document["revokedAt"] == NOW + timedelta(hours=1)
    assert document["revokedBy"] == "usr_local_issuer"
    assert document["revocationReason"] == "Affiliation ended"
    assert restored == credential


def test_credential_mapper_reads_legacy_storage_status_as_active() -> None:
    active = PersistedCredential(
        id=OBJECT_ID,
        credential_id="urn:uuid:credential-1",
        issuer_did="did:web:issuer.example.test",
        holder_did="did:key:zholder",
        credential_type=("VerifiableCredential",),
        issuance_date=NOW,
        expiration_date=None,
        credential_hash="a" * 64,
        status=CredentialStatus.ACTIVE,
        raw_credential=None,
        created_at=NOW,
        updated_at=NOW,
    )
    document = CredentialDocumentMapper.to_document(active)
    document["status"] = CredentialStorageStatus.STORED.value

    restored = CredentialDocumentMapper.from_document(document)

    assert restored.status is CredentialStatus.ACTIVE


def test_audit_mapper_round_trips_allowlisted_metadata() -> None:
    event = AuditEvent(
        id=OBJECT_ID,
        event_type=AuditEventType.VC_VERIFIED,
        subject_id="urn:uuid:credential-1",
        actor_id=None,
        correlation_id="request-1",
        metadata={"result": "valid"},
        created_at=NOW,
        updated_at=NOW,
    )

    restored = AuditEventDocumentMapper.from_document(
        AuditEventDocumentMapper.to_document(event)
    )

    assert restored == event
    assert restored.metadata == {"result": "valid"}


def test_mapper_rejects_wrong_bson_types() -> None:
    with pytest.raises(DocumentMappingError):
        UserDocumentMapper.from_document(
            {
                "_id": OBJECT_ID,
                "username": "issuer@example.test",
                "displayName": "Issuer",
                "roles": ["issuer"],
                "enabled": True,
                "passwordHash": ARGON_HASH,
                "createdAt": NOW,
                "updatedAt": NOW,
                "version": 1,
            }
        )
