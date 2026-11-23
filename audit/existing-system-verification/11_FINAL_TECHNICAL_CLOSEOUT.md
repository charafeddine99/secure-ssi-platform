# 11 – Final Technical Closeout

Secure SSI Platform: live verification of FIX-4 to FIX-6, the F-06 QR test update, the real-MongoDB integration run, the Git and owner-stack record, and a full regression.

| Item | Value |
|---|---|
| Prepared | 2026-11-23 |
| Starting point | `10_FINAL_EXECUTION_REPORT.md` (FIX-1 to FIX-6 made; FIX-4/5/6 not verified live; F-06 open; no final MongoDB integration log; nothing committed; owner stack on pre-fix images) |
| Where the tests ran | Only the isolated compose project `audit-20261121` (ports 29300–29383 on 127.0.0.1, own network, own volumes), its throw-away MongoDB databases and the separate DR project `audit-20261121-dr5`. Synthetic users only. |
| Evidence | `evidence/closeout/`. The raw `*.log` files stay on the audit machine because the repository's `.gitignore` excludes `*.log`. The scripts, snapshots, summaries and JSON results are committed. |
| Earlier reports | `00`–`10` were not changed. |

**How to read it.** "Verified" means checked against a saved log, the code or a read-only query during this closeout. Every number below comes from a file in `evidence/closeout/` or `evidence/scripts/*_results.json`. Failures and harness mistakes are listed, not hidden.

---

## A. Executive summary

| Closeout job | Result | Key evidence |
|---|---|---|
| 1. FIX-4, FIX-5, FIX-6 live | **Done.** Routine syncs add no audit event (idle 7 min with 6 keys: 175 → 175 events; before the fix about 2 events per key per minute). State changes, failures and administrator reconciliations are still audited. The DR drill is back to **32/32, exit 0**. A successful sync resets the retry counter, one transient failure no longer fails a key, and three consecutive failures still do. | `fix46_live_scenario.log` 33/0, `fix4_live_rotation_grace.log` 5/0, `fix4_live_api.log` 8/1 (the FAIL is a test-design error, section B.6), idle and restart snapshots, `dr.log` 32/0, `fix5_fields_and_negative_cases.log` |
| 2. F-06 QR checks | **Done.** The two outdated checks were rewritten for the current `request_uri` design and are stricter than before: they now verify the request object's Ed25519 signature against the `did:jwk` client_id. E2E **130/2 → 132/0**. | `e2e_pre_f06.log`, `e2e.log`, `f06_check_selftest.log` 7/0 |
| 3. Real-MongoDB integration | **Done.** 7 passed, 0 failed, 0 skipped, 0 errors, on a throw-away database of the isolated audit MongoDB. | `mongo_integration.log`, `mongo_it_*.txt` |
| 4. Git and owner stack | **Recorded.** The owner stack was not rebuilt, stopped or written to; its containers still run images built on or before 7–10 November, without the audit fixes. A safe rebuild plan is in section H.4. At the owner's request on 2026-11-23, all the work was committed in small groups and pushed to `besna-dev` (section H.1). | `git_before.txt`, `git_ownership.txt`, `docker_before.txt`, `integrity_after.txt` |
| Full regression | **Green, with no new failure.** Unit, build and lint results equal 21 November (identity 1095/0/12, gateway 50, recovery 131/0/1, fraud 90, web 42). Every live stage passes: E2E 132/0, DR 32/0, browser 40/0, 62 pages with 0 axe issues, UI 41/0, scenarios 41/0, OID4VP security 16/0, `request_uri` scan 11/0, wallet card 31/0, cross-device 13/0, wp32 UI 12/0, onboarding 40/0, gaps 38/0, post 15/0, FIX-1 default origin 7/0. Two harness incidents (a missing argument, one hung run) are documented, and the affected stages were run again. | section G |
| Data integrity | **Preserved.** Owner containers kept their images and start times (no restart). The 5 owner volumes and the owner image tags are unchanged. No container crosses between the owner and audit networks. Only `besna-dev` moved, and its local and remote tips are equal. No secret or personal data is in the committed evidence: the scan's 4 hits are false positives. | section H.3 |

**Decision (section J): ready to start D1–D5,** working from the committed `besna-dev` tree on an isolated stack. The owner stack still runs pre-fix images and needs an approved rebuild (H.4) before it is used for experiments.

---

## B. FIX-4 live verification (F-14: routine reconciliation audit noise)

### B.1 The running code contains the fix

`audit_image_contains_fixes.txt` (read-only `docker exec`): the audit identity container runs an image built on 2026-11-23 14:49 UTC. Its `managed_key_service.py`, `platform_restore_drill.py` and `oid4vp.py`, and the audit gateway's `proxy.py`, have the same SHA-256 as the committed files.

### B.2 Before the fix (from `03`, F-14)

190 of 360 audit events (53 %) in about 1.5 h were routine `KEY_RECONCILIATION_CLAIMED` / `KEY_RECONCILIATION_COMPLETED` pairs: about 2,880 events per key per day while idle. `audit_events` and `audit_outbox` grew by 2 every ~15 s on an idle stack.

### B.3 Routine syncs on the running stack

Read-only snapshots of the isolated database (`audit_snapshot.sh`, guarded by the compose project label):

