"""Closeout live check for FIX-4 (F-14) and FIX-6 (F-15) on a real MongoDB.

Runs the identity service's own ManagedKeyService code, as built into the
audit-20261121 identity image, against a fresh database on the ISOLATED audit
mongod. The database name is printed; the connection string is never printed.
A controllable clock replaces waiting for real minutes, and the development
provider's failure switch simulates provider timeouts. Nothing here touches the
owner stack.

Usage (inside the audit identity image, /app as working directory):
    MONGO_URI=... python /closeout/fix46_live_scenario.py
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo import MongoClient

from app.application.services.audit_outbox_service import AuditOutboxDeliveryService
from app.application.services.internal_metrics import InternalMetrics
from app.application.services.managed_key_service import ManagedKeyService
from app.config.audit_outbox_settings import AuditOutboxSettings
from app.config.key_management_settings import ConfiguredKeyPolicy, KeyManagementSettings
from app.domain.holder_wallet import HolderWallet, WalletStatus
from app.domain.managed_key import KeyAlgorithm, KeyPurpose, ManagedKeyState
from app.domain.persistence import AuditEventType
from app.infrastructure.key_management.development_provider import (
    DevelopmentExternalKeyProvider,
    DevelopmentProviderFailure,
)
from app.infrastructure.persistence.audit_outbox_repository import MongoAuditOutboxRepository
from app.infrastructure.persistence.holder_wallet_repositories import MongoHolderWalletRepository
from app.infrastructure.persistence.indexes import ensure_mongo_indexes
from app.infrastructure.persistence.managed_key_repository import MongoManagedKeyRepository
from app.infrastructure.persistence.repositories import MongoAuditEventRepository

RESULTS = {"pass": 0, "fail": 0}
RECON = (
    AuditEventType.KEY_RECONCILIATION_CLAIMED,
    AuditEventType.KEY_RECONCILIATION_COMPLETED,
    AuditEventType.KEY_RECONCILIATION_FAILED,
)


def check(area: str, name: str, ok: bool, detail: Any = "") -> None:
    RESULTS["pass" if ok else "fail"] += 1
    print(f"{'PASS' if ok else 'FAIL'} [{area}] {name} | {detail}", flush=True)


class Clock:
    def __init__(self) -> None:
        self.value = datetime.now(UTC).replace(microsecond=0)

    def __call__(self) -> datetime:
        return self.value


class Ids:
    def __init__(self) -> None:
        self.n = 0

    def storage_id(self) -> str:
        self.n += 1
        return f"{0xC105E0000000 + self.n:024x}"

    def key_id(self) -> str:
        self.n += 1
        return f"key_{9_000_000_000_000_000 + self.n:016d}"


def main() -> int:
    uri = os.environ["MONGO_URI"]
    db_name = f"closeout_fix46_{datetime.now(UTC):%Y%m%d%H%M%S}"
    client: MongoClient[dict[str, Any]] = MongoClient(uri, tz_aware=True, serverSelectionTimeoutMS=5000)
    db = client[db_name]
    ensure_mongo_indexes(db)
    print(f"database={db_name} server={client.address[0]}", flush=True)

    clock = Clock()
    ids = Ids()
    wallets = MongoHolderWalletRepository(db["holder_wallets"])
    keys = MongoManagedKeyRepository(db["managed_keys"])
    audit = MongoAuditEventRepository(db["audit_events"])
    delivery = AuditOutboxDeliveryService(
        outbox_repository=MongoAuditOutboxRepository(db["audit_outbox"], db["credentials"]),
        audit_repository=audit,
        settings=AuditOutboxSettings(),
        clock=clock,
    )
    provider = DevelopmentExternalKeyProvider()
    metrics = InternalMetrics()
    service = ManagedKeyService(
        repository=keys,
        wallet_repository=wallets,
        providers={"development": provider},
        policy=ConfiguredKeyPolicy(KeyManagementSettings()),
        audit_delivery_service=delivery,
        clock=clock,
        storage_id_generator=ids.storage_id,
        key_id_generator=ids.key_id,
        default_provider="development",
        metrics=metrics,
        reconciliation_retry_limit=3,
    )

    def wallet(n: int) -> str:
        wallet_id = f"wallet_closeout{n:010d}"
        wallets.add(
            HolderWallet(
                id=f"{0xC105E1000000 + n:024x}",
                wallet_id=wallet_id,
                owner_user_id=f"usr_closeout_{n}",
                holder_did=f"did:key:zCloseoutHolder{n}",
                status=WalletStatus.ACTIVE,
                key_reference=f"local-dev:wallet:closeout{n}",
                created_at=clock.value,
                updated_at=clock.value,
            )
        )
        return wallet_id

    def create(n: int):
        wallet_id = wallet(n)
        return service.create_for_wallet(
            wallet_id=wallet_id,
            owner_user_id=f"usr_closeout_{n}",
            purpose=KeyPurpose.PRESENTATION_SIGNING,
            algorithm=KeyAlgorithm.ED25519,
            provider_name=None,
            idempotency_key=f"closeout-create-{n:04d}",
            correlation_id=f"closeout-create-{n:04d}",
        )

    def recon_events() -> dict[str, int]:
        return {t.value: db["audit_events"].count_documents({"eventType": t.value}) for t in RECON}

    def totals() -> tuple[int, int]:
        return db["audit_events"].count_documents({}), db["audit_outbox"].count_documents({})

    def routine() -> tuple[int, int]:
        clock.value += timedelta(seconds=61)
        return service.reconcile_batch(stale_seconds=60, batch_size=10)

    # ---------------- FIX-4 / FIX-6: routine syncs on one ACTIVE key
    key = create(1)
    check("setup", "key is ACTIVE after creation", key.state is ManagedKeyState.ACTIVE, key.state.value)
    events0, outbox0 = totals()
    recon0 = recon_events()
    print(f"baseline audit_events={events0} audit_outbox={outbox0} reconciliation_events={recon0}", flush=True)
    for cycle in range(1, 6):
        result = routine()
        current = keys.get(key.key_id)
        check("fix4", f"routine sync {cycle} succeeds", result == (1, 0), result)
        check("fix6", f"retry counter is 0 after routine sync {cycle}", current.reconciliation_attempts == 0, current.reconciliation_attempts)
        check("fix4", f"lastProviderSyncAt advanced in sync {cycle}", current.last_provider_sync_at == clock.value, current.last_provider_sync_at)
    events1, outbox1 = totals()
    check("fix4", "5 routine syncs added no audit event", events1 == events0, f"{events0} -> {events1}")
    check("fix4", "5 routine syncs added no outbox record", outbox1 == outbox0, f"{outbox0} -> {outbox1}")
    check("fix4", "no reconciliation event for routine syncs", recon_events() == recon0, recon_events())
    snap = metrics.snapshot()
    check("metrics", "routine syncs counted: 5 attempts, 5 succeeded", (snap.key_reconciliation_attempts, snap.key_reconciliation_succeeded) == (5, 5), (snap.key_reconciliation_attempts, snap.key_reconciliation_succeeded, snap.key_reconciliation_failed))

    # ---------------- administrative reconciliation is always audited
    clock.value += timedelta(seconds=61)
    service.reconcile(keys.get(key.key_id), actor_id="usr_closeout_admin", correlation_id="closeout-admin-0001")
    recon2 = recon_events()
    check("fix4", "admin reconciliation is audited (claim + completion)",
          recon2["KEY_RECONCILIATION_CLAIMED"] == recon0["KEY_RECONCILIATION_CLAIMED"] + 1
          and recon2["KEY_RECONCILIATION_COMPLETED"] == recon0["KEY_RECONCILIATION_COMPLETED"] + 1, recon2)

    # ---------------- one transient provider failure
    provider.inject_failure(DevelopmentProviderFailure.TIMEOUT)
    result = routine()
    after_fail = keys.get(key.key_id)
    recon3 = recon_events()
    check("fix4", "a failed routine sync is reported as failed", result == (0, 1), result)
    check("fix4", "the failure is audited (claim + failure)",
          recon3["KEY_RECONCILIATION_CLAIMED"] == recon2["KEY_RECONCILIATION_CLAIMED"] + 1
          and recon3["KEY_RECONCILIATION_FAILED"] == recon2["KEY_RECONCILIATION_FAILED"] + 1, recon3)
    check("fix6", "one transient failure leaves the key ACTIVE", after_fail.state is ManagedKeyState.ACTIVE, after_fail.state.value)
    check("fix6", "retry counter is 1 after one failure", after_fail.reconciliation_attempts == 1, after_fail.reconciliation_attempts)
    provider.inject_failure(DevelopmentProviderFailure.NONE)
    result = routine()
    healed = keys.get(key.key_id)
    check("fix6", "the next successful sync resets the counter to 0", result == (1, 0) and healed.reconciliation_attempts == 0, (result, healed.reconciliation_attempts))
    check("fix4", "the successful sync after the failure is not audited", recon_events() == recon3, recon_events())

    # ---------------- consecutive failures still reach the retry limit (3)
    provider.inject_failure(DevelopmentProviderFailure.TIMEOUT)
    states = []
    for _ in range(3):
        routine()
        current = keys.get(key.key_id)
        states.append((current.state.value, current.reconciliation_attempts))
    final = keys.get(key.key_id)
    check("fix6", "three consecutive failures move the key to FAILED", final.state is ManagedKeyState.FAILED and final.failure_code == "RETRY_LIMIT_REACHED", states)
    recon4 = recon_events()
    check("fix4", "each consecutive failure is audited", recon4["KEY_RECONCILIATION_FAILED"] == recon3["KEY_RECONCILIATION_FAILED"] + 3, recon4)
    provider.inject_failure(DevelopmentProviderFailure.NONE)

    # ---------------- a state change found by a routine sync is audited
    other = create(2)
    recon5 = recon_events()
    provider.suspend_key(other.provider_key_reference or "")
    result = routine()
    suspended = keys.get(other.key_id)
    recon6 = recon_events()
    check("fix4", "a routine sync that finds the provider key disabled suspends it", suspended.state is ManagedKeyState.SUSPENDED, suspended.state.value)
    check("fix4", "that state change is audited (claim + completion)",
          recon6["KEY_RECONCILIATION_CLAIMED"] >= recon5["KEY_RECONCILIATION_CLAIMED"] + 1
          and recon6["KEY_RECONCILIATION_COMPLETED"] >= recon5["KEY_RECONCILIATION_COMPLETED"] + 1, recon6)

    snap = metrics.snapshot()
    print(f"metrics attempts={snap.key_reconciliation_attempts} succeeded={snap.key_reconciliation_succeeded} failed={snap.key_reconciliation_failed}", flush=True)
    check("metrics", "every reconciliation is counted (attempts = succeeded + failed)",
          snap.key_reconciliation_attempts == snap.key_reconciliation_succeeded + snap.key_reconciliation_failed, snap)
    check("metrics", "failures counted: 1 transient + 3 consecutive", snap.key_reconciliation_failed == 4, snap.key_reconciliation_failed)
    events_end, outbox_end = totals()
    print(f"final audit_events={events_end} audit_outbox={outbox_end} reconciliation_events={recon_events()}", flush=True)
    print(f"TOTAL pass={RESULTS['pass']} fail={RESULTS['fail']}", flush=True)
    client.close()
    return 0 if RESULTS["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
