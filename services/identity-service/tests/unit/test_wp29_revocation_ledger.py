"""WP-29 P0-2: revocation history must survive record loss and stale restores.

These run against the in-memory collection adapter. The database-permission
test (ordinary principal cannot update or delete) needs real MongoDB and lives
in the isolated stack run.
"""

import threading
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.application.services.revocation_ledger_service import (
    LedgerDuplicateError,
    RevocationLedgerService,
)
from app.application.services.revocation_reconciliation_service import (
    RevocationReconciliationService,
)
from app.application.services.status_list_service import StatusListService
from app.config.revocation_ledger_settings import (
    load_revocation_ledger_settings,
)
from app.config.status_list_settings import StatusListSettings
from app.domain.bitstring_status_list import (
    StatusPurpose,
    generate_status_list_id,
)
from app.domain.persistence import (
    PersistenceConfigurationError,
    PersistenceUnavailableError,
)
from app.domain.revocation_ledger import (
    LedgerHead,
    RevocationEvent,
    RevocationLedgerIntegrityError,
    RevocationLedgerUnavailableError,
)
from app.infrastructure.persistence.memory_db import MemoryCollection
from app.infrastructure.persistence.revocation_ledger_anchor import (
    FileLedgerAnchor,
)
from app.infrastructure.persistence.revocation_ledger_repository import (
    MongoRevocationLedgerRepository,
)
from app.infrastructure.status_list_document_generator import (
    decode_status_list_bit,
    encode_status_list,
)


KEY = b"k" * 32
LENGTH = 131_072
NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
LIST_ID = generate_status_list_id("did:web:issuer.example", sequence=1)


class Repo:
    """Plain list repository so tests can tamper exactly like an attacker."""

    def __init__(self) -> None:
        self.events: list[RevocationEvent] = []
        self.down = False
        self.lock = threading.Lock()

    def _guard(self) -> None:
        if self.down:
            raise PersistenceUnavailableError("down")

    def head(self):
        self._guard()
        return max(self.events, key=lambda e: e.sequence, default=None)

    def by_key(self, key):
        self._guard()
        return next((e for e in self.events if e.event_key == key), None)

    def by_sequence(self, sequence):
        self._guard()
        return next((e for e in self.events if e.sequence == sequence), None)

    def by_status_list(self, status_list_id):
        self._guard()
        return tuple(
            e for e in self.events if e.status_list_id == status_list_id
        )

    def by_credential(self, credential_id):
        self._guard()
        return tuple(
            e for e in self.events if e.credential_id == credential_id
        )

    def ordered(self):
        self._guard()
        return tuple(sorted(self.events, key=lambda e: e.sequence))

    def append(self, event):
        self._guard()
        with self.lock:
            if any(
                e.sequence == event.sequence or e.event_key == event.event_key
                for e in self.events
            ):
                raise LedgerDuplicateError()
            self.events.append(event)


class Anchor:
    def __init__(self) -> None:
        self.head: LedgerHead | None = None

    def read(self):
        return self.head

    def advance(self, head):
        if self.head is None or head.sequence > self.head.sequence:
            self.head = head


def ledger(repo=None, anchor=None, **options) -> RevocationLedgerService:
    return RevocationLedgerService(
        repository=repo or Repo(),
        mac_key=options.pop("mac_key", KEY),
        clock=lambda: NOW,
        anchor=anchor,
        full_verify_seconds=0,
        **options,
    )


def revoke(service, index: int, credential_id: str | None = None):
    return service.record_revocation(
        credential_id=credential_id or f"urn:cred:{index}",
        issuer_did="did:web:issuer.example",
        status_list_id=LIST_ID,
        status_list_index=index,
        status_purpose="revocation",
        reason="key compromise",
        actor="issuer-1",
        correlation_id=f"corr-{index}",
    )


class Entries:
    def __init__(self, indices) -> None:
        self.indices = set(indices)

    def list_by_status_list(self, status_list_id, *, limit):
        return tuple(
            SimpleNamespace(
                issuer_did="did:web:issuer.example",
                status_purpose=StatusPurpose.REVOCATION,
            )
            for _ in sorted(self.indices or {0})
        ) if self.has_entries else ()

    has_entries = True

    def revoked_indices(self, status_list_id, *, limit):
        return tuple(sorted(self.indices))


class Lists:
    def __init__(self) -> None:
        self.current = None
        self.versions = []

    def get(self, status_list_id):
        return self.current

    def publish(self, publication, *, expected_version):
        self.current = publication
        self.versions.append(publication)
        return publication