| Snapshot | Time (UTC) | `audit_events` | `audit_outbox` | Reconciliation events (claimed / completed / failed) | Managed keys | Highest key `version` | `reconciliationAttempts` |
|---|---|---|---|---|---|---|---|
| `idle_t0.json` | 15:10:03 | 175 | 34 | 0 / 0 / 0 | 6 (ACTIVE, COMPROMISED) | 40 | all 0 |
| `idle_t1.json` | 15:17:04 | **175** | **34** | 0 / 0 / 0 | 6 | 54 | all 0 |
| `restart_t_before.json` | 15:17:45 | 175 | 34 | 0 / 0 / 0 | 6 | 56 | all 0 |
| identity service restarted | 15:17:46 | | | | | | |
| `restart_t2.json` | 15:20:18 | **175** | **34** | 0 / 0 / 0 | 6 | 60 | all 0 |
| `restart_t3.json` | 15:22:49 | **175** | **34** | 0 / 0 / 0 | 6 | 66 | all 0 |

- The rising `version` and `lastSync` values show the routine syncs ran about once a minute per key.
- Over 12 minutes, including a restart, they added **no** audit or outbox record. With the old code the same window would have produced roughly 2 events per key per sync.
- The restart caused no state change: the development key provider derives keys deterministically, so the keys are found again after a restart.

`fix4_live_api.mjs` (real API, fresh synthetic holder and administrator): a newly provisioned key was re-synced for 130 s (`version` 2 → 6). The audit log stayed at 181 events with 0 reconciliation events, and the retry counter stayed 0.

### B.4 A real state change is audited

With the stack's normal rotation grace of 0 s, `rotate()` suspends the predecessor inside the API call itself, so no background reconciliation is involved. To make the *background* path change a state, the audit identity service alone was recreated with `IDENTITY_KMS_ROTATION_GRACE_SECONDS=30`, and the normal setting was restored afterwards (`fix4_live_rotation_grace.log`, which ends with "grace now: 0").

- Right after the rotation call, the predecessor key was `ROTATING`.
- The routine reconciliation moved it to `SUSPENDED` after 61 s.
- That reconciliation was audited for this key: claimed 0 → 1, completed 0 → 1.
- Result **5/0**.

`fix46_live_scenario.log` adds a second kind of state change: a routine sync that finds the provider key disabled suspends the key, and is audited as claim + completion.

### B.5 Failures and administrator reconciliations are audited

`fix46_live_scenario.py` runs the identity service's own `ManagedKeyService`, from the audit image, against a fresh database (`closeout_fix46_20261123145939`) on the isolated audit MongoDB. It uses a controllable clock and the development provider's failure switch. **33/0.**

| Step | Audit result |
|---|---|
| 5 successful routine syncs | `audit_events` 3 → 3, `audit_outbox` 3 → 3, 0 reconciliation events |
| Administrator reconciliation | audited (claim + completion) |
| 1 failed routine sync (provider timeout) | audited (claim + failure) |
| Next successful sync | not audited (bookkeeping only) |
| 3 consecutive failures | each audited (claim + failure) |
| Sync that finds the provider key disabled | `SUSPENDED`, audited (claim + completion) |
| End | `audit_events` 18; reconciliation events: 6 claimed, 2 completed, 4 failed |

Live API (`fix4_live_api.log`): an administrator's `POST …/keys/{id}/reconcile` on an unchanged key was audited (claimed 0 → 1, completed 0 → 1).

### B.6 The one FAIL in `fix4_live_api.log` (8/1)

The check "that state change is audited (claim + completion)" expected a background reconciliation event after a rotation. With a grace of 0 s the rotation API finishes the rotation in the call itself (code: `rotate()` in `managed_key_service.py`, the `rotation_grace_seconds == 0` branch), so no reconciliation was due.

This is a mistake in the test design, not in the product. The check was not changed to pass. It was repeated in the setting where the background path really runs (B.4, 5/0).

### B.7 Metrics

`InternalMetrics` lives inside the service process and has **no HTTP endpoint**, so it cannot be read from the running stack. It was checked inside the scenario process (B.5):

- 5 routine syncs counted as 5 attempts, 5 succeeded;
- at the end, attempts 13 = 9 succeeded + 4 failed (1 transient + 3 consecutive).

Routine syncs are therefore still counted while no longer audited.

**Result: met.** Routine syncs produce no audit events. State changes, failures and administrator reconciliations are audited. Metrics count every reconciliation. No security event type was removed; only successful routine syncs that change nothing but bookkeeping fields are silent.

---

## C. FIX-5 DR verification (F-12: false "source changed" alarm)

### C.1 Live drill (`wp31_dr.mjs` → `dr.log`, project `audit-20261121-dr5`): **32/0, exit 0**

| Topic | Result |
|---|---|
| Backup | Coordinated backup `COMPLETE` with ledger watermark `seq=9`; 37 collections; archive verifies (200); 58,109 bytes in 121 ms |
| Refusals | No approval → `DUAL_CONTROL_REQUIRED`; self-approval → 403; approval for another target → refused; live database name → `PLATFORM_RESTORE_TARGET_REJECTED`; corrupted artifact → `PLATFORM_BACKUP_INTEGRITY_FAILED`; nothing reached the target |
| Failure handling | A write failure rolls back every component (`FAILED_ROLLED_BACK`, 13); no partial database survives |
| Restore | Two-person restore into a separate mongod: `RESTORED_AND_VERIFIED`; index and collection options match for all 37 collections; restore 9.8 s; application boot on restored data 46.9 s |
| Source comparison | "Source database was not changed by the restore": PASS |
| CLI exit code | 0 (the harness requires `RESTORED_AND_VERIFIED` **and** exit code 0) |
| Restored stack | Own project; healthy; readiness `READY`; old session rejected (401); fresh sign-in works; trust registry readable; valid credential `ACCEPTED`; revoked credential stays revoked; guardian cases survived (2); ledger chain whole (9 events) and verifies |
| Audit chain | Same verdict on source and restore: "BROKEN at 116". This is expected: the E2E stage deletes audit rows on purpose to prove tamper detection ("the audit chain reports the deleted audit rows"). The 21 November drills show the same pattern (204, 198, 196). |

