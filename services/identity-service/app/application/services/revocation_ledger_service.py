import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from threading import Lock
from typing import Protocol

from app.domain.persistence import PersistenceUnavailableError
from app.domain.revocation_ledger import (
    EVENT_REVOKED,
    GENESIS_HASH,
    SOURCE_REVOCATION,
    LedgerHead,
    RevocationEvent,
    RevocationLedgerIntegrityError,
    RevocationLedgerUnavailableError,
    compute_event_hash,
    event_key,
    seal,
    seal_matches,
)


Clock = Callable[[], datetime]
_EVENT_PURPOSE = "revocation-event"
_APPEND_ATTEMPTS = 32


class LedgerDuplicateError(Exception):
    """Another writer took this sequence or event key first."""


class RevocationLedgerRepository(Protocol):
    def head(self) -> RevocationEvent | None: ...

    def by_key(self, key: str) -> RevocationEvent | None: ...

    def by_sequence(self, sequence: int) -> RevocationEvent | None: ...

    def by_status_list(
        self,
        status_list_id: str,
    ) -> tuple[RevocationEvent, ...]: ...

    def by_credential(
        self,
        credential_id: str,
    ) -> tuple[RevocationEvent, ...]: ...

    def ordered(self) -> tuple[RevocationEvent, ...]: ...

    def append(self, event: RevocationEvent) -> None: ...


class LedgerAnchor(Protocol):
    """The highest ledger head ever seen, stored outside the ledger's reach."""

    def read(self) -> LedgerHead | None: ...

    def advance(self, head: LedgerHead) -> None: ...


@dataclass
class LedgerVerificationCache:
    """Avoids re-walking an unchanged chain on every status fetch."""

    head: LedgerHead | None = None
    verified_at: datetime | None = None
    lock: Lock = field(default_factory=Lock)


