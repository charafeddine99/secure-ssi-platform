"""Platform restore drill (operator CLI, never exposed over HTTP).

Restores one verified platform backup into empty, separately named
``restore_drill_*`` databases and compares counts, indexes and collection
options. Live data is only read, apart from marking the two-person approval as
used. Nothing runs without an approval from a second administrator.

Connection strings come from the environment, never from arguments, so they
do not appear in the process list or shell history:

    IDENTITY_MONGO_URI / IDENTITY_MONGO_DATABASE   source (as the service uses)
    PLATFORM_RESTORE_TARGET_URI                    drill server credentials
    PLATFORM_RESTORE_TARGET_DATABASE               restore_drill_<suffix>
    PLATFORM_RESTORE_OPERATION_ID                  approved dual-control id
    PLATFORM_RESTORE_EXECUTION_TOKEN               one-time execution token
    IDENTITY_PLATFORM_BACKUP_RECOVERY_URI          recovery source, read only
    IDENTITY_REVOCATION_LEDGER_URI                 ledger source, if separate

Usage: python -m app.tools.platform_restore_drill <backup-id>
Prints a JSON report without secrets. Exit code 0 only when the backup was
restored and verified and the live source is unchanged; the append-only audit
collections may grow from the platform's own background work meanwhile.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from typing import Any

from pymongo import MongoClient

from app.application.services.dual_control_service import (
    DUAL_CONTROL_COLLECTION,
    PLATFORM_RESTORE,
    DualControlError,
    DualControlService,
)
from app.application.services.platform_backup_service import (
    LEDGER_COMPONENT,
    PLATFORM_BACKUPS_COLLECTION,
    RECOVERY_COMPONENT,
    PlatformBackupError,
    PlatformBackupService,
    load_platform_backup_settings,
)
from app.core.config import APP_VERSION
from app.infrastructure.persistence.indexes import (
    AUDIT_EVENTS_COLLECTION,
    AUDIT_OUTBOX_COLLECTION,
)

# The running platform only appends to these collections (no deletes, no TTL).
# Its background jobs may add documents while a drill runs; that growth is
# reported but does not fail the check. Any decrease still fails (F-12).
APPEND_ONLY_COLLECTIONS = frozenset(
    {AUDIT_EVENTS_COLLECTION, AUDIT_OUTBOX_COLLECTION}
)


class _NoAudit:
    def append(self, event: Any) -> Any:  # the drill writes nothing to the live database
        return event


def fingerprint(database: Any) -> dict[str, int]:
    """Document counts per collection; the backup metadata collection is excluded."""
    return {
        name: database[name].count_documents({})
        for name in sorted(database.list_collection_names())
        if name not in {PLATFORM_BACKUPS_COLLECTION, DUAL_CONTROL_COLLECTION}
        and not name.startswith("system.")
    }


def compare_source(before: dict[str, int], after: dict[str, int]) -> dict[str, Any]:
    """Compare live-source document counts taken before and after a restore.

    The restore writes only to the separate drill databases, so every count
    must stay the same. Append-only collections may grow from live background
    work but must never shrink.
    """
    changed = [
        name
        for name in sorted(set(before) | set(after))
        if before.get(name) != after.get(name)
        and not (
            name in APPEND_ONLY_COLLECTIONS
            and after.get(name, -1) >= before.get(name, 0)
        )
    ]
    growth = {
        name: after[name] - before.get(name, 0)
        for name in sorted(APPEND_ONLY_COLLECTIONS)
        if after.get(name, 0) > before.get(name, 0)
    }
    return {"unchanged": not changed, "changed": changed, "appendOnlyGrowth": growth}


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(json.dumps({"error": "usage: platform_restore_drill <backup-id>"}))
        return 2
    target_uri = os.environ.get("PLATFORM_RESTORE_TARGET_URI", "")
    target_name = os.environ.get("PLATFORM_RESTORE_TARGET_DATABASE", "")
    if not target_uri or not target_name:
        print(json.dumps({"error": "PLATFORM_RESTORE_TARGET_URI and _DATABASE are required."}))
        return 2
    source_client: MongoClient[dict[str, Any]] = MongoClient(
        os.environ["IDENTITY_MONGO_URI"], tz_aware=True, serverSelectionTimeoutMS=5000
    )
    target_client: MongoClient[dict[str, Any]] = MongoClient(
        target_uri, tz_aware=True, serverSelectionTimeoutMS=5000
    )
    source = source_client[os.environ.get("IDENTITY_MONGO_DATABASE", "secure_identity")]
    settings = load_platform_backup_settings()
    sources: dict[str, Any] = {}
    targets: dict[str, Any] = {}
    if settings.recovery_uri is not None:
        sources[RECOVERY_COMPONENT] = MongoClient(
            settings.recovery_uri, tz_aware=True, serverSelectionTimeoutMS=5000
        )[settings.recovery_database]
        targets[RECOVERY_COMPONENT] = target_client[f"{target_name}_recovery"]
    ledger_uri = os.environ.get("IDENTITY_REVOCATION_LEDGER_URI", "").strip()
    if ledger_uri:
        sources[LEDGER_COMPONENT] = MongoClient(
            ledger_uri, tz_aware=True, serverSelectionTimeoutMS=5000
        )[os.environ.get("IDENTITY_REVOCATION_LEDGER_DATABASE", "secure_revocation_ledger")]
        targets[LEDGER_COMPONENT] = target_client[f"{target_name}_ledger"]
    service = PlatformBackupService(
        database=source,
        settings=settings,
        audits=_NoAudit(),
        app_version=APP_VERSION,
        additional_sources=sources,
    )
    before = fingerprint(source)
    try:
        DualControlService(
            operations=source[DUAL_CONTROL_COLLECTION],
            clock=lambda: datetime.now(UTC),
        ).consume(
            os.environ.get("PLATFORM_RESTORE_OPERATION_ID"),
            os.environ.get("PLATFORM_RESTORE_EXECUTION_TOKEN"),
            operation_type=PLATFORM_RESTORE,
            target=f"{argv[0]}:{target_name}",
        )
        report = service.restore_to_target(
            argv[0],
            target=target_client[target_name],
            additional_targets=targets,
            actor_id="cli-restore-drill",
        )
        outcome: dict[str, Any] = {
            "backupId": report.backup_id,
            "targetDatabase": report.target_database,
            "status": report.status,
            "restoreDurationMs": round(report.duration_ms, 2),
            "collections": list(report.collections),
            "failureCode": report.failure_code,
        }
    except PlatformBackupError as error:
        outcome = {"backupId": argv[0], "status": "REJECTED", "failureCode": error.code, "message": str(error)}
    except DualControlError as error:
        outcome = {
            "backupId": argv[0],
            "status": "REJECTED",
            "failureCode": "DUAL_CONTROL_REQUIRED",
            "message": str(error),
        }
    after = fingerprint(source)
    source_check = compare_source(before, after)
    outcome["sourceDatabase"] = source.name
    outcome["sourceFingerprintUnchanged"] = before == after
    outcome["sourceUnchanged"] = source_check["unchanged"]
    outcome["sourceChangedCollections"] = source_check["changed"]
    outcome["sourceAppendOnlyGrowth"] = source_check["appendOnlyGrowth"]
    outcome["sourceCollectionCount"] = len(before)
    print(json.dumps(outcome, indent=2, default=str))
    source_client.close()
    target_client.close()
    restored = outcome.get("status") == "RESTORED_AND_VERIFIED"
    return 0 if restored and source_check["unchanged"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