Before: 21 November initial drill 32/0, final drill **30/2** (F-12), with the CLI exiting non-zero although the restore was `RESTORED_AND_VERIFIED`.

**Why 32/32 now.** The harness check reads the *strict* field `sourceFingerprintUnchanged` (all document counts equal). In this drill the source did not grow at all, because FIX-4 removed the routine audit writes that grew the log on 21 November. The harness was not changed to read the new tolerant field: its meaning stayed the same.

### C.2 The new tolerance itself (`fix5_fields_and_negative_cases.log`)

**1. CLI run without approval.** Refused before any write (`REJECTED`, `DUAL_CONTROL_REQUIRED`, exit 1). The report still carries every new field:
- `sourceFingerprintUnchanged: true`
- `sourceUnchanged: true`
- `sourceChangedCollections: []`
- `sourceAppendOnlyGrowth: {}`
- 26 source collections

**2. `compare_source()` on the live source's real counts (read-only), with simulated after-states:**

| Case | `sourceUnchanged` | Reported |
|---|---|---|
| Nothing changed | true | – |
| Audit log grew by 4 (background work) | **true** | growth `audit_events +2`, `audit_outbox +2` |
| A business collection changed (`credentials +1`) | **false** | `credentials` |
| `audit_events` shrank by 1 | **false** | `audit_events` |
| A collection disappeared (`holder_wallets`) | **false** | `holder_wallets` |
| A new collection appeared | **false** | `unexpected_collection` |

**3. Unit tests.** `tests/unit/test_platform_restore_drill_source_check.py`, 5/0, inside the identity suite of section G.

**Limit.** Real concurrent audit growth *during* a live drill did not occur in this run, so the tolerant path was proven with live counts plus simulated growth, not with growth caused by a concurrent writer.

**Result: met.** 32/32 expected checks pass, the CLI exits 0, the source was not changed, normal audit growth is accepted, and business-data changes, shrinking audit collections, missing or unexpected collections are refused.

**Incident.** The first DR attempt stopped after 9 s with "user drill_partial@admin already exists". That state was left in the `audit-20261121-dr4` mongod by an earlier drill. The DR target was moved to a fresh project, `audit-20261121-dr5`; this is the only change to `wp31_dr.mjs`, and the original file is kept as `closeout/wp31_dr.before_dr5.mjs`. The rerun gave 32/0. The aborted log is kept as `dr_run1_aborted_dr4_leftover_user.log`.

---

## D. FIX-6 live verification (F-15: retry counter never reset)

| Topic | Result | Evidence |
|---|---|---|
| Starting state | New keys are `ACTIVE` with `reconciliationAttempts` 0 | `fix4_live_api.log`, `fix46_live_scenario.log` |
| Counter after successful syncs (running stack) | 0 for all 6 keys over 12 minutes of routine syncs, including a restart; 0 for a fresh key after 130 s | snapshots (B.3), `fix4_live_api.log` |
| Counter after each successful sync (scenario) | 0 after each of 5 syncs | `fix46_live_scenario.log` |
| One transient provider failure | Key stays `ACTIVE`, counter 1 | same |
| Next successful sync | Counter back to 0 | same |
| Three consecutive failures | `ACTIVE` (1) → `ACTIVE` (2) → `FAILED` (3); each failure audited | same |
| Metrics | 4 failures counted (1 transient + 3 consecutive) | same |

Before the fix (`03`, F-15, reproduced by a unit test on the old code): after 5 routine syncs and one timeout, the key went straight to `FAILED` with attempts 6.

**Limit.** The provider failures were simulated with the development provider's failure switch in the scenario process (same code and image, real isolated MongoDB). The running stack's provider was not broken on purpose, because that would need a change to the stack's configuration.

**Result: met.** A successful sync resets the counter, a single transient failure does not fail an ACTIVE key, and consecutive failures still reach `FAILED` at the retry limit.

---

## E. F-06 QR E2E checks

### E.1 What was wrong

Two checks in `evidence/scripts/wp31_e2e.mjs` (section `qr`) still expected the old WP-32 design.

**Check 1: "client_id is the public origin, not an internal host"**
- Old assertion: `qrSession.clientId === "http://wallet.wp31.test/verifier"`.
- What the system does now: the verifier is identified by a key, `decentralized_identifier:did:jwk:<Ed25519 public JWK>`, used in a signed request object (JAR).

**Check 2: "the same-device link is an OID4VP authorization request"**
- Old assertion: the link starts with `openid4vp://?client_id=` and contains `dcql_query=` and `nonce=` inline.
- What the system does now: the request is passed by reference (`request_uri`), so the query and nonce are no longer in the link.

The root cause is test drift, not a product bug. The product behaviour was confirmed by the code (`oid4vp.py`, `request_uri_resolver.py`) and by the OID4VP security stage.

### E.2 New assertions

The original file is kept as `closeout/wp31_e2e.before_F06.mjs`.

**Check 1: "client_id is a did:jwk verifier key, not an internal host"**
- The client_id matches `decentralized_identifier:did:jwk:<base64url>`.
- The JWK is `OKP` / `Ed25519` with `x`, and has **no private part `d`**.
- No internal host name appears in it.

**Check 2: "the same-device link is a signed OID4VP authorization request"**
- The link is `openid4vp://?` with the same `client_id`.
- `dcql_query` and `nonce` are **not** in the link.
- `request_uri` is on the public origin.
- Fetching it returns 200 with `typ oauth-authz-req+jwt` and `alg EdDSA`.
- **The Ed25519 signature verifies with the client_id key.**
- Claims: `client_id` equal, `response_type vp_token`, `nonce` equal to the session nonce, `dcql_query` present, and an http(s) `response_uri` without an internal host.

