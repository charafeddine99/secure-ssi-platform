from collections.abc import Callable
from datetime import datetime
from hashlib import sha256

from app.application.ports.repositories import RevocationRepository
from app.application.services.audit_outbox_service import (
    AuditOutboxDeliveryService,
)
from app.application.services.status_list_service import StatusListService
from app.domain.audit_outbox import (
    AuditOutboxRecord,
    AuditOutboxSource,
)
from app.domain.credential_status import (
    CredentialNotFoundError,
    CredentialStatus,
    CredentialStatusSnapshot,
    RevocationPolicy,
)
from app.domain.persistence import (
    AuditEvent,
    AuditEventType,
    PersistedCredential,
    RepositoryError,
)


Clock = Callable[[], datetime]
EventIdGenerator = Callable[[], str]


class CredentialRevocationService:
    def __init__(
        self,
        *,
        revocation_repository: RevocationRepository,
        status_list_service: StatusListService,
        audit_delivery_service: AuditOutboxDeliveryService,
        clock: Clock,
        event_id_generator: EventIdGenerator,
    ) -> None:
        self._revocation_repository = revocation_repository
        self._status_lists = status_list_service
        self._audit_delivery = audit_delivery_service
        self._clock = clock
        self._event_id_generator = event_id_generator

    def revoke(
        self,
        credential_id: str,
        *,
        reason: str,
        revoked_by: str,
        correlation_id: str,
    ) -> CredentialStatusSnapshot:
        credential = self._require_credential(credential_id)
        if credential.status is CredentialStatus.REVOKED:
            self._ensure_legacy_revocation_delivery(
                credential,
                correlation_id=correlation_id,
            )
        RevocationPolicy.require_revocable(credential.status)
        RevocationPolicy.require_transition(
            current=credential.status,
            target=CredentialStatus.REVOKED,
        )
        normalized_reason = RevocationPolicy.normalize_reason(reason)
        revoked_at = self._clock()
        status_entry = self._status_lists.ensure_entry(credential)
        audit_event = self._revocation_event(
            credential_id=credential.credential_id,
            revoked_at=revoked_at,
            revoked_by=revoked_by,
            correlation_id=correlation_id,
        )
        audit_outbox = AuditOutboxRecord.pending(
            event=audit_event,
            aggregate_type="credential",
            aggregate_id=credential.credential_id,
            source=AuditOutboxSource.CREDENTIAL,
        )
        revoked = self._revocation_repository.revoke(
            credential.credential_id,
            revoked_at=revoked_at,
            revoked_by=revoked_by,
            revocation_reason=normalized_reason,
            expected_version=credential.version,
            status_entry=status_entry,
            audit_outbox=audit_outbox,
        )
        self._try_deliver(audit_event.id)
        return self._snapshot(revoked)

    def get_status(
        self,
        credential_id: str,
        *,
        correlation_id: str,
        actor_id: str | None = None,
    ) -> CredentialStatusSnapshot:
        credential = self._require_credential(credential_id)
        checked_at = self._clock()
        effective_status = RevocationPolicy.effective_status(
            stored_status=credential.status,
            expiration_date=credential.expiration_date,
            checked_at=checked_at,
        )
        if effective_status is not credential.status:
            RevocationPolicy.require_transition(
                current=credential.status,
                target=effective_status,
            )
            credential = self._revocation_repository.mark_expired(
                credential.credential_id,
                expired_at=checked_at,
                expected_version=credential.version,
            )
        if credential.status is CredentialStatus.REVOKED:
            self._ensure_legacy_revocation_delivery(
                credential,
                correlation_id=correlation_id,
            )
        self._enqueue_status_check(
            event_type=AuditEventType.STATUS_CHECKED,
            credential_id=credential.credential_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            status=credential.status,
            occurred_at=checked_at,
        )
        return self._snapshot(credential)

    def _require_credential(
        self,
        credential_id: str,
    ) -> PersistedCredential:
        normalized = credential_id.strip()
        if not normalized or len(normalized) > 2_048:
            raise CredentialNotFoundError("Credential does not exist.")
        credential = self._revocation_repository.get_by_credential_id(
            normalized
        )
        if credential is None:
            raise CredentialNotFoundError("Credential does not exist.")
        return credential

    def _ensure_legacy_revocation_delivery(
        self,
        credential: PersistedCredential,
        *,
        correlation_id: str,
    ) -> None:
        if (
            credential.status is not CredentialStatus.REVOKED
            or credential.revoked_at is None
            or credential.revoked_by is None
        ):
            raise ValueError(
                "Revocation audit requires persisted revocation metadata."
            )
        self._status_lists.ensure_entry(credential)
        event_id = _revocation_event_id(credential.credential_id)
        if self._try_deliver(event_id):
            return
        event = self._revocation_event(
            credential_id=credential.credential_id,
            revoked_at=credential.revoked_at,
            revoked_by=credential.revoked_by,
            correlation_id=correlation_id,
        )
        try:
            self._audit_delivery.ensure(
                AuditOutboxRecord.pending(
                    event=event,
                    aggregate_type="credential",
                    aggregate_id=credential.credential_id,
                    source=AuditOutboxSource.COLLECTION,
                )
            )
        except RepositoryError:
            return
        self._try_deliver(event.id)

    def _enqueue_status_check(
        self,
        *,
        event_type: AuditEventType,
        credential_id: str,
        actor_id: str | None,
        correlation_id: str,
        status: CredentialStatus,
        occurred_at: datetime,
    ) -> None:
        event = AuditEvent(
            id=self._event_id_generator(),
            event_type=event_type,
            subject_id=credential_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            metadata={"status": status.value},
            created_at=occurred_at,
            updated_at=occurred_at,
        )
        self._audit_delivery.enqueue(
            AuditOutboxRecord.pending(
                event=event,
                aggregate_type="credential",
                aggregate_id=credential_id,
                source=AuditOutboxSource.COLLECTION,
            )
        )
        self._try_deliver(event.id)

    @staticmethod
    def _revocation_event(
        *,
        credential_id: str,
        revoked_at: datetime,
        revoked_by: str,
        correlation_id: str,
    ) -> AuditEvent:
        return AuditEvent(
            id=_revocation_event_id(credential_id),
            event_type=AuditEventType.CREDENTIAL_REVOKED,
            subject_id=credential_id,
            actor_id=revoked_by,
            correlation_id=correlation_id,
            metadata={"status": CredentialStatus.REVOKED.value},
            created_at=revoked_at,
            updated_at=revoked_at,
        )

    def _try_deliver(self, event_id: str) -> bool:
        try:
            return self._audit_delivery.deliver_event(event_id)
        except RepositoryError:
            return False

    @staticmethod
    def _snapshot(
        credential: PersistedCredential,
    ) -> CredentialStatusSnapshot:
        return CredentialStatusSnapshot(
            credential_id=credential.credential_id,
            status=credential.status,
            expiration_date=credential.expiration_date,
            revoked_at=credential.revoked_at,
            revocation_reason=credential.revocation_reason,
            revoked_by=credential.revoked_by,
            version=credential.version,
        )


def _revocation_event_id(credential_id: str) -> str:
    value = f"CREDENTIAL_REVOKED\0{credential_id}".encode("utf-8")
    return sha256(value).hexdigest()[:24]
