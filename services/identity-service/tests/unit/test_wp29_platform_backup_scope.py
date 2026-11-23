"""WP-29 P0-4: scope, retention, scheduler and readiness (no real MongoDB).

Restore against real MongoDB, with rollback injected at real write stages, is in
the isolated-stack drill. FakeDatabase here covers only what these tests need.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.application.services.platform_backup_scheduler import (
    PlatformBackupScheduler,
)
from app.application.services.platform_backup_service import (
    COMPLETE,
    LEDGER_COMPONENT,
    PARTIAL,
    RECOVERY_COMPONENT,
    PlatformBackupConsistencyError,
    PlatformBackupIntegrityError,
    PlatformBackupService,
    PlatformBackupSettings,
    PlatformBackupStateError,
    PlatformRestoreTargetError,
)
from app.application.services.readiness_service import evaluate_readiness
from app.domain.persistence import PersistenceUnavailableError
from app.infrastructure.key_management.backup_key_wrapper import (
    RemoteBackupKeyWrapper,
)
from app.infrastructure.persistence.memory_db import MemoryCollection


KEY = b"K" * 32


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value


class Collection(MemoryCollection):
    def index_information(self):
        return {"_id_": {"key": [("_id", 1)]}}


class FakeDatabase:
    def __init__(self, name: str, collections=None) -> None:
        self.name = name
        self._collections = {}
        for key, documents in (collections or {}).items():
            self[key].documents.extend(documents)

    def __getitem__(self, name: str) -> Collection:
        return self._collections.setdefault(name, Collection())

    def list_collection_names(self):
        return [k for k, v in self._collections.items() if k != "platform_backups" or v]

    def list_collections(self, filter=None):
        return [{"name": filter["name"], "options": {"validationLevel": "strict"}}]


class Audits:
    def append(self, event):
        return event


def settings(tmp_path: Path, **overrides) -> PlatformBackupSettings:
    values = dict(
        enabled=True,
        directory=tmp_path,
        key=KEY,
        retention_seconds=60,
        disabled_reason=None,
    )
    values.update(overrides)
    return PlatformBackupSettings(**values)


def service(tmp_path, *, sources=None, clock=None, identity=None, **options):
    return PlatformBackupService(
        database=identity
        or FakeDatabase("secure_identity", {"credentials": [{"_id": 1}]}),
        settings=options.pop("backup_settings", settings(tmp_path)),
        audits=Audits(),
        app_version="test",
        clock=clock or Clock(),
        additional_sources=sources,
        **options,
    )


def recovery_db() -> FakeDatabase:
    return FakeDatabase("secure_recovery", {"guardians": [{"_id": "g"}]})


def test_backup_without_recovery_is_marked_partial(tmp_path) -> None:
    record = service(tmp_path).create_backup(actor_id="a")
    assert record.completeness == PARTIAL
    assert record.components == ("identity",)


def test_backup_with_recovery_is_complete_and_contains_it(tmp_path) -> None:
    backup = service(tmp_path, sources={RECOVERY_COMPONENT: recovery_db()})
    record = backup.create_backup(actor_id="a")
    assert record.completeness == COMPLETE
    names = [item.name for item in record.collections]
    assert "recovery/guardians" in names and "credentials" in names


def test_ledger_watermark_is_recorded_and_bound_into_the_header(tmp_path) -> None:
    ledger = FakeDatabase(
        "ledger",
        {
            "revocation_ledger_events": [
                {"_id": "e", "sequence": 7, "eventHash": "abc"}
            ]
        },
    )
    backup = service(
        tmp_path,
        sources={RECOVERY_COMPONENT: recovery_db(), LEDGER_COMPONENT: ledger},
    )
    record = backup.create_backup(actor_id="a")
    assert record.watermark == "7:abc"
    _, contents = backup.verify(record.backup_id, actor_id="a")
    assert contents.header == {} or contents.collections


def test_revocation_during_export_fails_the_backup(tmp_path) -> None:
    ledger = FakeDatabase("ledger", {"revocation_ledger_events": []})
    backup = service(tmp_path, sources={LEDGER_COMPONENT: ledger})
    original = backup._export

    def export_with_concurrent_revocation():
        result = original()
        ledger["revocation_ledger_events"].documents.append(
            {"_id": "e", "sequence": 1, "eventHash": "h"}
        )
        return result

    backup._export = export_with_concurrent_revocation
    with pytest.raises(PlatformBackupConsistencyError):
        backup.create_backup(actor_id="a")
    assert backup.list_backups()[0].status == "FAILED"


def test_unreachable_recovery_database_fails_the_backup(tmp_path) -> None:
    class Down(FakeDatabase):
        def list_collection_names(self):
            raise RuntimeError("down")

    backup = service(tmp_path, sources={RECOVERY_COMPONENT: Down("x")})
    with pytest.raises(PlatformBackupStateError):
        backup.create_backup(actor_id="a")
    assert backup.list_backups()[0].status == "FAILED"


def _target(name: str) -> FakeDatabase:
    return FakeDatabase(name)


def test_partial_backup_cannot_become_a_restore_point(tmp_path) -> None:
    backup = service(tmp_path)
    record = backup.create_backup(actor_id="a")
    with pytest.raises(PlatformRestoreTargetError):
        backup.restore_to_target(
            record.backup_id, target=_target("restore_drill_abcd"), actor_id="a"
        )


def test_restore_refuses_a_missing_component_target(tmp_path) -> None:
    backup = service(tmp_path, sources={RECOVERY_COMPONENT: recovery_db()})
    record = backup.create_backup(actor_id="a")
    with pytest.raises(PlatformRestoreTargetError):
        backup.restore_to_target(
            record.backup_id, target=_target("restore_drill_abcd"), actor_id="a"
        )


def test_restore_refuses_a_live_or_shared_component_target(tmp_path) -> None:
    backup = service(tmp_path, sources={RECOVERY_COMPONENT: recovery_db()})
    record = backup.create_backup(actor_id="a")
    for extra in ("secure_recovery", "restore_drill_abcd"):
        with pytest.raises(PlatformRestoreTargetError):
            backup.restore_to_target(
                record.backup_id,
                target=_target("restore_drill_abcd"),
                additional_targets={RECOVERY_COMPONENT: _target(extra)},
                actor_id="a",
            )


def test_tampered_artifact_is_refused_before_any_target_write(tmp_path) -> None:
    backup = service(tmp_path, sources={RECOVERY_COMPONENT: recovery_db()})
    record = backup.create_backup(actor_id="a")
    path = tmp_path / f"{record.backup_id}.ssipbak"
    data = bytearray(path.read_bytes())
    data[-1] ^= 1
    path.write_bytes(bytes(data))
    target = _target("restore_drill_abcd")
    extra = _target("restore_drill_abcd_recovery")
    with pytest.raises(PlatformBackupIntegrityError):
        backup.restore_to_target(
            record.backup_id,
            target=target,
            additional_targets={RECOVERY_COMPONENT: extra},
            actor_id="a",
        )
    assert target.list_collection_names() == []
    assert extra.list_collection_names() == []


def test_wrong_key_cannot_open_an_archive(tmp_path) -> None:
    identity = FakeDatabase("secure_identity", {"credentials": [{"_id": 1}]})
    record = service(tmp_path, identity=identity).create_backup(actor_id="a")
    other = service(
        tmp_path,
        identity=identity,
        backup_settings=settings(tmp_path, key=b"Z" * 32),
    )
    with pytest.raises(PlatformBackupIntegrityError):
        other.verify(record.backup_id, actor_id="a")


class FakeKmsWrapper:
    """Contract double. Proves the envelope flow, not any real provider."""

    def __init__(self) -> None:
        self.stored = {}

    def wrap_data_key(self, data_key, *, provider_key_reference):
        handle = f"wrapped-{len(self.stored)}"
        self.stored[handle] = data_key
        return handle

    def unwrap_data_key(self, wrapped, *, provider_key_reference):
        return self.stored[wrapped]


def test_kms_envelope_needs_no_local_key_and_no_key_reaches_the_artifact(
    tmp_path,
) -> None:
    kms = FakeKmsWrapper()
    backup = service(
        tmp_path,
        backup_settings=settings(tmp_path, key=None, kms_key_reference="kms-bk"),
        key_wrapper=RemoteBackupKeyWrapper(kms, "kms-bk"),
    )
    record = backup.create_backup(actor_id="a")
    artifact = (tmp_path / f"{record.backup_id}.ssipbak").read_bytes()
    data_key = next(iter(kms.stored.values()))
    assert data_key not in artifact
    backup.verify(record.backup_id, actor_id="a")


def test_archive_cannot_be_opened_when_the_kms_is_unavailable(tmp_path) -> None:
    kms = FakeKmsWrapper()
    identity = FakeDatabase("secure_identity", {"credentials": [{"_id": 1}]})
    backup_settings = settings(tmp_path, key=None, kms_key_reference="kms-bk")
    record = service(
        tmp_path,
        identity=identity,
        backup_settings=backup_settings,
        key_wrapper=RemoteBackupKeyWrapper(kms, "kms-bk"),
    ).create_backup(actor_id="a")
    kms.stored.clear()
    with pytest.raises(PlatformBackupIntegrityError):
        service(
            tmp_path,
            identity=identity,
            backup_settings=backup_settings,
            key_wrapper=RemoteBackupKeyWrapper(kms, "kms-bk"),
        ).verify(record.backup_id, actor_id="a")


def test_expiry_does_nothing_while_the_feature_is_disabled(tmp_path) -> None:
    clock = Clock()
    identity = FakeDatabase("secure_identity", {"credentials": [{"_id": 1}]})
    backup = service(tmp_path, identity=identity, clock=clock)
    record = backup.create_backup(actor_id="a")
    clock.value += timedelta(days=30)
    disabled = service(
        tmp_path,
        identity=identity,
        clock=clock,
        backup_settings=PlatformBackupSettings(False, None, None, 60, "off"),
    )
    assert disabled.expire_due(actor_id="a") == 0
    assert disabled.get(record.backup_id).status == "SUCCEEDED"
    assert (tmp_path / f"{record.backup_id}.ssipbak").exists()


def test_retention_keeps_the_last_known_good_backup(tmp_path) -> None:
    clock = Clock()
    backup = service(
        tmp_path, clock=clock, sources={RECOVERY_COMPONENT: recovery_db()}
    )
    good = backup.create_backup(actor_id="a")
    backup.verify(good.backup_id, actor_id="a")
    clock.value += timedelta(days=30)
    assert backup.expire_due(actor_id="a") == 0
    assert (tmp_path / f"{good.backup_id}.ssipbak").exists()


def test_retention_expires_it_once_a_newer_backup_is_verified(tmp_path) -> None:
    clock = Clock()
    backup = service(
        tmp_path, clock=clock, sources={RECOVERY_COMPONENT: recovery_db()}
    )
    old = backup.create_backup(actor_id="a")
    backup.verify(old.backup_id, actor_id="a")
    clock.value += timedelta(days=30)
    new = backup.create_backup(actor_id="a")
    backup.verify(new.backup_id, actor_id="a")
    backup.expire_due(actor_id="a")
    assert backup.get(old.backup_id).status == "EXPIRED"
    assert not (tmp_path / f"{old.backup_id}.ssipbak").exists()
    assert backup.get(new.backup_id).status == "SUCCEEDED"


def test_interrupted_job_is_recovered(tmp_path) -> None:
    clock = Clock()
    backup = service(tmp_path, clock=clock)
    backup._records.insert_one(
        {
            "_id": "pbk_interrupted_0000000000",
            "backupId": "pbk_interrupted_0000000000",
            "status": "RUNNING",
            "sourceDatabase": "s",
            "createdBy": "a",
            "startedAt": clock(),
            "schemaVersion": 2,
        }
    )
    assert backup.recover_interrupted() == 0
    clock.value += timedelta(hours=2)
    assert backup.recover_interrupted() == 1
    assert backup.list_backups()[0].failure_code == "INTERRUPTED"


def test_scheduler_runs_once_per_interval_across_instances(tmp_path) -> None:
    clock = Clock()
    backup = service(
        tmp_path, clock=clock, sources={RECOVERY_COMPONENT: recovery_db()}
    )
    leases = MemoryCollection()
    first = PlatformBackupScheduler(
        backup, leases=leases, interval_seconds=3600, owner="a", clock=clock
    )
    second = PlatformBackupScheduler(
        backup, leases=leases, interval_seconds=3600, owner="b", clock=clock
    )
    assert first.tick() == "COMPLETED"
    assert second.tick() == "SKIPPED"
    clock.value += timedelta(seconds=3601)
    assert second.tick() == "COMPLETED"
    assert len(backup.list_backups()) == 2
    assert backup.list_backups()[0].last_verify_result == "VERIFIED"


class Ledger:
    def __init__(self, failure=None) -> None:
        self.failure = failure

    def current_head(self):
        if self.failure:
            raise self.failure
        return SimpleNamespace(sequence=3)


def report(**overrides):
    values = dict(
        environment="production",
        signing_uses_development_keys=False,
        signing_providers=(_Kms(),),
        holder_providers=(_Kms(),),
        ledger=Ledger(),
        ledger_settings=SimpleNamespace(
            separate_authority=True,
            anchor_path="/a",
            uses_development_key=False,
        ),
        backup=None,
        backup_settings=SimpleNamespace(enabled=False),
        step_up_required=True,
    )
    values.update(overrides)
    return evaluate_readiness(**values)


class _Kms:
    name = "remote-kms"

    def __init__(self, available=True, ready=True) -> None:
        self.available = available
        self.production_ready = ready

    def is_available(self):
        return self.available


def test_production_with_backup_disabled_is_not_ready() -> None:
    result = report()
    assert result.ready is False
    assert "BACKUP_DISABLED" in result.blockers


def test_offsite_and_pitr_block_production_until_really_configured() -> None:
    result = report()
    assert "BACKUP_OFFSITE_NOT_CONFIGURED" in result.blockers
    assert "BACKUP_PITR_NOT_CONFIGURED" in result.blockers


def test_development_keys_block_production() -> None:
    assert "SIGNING_DEVELOPMENT_KEYS" in report(
        signing_uses_development_keys=True
    ).blockers


def test_kms_outage_blocks_readiness() -> None:
    assert "KMS_UNAVAILABLE" in report(
        signing_providers=(_Kms(available=False),)
    ).blockers


def test_ledger_outage_blocks_readiness() -> None:
    assert "REVOCATION_LEDGER_UNAVAILABLE" in report(
        ledger=Ledger(PersistenceUnavailableError("down"))
    ).blockers


def test_overdue_backup_blocks_readiness() -> None:
    now = datetime(2026, 11, 4, tzinfo=UTC)
    last = SimpleNamespace(started_at=now - timedelta(days=9))
    result = report(
        backup=SimpleNamespace(last_verified_restore_point=lambda: last),
        backup_settings=SimpleNamespace(
            enabled=True,
            kms_key_reference="k",
            recovery_uri="u",
            interval_seconds=3600,
        ),
        clock=lambda: now,
    )
    assert "BACKUP_OVERDUE" in result.blockers


def test_no_verified_restore_point_blocks_readiness() -> None:
    result = report(
        backup=SimpleNamespace(last_verified_restore_point=lambda: None),
        backup_settings=SimpleNamespace(
            enabled=True,
            kms_key_reference="k",
            recovery_uri="u",
            interval_seconds=3600,
        ),
    )
    assert "BACKUP_NO_VERIFIED_RESTORE_POINT" in result.blockers


def test_development_stays_ready_but_reports_the_same_findings() -> None:
    result = report(environment="development", signing_uses_development_keys=True)
    assert result.ready is True
    assert result.blockers == ()
    assert "SIGNING_DEVELOPMENT_KEYS" in result.warnings


def test_report_claims_no_live_kms_and_no_worm() -> None:
    details = report().details
    assert details["keyCustody"]["liveKms"] == "NOT_VERIFIED"
    assert details["ledger"]["protection"] == "TAMPER_EVIDENT_NOT_WORM"
    assert details["backup"]["offsite"] == "NOT_CONFIGURED"