The two new checks are stricter than the old ones. `f06_check_selftest.mjs` (7/0) shows they accept a real key and a correctly signed request object, and refuse:
- a client_id carrying `d`;
- the old URL client_id;
- an internal host;
- a request object signed by another key;
- a tampered payload.

### E.3 Security checks still covered

| Required check | Where it is verified |
|---|---|
| QR content | E2E `qr`: "verifier QR is an http(s) link a camera can open", "the QR holds no credential id, urn, DID, nonce or claim" |
| No internal Docker hostname | E2E `qr`: check 1 above, "no internal host appears in the same-device link", and the `response_uri` part of check 2; FIX-1 default-origin check (7/0, with `IDENTITY_PUBLIC_ORIGIN` empty); `request_uri` scan stage |
| Opaque handle / `request_uri` built correctly | QR `…/wallet/present?request=<handle>`; same-device `request_uri` on the public origin (check 2) |
| Request content fetched correctly | check 2 (status, type, algorithm, claims) |
| Valid nonce | check 2 (nonce equals the session nonce); "every request gets a fresh nonce and handle"; OID4VP security nonce 2/0 |
| Verifier identity | check 2 (signature by the client_id key); OID4VP security client_id 1/0 |
| Holder consent | "after a denial no presentation can be created" (409); OID4VP security consent 2/0 |
| Single use / replay | "a replayed presentation is refused" (409); OID4VP security replay 1/0; cross-device stage |
| Result shown correctly | "the full request to verdict path is accepted" (`ACCEPTED`); cross-device and wp32 UI browser stages (section G) |

### E.4 Result

| Run | E2E total | `qr` section |
|---|---|---|
| 21 November final (`final_e2e.log`) | 130 / 2 | 9 / 2 |
| Closeout before the edit (`e2e_pre_f06.log`) | 130 / 2 | 9 / 2 |
| Closeout after the edit (`e2e.log`) | **132 / 0** | **11 / 0** |

No other E2E check changed. Every other section has the same pass count as before:

| Section | Passed |
|---|---|
| guardian | 24 |
| keys | 6 |
| ledger | 28 |
| mfa | 6 |
| password | 7 |
| recovery | 12 |
| reissue | 12 |
| risk | 6 |
| session | 5 |
| trust | 5 |
| wallet | 9 |

---

## F. Real-MongoDB integration tests

| Item | Value |
|---|---|
| Test file | `services/identity-service/tests/integration/test_mongo_repositories.py` (7 tests) |
| Command | `pytest tests/integration/test_mongo_repositories.py -v` |
| Environment | A one-off container from the audit identity image (Python 3.12.16, pytest 9.0.3), repository mounted read-only, attached only to the audit network `audit-20261121_default` |
| Target | The isolated audit mongod (192.168.0.3 on the audit network). The owner mongod is on another network (`secure-ssi-platform_default`, 172.22.0.8) that the test container could not reach. |
| Database | `secure_identity_test_6b04546f9003bc2f6a30c92e` (the fixture creates `secure_identity_test_<ObjectId>`, asserts the prefix and drops only that database at the end) |
| Isolation proof | The databases before and after the run are identical (`admin config local secure_identity secure_recovery secure_revocation_ledger secure_security_intel`). The only database seen during the run was the test database. |
| Data | Synthetic fixtures from the test file; no user data |
| Result | **7 passed, 0 failed, 0 skipped, 0 errors** (2.10 s) |
| Logs | `closeout/mongo_integration.log`, `mongo_it_isolation.txt`, `mongo_it_databases.txt`, `mongo_it_seen.txt` |

The tests covered:
- idempotent indexes;
- user versioning and soft delete;
- credential and audit repositories;
- single-use presentations;
- atomic, irreversible revocation;
- wallet and challenge repositories;
- the managed-key optimistic lifecycle.

No connection string, user name or password appears in these files.

---

## G. Full regression

### G.1 Unit, build and lint

| Suite | Command and environment | 21 Nov initial | 21/23 Nov final (`10`) | Closeout 23 Nov | Change | Log (`closeout/`) |
|---|---|---|---|---|---|---|
| API gateway | `pytest -q`, local `.venv` | 48 / 0 / 0 | 50 / 0 / 0 | **50 / 0 / 0** | – | `unit_api-gateway.log` |
| Identity | `pytest -q -rs tests`, container `--network none` | 1083 / 0 / 12 | 1095 / 0 / 12 | **1095 / 0 / 12** | – | `unit_identity.log` |
| Identity real MongoDB | section F | 7 / 0 / 0 | not evidenced | **7 / 0 / 0** | now evidenced | `mongo_integration.log` |
| Recovery | `pytest -q`, local `.venv` | 131 / 0 / 1 | 131 / 0 / 1 | **131 / 0 / 1** | – | `unit_recovery-service.log` |
| Fraud | `pytest -q`, local `.venv` | 90 / 0 / 0 | 90 / 0 / 0 | **90 / 0 / 0** | – | `unit_fraud-service.log` |
| Shared package | `unittest` | 5 | 5 | **5 OK** | – | `unit_shared_pkg.log` |
| Root tests | `unittest` | 3 | 3 | **3 OK** | – | `unit_root_tests.log` |
| Web unit | `npm test` | 42 | 42 | **42** (output identical to `final_web_unit.log` except durations) | – | `web_unit.log` |
| Web lint | `npm run lint` (`eslint .`) | no problems | no problems (no exit line saved) | **no problems, exit 0** | exit code now recorded | `web_lint.log` |
| Web build | `npm run build` | OK | OK | **OK** (6428 modules, built in 11.45 s) | – | `web_build.log` |

