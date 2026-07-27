from datetime import UTC, datetime, timedelta

import pytest

from app.domain.credential_status import CredentialStatus
from app.domain.permissions import Role
from app.domain.persistence import (
    AuditEvent,
    AuditEventType,
    CredentialStorageStatus,
    PersistedCredential,
    PersistedUser,
)


NOW = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
OBJECT_ID = "64b64c0f0123456789abcdef"
ARGON_HASH = "$argon2id$v=19$m=19456,t=2,p=1$salt$hash"


def test_persisted_user_normalizes_identity_and_hides_hash() -> None:
    user = PersistedUser(
        id=OBJECT_ID,
        username=" Admin@Example.TEST ",
        display_name=" Admin ",
        roles=(Role.ADMIN, Role.ADMIN),
        enabled=True,
        password_hash=ARGON_HASH,
        created_at=NOW,
        updated_at=NOW,
    )

    assert user.username == "admin@example.test"
    assert user.display_name == "Admin"
    assert user.roles == (Role.ADMIN,)
    assert user.to_public_user().id == OBJECT_ID
    assert ARGON_HASH not in repr(user)


@pytest.mark.parametrize(
    "mutation",
    [
        {"id": "not-an-object-id"},
        {"password_hash": "plain-text"},
        {"version": 0},
        {"updated_at": NOW - timedelta(seconds=1)},
    ],
)
def test_persisted_user_rejects_invalid_storage_state(
    mutation: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "id": OBJECT_ID,
        "username": "admin@example.test",
        "display_name": "Admin",
        "roles": (Role.ADMIN,),
        "enabled": True,
        "password_hash": ARGON_HASH,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(mutation)

    with pytest.raises(ValueError):
        PersistedUser(**values)  # type: ignore[arg-type]


def test_persisted_credential_requires_hash_and_validity_window() -> None:
    credential = PersistedCredential(
        id=OBJECT_ID,
        credential_id="urn:uuid:credential-1",
        issuer_did="did:web:issuer.example.test",
        holder_did="did:key:zholder",
        credential_type=("VerifiableCredential", "UniversityAffiliation"),
        issuance_date=NOW,
        expiration_date=NOW + timedelta(days=365),
        credential_hash="a" * 64,
        status=CredentialStorageStatus.STORED,
        raw_credential={"id": "urn:uuid:credential-1"},
        created_at=NOW,
        updated_at=NOW,
    )

    assert credential.credential_type == (
        "VerifiableCredential",
        "UniversityAffiliation",
    )
    assert credential.status is CredentialStatus.ACTIVE

    with pytest.raises(ValueError):
        PersistedCredential(
            **{
                **vars(credential),
                "credential_hash": "not-sha256",
            }
        )


def test_revoked_credential_requires_immutable_metadata() -> None:
    values = {
        "id": OBJECT_ID,
        "credential_id": "urn:uuid:credential-1",
        "issuer_did": "did:web:issuer.example.test",
        "holder_did": "did:key:zholder",
        "credential_type": ("VerifiableCredential",),
        "issuance_date": NOW,
        "expiration_date": NOW + timedelta(days=365),
        "credential_hash": "a" * 64,
        "status": CredentialStatus.REVOKED,
        "raw_credential": None,
        "created_at": NOW,
        "updated_at": NOW + timedelta(minutes=1),
        "version": 2,
        "revoked_at": NOW + timedelta(minutes=1),
        "revoked_by": " usr_local_issuer ",
        "revocation_reason": " Affiliation ended ",
    }

    credential = PersistedCredential(**values)

    assert credential.revoked_by == "usr_local_issuer"
    assert credential.revocation_reason == "Affiliation ended"
    with pytest.raises(ValueError):
        PersistedCredential(**{**values, "revocation_reason": None})
    with pytest.raises(ValueError):
        PersistedCredential(
            **{
                **values,
                "status": CredentialStatus.ACTIVE,
            }
        )


@pytest.mark.parametrize(
    "metadata",
    [
        {"token": "secret"},
        {"authorization_header": "secret"},
        {"credentialHash": "secret"},
    ],
)
def test_audit_event_rejects_sensitive_metadata(
    metadata: dict[str, str],
) -> None:
    with pytest.raises(ValueError):
        AuditEvent(
            id=OBJECT_ID,
            event_type=AuditEventType.LOGIN_FAILURE,
            subject_id=None,
            actor_id=None,
            correlation_id="request-1",
            metadata=metadata,
            created_at=NOW,
            updated_at=NOW,
        )


def test_audit_event_is_append_only() -> None:
    with pytest.raises(ValueError):
        AuditEvent(
            id=OBJECT_ID,
            event_type=AuditEventType.TOKEN_ISSUED,
            subject_id=OBJECT_ID,
            actor_id=OBJECT_ID,
            correlation_id="request-1",
            metadata={"source": "local"},
            created_at=NOW,
            updated_at=NOW + timedelta(seconds=1),
            version=2,
        )
