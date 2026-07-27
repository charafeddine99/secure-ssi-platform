from datetime import datetime
from typing import Protocol

from app.domain.audit_outbox import AuditOutboxRecord
from app.domain.bitstring_status_list import CredentialStatusEntry
from app.domain.credential_status import CredentialStatus
from app.domain.persistence import (
    AuditEvent,
    AuditEventType,
    CredentialStorageStatus,
    PersistedCredential,
    PersistedUser,
)


class UserRepository(Protocol):
    def add(self, user: PersistedUser) -> PersistedUser: ...

    def get_by_id(self, user_id: str) -> PersistedUser | None: ...

    def get_by_username(self, username: str) -> PersistedUser | None: ...

    def update(
        self,
        user: PersistedUser,
        *,
        expected_version: int,
    ) -> PersistedUser: ...

    def soft_delete(
        self,
        user_id: str,
        *,
        expected_version: int,
    ) -> None: ...


class CredentialRepository(Protocol):
    def add(
        self,
        credential: PersistedCredential,
    ) -> PersistedCredential: ...

    def get_by_credential_id(
        self,
        credential_id: str,
    ) -> PersistedCredential | None: ...

    def update(
        self,
        credential: PersistedCredential,
        *,
        expected_version: int,
    ) -> PersistedCredential: ...

    def soft_delete(
        self,
        credential_id: str,
        *,
        expected_version: int,
    ) -> None: ...

    def list_by_issuer(
        self,
        issuer_did: str,
        *,
        limit: int = 100,
    ) -> tuple[PersistedCredential, ...]: ...

    def list_by_holder(
        self,
        holder_did: str,
        *,
        limit: int = 100,
    ) -> tuple[PersistedCredential, ...]: ...

    def list_by_wallet(
        self,
        wallet_id: str,
        *,
        owner_user_id: str,
        limit: int = 100,
    ) -> tuple[PersistedCredential, ...]: ...

    def list_by_status(
        self,
        status: CredentialStatus | CredentialStorageStatus,
        *,
        limit: int = 100,
    ) -> tuple[PersistedCredential, ...]: ...


class RevocationRepository(Protocol):
    def get_by_credential_id(
        self,
        credential_id: str,
    ) -> PersistedCredential | None: ...

    def revoke(
        self,
        credential_id: str,
        *,
        revoked_at: datetime,
        revoked_by: str,
        revocation_reason: str,
        expected_version: int,
        status_entry: CredentialStatusEntry,
        audit_outbox: AuditOutboxRecord,
    ) -> PersistedCredential: ...

    def mark_expired(
        self,
        credential_id: str,
        *,
        expired_at: datetime,
        expected_version: int,
    ) -> PersistedCredential: ...


class AuditEventRepository(Protocol):
    def append(self, event: AuditEvent) -> AuditEvent: ...

    def get_by_id(self, event_id: str) -> AuditEvent | None: ...

    def list_recent(
        self,
        *,
        event_type: AuditEventType | None = None,
        limit: int = 100,
    ) -> tuple[AuditEvent, ...]: ...
