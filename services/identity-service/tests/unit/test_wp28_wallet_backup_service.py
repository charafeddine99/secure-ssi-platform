"""WP-28 Holder Wallet Backup & Restore service rules."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.application.services.wallet_backup_service import (
    ALREADY_PRESENT,
    HELD_BY_ANOTHER_WALLET,
    HOLDER_BINDING_MISMATCH,
    PROOF_INVALID,
    RESTORABLE,
    REVOKED,
    STATUS_UNVERIFIABLE,
    WalletBackupConflictError,
    WalletBackupIntegrityError,
    WalletBackupNotFoundError,
    WalletBackupService,
    WalletBackupTooLargeError,
)
from app.domain.credential_status import CredentialStatus
from app.domain.holder_wallet import HolderWallet, HolderWalletNotFoundError, WalletStatus
from app.domain.persistence import PersistedCredential
from app.infrastructure.persistence.mappers import new_object_id
from app.infrastructure.status_list_document_generator import encode_status_list
from tests.support.fake_mongo import FakeCollection

NOW = datetime(2026, 11, 3, 10, 0, tzinfo=UTC)
WALLET = "wallet_wp28_holder_a_000001"
OTHER_WALLET = "wallet_wp28_holder_b_000001"
HOLDER_DID = "did:key:z6MkWp28HolderA"
LIST_ID = "sl_wp28"


def _wallet(wallet_id: str, owner: str, did: str) -> HolderWallet:
    return HolderWallet(
        id=new_object_id(),
        wallet_id=wallet_id,
        owner_user_id=owner,
        holder_did=did,
        status=WalletStatus.ACTIVE,
        key_reference="dev-key-ref-wp28-" + owner,
        created_at=NOW,
        updated_at=NOW,
    )


class Wallets:
    def __init__(self, *wallets: HolderWallet) -> None:
        self.wallets = {item.wallet_id: item for item in wallets}

    def require_owned_active(self, wallet_id, *, owner_user_id, correlation_id):
        wallet = self.wallets.get(wallet_id)
        if wallet is None or wallet.owner_user_id != owner_user_id:
            raise HolderWalletNotFoundError("hidden")
        return wallet


class Credentials:
    def __init__(self) -> None:
        self.records: dict[str, PersistedCredential] = {}
        self.fail_after: int | None = None

    def add(self, record):
        if self.fail_after is not None:
            if self.fail_after == 0:
                raise RuntimeError("disk full")
            self.fail_after -= 1
        self.records[record.credential_id] = record
        return record

    def get_by_credential_id(self, credential_id):
        return self.records.get(credential_id)

    def list_by_wallet(self, wallet_id, *, owner_user_id, limit=100):
        return tuple(
            item for item in self.records.values()
            if item.wallet_id == wallet_id and item.owner_user_id == owner_user_id
        )[:limit]


@dataclass
class Proofs:
    invalid: set[str]

    def verify_credential(self, credential, *, verified_at):
        return SimpleNamespace(verified=credential["id"] not in self.invalid)


class StatusLists:
    def __init__(self, revoked: set[int]) -> None:
        self.revoked = revoked

    def get(self, status_list_id):
        if status_list_id != LIST_ID:
            return None
        return SimpleNamespace(encoded_list=encode_status_list(self.revoked, list_length=131072))


class Audits:
    def __init__(self) -> None:
        self.events = []

    def append(self, event):
        self.events.append(event)
        return event

    def list_by_subject(self, subject_id, *, limit=100):
        return tuple(event for event in self.events if event.subject_id == subject_id)[:limit]


def _vc(credential_id: str, index: int, subject: str = HOLDER_DID) -> dict:
    return {
        "@context": ["https://www.w3.org/ns/credentials/v2"],
        "id": credential_id,
        "type": ["VerifiableCredential", "UniversityDegreeCredential"],
        "issuer": "did:web:synthetic-issuer.local",
        "validFrom": "2026-01-01T00:00:00Z",
        "validUntil": "2027-01-01T00:00:00Z",
        "credentialSubject": {"id": subject, "degree": "BSc", "gpa": 4.0},
        "credentialStatus": {
            "type": "BitstringStatusListEntry",
            "statusPurpose": "revocation",
            "statusListIndex": str(index),
            "statusListCredential": f"https://issuer.example/status-lists/{LIST_ID}",
        },
        "proof": {"type": "DataIntegrityProof", "proofValue": "zSynthetic"},
    }


def _stored(vc: dict, wallet_id: str = WALLET, owner: str = "usr_a") -> PersistedCredential:
    return PersistedCredential(
        id=new_object_id(),
        credential_id=vc["id"],
        issuer_did=vc["issuer"],
        holder_did=HOLDER_DID,
        credential_type=tuple(vc["type"]),
        issuance_date=NOW - timedelta(days=1),
        expiration_date=NOW + timedelta(days=300),
        credential_hash="0" * 64,
        status=CredentialStatus.ACTIVE,
        raw_credential=vc,
        wallet_id=wallet_id,
        owner_user_id=owner,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.fixture
def env():
    credentials = Credentials()
    audits = Audits()
    proofs = Proofs(invalid=set())
    status = StatusLists(revoked=set())
    service = WalletBackupService(
        wallets=Wallets(
            _wallet(WALLET, "usr_a", HOLDER_DID),
            _wallet(OTHER_WALLET, "usr_b", "did:key:z6MkWp28HolderB"),
        ),
        credentials=credentials,
        status_lists=status,
        proof_service=proofs,
        audits=audits,
        backups=FakeCollection(),
        restore_jobs=FakeCollection(),
        clock=lambda: NOW,
    )
    for index in range(3):
        credentials.add(_stored(_vc(f"urn:uuid:wp28-{index}", index)))
    return SimpleNamespace(
        service=service, credentials=credentials, audits=audits, proofs=proofs, status=status
    )


def _lose_all(env) -> None:
    env.credentials.records.clear()


def test_backup_payload_is_canonical_metadata_only_and_has_no_key_material(env) -> None:
    record, payload = env.service.create_backup(WALLET, owner_user_id="usr_a")
    content = json.loads(payload)

    assert record.item_count == 3 and content["walletId"] == WALLET
    assert [item["credentialId"] for item in content["items"]] == sorted(
        f"urn:uuid:wp28-{i}" for i in range(3)
    )
    assert "dev-key-ref" not in payload and "keyReference" not in payload
    assert "gpa\":4.0" in payload  # floats survive: the exact string is what gets encrypted
    stored = env.service._backups.documents[0]
    assert "payload" not in stored and "items" not in stored
    assert env.audits.events[-1].event_type.value == "WALLET_BACKUP_CREATED"


def test_restore_after_loss_reimports_verified_credentials_and_is_idempotent(env) -> None:
    record, payload = env.service.create_backup(WALLET, owner_user_id="usr_a")
    _lose_all(env)

    preview = env.service.preview(WALLET, record.backup_id, owner_user_id="usr_a", payload=payload)
    job, created = env.service.restore(
        WALLET, record.backup_id, owner_user_id="usr_a", payload=payload,
        idempotency_key="restore-key-000000001",
    )
    replay, replay_created = env.service.restore(
        WALLET, record.backup_id, owner_user_id="usr_a", payload=payload,
        idempotency_key="restore-key-000000001",
    )
    second, _ = env.service.restore(
        WALLET, record.backup_id, owner_user_id="usr_a", payload=payload,
        idempotency_key="restore-key-000000002",
    )

    assert preview.count(RESTORABLE) == 3
    assert created and job.status == "COMPLETED" and job.restored == 3
    assert not replay_created and replay.restore_id == job.restore_id
    assert second.restored == 0 and second.already_present == 3 and second.status == "COMPLETED"
    assert len(env.credentials.records) == 3
    restored = env.credentials.records["urn:uuid:wp28-0"]
    assert restored.wallet_id == WALLET and restored.status_list_index == 0


def test_tampered_or_foreign_archives_fail_closed(env) -> None:
    record, payload = env.service.create_backup(WALLET, owner_user_id="usr_a")
    tampered = payload.replace('"degree":"BSc"', '"degree":"PhD"')

    with pytest.raises(WalletBackupIntegrityError):
        env.service.preview(WALLET, record.backup_id, owner_user_id="usr_a", payload=tampered)
    with pytest.raises(WalletBackupNotFoundError):  # Holder B cannot use Holder A's archive
        env.service.preview(OTHER_WALLET, record.backup_id, owner_user_id="usr_b", payload=payload)
    with pytest.raises(HolderWalletNotFoundError):  # nor target Holder A's wallet
        env.service.preview(WALLET, record.backup_id, owner_user_id="usr_b", payload=payload)
    with pytest.raises(WalletBackupIntegrityError):  # the file names another backup
        env.service.preview(WALLET, "wbk_unknown_backup_0001", owner_user_id="usr_a", payload=payload)
    with pytest.raises(WalletBackupTooLargeError):
        env.service.preview(WALLET, record.backup_id, owner_user_id="usr_a", payload="x" * 400_001)
    with pytest.raises(WalletBackupIntegrityError):
        env.service.restore(
            WALLET, record.backup_id, owner_user_id="usr_a", payload=tampered,
            idempotency_key="restore-key-tampered01",
        )
    assert env.audits.events[-1].event_type.value == "WALLET_RESTORE_REJECTED"


def test_revoked_unverifiable_invalid_and_rebound_credentials_are_never_restored(env) -> None:
    env.credentials.add(_stored(_vc("urn:uuid:wp28-rebound", 9, subject="did:key:z6MkOld")))
    no_status = _vc("urn:uuid:wp28-nostatus", 10)
    del no_status["credentialStatus"]
    env.credentials.add(_stored(no_status))
    record, payload = env.service.create_backup(WALLET, owner_user_id="usr_a")
    _lose_all(env)
    env.status.revoked = {1}
    env.proofs.invalid = {"urn:uuid:wp28-2"}

    plan = env.service.preview(WALLET, record.backup_id, owner_user_id="usr_a", payload=payload)
    outcomes = {item.credential_id: item.outcome for item in plan.items}

    assert outcomes["urn:uuid:wp28-0"] == RESTORABLE
    assert outcomes["urn:uuid:wp28-1"] == REVOKED
    assert outcomes["urn:uuid:wp28-2"] == PROOF_INVALID
    assert outcomes["urn:uuid:wp28-rebound"] == HOLDER_BINDING_MISMATCH
    assert outcomes["urn:uuid:wp28-nostatus"] == STATUS_UNVERIFIABLE

    job, _ = env.service.restore(
        WALLET, record.backup_id, owner_user_id="usr_a", payload=payload,
        idempotency_key="restore-key-mixed00001",
    )
    assert job.status == "PARTIAL" and job.rejected == 4
    assert set(env.credentials.records) == {"urn:uuid:wp28-0"}


def test_status_list_unavailable_is_fail_closed(env) -> None:
    record, payload = env.service.create_backup(WALLET, owner_user_id="usr_a")
    _lose_all(env)
    env.service._status_lists = SimpleNamespace(get=lambda _id: None)

    plan = env.service.preview(WALLET, record.backup_id, owner_user_id="usr_a", payload=payload)

    assert {item.outcome for item in plan.items} == {STATUS_UNVERIFIABLE}


def test_existing_credentials_are_never_overwritten(env) -> None:
    record, payload = env.service.create_backup(WALLET, owner_user_id="usr_a")
    original = env.credentials.records["urn:uuid:wp28-0"]
    env.credentials.records["urn:uuid:wp28-1"] = replace(
        env.credentials.records["urn:uuid:wp28-1"], wallet_id=OTHER_WALLET
    )

    plan = env.service.preview(WALLET, record.backup_id, owner_user_id="usr_a", payload=payload)
    outcomes = {item.credential_id: item.outcome for item in plan.items}
    job, _ = env.service.restore(
        WALLET, record.backup_id, owner_user_id="usr_a", payload=payload,
        idempotency_key="restore-key-present001",
    )

    assert outcomes["urn:uuid:wp28-0"] == ALREADY_PRESENT
    assert outcomes["urn:uuid:wp28-1"] == HELD_BY_ANOTHER_WALLET
    assert job.restored == 0 and env.credentials.records["urn:uuid:wp28-0"] is original


def test_partial_persistence_failure_is_reported_not_hidden(env) -> None:
    record, payload = env.service.create_backup(WALLET, owner_user_id="usr_a")
    _lose_all(env)
    env.credentials.fail_after = 1

    job, _ = env.service.restore(
        WALLET, record.backup_id, owner_user_id="usr_a", payload=payload,
        idempotency_key="restore-key-diskfull01",
    )

    assert job.status == "PARTIAL" and job.restored == 1
    assert job.failure_code == "PERSISTENCE_FAILED"
    assert [item.outcome for item in job.items].count("NOT_ATTEMPTED") == 2


def test_idempotency_key_cannot_be_reused_for_another_backup(env) -> None:
    first, payload = env.service.create_backup(WALLET, owner_user_id="usr_a")
    second, payload_two = env.service.create_backup(WALLET, owner_user_id="usr_a")
    env.service.restore(
        WALLET, first.backup_id, owner_user_id="usr_a", payload=payload,
        idempotency_key="restore-key-shared0001",
    )
    with pytest.raises(WalletBackupConflictError):
        env.service.restore(
            WALLET, second.backup_id, owner_user_id="usr_a", payload=payload_two,
            idempotency_key="restore-key-shared0001",
        )
    listed = env.service.list_backups(WALLET, owner_user_id="usr_a")
    assert {item.backup_id for item in listed} == {first.backup_id, second.backup_id}
    assert env.service.list_backups(OTHER_WALLET, owner_user_id="usr_b") == ()


def test_audit_log_revocation_wins_over_a_republished_clean_status_list(env) -> None:
    """Record loss can make the re-derived status list drop a revocation bit."""
    from app.domain.persistence import AuditEvent, AuditEventType

    record, payload = env.service.create_backup(WALLET, owner_user_id="usr_a")
    _lose_all(env)
    env.status.revoked = set()  # list republished from records: the revocation bit is gone
    env.audits.append(
        AuditEvent(
            id=new_object_id(), event_type=AuditEventType.CREDENTIAL_REVOKED,
            subject_id="urn:uuid:wp28-1", actor_id="did:web:synthetic-issuer.local",
            correlation_id=None, metadata={"status": "REVOKED"}, created_at=NOW, updated_at=NOW,
        )
    )

    plan = env.service.preview(WALLET, record.backup_id, owner_user_id="usr_a", payload=payload)
    outcomes = {item.credential_id: item.outcome for item in plan.items}

    assert outcomes["urn:uuid:wp28-1"] == REVOKED
    assert outcomes["urn:uuid:wp28-0"] == RESTORABLE


def test_audit_log_unavailable_is_fail_closed(env) -> None:
    record, payload = env.service.create_backup(WALLET, owner_user_id="usr_a")
    _lose_all(env)

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("audit store down")

    env.audits.list_by_subject = unavailable
    plan = env.service.preview(WALLET, record.backup_id, owner_user_id="usr_a", payload=payload)

    assert {item.outcome for item in plan.items} == {STATUS_UNVERIFIABLE}


def test_wp29_archive_restores_without_the_server_row(env) -> None:
    record, payload = env.service.create_backup(WALLET, owner_user_id="usr_a")
    _lose_all(env)
    env.service._backups.documents.clear()

    plan = env.service.preview(WALLET, record.backup_id, owner_user_id="usr_a", payload=payload)

    assert plan.count("RESTORABLE") > 0


def test_wp29_standalone_archive_is_still_checked_item_by_item(env) -> None:
    record, payload = env.service.create_backup(WALLET, owner_user_id="usr_a")
    _lose_all(env)
    env.service._backups.documents.clear()
    env.proofs.invalid = {"urn:uuid:wp28-2"}
    env.status.revoked = {1}

    plan = env.service.preview(WALLET, record.backup_id, owner_user_id="usr_a", payload=payload)

    outcomes = {item.outcome for item in plan.items}
    assert "PROOF_INVALID" in outcomes and "REVOKED" in outcomes


def test_wp29_second_holder_gains_nothing_from_a_standalone_archive(env) -> None:
    record, payload = env.service.create_backup(WALLET, owner_user_id="usr_a")
    env.service._backups.documents.clear()

    plan = env.service.preview(OTHER_WALLET, record.backup_id, owner_user_id="usr_b", payload=payload)

    assert plan.count("RESTORABLE") == 0


@pytest.mark.parametrize(
    "payload",
    ["not json", "[]", '{"format":"other"}', '{"format":"x","items":"y"}'],
)
def test_wp29_malformed_standalone_archive_is_rejected(env, payload: str) -> None:
    with pytest.raises(WalletBackupIntegrityError):
        env.service.preview(
            WALLET, "wbk_unknown_backup_0001", owner_user_id="usr_a", payload=payload
        )


def test_wp29_ledger_revocation_blocks_restore_even_if_status_list_looks_clean(env) -> None:
    class Ledger:
        def is_revoked(self, credential_id: str) -> bool:
            return credential_id == "urn:uuid:wp28-1"

    record, payload = env.service.create_backup(WALLET, owner_user_id="usr_a")
    _lose_all(env)
    env.service._ledger = Ledger()

    plan = env.service.preview(WALLET, record.backup_id, owner_user_id="usr_a", payload=payload)

    outcomes = {item.credential_id: item.outcome for item in plan.items}
    assert outcomes["urn:uuid:wp28-1"] == "REVOKED"


def test_wp29_unavailable_ledger_means_unverifiable(env) -> None:
    class Ledger:
        def is_revoked(self, credential_id: str) -> bool:
            raise RuntimeError("down")

    record, payload = env.service.create_backup(WALLET, owner_user_id="usr_a")
    _lose_all(env)
    env.service._ledger = Ledger()

    plan = env.service.preview(WALLET, record.backup_id, owner_user_id="usr_a", payload=payload)

    assert plan.count("RESTORABLE") == 0


def test_wp32_list_nobody_fetched_yet_is_built_by_the_status_service(env) -> None:
    # Lists are published on first read; restore must not depend on a prior fetch.
    record, payload = env.service.create_backup(WALLET, owner_user_id="usr_a")
    _lose_all(env)
    env.service._status_lists = SimpleNamespace(get=lambda _id: None)
    built = []

    def get_publication(status_list_id):
        built.append(status_list_id)
        return SimpleNamespace(encoded_list=encode_status_list({1}, list_length=131072))

    env.service._status_list_service = SimpleNamespace(get_publication=get_publication)

    plan = env.service.preview(WALLET, record.backup_id, owner_user_id="usr_a", payload=payload)

    outcomes = {item.credential_id: item.outcome for item in plan.items}
    assert built and set(built) == {LIST_ID}
    assert outcomes["urn:uuid:wp28-0"] == RESTORABLE
    assert outcomes["urn:uuid:wp28-1"] == REVOKED
    assert outcomes["urn:uuid:wp28-2"] == RESTORABLE


def test_wp32_list_the_status_service_cannot_build_stays_unverifiable(env) -> None:
    record, payload = env.service.create_backup(WALLET, owner_user_id="usr_a")
    _lose_all(env)

    def missing(_status_list_id):
        raise LookupError("The requested status list does not exist.")

    env.service._status_list_service = SimpleNamespace(get_publication=missing)

    plan = env.service.preview(WALLET, record.backup_id, owner_user_id="usr_a", payload=payload)

    assert {item.outcome for item in plan.items} == {STATUS_UNVERIFIABLE}