class RevocationLedgerService:
    def __init__(
        self,
        *,
        repository: RevocationLedgerRepository,
        mac_key: bytes,
        clock: Clock,
        anchor: LedgerAnchor | None = None,
        anchor_required: bool = False,
        anchor_bootstrap: bool = False,
        cache: LedgerVerificationCache | None = None,
        full_verify_seconds: int = 60,
    ) -> None:
        self._repository = repository
        self._mac_key = mac_key
        self._clock = clock
        self._anchor = anchor
        self._anchor_required = anchor_required
        self._anchor_bootstrap = anchor_bootstrap
        self._cache = cache or LedgerVerificationCache()
        self._full_verify_after = timedelta(seconds=full_verify_seconds)

    def record_revocation(
        self,
        *,
        credential_id: str,
        issuer_did: str,
        status_list_id: str,
        status_list_index: int,
        status_purpose: str,
        reason: str,
        actor: str,
        correlation_id: str,
        source: str = SOURCE_REVOCATION,
    ) -> RevocationEvent:
        key = event_key(status_list_id, status_list_index)
        for attempt in range(_APPEND_ATTEMPTS):
            try:
                existing = self._repository.by_key(key)
                if existing is not None:
                    return existing
                head = self._repository.head()
                event = self._sealed(
                    RevocationEvent(
                        event_key=key,
                        sequence=1 if head is None else head.sequence + 1,
                        credential_id=credential_id,
                        issuer_did=issuer_did,
                        status_list_id=status_list_id,
                        status_list_index=status_list_index,
                        status_purpose=status_purpose,
                        event_type=EVENT_REVOKED,
                        occurred_at=self._now().isoformat(),
                        reason_digest=sha256(reason.encode()).hexdigest(),
                        actor=actor,
                        correlation_id=correlation_id,
                        source=source,
                        previous_hash=(
                            GENESIS_HASH if head is None else head.event_hash
                        ),
                        event_hash="",
                        mac="",
                    )
                )
                self._repository.append(event)
            except LedgerDuplicateError:
                # A concurrent writer won this sequence: spread the retries out.
                time.sleep(random.uniform(0, 0.002 * (attempt + 1)))
                continue
            except RevocationLedgerIntegrityError:
                raise
            except PersistenceUnavailableError as error:
                raise RevocationLedgerUnavailableError(
                    "The revocation ledger is unavailable."
                ) from error
            if self._anchor is not None:
                self._anchor.advance(
                    LedgerHead(event.sequence, event.event_hash)
                )
            return event
        raise RevocationLedgerUnavailableError(
            "The revocation ledger is too contended to accept this event."
        )

    def assert_intact(self) -> None:
        """Raises unless the whole chain and the external anchor agree."""
        try:
            tip = self._repository.head()
        except RevocationLedgerIntegrityError:
            raise
        except PersistenceUnavailableError as error:
            raise RevocationLedgerUnavailableError(
                "The revocation ledger is unavailable."
            ) from error
        head = (
            None if tip is None else LedgerHead(tip.sequence, tip.event_hash)
        )
        self._check_anchor(head)
        if self._recently_verified(head):
            return
        self._verify_chain(head)
        with self._cache.lock:
            self._cache.head = head
            self._cache.verified_at = self._now()

    def events_for_list(
        self,
        status_list_id: str,
    ) -> tuple[RevocationEvent, ...]:
        self.assert_intact()
        return self._read(
            lambda: self._repository.by_status_list(status_list_id)
        )

    def is_revoked(self, credential_id: str) -> bool:
        return self.revocation_of(credential_id) is not None

    def revocation_of(self, credential_id: str) -> RevocationEvent | None:
        self.assert_intact()
        events = self._read(
            lambda: self._repository.by_credential(credential_id)
        )
        return events[0] if events else None

    def ordered_events(self) -> tuple[RevocationEvent, ...]:
        self.assert_intact()
        return self._read(self._repository.ordered)

    def current_head(self) -> LedgerHead | None:
        self.assert_intact()
        tip = self._read(self._repository.head)
        return None if tip is None else LedgerHead(tip.sequence, tip.event_hash)

    def _check_anchor(self, head: LedgerHead | None) -> None:
        if self._anchor is None:
            if self._anchor_required:
                raise RevocationLedgerIntegrityError("LEDGER_ANCHOR_MISSING")
            return
        anchored = self._anchor.read()
        if anchored is None:
            if head is None:
                return
            if self._anchor_required and not self._anchor_bootstrap:
                raise RevocationLedgerIntegrityError("LEDGER_ANCHOR_MISSING")
            self._anchor.advance(head)
            return
        if head is None or head.sequence < anchored.sequence:
            raise RevocationLedgerIntegrityError("LEDGER_ROLLED_BACK")
        at_anchor = self._read(
            lambda: self._repository.by_sequence(anchored.sequence)
        )
        if at_anchor is None or at_anchor.event_hash != anchored.event_hash:
            raise RevocationLedgerIntegrityError("LEDGER_FORKED")
        if head.sequence > anchored.sequence:
            self._anchor.advance(head)

    def _recently_verified(self, head: LedgerHead | None) -> bool:
        with self._cache.lock:
            return (
                self._cache.verified_at is not None
                and self._cache.head == head
                and self._now() - self._cache.verified_at
                < self._full_verify_after
            )

    def _verify_chain(self, head: LedgerHead | None) -> None:
        previous = GENESIS_HASH
        expected = 1
        for event in self._read(self._repository.ordered):
            if event.sequence != expected:
                raise RevocationLedgerIntegrityError("LEDGER_SEQUENCE_GAP")
            if event.previous_hash != previous:
                raise RevocationLedgerIntegrityError("LEDGER_CHAIN_BROKEN")
            if compute_event_hash(event) != event.event_hash:
                raise RevocationLedgerIntegrityError("LEDGER_EVENT_ALTERED")
            if not seal_matches(
                self._mac_key,
                _EVENT_PURPOSE,
                event.event_hash,
                event.mac,
            ):
                raise RevocationLedgerIntegrityError("LEDGER_EVENT_FORGED")
            if event.event_key != event_key(
                event.status_list_id,
                event.status_list_index,
            ):
                raise RevocationLedgerIntegrityError("LEDGER_EVENT_ALTERED")
            previous = event.event_hash
            expected += 1
        tip_sequence = 0 if head is None else head.sequence
        if expected - 1 < tip_sequence:
            raise RevocationLedgerIntegrityError("LEDGER_SEQUENCE_GAP")

    def _sealed(self, event: RevocationEvent) -> RevocationEvent:
        event_hash = compute_event_hash(event)
        return replace(
            event,
            event_hash=event_hash,
            mac=seal(self._mac_key, _EVENT_PURPOSE, event_hash),
        )

    def _read(self, operation):
        try:
            return operation()
        except RevocationLedgerIntegrityError:
            raise
        except PersistenceUnavailableError as error:
            raise RevocationLedgerUnavailableError(
                "The revocation ledger is unavailable."
            ) from error

    def _now(self) -> datetime:
        return self._clock().astimezone(UTC)
