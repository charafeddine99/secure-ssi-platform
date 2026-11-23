# 10 – Final Execution Report

Secure SSI Platform: audit of the existing system, consolidated.

| Item | Value |
|---|---|
| Prepared | 2026-11-23 |
| Audit work | 2026-11-21 (baseline, inventory, tests, FIX-1 to FIX-3) and 2026-11-23 (FIX-4 to FIX-6, full identity suite) |
| Sources | Reports `00`–`09` in this folder, raw logs in `evidence/`, the code in the working tree, `git`, and read-only Docker queries (`docker ps -a`, `docker volume ls`) |
| Changes made to write this report | None: no code, data, Docker state, configuration or Git history was changed |

**How to read it.** "Verified" means that for this report the claim was checked against a saved log, the code or a read-only query. "Reported" means that an earlier report states it but no saved log backs it. Section 0 lists the corrections to the earlier reports.

---

## 0. Corrections to earlier reports

The evidence was re-checked line by line. Three statements in earlier reports are not fully backed by the saved logs.

| Earlier statement | What the evidence shows | Consequence |
|---|---|---|
| `02`: the E2E run before the step-up secrets matched ended "36/46" (F-02) | `evidence/initial_e2e_run2_stepup403.log`: 41 checks passed. The run then aborted with `step-up 403 PERMISSION_DENIED` while setting the guardian policy, and no total was printed. | The F-02 diagnosis stands (step-up 403 on guardian actions). The figure "36/46" is not backed by a saved log. |
| `05`: identity final "skips = 7 real-Mongo (run separately: 7/7)" | Only `evidence/initial_identity_mongo_integration.log` (7 passed) exists. There is no log for a final run. | The **final** real-MongoDB integration result is not evidenced. The fixes do not touch the repository code these tests cover. |
| `02`/`05`: web lint "exit 0" | Both lint logs contain only the command header (`eslint .`): no problem is listed, but no exit-code line was recorded either. | Recorded below as "no problems reported". |

---

## 1. Executive summary

- **What exists.** The project is a working, multi-service academic prototype, not a mock-up. It consists of:
  - a React/TypeScript web app (36 routes);
  - an API gateway (44 operations);
  - an identity service (117 operations);
  - a recovery service (25);
  - a fraud and security-intelligence service (21);
  - MongoDB (4 databases, 43 collections) and Redis.
- **What was done.**
  - Baseline and rollback copy.
  - Feature inventory built from code.
  - Every unit suite and 17 live stages run before and after the fixes.
  - 15 findings recorded (F-01 to F-15) and 6 fixes made:
    - FIX-1 to FIX-3 on 2026-11-21, re-verified on the live isolated stack;
    - FIX-4 to FIX-6 on 2026-11-23, unit-tested and full identity suite green; **live re-check pending**.
- **Tests now.**
  - Every unit suite is green: identity **1095 passed / 0 failed / 12 skipped** (2026-11-23), gateway 50, recovery 131/1 skip, fraud 90, web 42.
  - Every live stage is green except two kinds of check:
    - 2 outdated E2E QR checks (F-06, test drift);
    - the DR "source unchanged" check (F-12). Its code is fixed on 2026-11-23, but the drill was not re-run.
- **Security.**
  - No Critical or High issue is open.
  - The security suites found no authentication bypass, IDOR, injection, signature bypass or replay.
  - The system is **not production-ready**. There was no independent penetration test, no real KMS/HSM, no physical phone or public HTTPS, and backups are not off-site and have no PITR.
- **Data and Git.**
  - Owner data and volumes were not touched. Tests ran on isolated compose projects with synthetic users.
  - Nothing was committed or pushed; every change is uncommitted on `besna-dev`.
  - Three incidents caused by things outside the session are documented (section 12).
- **Next phase (TÜBİTAK D1–D5).**
  - The platform already contains most of the controls the experiments compare: OID4VP replay, nonce, audience, client_id, expiry and revocation checks; TOTP/WebAuthn step-up; guardian recovery with a time lock; session revocation after recovery.
  - Missing:
    - an experiment harness with switchable controls;
    - password reset (A3);
    - risk-based step-up at sign-in;
    - step-up before a presentation;
    - QR session binding and a proximity check (P4);
    - the D2/D3 analysis code and the statistics package.
  - Real devices depend on the TÜBİTAK budget items.

---

## 2. Work performed

| Date | Work | Output |
|---|---|---|
| 2026-11-21 | Baseline: branch, HEAD, 233 uncommitted entries, versions, environment; rollback copy before any change | `00_SYSTEM_BASELINE.md` |
| 2026-11-21 | Inventory from code: OpenAPI of each service, web routes, existing collections, test files | `01_COMPLETE_FEATURE_INVENTORY.md`, `evidence/routes_*.txt` |
| 2026-11-21 | Initial run of every unit suite and of the live stages on the isolated stack `audit-20261121` | `02_INITIAL_TEST_RESULTS.md`, `evidence/initial_*.log` |
| 2026-11-21 | Findings F-01 to F-13; FIX-1 to FIX-3; image rebuild; regression run | `03`, `04`, `05`, `evidence/final_*.log`, `evidence/regression_*.log` |
| 2026-11-21 | Module matrix, security review, external dependencies, final status | `06`, `07`, `08`, `09` |
| 2026-11-21 | Incident handling: 37 old web files that reappeared were moved out with the owner's approval; a new rollback copy was made outside OneDrive | `08`, `README.md` |
| 2026-11-23 | Owner's decision on F-14. FIX-4 (F-14), FIX-5 (F-12) and FIX-6 (new finding F-15) with 9 new tests; mutation check; full identity suite in a network-less container (Docker started by the owner); reports `03`–`09` updated | `04`, `05`, `evidence/final_identity-service_20261123.log` |
| 2026-11-23 | This consolidated report | `10_FINAL_EXECUTION_REPORT.md` |

---

## 3. What was examined

### 3.1 Folders and modules (Q1)

| Part | Path | Examined for |
|---|---|---|
| Web app | `apps/web` (`src/pages`, `src/components`, `src/routes`, `src/lib`, `src/api`, `tests`) | Routes, guards, pages, client-side crypto, unit tests, build, lint |
| API gateway | `services/api-gateway` (`app/api/routes/proxy.py`, `app/core/session.py`, `app/core/middleware.py`) | Proxying, session cookie, CSRF, rate limit, security headers |
| Identity service | `services/identity-service/app` (api/v1, application/services, domain, infrastructure, tools) | Auth, MFA, WebAuthn, dual control, VC issuance, OID4VCI, OID4VP, status lists, ledger, wallets, managed keys, trust registry, audit, platform backup, DR tool |
| Recovery service | `services/recovery-service` | Guardians, M-of-N policy, decisions, time lock, step-up |
| Fraud / security intelligence | `services/fraud-service` (`app/application/hybrid_detector.py`, `app/ml/*`, `app/intelligence/*`) | Rule-based scoring, intel pipeline, model status |
| Shared package | `packages/shared` | Helpers (5 tests) |
| Smart contracts | `blockchain/` | Optional anchoring (not run live) |
| Deployment | `docker-compose.yml`, `.env.example`, Dockerfiles | Wiring of secrets, database URIs, origins |