Skipped tests (reasons from `-rs`; none was skipped to get green):
- identity, 12 in total:
  - 5 blockchain-anchoring tests, skipped because no local Hardhat node is running (an external dependency, outside the default setup);
  - the 7 real-MongoDB tests, skipped in the unit run because `IDENTITY_TEST_MONGODB_URI` is not set, and run separately in section F (7/0);
- recovery: 1, the same skip as in every earlier run.

### G.2 Live stages on the isolated stack

Each stage ran on a freshly reset isolated stack (`stage.sh`). `ui` runs on the scenarios data without a reset, as on 21 November.

| Stage | 21 Nov initial | 21 Nov final (`10`) | Closeout | Change | Log (`closeout/`) |
|---|---|---|---|---|---|
| E2E | 130 / 2 | 130 / 2 | **132 / 0** | F-06 fixed | `e2e.log` |
| Gaps | 38 / 0 | 38 / 0 | **38 / 0** | – | `gaps.log` |
| Post (security intelligence feed) | 15 / 0 | 15 / 0 | **15 / 0** | – | `post.log` |
| Onboarding | 40 / 0 | 40 / 0 | **40 / 0** | – | `onboarding.log` |
| Scenarios | 41 / 0 | 41 / 0 | **41 / 0** (first chain), **41 / 0** (re-run before `ui`) | – | `scenarios.log`, `scenarios_rerun.log` |
| OID4VP security | 16 / 0 | 16 / 0 | **16 / 0** | – | `oid4vp_security.log` |
| `request_uri` scan | 11 / 0 | 11 / 0 | **11 / 0** | – | `wp32_scan.log` |
| Wallet card UI | 31 / 0 | 31 / 0 | **31 / 0** | – | `wp32_card.log` |
| Cross-device (two browsers) | 13 / 0 | 13 / 0 | **13 / 0** | – | `wp32_cross.log` |
| wp32 UI | 12 / 0 | 12 / 0 | **12 / 0** | – | `wp32_ui.log` |
| UI (security intelligence) | 25 / 16 | 41 / 0 | **41 / 0** (57 s; an earlier attempt hung, G.3) | – | `ui_rerun.log`; hung attempt `run2_ui_hung/ui.log` |
| Browser | 40 / 0 | 40 / 0 | **40 / 0** | – | `browser.log` |
| Pages (every route, every role, desktop and 390 px) | 62 pages, axe 0 | 62 pages, axe 0 | **62 pages, axe 0, console errors 0, overflow 0** (exit 0) | – | `pages.log` |
| DR drill | 32 / 0 | 30 / 2 | **32 / 0**, exit 0 | F-12 fixed | `dr.log` |
| FIX-1 default origin (`IDENTITY_PUBLIC_ORIGIN` empty) | – (before the fix: E2E 128 / 4, internal host in the link) | 7 / 0 | **7 / 0** (setting confirmed empty inside the container, restored afterwards) | – | `fix1_default_origin.log` |
| FIX-4/6 scenario (new) | – | – | **33 / 0** | new | `fix46_live_scenario.log` |
| FIX-4 live API (new) | – | – | 8 / 1 (test design, B.6) | new | `fix4_live_api.log` |
| FIX-4 background rotation (new) | – | – | **5 / 0** | new | `fix4_live_rotation_grace.log` |
| F-06 check self-test (new) | – | – | **7 / 0** | new | `f06_check_selftest.log` |

### G.3 Harness mistake in this closeout

The first regression runner (`run_regression_chain.sh`) left out the screenshot-folder argument for the seven browser stages (`browser`, `pages`, `wp32_scan`, `wp32_card`, `wp32_cross`, `wp32_ui`, `ui`). Each crashed at `mkdirSync(undefined)` within a second, before sending any request.

This was a mistake in how the stages were called, not a product result. The seven logs are kept in `closeout/run1_missing_shots_arg/`. `run_regression_fixup.sh` ran the seven stages again with the argument (summary in `chain_regression_fixup.txt`):
- browser, pages, scan, card, cross-device and wp32 UI passed with the 21 November numbers;
- `ui`, run first on the scenarios data, **hung for 65 minutes** before its first check.

**Diagnosis of the hung run:**
- A second, read-only DevTools client (`closeout/probe_devtools.mjs`; observations in `closeout/ui_hang_probe.txt`) found the page fully loaded on `/admin/intelligence`, signed in, with all 8 tabs present and the first one selected.
- That client got a screenshot at once.
- axe had not yet been injected.

So the stage's own DevTools session had stopped receiving answers; the product page was healthy.

The harness's `timeout 2400` did not stop the native `node.exe` (I-5). The process tree (`node` and its headless Edge) was stopped with taskkill; its log is in `run2_ui_hung/`. `run_closeout_tail.sh` then ran scenarios again (with a reset) and `ui` right after it, under a watchdog that really stops the process tree: `ui` passed 41/0 in 57 s (summary in `chain_regression_tail.txt`).

**Not run:** the 5 blockchain-anchoring tests (no local Hardhat node, G.1). Every other suite and stage listed in `10` was run.

### G.4 Areas the prompt lists

| Area | Covered by |
|---|---|
| API Gateway | gateway unit 50/0; every live stage goes through the gateway |
| Identity / Recovery / Fraud | unit suites (G.1) |
| Web unit / build / lint | G.1 |
| E2E | 132/0 |
| QR / `request_uri` | E2E `qr` 11/0, `request_uri` scan, cross-device, FIX-1 default origin |
| OID4VP security | 16/0 |
| Wallet | E2E wallet 9/0, wallet card UI |
| Guardian recovery | E2E guardian 24/0, recovery 12/0, recovery unit 131/0/1 |
| Backup & restore | E2E wallet backup checks; DR drill |
| Platform DR | 32/0 |
| Managed key | E2E keys 6/0; B and D |
| MongoDB repository integration | 7/0 |
| Browser / admin pages | browser, pages, UI stages |

