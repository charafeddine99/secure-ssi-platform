# 04 – Fixes Implemented

All changes are uncommitted, minimal and limited to the defect. Nothing was refactored, no dependency changed, no test assertion was weakened.

## FIX-1 – QR / request_uri no longer uses the internal hostname (F-01)

| Item | Detail |
|---|---|
| Files | `services/api-gateway/app/api/routes/proxy.py`, `services/identity-service/app/api/v1/oid4vp.py` |
| Problem | Without `IDENTITY_PUBLIC_ORIGIN`, `request_uri` = `http://identity-service:8000/api/v1/oid4vp/request-objects/<id>`. |
| Root cause | The gateway drops the `Host` header when proxying, so identity only sees its own internal address and `_origin()` fell back to `request.base_url`. |
| Change | The gateway now **sets** `X-Forwarded-Host` (the host the caller used, `host[:port]` only) and `X-Forwarded-Proto` (`http`/`https` only), after dropping any client-supplied values. Identity's `_origin()` keeps `IDENTITY_PUBLIC_ORIGIN` first; without it, it uses those two headers if they are well-formed; otherwise the old fallback. |
| Why this way | Smallest change that fixes the link and keeps the existing public-origin rule and phone-reachability guard. Values cannot be injected through the gateway, and a forged value would only affect the caller's own request (the wallet still refuses foreign request_uri origins). |
| Unchanged | With `IDENTITY_PUBLIC_ORIGIN` set (the documented setup for phone tests) behaviour is identical. |
| Tests | New: `services/api-gateway/tests/test_gateway.py` (2 tests: header is set; client value never passes through), `services/identity-service/tests/unit/test_audit_forwarded_origin.py` (3 tests). Related existing: `test_wp30_public_origin_and_qr.py`, `test_wp32_request_uri.py`: 32/32. |

## FIX-2 – Recovery step-up secret follows the identity secret (F-02)

| Item | Detail |
|---|---|
| File | `docker-compose.yml` (recovery-service environment), `.env.example` comment |
| Root cause | Two independent variables for one shared secret. |
| Change | `RECOVERY_STEP_UP_SECRET: ${RECOVERY_STEP_UP_SECRET:-${IDENTITY_STEP_UP_SECRET:-}}`. Unset, recovery uses the identity secret (same pattern compose already uses for the JWT and grant secrets); an explicit value still wins. |
| Verification | `docker compose config`: unset → identity value; both set → explicit value. |

## FIX-3 – Mongo URIs follow the password variables (F-03)

| Item | Detail |
|---|---|
| File | `docker-compose.yml`, `.env.example` comments |
| Change | Default `IDENTITY_MONGO_URI` / `RECOVERY_MONGO_URI` now embed `${MONGO_APP_PASSWORD:-<old default>}` / `${MONGO_RECOVERY_PASSWORD:-<old default>}`, as compose already did for the intel database. |
| Verification | `docker compose config` with custom passwords → URIs carry them; with no env → output identical to before (the owner stack, which runs on defaults, is unaffected). |

## Harness-only changes (not product code)

Kept in `evidence/scripts/` (copies of the WP-31/32 harness): retargeted to the `audit-20261121` project and ports; isolation guards kept but pointed at the audit project; `reset_audit.sh` also clears the ledger anchor and the isolated Redis counters (F-05, F-07); DR stage moved to its own project and ports.

## Follow-up fixes, 2026-11-23 (owner's decision on F-14)

Same rules as above: uncommitted, minimal, no assertion weakened, no new feature.

## FIX-4 – Routine key re-syncs that change nothing are no longer audited (F-14)

| Item | Detail |
|---|---|
| File | `services/identity-service/app/application/services/managed_key_service.py` |
| Problem | Every background re-sync of an ACTIVE key (every 60 s) wrote `KEY_RECONCILIATION_CLAIMED` and `KEY_RECONCILIATION_COMPLETED`, even when nothing changed: about 53% of all audit events while idle. |
| Decision | The owner chose the report's recommendation: audit state changes and failures, count routine syncs in the metrics. |
| Change | `reconcile()` takes `routine=True` only from the background batch (`reconcile_batch`). For a routine sync of an ACTIVE, ROTATING or FAILED key, the claim is held back. If the result differs from the claimed key in anything other than sync bookkeeping (`updatedAt`, `version`, `reconciliationAttempts`, `reconciliationLeaseUntil`, `lastProviderSyncAt`), the claim and the completion are recorded as before, with the same timestamps. A failure records the claim, the failure and, for metadata mismatches, `KEY_PROVIDER_MISMATCH`, as before. A sync that changed nothing is counted in `key_reconciliation_attempts/succeeded` and not audited. |
| Unchanged | Administrative reconciliation (`reconcile_authorized`, admin API) is always audited. PENDING and DESTROY_PENDING keys still record the claim before the provider call. Every state change (activation, suspension, failure, destruction, end of rotation) is audited exactly as before. |
| Known limit | For routine syncs of ACTIVE, ROTATING or FAILED keys the claim is written after the provider check. If the process stops in between, that claim is missing from the log. The key itself stays consistent: the lease expires and the next sync is audited if it changes anything. |
| Tests | New in `tests/unit/test_managed_key_service.py`: a routine sync without changes is counted but not audited; a routine sync that suspends the key, and one that fails, are audited (claim + completion or claim + failure); administrative reconciliation is always audited. |

## FIX-5 – DR drill: the source check tolerates growth of the append-only audit log (F-12)

| Item | Detail |
|---|---|
| File | `services/identity-service/app/tools/platform_restore_drill.py` |
| Change | New `compare_source(before, after)`: every collection of the live source must keep its exact document count. Only `audit_events` and `audit_outbox` may grow, because the platform only appends to them (no deletes, no TTL index) and its own background jobs can write during a drill. A decrease or a missing collection still fails. The exit code uses this check. The report keeps `sourceFingerprintUnchanged` (strict equality, for information) and adds `sourceUnchanged`, `sourceChangedCollections` and `sourceAppendOnlyGrowth`. |
| Why this way | The restore writes only to the separate `restore_drill_*` databases, and the drill itself writes no audit events (`_NoAudit`). A restore that wrongly wrote into the source would change the business collections, which are still compared exactly. |
| Tests | New `tests/unit/test_platform_restore_drill_source_check.py` (5 tests: identical counts pass; audit-log growth is reported and passes; any other change fails; the audit collections must not shrink or disappear; only those two collections are treated as append-only). |

## FIX-6 – A successful sync resets the retry counter (F-15)

| Item | Detail |
|---|---|
| File | `services/identity-service/app/application/services/managed_key_service.py` |
| Change | The two sync paths that run again and again (routine sync of a key; ROTATING key waiting for its grace period) now set `reconciliationAttempts` to 0. The retry limit therefore counts consecutive failures, as its name says. |
| Tests | New: after five routine syncs the counter is 0, and one timeout leaves the key ACTIVE with attempts 1. On a copy of the old code the same scenario ends in `FAILED` (`RETRY_LIMIT_REACHED`) with attempts 6. The existing test `test_reconciliation_retry_limit_dead_letters_failed_operation` (consecutive failures still dead-letter the key) passes unchanged. |