### 3.2 Frontend components (Q2)

From `01`:
- **Sign-in and roles:** `LoginPage`, `RegisterPage`, `api/session.ts`; route guards in `routes/AppRoutes.tsx` and `routes/navigation.ts`.
- **Account security:** `AccountSecurityCards`, `StepUpProvider`, `AuthenticatorCard` with `lib/webauthnClient.ts`, `DualControlPanel`.
- **Issuer:** `IssueCredentialPage`, `CredentialTemplatesPage`, `RevocationRegistryPage`, and `offerUri.ts` for holder offer handling.
- **Wallet:** `WalletDashboard`, `CredentialDetailPage`, `CredentialCard` (the green card).
- **Verifier and presentation:** `CreateRequestPage`, `PresentationConsentPage`, `ScanQrPage`, `PresentRequestHandoff`, `QrPanel`, `utils/scanInput.ts`.
- **Backup and recovery:** `WalletBackupPage` with `lib/walletBackupCrypto.ts`; `GuardianDashboard`, `GuardianEnrollment`, `ApproveRecoveryPage`, `RecoveryTimeline`.
- **Admin:** `PlatformBackupPage`, `TrustRegistryPage`, `AuditExplorerPage`, `SecurityIntelligencePage`, `SmartContractsPage`, and the other admin pages.

The app has 36 routes in total: public 5, holder 11, issuer 4, verifier 4, guardian 3, admin 9. All of them were rendered in 62 page/viewport combinations (`final_pages.log`: `TOTAL pages=62 axe=0 console=0 overflow=0`).

### 3.3 Backend services and API endpoints (Q3)

Counts are verified against the headers of `evidence/routes_identity.txt` (`identity-service 117`) and `evidence/routes_other_services.txt` (`recovery-service 25`, `fraud-service 21`).

| Service | Operations | Groups |
|---|---|---|
| Identity | 117 | `/api/v1/wallets` 19, `/auth` 15, `/admin` 15, `/oid4vp` 12, `/oid4vci` 8, `/credentials` 8, `/trust-registry` 6, `/blockchain` 6, `/status-lists` 4, `/reissuance-requests` 4, `/presentations` 4, `/audit` 3, `/presentation-challenges` 2, `/database` 1, internal recovery 2 |
| Recovery | 25 | Guardians, policy, requests, approvals, timeline, notifications, admin oversight |
| Fraud | 21 | Legacy `evaluate`/`events`/`quarantine`/`stats` and `/intel/*` |
| Gateway | 44 | Proxy routes, session cookie, `/system/status`, `/health` (from `01`) |

### 3.4 Database models and data flows (Q4)

Databases:
- `secure_identity`: 28 collections, among them `users`, `session_revocations`, `mfa_factors`, `step_up_tokens`, `webauthn_credentials`, `credentials`, `credential_offers`, `status_lists`, `holder_wallets`, `verification_sessions`, `presentations`, `wallet_backups`, `platform_backups`, `managed_keys`, `trust_registry`, `audit_events`, `audit_outbox`, `dual_control_operations` and `blockchain_anchors`.
- `secure_recovery`: 9 collections.
- `secure_revocation_ledger`: 1 collection.
- `secure_security_intel`: 5 collections.

Flows checked end to end on the isolated stack:
- **Issuance:** OID4VCI offer, then token (pre-authorized code plus `tx_code` with an attempt limit), then a credential with proof of possession, then a status-list entry.
- **Presentation:** verifier request, then a signed request object (JAR, `did:jwk` client_id), then the `request_uri` in the QR, then the wallet resolves and the holder consents, then the response is checked (signature, issuer trust, holder binding, nonce, audience, expiry, status), then the verdict.
- **Recovery:** guardian invitations, then M-of-N signed decisions, then the time lock, then internal recovery in identity. Recovery rotates the wallet key and revokes all sessions (`services/identity-service/app/api/internal/recovery.py`, `authentication.revoke_subject(...)`).
- **Backups:**
  - wallet archive encrypted on the client (Argon2id + AES-GCM);
  - platform archive encrypted and integrity-verified, restored into a separate database under dual control.
- **Audit:** hash-chained `audit_events`, then `audit_outbox`, then the security-intelligence forwarder.

### 3.5 Security controls examined (Q5)

| Area | Controls examined |
|---|---|
| Authentication | Argon2id, short-lived JWT, server-side revocation, gateway cookie (HttpOnly, SameSite=Strict, `__Host-` prefix when Secure), CSRF |
| Step-up and dual control | TOTP and WebAuthn step-up bound to action and resource; dual control |
| Authorization | RBAC and IDOR |
| Request handling | Request size and depth limits; CORS; error handling that does not leak internals |
| Credentials | Credential signature verification with 15 tamper variants, key substitution and non-Ed25519 keys |
| Presentation | OID4VP replay, nonce, audience, expiry and tampering; SSRF-safe `request_uri` fetch |
| Recovery | Time lock, M-of-N, policy floors, owner cancel |
| Keys and audit | Key custody (development provider); audit hash chain and ledger principal limits |
| Backups | Backup encryption and integrity |

Details are in `07_SECURITY_AUDIT.md`.

### 3.6 Features tested (Q6)

Unit suites: gateway, identity, recovery, fraud, shared package, root tests, web.

The 17 live stages on the isolated stack:
- E2E
- gaps
- post
- onboarding
- scenarios
- OID4VP security
- `request_uri` scan
- wallet card UI
- cross-device
- wp32 UI
- UI (security intelligence)
- browser
- pages
- DR drill
- FIX-1 live check
- real-MongoDB repositories (initial run only)
- web build and lint

The numbers are in section 7.

---

## 4. Findings (Q7)