---

## H. Git and Docker state

### H.1 Git

**Before** (`git_before.txt`, 2026-11-23 17:46):
- branch `besna-dev`;
- HEAD `9fa97d7` (2026-11-03), equal to `origin/besna-dev`;
- 240 uncommitted entries (134 modified, 1 deleted, 105 untracked).

**Ownership** (`git_ownership.txt`):

| Group | Entries |
|---|---|
| New audit files and folders | 3 |
| Files changed only by FIX-4/FIX-6 | 2 |
| Mixed WP and audit-fix files | 5 |
| Pre-audit WP-28..WP-32 work | 230 |

**Owner's instruction of 2026-11-23.** The closeout task said "no commit or push". On 2026-11-23 the owner asked in writing for a commit after each small task, pushed to their branch, with many commits. That later instruction was followed.

**What was committed and pushed** (normal `git push`, no force):

| Commits | Content |
|---|---|
| 42 | The uncommitted work, in topic groups:<br>• gateway 2;<br>• identity 19;<br>• recovery 5;<br>• fraud 3;<br>• web 7;<br>• deploy 1;<br>• docs 1;<br>• audit reports, evidence and harness 4 (the last one, `6918915`, also carries the F-06 and `dr5` harness edits) |
| 11 | Closeout evidence, from `504be04` to `111af9e` |
| 1 | This report, with the record of the hung-run diagnosis (`probe_devtools.mjs`, `ui_hang_probe.txt`) |

- The audit fixes have their own commits: `d40e064` (FIX-1, gateway), `37bad3e` (FIX-1, identity), `9b972c1` (FIX-2, FIX-3), `df97598` (FIX-4, FIX-6), `3ed21c7` (FIX-5).
- Each message says whether a file also contains earlier WP work.
- Commit messages are in English and end with the co-author line.

