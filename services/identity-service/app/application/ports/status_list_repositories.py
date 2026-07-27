from datetime import datetime
from typing import Protocol

from app.domain.audit_outbox import AuditOutboxRecord, AuditOutboxSource
from app.domain.bitstring_status_list import (
    CredentialStatusEntry,
    StatusListPublication,
    StatusPurpose,
)


class CredentialStatusEntryRepository(Protocol):
    def ensure(
        self,
        *,
        credential_id: str,
        issuer_did: str,
        status_list_id: str,
        status_purpose: StatusPurpose,
        candidate_index: int,
        list_length: int,
        created_at: datetime,
    ) -> CredentialStatusEntry: ...

    def get_by_credential_id(
        self,
        credential_id: str,
    ) -> CredentialStatusEntry | None: ...

    def list_by_status_list(
        self,
        status_list_id: str,
        *,
        limit: int,
    ) -> tuple[CredentialStatusEntry, ...]: ...

    def revoked_indices(
        self,
        status_list_id: str,
        *,
        limit: int,
    ) -> tuple[int, ...]: ...

    def list_status_list_ids(
        self,
        issuer_did: str,
        *,
        status_purpose: StatusPurpose,
    ) -> tuple[str, ...]: ...


class StatusListRepository(Protocol):
    def get(
        self,
        status_list_id: str,
    ) -> StatusListPublication | None: ...

    def publish(
        self,
        publication: StatusListPublication,
        *,
        expected_version: int | None,
    ) -> StatusListPublication: ...

    def list_history(
        self,
        status_list_id: str,
    ) -> tuple[StatusListPublication, ...]: ...

    def get_version(
        self,
        status_list_id: str,
        version: int,
    ) -> StatusListPublication | None: ...


class AuditOutboxRepository(Protocol):
    def enqueue(self, record: AuditOutboxRecord) -> AuditOutboxRecord: ...

    def get(self, event_id: str) -> AuditOutboxRecord | None: ...

    def list_ready(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> tuple[AuditOutboxRecord, ...]: ...

    def claim(
        self,
        event_id: str,
        *,
        source: AuditOutboxSource,
        claimed_at: datetime,
        lease_until: datetime,
        expected_version: int,
    ) -> AuditOutboxRecord | None: ...

    def mark_delivered(
        self,
        event_id: str,
        *,
        source: AuditOutboxSource,
        delivered_at: datetime,
        expected_version: int,
    ) -> AuditOutboxRecord: ...

    def reschedule(
        self,
        event_id: str,
        *,
        source: AuditOutboxSource,
        available_at: datetime,
        failed_at: datetime,
        error_code: str,
        expected_version: int,
    ) -> AuditOutboxRecord: ...