| ID | Severity | Module | Finding | Status (2026-11-23) |
|---|---|---|---|---|
| F-01 | High | OID4VP / QR (`oid4vp.py`, gateway proxy) | Without `IDENTITY_PUBLIC_ORIGIN` (the default), the QR and the same-device link carried `http://identity-service:8000/...`. A phone cannot reach this internal hostname, and the link leaks it. | Fixed (FIX-1), live 7/7 |
| F-02 | Medium | Recovery step-up (`docker-compose.yml`) | One shared secret was wired as two independent variables. When they differed, every guardian or recovery-policy action failed with 403. | Fixed (FIX-2) |
| F-03 | Low | Deployment config | The default Mongo URIs hard-coded the default passwords, so the identity service did not start after a password change. | Fixed (FIX-3) |
| F-04 | Info | Security defaults | Step-up, dual control and recovery step-up are off in development mode by default. This is documented. | Documented |
| F-05 | Info | Revocation ledger | The ledger is off unless configured. With it on, rollback protection works. | Documented |
| F-06 | Info | Test harness | 2 E2E checks still expect the pre-WP-32 QR design. | Open (test drift) |
| F-07 | Info | Test harness | A wait after the rate limit made TOTP codes expire. | Harness fixed |
| F-08 | Info | Local environment | Windows Smart App Control blocks `cbor2` in `.venv`. | Environment |
| F-09 | Info | Blockchain | No chain node is running. | External dependency |
| F-10 | Info | KMS | Only the development provider runs. | External dependency |
| F-11 | Info | Fraud / risk | Rule-based only. `hybrid_detector.py` declares `MODEL_VERSION = "rule-heuristic-v1"`, `model_status = "NOT_TRAINED"`. | Documented |
| F-12 | Low | DR tool | The "source unchanged" document count false-alarmed on a live source. | Fixed in code (FIX-5); drill not re-run |
| F-13 | Info | Test environment | A test stack must label its events `SYNTHETIC_TEST`. | Documented |
| F-14 | Medium (operations) | Managed-key reconciliation | Routine key re-syncs wrote 2 audit events every 60 s per ACTIVE key: about 53% of all audit events, about 2,880 per key per day. | Fixed in code (FIX-4); live re-check pending |
| F-15 | Medium (availability) | Managed-key reconciliation | The retry counter was never reset after a successful sync. After about 5 minutes, one transient provider error moved an ACTIVE key to `FAILED`. | Fixed in code (FIX-6) |

## 5. Fixed, not fixed, not done (Q8–Q10)

**Fixed (Q8):** F-01, F-02, F-03 (2026-11-21, re-verified live) and F-14, F-12, F-15 (2026-11-23, unit-tested; full identity suite green).

**Not fixed (Q9):**
- F-06: the two E2E checks were deliberately not edited, so that their meaning is kept. Updating them is a harness change.
- Missing features were not added, as the task required: password reset, selective disclosure, trained ML model.

**Not done, and why (Q10):**

| Item | Why |
|---|---|
| Live re-check of FIX-4/5/6 (idle audit volume, DR drill exit code) | Needs the isolated stack rebuilt with the fixes. Docker was off until the owner started it on 2026-11-23, and this report's task forbids Docker changes. |
| Final real-MongoDB integration run (7 tests) | No saved final log (section 0) |
| Physical phone, public HTTPS, real WebAuthn authenticator, KMS/HSM, blockchain node, OpenID conformance suites, penetration test, legal review | External dependencies (section 10) |
| Rebuilding the owner stack with the fixes | Needs the owner's approval. The owner stack still runs images built before the fixes. |

---

## 6. Files changed by the audit

**Method.**
- `find` listed every repository file modified since 2026-11-21 00:00. Excluded: `node_modules`, `.git`, `.venv`, `__pycache__`, `dist`, blockchain build output, and this `audit/` folder.
- The result was compared with `04_FIXES_IMPLEMENTED.md` and with the rollback snapshot `C:\Users\besna\secure-ssi-audit-rollback-20261121\status-now.txt` (2026-11-21 18:07, taken after FIX-1 to FIX-3).
- The list below is the complete result; no other file changed.

**Limit.**
- The working tree already held uncommitted WP-28 to WP-32 work before the audit (`00`: 233 entries). `git diff --stat` mixes that work with the audit's changes, so its line counts are **not** the size of the audit's changes.
- A line-level diff of FIX-1 to FIX-3 against the pre-audit state is not possible: the first rollback copy (Desktop) was deleted by a process outside the session.
- The fixes were therefore verified directly in the code (file and line below).
- For FIX-4 to FIX-6 the attribution is exact: `managed_key_service.py` and `test_managed_key_service.py` were unmodified in the 21 November snapshot and are modified now.

| File path | Change type | Previous problem | Fix | Related test |
|---|---|---|---|---|
| `services/api-gateway/app/api/routes/proxy.py` | Modified (FIX-1) | Gateway dropped the caller's host | Removes client-supplied `x-forwarded-host/proto` (line 138) and sets them from the caller's `Host` and scheme (lines 145–147) | `services/api-gateway/tests/test_gateway.py` incl. `test_proxy_never_passes_client_forwarded_host_through` (gateway 48 → 50) |
| `services/api-gateway/tests/test_gateway.py` | Modified (tests) | – | +2 FIX-1 tests | gateway 50/0 |
| `services/identity-service/app/api/v1/oid4vp.py` | Modified (FIX-1) | `_origin()` fell back to the internal `request.base_url` | Uses well-formed `x-forwarded-host/proto` when `IDENTITY_PUBLIC_ORIGIN` is empty (lines 61–72); the public origin still wins | `tests/unit/test_audit_forwarded_origin.py` (3), `regression_fix1_origin.log` 7/7 |
| `services/identity-service/tests/unit/test_audit_forwarded_origin.py` | New (tests, 2026-11-21 16:06) | – | 3 FIX-1 tests | identity 1083 → 1086 |
| `docker-compose.yml` | Modified (FIX-2, FIX-3) | F-02, F-03 | Line 241: `RECOVERY_STEP_UP_SECRET` falls back to `IDENTITY_STEP_UP_SECRET`; lines 103 and 222: default URIs use `MONGO_APP_PASSWORD` and `MONGO_RECOVERY_PASSWORD` | Live E2E with recovery secret empty: guardian 24/0, recovery 12/0; `docker compose config` checks (reported in `04`, no saved log) |
| `.env.example` | Modified (comments for FIX-2/3) | Undocumented wiring | Comment lines 21, 88 and 143 explain the fallbacks. The template's other differences are pre-audit WP work. | – |
| `services/identity-service/app/application/services/managed_key_service.py` | Modified (FIX-4, FIX-6; 2026-11-23) | F-14, F-15 | `reconcile(..., routine=False)`; `reconcile_batch` passes `routine=True`; `_ROUTINE_SYNC_STATES`, `_only_sync_bookkeeping_changed`, `_record_reconciliation_claim`; `reconciliation_attempts=0` in the two sync paths | 4 new tests in `test_managed_key_service.py`; identity 1095/0/12 |
| `services/identity-service/tests/unit/test_managed_key_service.py` | Modified (tests) | – | +4 tests: routine sync not audited; state change and failure audited; admin reconcile always audited; successful sync resets the retry streak | 16/16 locally, 1095/0/12 in the container |
| `services/identity-service/app/tools/platform_restore_drill.py` | Modified (FIX-5; file untracked since WP-28/29) | F-12 | `APPEND_ONLY_COLLECTIONS` (`audit_events`, `audit_outbox`); `compare_source()`; new report fields `sourceUnchanged`, `sourceChangedCollections`, `sourceAppendOnlyGrowth`; the exit code uses the new check | `tests/unit/test_platform_restore_drill_source_check.py` (5) |
| `services/identity-service/tests/unit/test_platform_restore_drill_source_check.py` | New (tests) | – | 5 tests | 5/5 |
| `apps/web/tsconfig.app.tsbuildinfo` | Build artifact | – | Written by `npm run build` (`tsc -b`). Not source code; not listed by `git status`. | – |