| Check (`integrity_after.txt`) | Result |
|---|---|
| Branch | `besna-dev`, never switched |
| Local and remote tip | equal (`111af9e` at the integrity check, before this report's commit) |
| Other branches | untouched: `main` last changed 2026-10-23, `backup/pre-g0-ui` 2026-10-04 (reflog) |
| History | nothing rewritten, reset, stashed or cleaned |
| Still uncommitted | `research/` (TÜBİTAK drafts, I-8) and the stray pytest temporary folder (I-8) |
| WP work | committed as it was. The only edits made by the closeout are listed in the appendix. |

### H.2 Audit stack

**Images:**

| Image | Built | Contents |
|---|---|---|
| `audit-20261121-identity-service` (`87834a642fde`) | 2026-11-23 | the committed fixes (B.1) |
| `audit-20261121-api-gateway` (`c2145200452e`) | 2026-11-21 | FIX-1 |

**Settings.** The temporary env copies (rotation grace 30 s; empty public origin) were each followed by a restore from the normal audit env. No temporary env file is left.

**State at the end:**
- The project `audit-20261121` (7 containers) was stopped after the last test, by a stop selected by its compose project label. Its volumes are kept.
- The DR projects `audit-20261121-dr` to `-dr5` are stopped, with their volumes kept (26 audit volumes in total, I-9).

### H.3 Owner stack and data integrity

From `integrity_after.txt` (read-only):

| Question | Answer | Evidence |
|---|---|---|
| Owner MongoDB data preserved? | Yes. The owner mongod was not restarted (same start time, 0 restarts), and no closeout command addressed it. Every database command names an `audit-20261121-*` container, and the helpers refuse anything else: `isolatedMongo` checks the name prefix, and `reset_audit.sh` and `audit_snapshot.sh` also check the compose project label. | sections 1 and 4 |
| Owner Docker volumes preserved? | Yes. The same 5 volumes exist, with their original creation dates. | section 3 |
| User data affected? | No. Tests used only synthetic users on isolated databases. | B–G |
| Audit/owner separation kept? | Yes. No audit container is on the owner network, and no owner container is on an audit network. The DR mongods join the audit network on purpose (`wp31_dr.mjs` line 49). | section 4 |
| Owner stack changed? | No. All 7 containers run the same images with the same start times. The owner image tags are unchanged. | sections 1 and 2 |
| Git branch changed? | No. | section 5 |
| Commit or push made? | Yes, at the owner's request, on `besna-dev` only (H.1). | section 5 |
| Existing WP work modified? | No. It was committed as it was. | H.1 |
| Test secrets moved into a real environment? | No. The repository has only `.env.example`, which the closeout did not edit. Temporary env files: 0 left. | section 6 |
| Secrets or personal data in the test logs? | No. Over 71 closeout files:<br>• 0 three-part JWTs;<br>• 0 e-mail addresses outside the synthetic domains;<br>• 0 national-ID-shaped numbers;<br>• 0 generated synthetic passwords.<br>The 4 heuristic hits are false positives: an env placeholder in two harness URIs, and deliberately wrong passwords in negative tests. | sections 7 and 8 |

### H.4 Owner stack: what runs, and a safe rebuild plan (not executed)

**What runs.** The owner containers were created between 2026-11-03 and 2026-11-10 (`docker_before.txt`):

| Container | Created |
|---|---|
| identity | 2026-11-07 |
| gateway, recovery, fraud | 2026-11-10 |
| web | 2026-11-10 |
| MongoDB | 2026-11-06 |
| Redis | 2026-11-03 |

Four of the running image IDs (identity, gateway, recovery, fraud) are no longer tagged, so `docker image inspect` cannot read them. Their build date is bounded by the container dates.

**What is missing from it.** The owner stack therefore contains **none of the audit fixes** (FIX-1 to FIX-6, made 21–23 November). It also lacks the later WP-28..WP-32 changes that were in the working tree, and are now committed, after those dates.

**What a rebuild affects.** The identity service, gateway, recovery service, fraud service and web app all have code changes. MongoDB and Redis keep their images.

**Safe rebuild plan** (needs the owner's explicit approval; never run during this closeout):

1. **Back up first**, outside OneDrive (for example `C:\ssi-backups\<date>\`):
   - an application platform backup (admin, step-up, dual control) and its verification;
   - a `mongodump` of the owner MongoDB;
   - a read-only tar of the volumes `secure-ssi-platform_mongodb_data`, `_identity_backups`, `_identity_ledger_anchor` and `_fraud_state`.
2. **Keep a rollback image of each running service:** `docker commit secure-ssi-platform-<service>-1 secure-ssi-platform-<service>:rollback-<date>`. The running images are untagged, so a plain `docker tag` is not enough.
3. **Check the configuration** with `docker compose -p secure-ssi-platform config`. Compare the owner's environment with `.env.example`:
   - the step-up secret shared with recovery (FIX-2);
   - Mongo passwords, which now feed the default URIs (FIX-3);
   - `IDENTITY_PUBLIC_ORIGIN`, which should be set for a real phone;
   - backup and ledger settings.
4. **Build from the committed tree** on `besna-dev`: `docker compose -p secure-ssi-platform build identity-service api-gateway recovery-service fraud-service web`.
5. **Replace one service at a time** with `docker compose -p secure-ssi-platform up -d --no-deps <service>`. Go in this order:
   - identity first (indexes are ensured at start-up);
   - then recovery and fraud;
   - then gateway and web.

   Never use `down -v` or any prune.
6. **Verify:**
   - health and readiness;
   - owner sign-in by the owner;
   - audit chain verdict;
   - one credential verification;
   - collection counts before and after (only growth expected).
7. **Roll back** with `up -d --no-deps` on the `rollback-<date>` images. Restore the dump only if data were damaged.

**Commits and review before a rebuild.** The five files that mix pre-audit WP work with an audit fix are already committed, with commit messages that say so:
- `proxy.py` and `test_gateway.py` (FIX-1);
- `oid4vp.py` (FIX-1);
- `docker-compose.yml` and `.env.example` (FIX-2, FIX-3).

The WP-28..WP-32 work was committed in groups as it was, without changes. It was not written by the audit and was not reviewed line by line by it. A human review of those commits (or a pull request to `main`) is advisable before the owner stack is rebuilt from them.

---

## I. Open issues

| # | Issue | Why it is still open | What closes it |
|---|---|---|---|
| I-1 | The owner stack runs pre-fix images (none of FIX-1 to FIX-6; built on or before 7–10 November) | Rebuilding needs the owner's approval; this task forbade it | Plan in H.4 |
| I-2 | Reconciliation metrics have no HTTP endpoint (`InternalMetrics` is process-local) | They can only be read inside the process; checked that way in B.7 | A read-only admin metrics endpoint (new feature, outside this closeout) |
| I-3 | FIX-4/FIX-6 failure paths were exercised in the scenario process (same code and image, isolated real MongoDB), not by breaking the running stack's key provider | Breaking the provider on the running stack needs a configuration change of that stack | Optional: a test-only provider fault switch on the isolated stack |
| I-4 | The FIX-5 tolerance was proven with live counts plus simulated growth; no concurrent audit growth happened during the live drill | The drill window was quiet once FIX-4 removed the routine writes | Optional: a drill run with a concurrent audit writer |
| I-5 | The harness's `timeout 2400` (in `stage.sh` and `run_noreset.sh`) does not stop the native `node.exe` under Git Bash on this machine; one `ui` run hung for 65 minutes (G.3) | The harness was kept as it was; `run_closeout_tail.sh` uses a taskkill watchdog instead | Replace `timeout` with a taskkill-based guard in the harness |
| I-6 | A Git pack file is "cloud-only" in OneDrive (`.git/objects/pack/pack-6e2bacab….pack`) while the OneDrive client is not running. `git fetch` fails with "Invalid argument", and Git's automatic maintenance (geometric repack) fails after each commit. Commits and pushes work, and the remote tip was checked with `git ls-remote`. | Needs the owner's OneDrive client | Start OneDrive and mark the repository "Always keep on this device", or move the repository out of OneDrive |
| I-7 | The raw `*.log` evidence is not on GitHub (`.gitignore` excludes `*.log`) | Repository policy | Owner's decision: keep it local, or add a `.gitignore` exception for `audit/**/*.log` |
| I-8 | Untracked items left on purpose:<br>• `research/2209A/` (TÜBİTAK application drafts; the repository is public);<br>• a stray pytest temporary folder at the repository root, `UsersbesnaAppDataLocalTempsecure-ssi-root-audit-…/` (3 DID JSON test files) | Owner's decision | Push `research/` only on the owner's instruction; the temporary folder can be deleted |
| I-9 | Leftover isolated DR projects (`audit-20261121-dr` to `-dr5`) and their volumes stay on the machine | This task forbade deleting Docker volumes | Owner-approved cleanup of the audit projects only |
| I-10 | Production-readiness gaps from `10` remain, outside this closeout:<br>• no independent penetration test;<br>• development key provider, no KMS/HSM;<br>• no physical phone or public HTTPS test;<br>• backups not off-site and no PITR;<br>• the audit log is tamper-evident, not WORM;<br>• the fraud/risk module is rule-based (`rule-heuristic-v1`, `NOT_TRAINED`), not a trained model;<br>• blockchain anchoring needs a local Hardhat node (5 skipped tests) | Not part of the four closeout jobs | Separate work packages; none of them blocks the D1–D5 research experiments |
| I-11 | The 42 commits of pre-audit WP-28..WP-32 work were committed as they were, in topic groups. The audit did not write that code and did not review it line by line. | Out of scope; the closeout only verified it through the test suites | A human review, or a pull request from `besna-dev` to `main`, before merging or rebuilding the owner stack |

---

## J. Final decision

**The existing system is technically ready for the next development phase (D1–D5).** The four closeout jobs are done:
- FIX-4 to FIX-6 behave as intended on the live isolated stack and on a real MongoDB;
- the F-06 checks are updated without weakening them;
- the real-MongoDB repository tests pass;
- the full regression is green, with no new failure.

The fixes and the existing WP work are now committed and pushed, so the D1–D5 work has a fixed, documented starting point: `besna-dev` at the commit that adds this report.

**Conditions** (none blocks starting the D1–D5 work itself):
1. **Run experiments on an isolated stack built from the committed tree**, as this closeout did. The owner stack still runs images from 7–10 November, without the fixes (I-1). Use it for experiments only after an approved rebuild following H.4.
2. **Review the committed WP-28..WP-32 work** (I-11) before merging it into `main`.
3. **Fix the harness watchdog** (I-5) before relying on long unattended experiment runs, and **resolve the OneDrive Git problem** (I-6) before heavy Git use.
4. **Describe results within the existing limits** (I-10). The platform is an academic prototype, not production-ready. The fraud/risk module is rule-based, not a trained model. Physical-device and KMS/HSM checks are still missing.

---

## Appendix: acceptance criteria (section 12 of the closeout task)

| # | Criterion | Status | Where |
|---|---|---|---|
| 1 | FIX-4 live test successful | **Met.** The failure path was run in the scenario process (I-3). | B |
| 2 | FIX-5 DR drill passes every expected check | **Met.** 32/32, exit 0. The tolerance was proven with live counts and simulated growth (I-4). | C |
| 3 | FIX-6 live key-reconciliation verification successful | **Met.** The failure path was run in the scenario process (I-3). | D |
| 4 | The two old F-06 QR checks updated, keeping their security meaning | **Met.** The checks are stricter than before; self-test 7/0. | E |
| 5 | Full E2E regression verified in the new state | **Met.** 132/0. | E.4, G.2 |
| 6 | Seven MongoDB integration tests run on a real isolated MongoDB | **Met.** 7/0/0/0. | F |
| 7 | Full regression results recorded | **Met**, including the two harness incidents and the re-runs. | G |
| 8 | Owner MongoDB data and Docker volumes preserved | **Met.** | H.3 |
| 9 | No Git commit or push made | **Not met as written: superseded.** On 2026-11-23 the owner explicitly asked for small commits pushed to `besna-dev`. 54 commits were pushed, with no force, no other branch touched and nothing rewritten. | H.1 |
| 10 | Owner stack not changed without permission | **Met.** | H.3 |
| 11 | Every operation documented with real logs | **Met.** The raw logs are on the audit machine only (`*.log` is gitignored, I-7). | `evidence/closeout/` |
| 12 | `11_FINAL_TECHNICAL_CLOSEOUT.md` created | **Met.** | this file |

## Appendix: changes made during this closeout

| Kind | What |
|---|---|
| Product code | **None.** FIX-4 to FIX-6 were made earlier on 2026-11-23, before this task; this closeout verified them. |
| Test harness | `evidence/scripts/wp31_e2e.mjs`: the two F-06 checks and the `node:crypto` import (original kept as `closeout/wp31_e2e.before_F06.mjs`).<br>`evidence/scripts/wp31_dr.mjs`: `DR_PROJECT` set to `audit-20261121-dr5` (original kept as `closeout/wp31_dr.before_dr5.mjs`). |
| New closeout files | `evidence/closeout/`:<br>• live-check scripts: `fix46_live_scenario.py`, `fix4_live_api.mjs`, `fix4_live_rotation_grace.mjs`, `audit_snapshot.sh`, `f06_check_selftest.mjs`, `probe_devtools.mjs` (read-only diagnosis of the hung run);<br>• runners: `run_regression_chain.sh`, `run_regression_fixup.sh`, `run_closeout_tail.sh`, `run_fix1_default_origin.sh`, `integrity_after.sh`;<br>• snapshots and state records: `idle_*.json`, `restart_*`, `git_*.txt`, `docker_before.txt`, `mongo_it_*.txt`, `audit_image_contains_fixes.txt`, `ui_hang_probe.txt`;<br>• summaries: `chain_regression*.txt`, `integrity_after.txt`;<br>• logs (local only). |
| Isolated audit stack | • Identity image rebuilt with the fixes (`build_identity.log`; `audit-20261121-identity-service`, and the DR image tagged for `dr4`/`dr5`).<br>• The identity container recreated twice from a temporary copy of the audit env (rotation grace 30 s; empty public origin) and restored from the normal audit env each time.<br>• Isolated data reset before each stage (`reset_audit.sh`, which only acts on containers with the audit project label).<br>• The `dr4` mongod stopped (leftover drill user) and a fresh `dr5` project used for the drill.<br>• The hung `ui` run's `node` and headless Edge processes stopped with taskkill. |
| Git | All work committed in small groups on `besna-dev` and pushed to `origin/besna-dev`, on the owner's instruction of 2026-11-23 (H.1) |
| Not changed | Reports `00`–`10` and the audit folder's `README.md`; the owner stack, its images, volumes and data; every environment file; every other branch |