class Generator:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, **kwargs):
        self.calls += 1
        return {"encoded": kwargs["encoded_list"]}


def status_service(entries, lists, revocation_ledger, generator=None):
    settings = SimpleNamespace(
        list_length=LENGTH,
        capacity=LENGTH,
        ttl_seconds=300,
        public_base_url="https://status.test",
    )
    service = StatusListService(
        entry_repository=entries,
        status_list_repository=lists,
        generator=generator or Generator(),
        settings=settings,
        clock=lambda: NOW,
        id_generator=lambda: "0" * 24,
        revocation_ledger=revocation_ledger,
    )
    service.status_list_url = lambda identifier: f"https://s.test/{identifier}"
    return service


def bit(publication, index: int) -> bool:
    return decode_status_list_bit(publication.encoded_list, index)


def test_scenario_1_deleted_record_keeps_the_revoked_bit() -> None:
    service = ledger()
    revoke(service, 7)
    entries, lists = Entries({7}), Lists()
    statuses = status_service(entries, lists, service)
    assert bit(statuses.get_publication(LIST_ID), 7) is True
    entries.indices = set()  # the credential document is gone
    assert bit(statuses.get_publication(LIST_ID), 7) is True


def test_scenario_1b_all_records_lost_still_publishes_the_revocation() -> None:
    service = ledger()
    revoke(service, 7)
    entries, lists = Entries(set()), Lists()
    entries.has_entries = False
    publication = status_service(entries, lists, service).get_publication(
        LIST_ID
    )
    assert bit(publication, 7) is True


def test_scenario_2_older_snapshot_cannot_clear_a_revocation() -> None:
    service = ledger()
    revoke(service, 3)
    entries, lists = Entries({3}), Lists()
    statuses = status_service(entries, lists, service)
    statuses.get_publication(LIST_ID)
    entries.indices = set()  # records rolled back to before the revocation
    lists.current = None  # status_lists rolled back as well
    assert bit(statuses.get_publication(LIST_ID), 3) is True


def test_scenario_4_without_ledger_support_a_clearing_list_is_refused() -> None:
    entries, lists = Entries({3}), Lists()
    statuses = status_service(entries, lists, None)
    statuses.get_publication(LIST_ID)
    entries.indices = set()
    with pytest.raises(RevocationLedgerIntegrityError) as caught:
        statuses.get_publication(LIST_ID)
    assert caught.value.code == "STATUS_BIT_WOULD_CLEAR"


def test_ledger_missing_event_with_older_signed_list_fails_closed() -> None:
    repo = Repo()
    service = ledger(repo)
    revoke(service, 3)
    entries, lists = Entries({3}), Lists()
    statuses = status_service(entries, lists, service)
    statuses.get_publication(LIST_ID)
    repo.events.clear()
    entries.indices = set()
    generator_calls = len(lists.versions)
    with pytest.raises(RevocationLedgerIntegrityError):
        statuses.get_publication(LIST_ID)
    assert len(lists.versions) == generator_calls


def test_scenario_4_unavailable_ledger_publishes_nothing() -> None:
    repo = Repo()
    service = ledger(repo)
    revoke(service, 1)
    repo.down = True
    lists = Lists()
    with pytest.raises(RevocationLedgerUnavailableError):
        status_service(Entries({1}), lists, service).get_publication(LIST_ID)
    assert lists.versions == []


def test_scenario_4_altered_event_is_detected() -> None:
    repo = Repo()
    service = ledger(repo)
    revoke(service, 1)
    revoke(service, 2)
    original = repo.events[0]
    repo.events[0] = RevocationEvent(
        **{**original.__dict__, "status_list_index": 9}
    )
    with pytest.raises(RevocationLedgerIntegrityError) as caught:
        service.assert_intact()
    assert caught.value.code == "LEDGER_EVENT_ALTERED"


def test_scenario_4_deleted_middle_event_is_detected() -> None:
    repo = Repo()
    service = ledger(repo)
    for index in (1, 2, 3):
        revoke(service, index)
    del repo.events[1]
    with pytest.raises(RevocationLedgerIntegrityError) as caught:
        service.assert_intact()
    assert caught.value.code == "LEDGER_SEQUENCE_GAP"


def test_scenario_4_forged_event_without_the_key_is_detected() -> None:
    repo = Repo()
    revoke(ledger(repo, mac_key=b"z" * 32), 1)
    with pytest.raises(RevocationLedgerIntegrityError) as caught:
        ledger(repo).assert_intact()
    assert caught.value.code == "LEDGER_EVENT_FORGED"


