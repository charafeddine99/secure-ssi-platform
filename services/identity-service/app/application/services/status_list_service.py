from collections.abc import Callable
from datetime import datetime
from hashlib import sha256

from app.application.ports.status_list_repositories import (
    CredentialStatusEntryRepository,
    StatusListRepository,
)
from app.application.ports.issuance import IssuerStatusListPublisher
from app.application.services.internal_metrics import InternalMetrics
from app.config.status_list_settings import StatusListSettings
from app.domain.bitstring_status_list import (
    CredentialStatusEntry,
    StatusListCapacityError,
    StatusListConflictError,
    StatusListNotFoundError,
    StatusListPublication,
    StatusListVersionNotFoundError,
    StatusPurpose,
    deterministic_index_candidate,
    generate_status_list_id,
    status_list_sequence,
)
from app.domain.persistence import PersistedCredential
from app.infrastructure.status_list_document_generator import encode_status_list


Clock = Callable[[], datetime]
IdGenerator = Callable[[], str]


class StatusListService:
    def __init__(
        self,
        *,
        entry_repository: CredentialStatusEntryRepository,
        status_list_repository: StatusListRepository,
        generator: IssuerStatusListPublisher,
        settings: StatusListSettings,
        clock: Clock,
        id_generator: IdGenerator,
        metrics: InternalMetrics | None = None,
    ) -> None:
        self._entries = entry_repository
        self._status_lists = status_list_repository
        self._generator = generator
        self._settings = settings
        self._clock = clock
        self._id_generator = id_generator
        self._metrics = metrics

    def ensure_entry(
        self,
        credential: PersistedCredential,
    ) -> CredentialStatusEntry:
        existing = self._entries.get_by_credential_id(
            credential.credential_id
        )
        if existing is not None:
            return existing
        identifiers = self._entries.list_status_list_ids(
            credential.issuer_did,
            status_purpose=StatusPurpose.REVOCATION,
        )
        sequence = (
            status_list_sequence(identifiers[-1]) if identifiers else 1
        )
        while sequence <= 999_999:
            status_list_id = generate_status_list_id(
                credential.issuer_did,
                sequence=sequence,
            )
            try:
                return self._entries.ensure(
                    credential_id=credential.credential_id,
                    issuer_did=credential.issuer_did,
                    status_list_id=status_list_id,
                    status_purpose=StatusPurpose.REVOCATION,
                    candidate_index=deterministic_index_candidate(
                        credential.credential_id,
                        list_length=self._settings.capacity,
                    ),
                    list_length=self._settings.capacity,
                    created_at=self._clock(),
                )
            except StatusListCapacityError:
                sequence += 1
                if self._metrics is not None:
                    self._metrics.record_rollover()
        raise StatusListCapacityError(
            "No status-list sequence remains for this issuer."
        )

    def get_publication(
        self,
        status_list_id: str,
    ) -> StatusListPublication:
        normalized = status_list_id.strip()
        entries = self._entries.list_by_status_list(
            normalized,
            limit=self._settings.list_length,
        )
        if not entries:
            raise StatusListNotFoundError(
                "The requested status list does not exist."
            )
        issuer_did = entries[0].issuer_did
        if any(
            entry.issuer_did != issuer_did
            or entry.status_purpose is not StatusPurpose.REVOCATION
            for entry in entries
        ):
            raise StatusListConflictError(
                "Status list entries have inconsistent ownership."
            )
        revoked_indices = self._entries.revoked_indices(
            normalized,
            limit=self._settings.list_length,
        )
        encoded_list = encode_status_list(
            revoked_indices,
            list_length=self._settings.list_length,
        )
        fingerprint = _publication_fingerprint(
            encoded_list=encoded_list,
            assigned_entries=len(entries),
        )
        existing = self._status_lists.get(normalized)
        if existing is not None and existing.content_hash == fingerprint:
            self._observe_utilization(existing)
            return existing
        return self._publish(
            status_list_id=normalized,
            issuer_did=issuer_did,
            encoded_list=encoded_list,
            content_hash=fingerprint,
            assigned_entries=len(entries),
            revoked_entries=len(revoked_indices),
            existing=existing,
        )

    def _publish(
        self,
        *,
        status_list_id: str,
        issuer_did: str,
        encoded_list: str,
        content_hash: str,
        assigned_entries: int,
        revoked_entries: int,
        existing: StatusListPublication | None,
    ) -> StatusListPublication:
        published_at = self._clock()
        version = 1 if existing is None else existing.version + 1
        publication = StatusListPublication(
            id=self._id_generator() if existing is None else existing.id,
            status_list_id=status_list_id,
            issuer_did=issuer_did,
            status_purpose=StatusPurpose.REVOCATION,
            encoded_list=encoded_list,
            content_hash=content_hash,
            document=self._generator.generate(
                status_list_url=self.status_list_url(status_list_id),
                issuer_did=issuer_did,
                encoded_list=encoded_list,
                ttl_seconds=self._settings.ttl_seconds,
                published_at=published_at,
            ),
            list_length=self._settings.list_length,
            capacity=self._settings.capacity,
            assigned_entries=assigned_entries,
            revoked_entries=revoked_entries,
            ttl_seconds=self._settings.ttl_seconds,
            etag=f'"{content_hash}-v{version}"',
            published_at=published_at,
            created_at=(
                published_at if existing is None else existing.created_at
            ),
            updated_at=published_at,
            version=version,
        )
        try:
            published = self._status_lists.publish(
                publication,
                expected_version=(
                    None if existing is None else existing.version
                ),
            )
            if self._metrics is not None:
                self._metrics.record_publication(
                    status_list_id=published.status_list_id,
                    assigned_entries=published.assigned_entries,
                    capacity=published.capacity,
                    published_at=published.published_at,
                )
            return published
        except StatusListConflictError:
            concurrent = self._status_lists.get(status_list_id)
            if (
                concurrent is not None
                and concurrent.content_hash == content_hash
            ):
                return concurrent
            raise

    def get_history(
        self,
        status_list_id: str,
    ) -> tuple[StatusListPublication, ...]:
        self.get_publication(status_list_id)
        history = self._status_lists.list_history(status_list_id)
        if not history:
            raise StatusListNotFoundError(
                "The requested status list does not exist."
            )
        return history

    def get_version(
        self,
        status_list_id: str,
        version: int,
    ) -> StatusListPublication:
        publication = self._status_lists.get_version(
            status_list_id,
            version,
        )
        if publication is None:
            raise StatusListVersionNotFoundError(
                "The requested status-list version does not exist."
            )
        return publication

    def is_active(self, publication: StatusListPublication) -> bool:
        identifiers = self._entries.list_status_list_ids(
            publication.issuer_did,
            status_purpose=publication.status_purpose,
        )
        return bool(
            identifiers
            and publication.status_list_id
            == max(identifiers, key=status_list_sequence)
        )

    def status_list_url(self, status_list_id: str) -> str:
        return (
            f"{self._settings.public_base_url.rstrip('/')}/"
            f"{status_list_id}"
        )

    def _observe_utilization(
        self,
        publication: StatusListPublication,
    ) -> None:
        if self._metrics is not None:
            self._metrics.observe_utilization(
                status_list_id=publication.status_list_id,
                assigned_entries=publication.assigned_entries,
                capacity=publication.capacity,
            )


def _publication_fingerprint(
    *,
    encoded_list: str,
    assigned_entries: int,
) -> str:
    payload = f"{encoded_list}\0{assigned_entries}".encode("ascii")
    return sha256(payload).hexdigest()