Files outside the repository: the 37 old web files were moved (not deleted) to `C:\Users\besna\secure-ssi-audit-rollback-20261121\restored-old-web-files\`. Test-harness copies live in `evidence/scripts/`.

**Modules not changed:** web app source, recovery service, fraud service, shared package, contracts. In the identity service only `oid4vp.py`, `managed_key_service.py` and the DR tool changed.

### 6.1 Per fix: cause, reason, behaviour, impact, verification

**FIX-1 (F-01)**

| | |
|---|---|
| Real cause | The gateway removes the `Host` header when proxying. Identity therefore saw only its internal address and built `request_uri` from it. |
| Why this fix | It is the smallest change: the public-origin rule and the phone-reachability guard stay as they are. Client-supplied forwarded headers are dropped first, so they cannot be injected. |
| Behaviour change | Without `IDENTITY_PUBLIC_ORIGIN`, links now use the host the browser called. With it set, the behaviour is unchanged: `final_fix1_check_with_public_origin_set_EXPECTED_public_origin_wins.log` exits 1 *by design*, because the configured origin wins. |
| Affected | Every proxied request now carries the two headers; identity reads them only in `_origin()`. |
| Verified | Gateway 50/0; identity 1086/0/12; live `regression_fix1_origin.log` 7/7. Before the fix, the default-origin E2E ran 128/4 (`initial_e2e_default_origin.log`: internal host in the link). |

**FIX-2 (F-02)**

| | |
|---|---|
| Real cause | One secret was wired as two variables. |
| Why this fix | Compose already uses the same fallback pattern for the JWT and grant secrets. An explicit value still wins. |
| Behaviour change | When unset, recovery uses the identity secret. |
| Affected | Recovery service configuration only. |
| Verified | E2E MFA, guardian and recovery sections with `RECOVERY_STEP_UP_SECRET` empty: `final_e2e.log` mfa 6/0, guardian 24/0, recovery 12/0. Before the fix: `initial_e2e_run2_stepup403.log` aborted with a step-up 403. |

**FIX-3 (F-03)**

| | |
|---|---|
| Real cause | Literal passwords in the default URIs. |
| Why this fix | The same pattern compose already used for the intel database. |
| Behaviour change | A custom DB password now flows into the URIs. With no environment set, the output is identical, so the owner stack is unaffected. |
| Affected | Identity and recovery configuration. |
| Verified | Regression stack started with derived URIs (`regression_up.log`, containers healthy); `docker compose config` comparisons (reported in `04`). |

**FIX-4 (F-14)**

| | |
|---|---|
| Real cause | Every routine sync was audited like a state change. |
| Why this fix | It is the owner's decision (2026-11-23), matching the recommendation in `03`: audit state changes and failures, count routine syncs in the metrics. |
| Behaviour change | A background sync of an ACTIVE, ROTATING or FAILED key that changes only bookkeeping fields (`updatedAt`, `version`, `reconciliationAttempts`, `reconciliationLeaseUntil`, `lastProviderSyncAt`) writes no audit event, but is counted in `key_reconciliation_attempts/succeeded`. These are unchanged: state changes, failures, provider mismatches and administrative reconciliation (always audited); and PENDING and DESTROY_PENDING claims, which are still recorded before the provider call. |
| Known limit | For a routine sync, the claim is written after the provider check. If the process stops in between, that claim is missing from the log; the key itself stays consistent. |
| Affected | Identity background reconciliation, audit-log volume, the outbox, and the security-intelligence feed (less noise). |
| Verified | 4 new tests (3 for F-14). Mutation check: with the fix undone, the F-14 test fails (4 extra audit events). Container suite 1095/0/12. **Not yet verified on the live stack.** |

**FIX-5 (F-12)**

| | |
|---|---|
| Real cause | An exact count comparison on a live source whose audit log grows. |
| Why this fix | The platform only appends to `audit_events` and `audit_outbox` (no delete call, no TTL index found in the code). The drill writes no audit events (`_NoAudit`). A wrong write into the source would still change the exactly compared business collections. |
| Behaviour change | Growth in the two audit collections is reported and accepted. A decrease, a missing collection or any other change fails the drill. The strict flag `sourceFingerprintUnchanged` is kept for information. |
| Affected | DR CLI tool only. |
| Verified | 5 new tests. **DR drill not re-run.** |

**FIX-6 (F-15)**

| | |
|---|---|
| Real cause | `claim_reconciliation` adds 1 to `reconciliationAttempts` on every claim, and a successful sync never reset it. |
| Why this fix | The retry limit should count consecutive failures, as its name says. |
| Behaviour change | A successful sync sets the counter to 0. Consecutive failures still dead-letter the key: the existing test `test_reconciliation_retry_limit_dead_letters_failed_operation` passes. |
| Affected | Managed-key availability under transient provider errors. |
| Verified | New test. Mutation check: on the old code, 5 routine syncs followed by 1 timeout end in `FAILED` / `RETRY_LIMIT_REACHED` with attempts 6. With the fix the key stays ACTIVE with attempts 1. |

---

## 7. Test results: before and after

### 7.1 Suite level

All numbers are taken from the saved logs in `evidence/`. "Before" is 2026-11-21, before any fix. "After" is 2026-11-21, after FIX-1 to FIX-3; the identity suite also has a 2026-11-23 run after FIX-4 to FIX-6.

**Unit and integration suites**

| Suite | Command | Environment | Before (pass / fail / skip) | After (pass / fail / skip) | Errors | Log |
|---|---|---|---|---|---|---|
| API gateway | `pytest -q` | local `.venv` (Python 3.11.16) | 48 / 0 / 0 | **50 / 0 / 0** | 0 | `initial_api-gateway.log`, `final_api-gateway.log` |
| Identity | `pytest -q -rs tests` | container, `--network none`, repo read-only (Python 3.12) | 1083 / 0 / 12 | **1086 / 0 / 12** (11-21); **1095 / 0 / 12** (11-23) | 0 | `initial_identity-service.log`, `final_identity-service.log`, `final_identity-service_20261123.log` |
| Identity real MongoDB repositories | `pytest tests/integration/test_mongo_repositories.py` | container on the audit network | 7 / 0 / 0 | not evidenced (section 0) | – | `initial_identity_mongo_integration.log` |
| Recovery | `pytest -q` | local `.venv` | 131 / 0 / 1 | **131 / 0 / 1** | 0 | `*_recovery-service.log` |
| Fraud | `pytest -q` | local `.venv` | 90 / 0 / 0 | **90 / 0 / 0** | 0 | `*_fraud-service.log` |
| Shared package | `unittest discover packages/shared/tests` | local | 5 OK | **5 OK** | 0 | `*_shared_pkg.log` |
| Root tests | `unittest discover tests` | local | 3 OK | **3 OK** | 0 | `*_root_tests.log` |
| Web unit | `npm test` | Node 24.19.0 | 42 / 0 / 0 | **42 / 0** | 0 | `*_web_unit.log` |
| Web build | `npm run build` | Node 24 | exit 0 | built | – | `*_web_build.log` |
| Web lint | `npm run lint` | Node 24 | no problems reported | no problems reported | – | `*_web_lint.log` |

**Live stages** on the isolated stack `audit-20261121` (harness `evidence/scripts/stage.sh` / `run_noreset.sh`):

| Stage | Before (pass / fail) | After (pass / fail) | Log |
|---|---|---|---|
| E2E (`wp31_e2e.mjs`) | 130 / 2 | **130 / 2** (F-06) | `*_e2e.log` |
| Gaps | 38 / 0 | **38 / 0** | `*_gaps.log` |
| Post | 15 / 0 | **15 / 0** | `*_post.log` |
| Onboarding | 40 / 0 | **40 / 0** | `*_onboarding.log` |
| Scenarios | 41 / 0 | **41 / 0** | `*_scenarios.log` |
| OID4VP security | 16 / 0 | **16 / 0** | `*_oid4vp_security.log` |
| `request_uri` scan | 11 / 0 | **11 / 0** | `*_wp32_scan.log` |
| Wallet card UI | 31 / 0 | **31 / 0** | `*_wp32_card.log` |
| Cross-device (two browsers) | 13 / 0 | **13 / 0** | `*_wp32_cross.log` |
| wp32 UI | 12 / 0 | **12 / 0** | `*_wp32_ui.log` |
| UI (security intelligence) | 25 / 16 | **41 / 0** (F-13 configuration) | `*_ui.log` |
| Browser | 40 / 0 | **40 / 0** | `*_browser.log` |
| Pages | 62 pages, axe 0, console 0, overflow 0 | **same** | `*_pages.log` |
| DR drill | 32 / 0 | **30 / 2** (F-12; fixed in code 11-23, not re-run) | `*_dr.log` |
| FIX-1 live check | – | **7 / 0** | `regression_fix1_origin.log` |

### 7.2 By category

Many categories have no separate suite. Where a stage reports its checks by section, the section counts are given; they were counted from the `PASS [tag]` and `FAIL [tag]` lines of each log. Before and after are identical unless stated otherwise.

| Test category | Before | After | Status | Source |
|---|---:|---:|---|---|
| Frontend Unit | 42 / 0 | 42 / 0 | Pass | web unit; build and lint clean |
| Backend Unit | gw 48, id 1083/12s, rec 131/1s, fraud 90, shared 5, root 3 | gw 50, id 1086/12s (11-21) and 1095/12s (11-23), rec 131/1s, fraud 90, shared 5, root 3 | Pass | section 7.1 |
| API Integration | Mongo repos 7/0; gaps 38/0; post 15/0; onboarding 40/0 | gaps 38/0; post 15/0; onboarding 40/0; Mongo repos not evidenced | Pass (Mongo final missing) | logs above |
| Authentication | E2E mfa 6/0, session 5/0, password 7/0 | same | Pass | `*_e2e.log` |
| Authorization | onboarding roles 7/0, admin 9/0 | same | Pass | `*_onboarding.log`; the E2E IDOR checks have no separate tag |
| Issuer | gaps ISS-04/07 6/0; onboarding issuer 10/0; E2E reissue 12/0, trust 5/0 | same | Pass | – |
| Holder | gaps HOL-05/12 4/0; onboarding holder 7/0; card 31/0 | same | Pass | – |
| Verifier | gaps VER-03/05/07 9/0; onboarding verifier 3/0 | same | Pass | – |
| OpenID4VCI | gaps OFFER 3/0; identity unit (`test_wp05_oid4vci_token_and_proof.py`, `test_oid4_protocols.py`) | same | Pass (platform) | no separate count for the unit files |
| OpenID4VP | 16/0 (replay 1, nonce 2, client_id 1, state 1, expiry 2, consent 2, holder binding 1, DCQL 2, outage 1, revocation 1, positive 2) | 16/0 | Pass | `*_oid4vp_security.log` |
| QR / Request URI | E2E qr 9/2; scan 11/0; cross 13/0 (default-origin run: E2E 128/4) | E2E qr 9/2 (F-06); scan 11/0; cross 13/0; FIX-1 7/0 | Pass except F-06 | – |
| Wallet | E2E wallet 9/0; card 31/0 | same | Pass | – |
| Backup & Restore (wallet) | inside E2E wallet section; web crypto tests in web unit | same | Pass | – |
| Guardian Recovery | E2E guardian 24/0, recovery 12/0; recovery unit 131/1s | same | Pass (F-02 fixed) | – |
| Platform DR | 32/0 | 30/2; 11-23: FIX-5 unit 5/0 | Open until the drill is re-run | `*_dr.log` |
| KMS | E2E keys 6/0 | E2E keys 6/0; 11-23: `test_managed_key_service.py` 16/16 | Pass (development provider only) | – |
| Fraud / Risk | fraud 90; E2E risk 6/0; scenarios 41/0; UI 25/16 | fraud 90; risk 6/0; scenarios 41/0; UI 41/0 | Pass (rule-based) | – |
| Admin | onboarding admin 9/0; gaps ADM-03/06 7/0; pages 62 | same | Pass | – |
| E2E | 130 / 2 | 130 / 2 | Pass except F-06 | `*_e2e.log` |
| Browser | 40/0; pages 62; wp32 UI 12/0 | same | Pass | – |
| Security | OID4VP security 16/0; gaps AUDIT-CHAIN 4/0; E2E ledger 28/0 | same | Pass | `07` |

No failing test was turned into a skip. The 12 identity skips are the same before and after: 5 tests need a Hardhat node on port 8545; 7 need `IDENTITY_TEST_MONGODB_URI`.

### 7.3 Runs that failed for environmental or ordering reasons

These logs are kept and are not counted as results.

| Log | Outcome | Reason |
|---|---|---|
| `initial_e2e_default_origin.log` | 128 / 4 | F-01, before the fix |
| `initial_e2e_run2_stepup403.log` | Aborted after 41 passed | F-02 (step-up 403) |
| `initial_dr_run1_onedrive_build.log` | Exit 1 | A OneDrive online-only file broke the Docker build |
| `initial_wp32_cross_run1_stall.log` | Stalled after 9 checks | Test timing |
| `initial_ui_run1_no_synthetic_data.log` / `initial_ui_run2_scenarios_503.log` | 25 / 16, 23 / 18 | Wrong order; F-13 configuration |
| `initial_wp32_ui_run1_admin_already_enrolled.log` | 6 / 1 | Order |
| `initial_scenarios_run2_503.log` | Node crash (exit 127) | – |
| `final_post_after_machine_sleep.log` | Exit 1 after 12,337 s | The machine slept for about 3.4 h |
| `final_web_build_with_restored_old_files.log` / `final_web_lint_with_restored_old_files.log` | TypeScript errors; 84 lint problems | 37 old files had reappeared in `apps/web/src`; both green after they were moved out |
| `final_dr_after_machine_sleep.log` | 30 / 2 | Same F-12 false alarm |

---

## 8. Module status

| Module | Real current state | Working features | Fixed | Remaining gaps | Evidence |
|---|---|---|---|---|---|
| Authentication | Verified | Argon2id, JWT, server-side revocation, gateway cookie session, CSRF | – | No password reset; per-account lockout or sign-in risk step-up not found (gateway has a per-IP rate limit) | E2E mfa/session/password; gateway 50 |
| Authorization / RBAC / IDOR | Verified | Roles, per-permission checks, IDOR refusals | – | – | onboarding roles/admin; E2E |
| Onboarding | Verified | Registration, applications, invitations | – | – | onboarding 40/0 |
| MFA and step-up | Verified | TOTP, action/resource-bound step-up, replay counter | F-02 | – | E2E mfa 6/0, guardian 24/0 |
| WebAuthn | Partially verified | Registration and step-up (`webauthn` 3.0.1) | – | Virtual authenticator only | browser stage; identity tests |
| Dual control | Verified | Two-person approval, single-use token | – | Off in development mode by default | DR drill |
| Issuer (VC 2.0, `eddsa-jcs-2022`) | Verified | Real Ed25519 Data Integrity proofs; 15 tamper variants refused | – | Selective disclosure not available | identity crypto tests; E2E |
| OpenID4VCI | Verified (platform) | Pre-authorized code, `tx_code` attempt limit, proof, `c_nonce` | – | No OpenID conformance run | gaps OFFER; identity tests |
| Status / revocation / ledger | Verified (ledger when configured) | Bitstring status list, revoke/suspend; ledger MAC chain and rollback anchor | – | Ledger off by default | E2E ledger 28/0 |
| Holder wallet and card UI | Verified | Live issuer status and trust; Present, Attributes, Details | – | – | card 31/0 |
| Verifier / OpenID4VP | Verified (platform) | DCQL, JAR with `did:jwk` client_id, `request_uri`, 8 fail-closed checks | – | No conformance run | OID4VP security 16/0 |
| QR / `request_uri` | Verified on **simulated** devices | Opaque handle or `request_uri`; SSRF-safe fetch | F-01 | Physical phone and public HTTPS not tested | scan 11/0, cross 13/0, FIX-1 7/0 |
| Wallet backup and restore | Verified | Client-side Argon2id + AES-GCM; preview; step-up for restore | – | – | E2E wallet 9/0; web tests |
| Guardian recovery | Verified | M-of-N, invitations bound to device keys, signed decisions, time lock, owner cancel; all sessions revoked after recovery | F-02 | Starts only from a signed-in account; revoking WebAuthn authenticators not found in the recovery path | E2E guardian 24/0, recovery 12/0; recovery 131 |
| Platform backup and DR | Verified in an isolated drill (32/0) | Encrypted archive, verify, dual-control restore into a separate database; RTO about 45 s on test data | F-12 (code) | Drill not re-run after FIX-5; off-site and PITR `NOT_CONFIGURED` | `*_dr.log`; `readiness_service.py` |
| KMS / managed keys | Partially verified | Development provider; reconciliation; rotation | F-14, F-15 (code) | No external KMS/HSM; live re-check pending | E2E keys 6/0; unit 16/16 |
| Audit log | Verified | Hash chain; tampering detected | F-14 noise (code) | Tamper-evident, not WORM (`TAMPER_EVIDENT_NOT_WORM`) | gaps AUDIT-CHAIN 4/0 |
| Fraud / risk | Verified as **rule-based** | `rule-heuristic-v1`, thresholds 0.25/0.50/0.75/0.80; advisory only, cannot override a failed check | – | No trained model (`NOT_TRAINED`) | fraud 90; E2E risk 6/0 |
| Security intelligence | Verified | Rules, median/MAD anomalies, incidents, synthetic/operational separation | – | – | scenarios 41/0; UI 41/0 |
| Blockchain anchoring | Present, untested live | Contracts, bridge, API | – | No chain node; 5 tests skipped | identity skips |
| Admin and other UI | Verified | 36 routes with real API data | – | – | pages 62, browser 40/0 |

### 8.1 Identity and credentials

The full issuer → holder → verifier chain works on the platform:
- VC 2.0 credentials carry real Ed25519 proofs and are issued over OID4VCI. Tampered credentials are refused.
- Presentations use OID4VP with DCQL, signed request objects and holder binding.

"Verified" here means verified on this platform with its own tests. No OpenID Foundation conformance suite was run, and no other wallet or verifier was tested against it.

### 8.2 Cross-device presentation

| Element | Status | Evidence |
|---|---|---|
| QR content | Only an opaque handle or a `request_uri` link | `request_uri` scan stage |
| Nonce | Fresh per request; reuse refused | OID4VP security: nonce 2/0 |
| Client ID | `did:jwk` in a signed request object | OID4VP security: client_id 1/0 |
| Replay protection | Replay refused; a second consent on the same QR refused | replay 1/0; cross-device |
| Holder consent | Required server-side; deny works | consent 2/0 |
| Session binding / proximity | **Not implemented**: the P4 class of attacks (relaying a legitimate QR) is not mitigated beyond the user's consent screen | 09 J.3; no `proximity` in the code |
| Real devices | **Not tested**: two isolated browsers and a QR decoded from the real canvas with jsQR; not a phone | cross 13/0 |

### 8.3 Wallet and recovery

- Wallet backup and restore works, including a wrong password and a restore without step-up, both refused.
- Guardian recovery enforces M-of-N, the time lock and owner cancel.
- Completion revokes every session of the owner (`revoke_subject`, reason `guardian_recovery_completed`) and rotates the wallet key.
- Old devices: sessions are revoked. Revoking registered WebAuthn authenticators was not found in the recovery path.
- Recovery can be started only from a signed-in account. This is a documented limit.

### 8.4 Platform security

- **Authentication and authorization:** verified (section 8).
- **KMS:** development provider only.
- **Audit log:** hash-chained and tamper-evident; F-14 noise fixed in code.
- **Platform backup and DR:** restore verified in isolation; off-site storage and PITR not configured.
- **Fraud and risk:** rule-based only, advisory.
- **Blockchain anchoring:** off by default; not run live.

---

## 9. Security status

| Security finding | Severity | Affected module | Before | After | Evidence |
|---|---|---|---|---|---|
| Internal hostname in the QR / `request_uri` (unreachable link, leaks the service name) | High | OID4VP, gateway | Present in the default configuration | Fixed; live 7/7 | `initial_e2e_default_origin.log`, `regression_fix1_origin.log` |
| Mismatched step-up secrets: guardian and recovery actions return 403 (availability, not a bypass) | Medium | Recovery | Present | Fixed | `initial_e2e_run2_stepup403.log`, `final_e2e.log` |
| DB password change: identity does not start | Low | Deployment | Present | Fixed | `04` |
| Audit log flooded by routine key syncs (could bury real events) | Medium (operations) | KMS / audit | Present | Fixed in code; live pending | `03` measurement; new tests |
| One transient provider error fails an ACTIVE key | Medium (availability) | KMS | Present | Fixed in code | new test; mutation check |
| DR false alarm | Low | DR tool | Present | Fixed in code; drill pending | `final_dr.log` 30/2; new tests |

**Not found by the suites:** authentication bypass, IDOR, injection, signature-verification bypass, replay (`07`).

### 9.1 Hardening to investigate

These are not vulnerabilities found by the suites. They are gaps relevant to the next phase.

| Area | Observation | Evidence |
|---|---|---|
| Sign-in | `/auth/token` describes itself as a local-development endpoint "with no rate limiting". The gateway applies a per-IP sliding window (`RateLimiterMiddleware`). No per-account lockout and no risk-based step-up at sign-in were found. | `identity-service/app/api/v1/auth.py` line 82; `api-gateway/app/core/middleware.py` line 67 |
| Presentation | Consent needs no step-up: there is no step-up reference in the OID4VP or presentation services. | `grep` of `oid4vp.py`, `oid4vp_service.py`, `presentation_service.py` |
| QR relay | No session binding or proximity check. | section 8.2 |
| Recovery | WebAuthn authenticators are not revoked on completion (sessions are). | `internal/recovery.py` |
| Backups | Off-site `NOT_CONFIGURED`, PITR `NOT_CONFIGURED`; the audit store is `TAMPER_EVIDENT_NOT_WORM`. | `readiness_service.py` lines 75, 103, 108 |
| Defaults | Development secrets must be replaced in any real deployment. Step-up and dual control are off in development mode (F-04). | `.env.example`, `07` |

### 9.2 By area

| Area | Result |
|---|---|
| Authentication | Pass |
| Authorization | Pass |
| Credential signatures | Pass (15 tamper variants) |
| Replay | Pass |
| QR | Pass on simulated devices; P4 open (section 8.2) |
| Session management | Pass (gateway tests, server-side revocation) |
| Recovery | Pass (F-02 was a false denial) |
| Key storage | Development provider only, keys never leave the service |
| Sensitive data | No secrets in logs or errors (F-01 leak fixed) |
| Audit integrity | Pass (tamper detected) |
| Backup | Encryption and integrity pass |

**No production security guarantee is given.** Not covered: an independent penetration test, a real KMS/HSM, a physical phone on public HTTPS, a live chain, OpenID conformance, load testing, and a legal (KVKK) review.

---

## 10. External dependencies and limited tests

| Operation | Why it could not be completed | Required condition | Current state |
|---|---|---|---|
| Real KMS/HSM | No account or service | KMS/HSM endpoint and credentials | Generic remote KMS client exists; development provider used |
| Real Android phones with QR | Needs a public HTTPS origin reachable by a phone | Public origin (`IDENTITY_PUBLIC_ORIGIN`), phones | Flow complete; tested with two browsers and jsQR (13/13). TÜBİTAK budget: 2 cloud servers and a domain |
| Real WebAuthn authenticator | No hardware | Security keys or a phone passkey | Implemented; virtual authenticator only. TÜBİTAK budget: 2 FIDO2 keys |
| External HTTPS server | Not available | Domain or tunnel and a certificate | Not available |
| Off-site / WORM backup | Not configured | Object store with retention lock | `OffsiteBackupStore` interface exists; readiness reports `BACKUP_OFFSITE_NOT_CONFIGURED`; audit `TAMPER_EVIDENT_NOT_WORM` |
| PITR | Not configured | Replica set and oplog-based backups | Readiness reports `BACKUP_PITR_NOT_CONFIGURED` |
| Independent penetration test | External party | Contract | Not done |
| OpenID interoperability | Needs the conformance suite and a public endpoint | OIDF suite access | Platform tests only |
| Real issuer DID | `did:web` network resolution off by default; issuers use locally generated DIDs | A domain serving `did.json` | Not done |
| Blockchain node | Not running | Hardhat on 8545 or a testnet | 5 tests skipped |
| Labelled real security data | Not available | Published data set | Planned D2 (Wiefling et al. data set) |
| Legal review (KVKK) | External | Lawyer or DPO | Not done |

---

## 11. Remaining issues

1. Live re-check of FIX-4/5/6:
   - the idle audit volume must stop growing from key syncs;
   - the DR drill must exit 0.
2. F-06: the two outdated E2E QR checks need a harness update.
3. The final real-MongoDB integration run (7 tests) has no log.
4. The six fixes are uncommitted, and the owner stack runs images built before them.
5. Not implemented, outside the audit's scope: password reset, selective disclosure, trained ML model, sign-in risk step-up, presentation step-up, QR session binding and proximity check, revoking WebAuthn authenticators on recovery, off-site/WORM backups and PITR.
6. External items: section 10.

---

## 12. MongoDB, Docker and Git

| Question | Answer | Evidence |
|---|---|---|
| MongoDB data kept? | **Yes.** The owner database was never targeted. The isolated audit databases were emptied between stages by `reset_audit.sh`; they held synthetic data only, and this was by design. | `00`; `docker volume ls` (2026-11-23): `secure-ssi-platform_mongodb_data` present |
| Docker volumes kept? | **Yes.** No `down -v`, no `volume rm`, no prune. 5 owner volumes and 21 audit volumes are present. | `docker volume ls` (2026-11-23) |
| Environment files changed? | **The real `.env`: no.** There is no `.env` in the repository root; it is git-ignored and compose uses its defaults. The audit's random secrets lived in a separate file in the session scratch folder. **The template `.env.example`: yes, comments only** (lines 21, 88, 143). | `ls .env`; `git check-ignore .env`; section 6 |
| User data affected? | **No.** Only synthetic accounts (`*@wp31.test` and fixture users) on isolated stacks. | `00` |
| Git changes? | **Working-tree changes only**, all uncommitted. 233 entries at the start (130 modified, 102 untracked, 1 deleted); 240 now (134 / 105 / 1). | `git status --porcelain` |
| Commit or push? | **None.** HEAD is still `9fa97d7` (2026-11-03); 0 commits since 2026-11-20; branch `besna-dev` unchanged. | `git log` |
| Test environment separate? | **Yes.** Compose projects `audit-20261121` and `-dr`…`-dr4`, ports 29300–29383 on 127.0.0.1, own volumes, random secrets. Identity unit tests ran in network-less containers with the repository mounted read-only. | `00`, `README.md` |

**Docker now (read-only check, 2026-11-23).** The owner stack is up and healthy: 7 containers, restarted by Docker's restart policy when the owner started Docker. The audit containers are stopped and their volumes kept.

**Incidents, none caused by the audit:**
- During the audit, a process outside the session deleted the Desktop rollback folder.
- 37 old web files reappeared in `apps/web/src`. They were moved, not deleted, with the owner's approval.
- A machine sleep of about 3.4 h invalidated one post run.
- A OneDrive online-only file broke one Docker build.
- Smart App Control blocks a native module locally.

---

## 13. Next phase: mapping to the D1–D5 research plan

Decision keys:

| Key | Meaning |
|---|---|
| G | Gerekli (needed) |
| M | Mevcut sistemde zaten bulunuyor (already exists) |
| Ö | Önce mevcut işlev düzeltilmeli (fix the existing function first) |
| K | Araştırma için gerekli ancak kapsamı daraltılmalı (needed, narrow the scope) |
| Ç | TÜBİTAK kapsamından çıkarılmalı (remove from scope) |
| H | Harici bağımlılığa bağlı (external dependency) |

| Research area | Planned feature | State in the current system | Decision | Priority |
|---|---|---|---|---|
| D1-A | Account-takeover experiments A1–A6 | The attack-side controls exist: gateway per-IP rate limit, TOTP/WebAuthn step-up for sensitive actions, guardian recovery with time lock, notifications and cancel, session revocation after recovery. Missing:<br>• the experiment harness with on/off controls and a database snapshot per block;<br>• password reset (A3, does not exist);<br>• risk step-up at sign-in (A1/A2);<br>• step-up before a presentation (A2);<br>• authenticator revocation after recovery (A6, partial). | G (harness and missing controls, in the isolated test configuration only) | High (İP1–İP3) |
| D1-P | QR / presentation experiments P1–P8 | P1, P2, P3, P5, P6, P7 and P8 controls exist and pass (OID4VP security 16/0). P4 (QR relay): no session binding or proximity check. No on/off switches. | M for P1–P3, P5–P8; G for P4 and the switches | High (İP2–İP3) |
| D2 | Wiefling data set and RBA (M0) | Not present (no data loader, no RBA model) | G (offline analysis package, not in the production services) | High (İP4) |
| D2 | M0–M4 model evaluation | Not present. `scikit-learn` 1.9.1 and `pandas` 3.1.0 are in the fraud service; no `xgboost` dependency. | G (offline; adding XGBoost is a dependency decision) | High (İP4) |
| D3 | Synthetic event generator | `fraud-service/app/ml/synthetic_dataset.py` exists: an explicitly labelled generator with a fixed fraud ratio. It has no hidden/observable layer split, overlap profiles, triviality test or blind set. | K (new generator to the D3 design; the existing one is not suitable as is) | High (İP2) |
| D3 | Blind test set and leakage controls | Not present | G | High (İP2–İP4) |
| D4 | Hybrid risk policy | `HybridFraudDetector` exists: `rule-heuristic-v1`, not trained, advisory. D4 needs an ML ceiling at HIGH, CRITICAL only from hard-evidence rules, and an appeal path. | Ö / K (adapt the existing module, do not rebuild it) | Medium (İP5) |
| D4 | Four-level risk management | Thresholds exist (0.25/0.50/0.75/0.80, ending in quarantine). There is no mapping to actions at sign-in or presentation (WebAuthn at MEDIUM, hold at HIGH, block at CRITICAL). | G | Medium (İP5) |
| D4 | Real WebAuthn verification | Implemented (`webauthn` 3.0.1); tested with a virtual authenticator only | H (2 FIDO2 keys in the budget) | Medium (İP3/İP5) |
| D5 | Real mobile QR experiments | QR flow complete; simulated only | H (public HTTPS: 2 cloud servers and a domain in the budget) | Medium (İP3/İP5) |
| D5 | Performance measurement | No measurement harness. Only DR timings measured once (backup 272 ms, restore 7.0 s, boot 46 s). | G (measurement scripts; no product change needed) | Medium (İP5) |
| İP6 | Statistics and reproducible test package | Not present: no McNemar, Holm, Clopper-Pearson or bootstrap code | G | Medium (İP6) |

**Consistency with the TÜBİTAK proposal.** The proposal (section 1.1) lists these prototype limits:
- the risk module is not a trained model;
- no risk step-up at sign-in;
- no password reset;
- recovery only from a signed-in account;
- WebAuthn only with a virtual authenticator;
- no real-phone QR test;
- no independent audit.

Each limit matches what this audit found in the code and the tests.

---

## 14. Overall assessment

**Status.** The audit of the existing system is complete:
- inventory from code;
- initial and final test runs with saved logs;
- 15 findings, of which 6 were fixed;
- security review and external dependencies documented.

The platform is a reliable, well-tested academic prototype and a sound base for the TÜBİTAK 2209-A experiments. It is **not production-ready**.

**Close these before new development starts:**

1. Re-run the isolated stack with FIX-4/5/6. Confirm that the idle audit volume stays flat and that the DR drill exits 0 (32/32 expected).
2. Update the two outdated E2E QR checks (F-06), so that the regression baseline is fully green before experiment code is added.
3. The owner decides how to commit the six fixes (one reviewed commit or separate commits) and whether to rebuild the owner stack.
4. Record a final real-MongoDB integration run (7 tests) for a complete baseline.

**Not blocking, external:** physical phones, public HTTPS, hardware security keys, KMS/HSM, OpenID conformance and a penetration test. The first three are covered by the TÜBİTAK budget.