def test_scenario_4_sequence_rollback_is_caught_by_the_anchor() -> None:
    repo, anchor = Repo(), Anchor()
    service = ledger(repo, anchor)
    for index in (1, 2, 3):
        revoke(service, index)
    repo.events.pop()  # a consistent, shorter, older ledger
    with pytest.raises(RevocationLedgerIntegrityError) as caught:
        service.assert_intact()
    assert caught.value.code == "LEDGER_ROLLED_BACK"


def test_full_ledger_wipe_is_caught_by_the_anchor() -> None:
    repo, anchor = Repo(), Anchor()
    service = ledger(repo, anchor)
    revoke(service, 1)
    repo.events.clear()
    with pytest.raises(RevocationLedgerIntegrityError) as caught:
        service.assert_intact()
    assert caught.value.code == "LEDGER_ROLLED_BACK"


def test_forked_ledger_is_caught_by_the_anchor() -> None:
    repo, anchor = Repo(), Anchor()
    service = ledger(repo, anchor)
    revoke(service, 1)
    repo.events.clear()
    revoke(ledger(repo), 2)  # valid chain, different history, same length
    with pytest.raises(RevocationLedgerIntegrityError) as caught:
        service.assert_intact()
    assert caught.value.code == "LEDGER_FORKED"


def test_production_refuses_a_ledger_with_no_anchor_file() -> None:
    repo = Repo()
    revoke(ledger(repo), 1)
    service = ledger(repo, Anchor(), anchor_required=True)
    with pytest.raises(RevocationLedgerIntegrityError) as caught:
        service.assert_intact()
    assert caught.value.code == "LEDGER_ANCHOR_MISSING"


def test_explicit_bootstrap_creates_the_anchor() -> None:
    repo, anchor = Repo(), Anchor()
    revoke(ledger(repo), 1)
    ledger(
        repo,
        anchor,
        anchor_required=True,
        anchor_bootstrap=True,
    ).assert_intact()
    assert anchor.head is not None and anchor.head.sequence == 1


def test_scenario_6_replayed_revocation_is_idempotent() -> None:
    repo = Repo()
    service = ledger(repo)
    first = revoke(service, 5)
    second = revoke(service, 5)
    assert first == second
    assert len(repo.events) == 1


def test_scenario_7_concurrent_revocations_lose_nothing() -> None:
    repo = Repo()
    service = ledger(repo)
    errors: list[Exception] = []

    def worker(index: int) -> None:
        try:
            revoke(service, index)
        except Exception as error:  # pragma: no cover - asserted below
            errors.append(error)

    threads = [
        threading.Thread(target=worker, args=(index,)) for index in range(16)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert sorted(e.sequence for e in repo.events) == list(range(1, 17))
    service.assert_intact()


def test_failed_ledger_write_blocks_the_revocation() -> None:
    repo = Repo()
    repo.down = True
    with pytest.raises(RevocationLedgerUnavailableError):
        revoke(ledger(repo), 1)


def test_ledger_stores_a_reason_digest_not_the_reason() -> None:
    event = revoke(ledger(), 1)
    assert "compromise" not in str(event.to_document())


def test_file_anchor_detects_tampering_and_only_moves_forward(tmp_path) -> None:
    path = tmp_path / "anchor" / "head.json"
    anchor = FileLedgerAnchor(str(path), mac_key=KEY)
    assert anchor.read() is None
    anchor.advance(LedgerHead(5, "a" * 64))
    anchor.advance(LedgerHead(3, "b" * 64))
    assert anchor.read() == LedgerHead(5, "a" * 64)
    path.write_text(
        path.read_text().replace('"sequence": 5', '"sequence": 1')
    )
    with pytest.raises(RevocationLedgerIntegrityError) as caught:
        anchor.read()
    assert caught.value.code == "LEDGER_ANCHOR_ALTERED"


def test_wrong_key_cannot_read_the_anchor(tmp_path) -> None:
    path = tmp_path / "head.json"
    FileLedgerAnchor(str(path), mac_key=KEY).advance(LedgerHead(1, "a" * 64))
    with pytest.raises(RevocationLedgerIntegrityError):
        FileLedgerAnchor(str(path), mac_key=b"q" * 32).read()


def _credentials() -> MemoryCollection:
    return MemoryCollection()


def test_scenario_3_reconciliation_repairs_an_old_active_record() -> None:
    service = ledger()
    revoke(service, 4, "urn:cred:a")
    credentials = _credentials()
    credentials.insert_one(
        {"credentialId": "urn:cred:a", "status": "ACTIVE", "version": 1}
    )
    result = RevocationReconciliationService(
        ledger=service,
        credentials=credentials,
        clock=lambda: NOW,
    ).reconcile()
    assert result.records_repaired == 1
    assert credentials.find_one({"credentialId": "urn:cred:a"})[
        "status"
    ] == "REVOKED"


def test_reconciliation_backfills_revocations_made_before_the_ledger() -> None:
    repo = Repo()
    service = ledger(repo)
    credentials = _credentials()
    credentials.insert_one(
        {
            "credentialId": "urn:cred:old",
            "status": "REVOKED",
            "statusListId": LIST_ID,
            "statusListIndex": 11,
            "issuerDid": "did:web:issuer.example",
            "revocationReason": "x",
            "revokedBy": "issuer-1",
        }
    )
    reconciler = RevocationReconciliationService(
        ledger=service,
        credentials=credentials,
        clock=lambda: NOW,
    )
    assert reconciler.reconcile().backfilled == 1
    assert repo.events[0].source == "BACKFILL"
    assert reconciler.reconcile().backfilled == 0


def test_reconciliation_refuses_to_run_on_a_broken_ledger() -> None:
    repo, anchor = Repo(), Anchor()
    service = ledger(repo, anchor)
    revoke(service, 1)
    repo.events.clear()
    with pytest.raises(RevocationLedgerIntegrityError):
        RevocationReconciliationService(
            ledger=service,
            credentials=_credentials(),
            clock=lambda: NOW,
        ).reconcile()


def test_repository_uses_only_find_and_insert() -> None:
    collection = MemoryCollection()
    service = ledger(MongoRevocationLedgerRepository(collection))
    revoke(service, 1)
    revoke(service, 2)
    service.assert_intact()
    assert service.is_revoked("urn:cred:1") is True
    assert service.is_revoked("urn:cred:9") is False
    source = MongoRevocationLedgerRepository.__dict__
    assert not {"update", "delete", "replace"} & set(source)


@pytest.mark.parametrize("missing", ["uri", "key", "anchor"])
def test_production_settings_require_every_ledger_control(missing) -> None:
    values = {
        "IDENTITY_ENVIRONMENT": "production",
        "IDENTITY_REVOCATION_LEDGER_URI": "mongodb://ledger.invalid/db",
        "IDENTITY_REVOCATION_LEDGER_MAC_KEY_BASE64": "QUFB" * 11,
        "IDENTITY_REVOCATION_ANCHOR_PATH": "/anchor/head.json",
    }
    assert load_revocation_ledger_settings(values).separate_authority
    del values[
        {
            "uri": "IDENTITY_REVOCATION_LEDGER_URI",
            "key": "IDENTITY_REVOCATION_LEDGER_MAC_KEY_BASE64",
            "anchor": "IDENTITY_REVOCATION_ANCHOR_PATH",
        }[missing]
    ]
    with pytest.raises(PersistenceConfigurationError):
        load_revocation_ledger_settings(values)


def test_production_ledger_cannot_share_the_application_principal() -> None:
    with pytest.raises(PersistenceConfigurationError):
        load_revocation_ledger_settings(
            {
                "IDENTITY_ENVIRONMENT": "production",
                "IDENTITY_MONGO_URI": "mongodb://app.invalid/db",
                "IDENTITY_REVOCATION_LEDGER_URI": "mongodb://app.invalid/db",
                "IDENTITY_REVOCATION_LEDGER_MAC_KEY_BASE64": "QUFB" * 11,
                "IDENTITY_REVOCATION_ANCHOR_PATH": "/anchor/head.json",
            }
        )


def test_verified_chain_cache_expires() -> None:
    clock = {"now": NOW}
    repo = Repo()
    service = RevocationLedgerService(
        repository=repo,
        mac_key=KEY,
        clock=lambda: clock["now"],
        full_verify_seconds=60,
    )
    revoke(service, 1)
    service.assert_intact()
    original = repo.events[0]
    repo.events[0] = RevocationEvent(
        **{**original.__dict__, "status_list_index": 9}
    )
    service.assert_intact()  # within the documented window
    clock["now"] = NOW + timedelta(seconds=61)
    with pytest.raises(RevocationLedgerIntegrityError):
        service.assert_intact()


def test_encoded_fixture_is_stable() -> None:
    assert decode_status_list_bit(
        encode_status_list({3}, list_length=LENGTH),
        3,
    )
