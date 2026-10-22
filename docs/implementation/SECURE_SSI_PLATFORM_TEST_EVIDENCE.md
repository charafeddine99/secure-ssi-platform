# Secure SSI Platform — Test Evidence Register

**Checkpoint:** 15 October 2026 · **Branch/HEAD:** `main` / `59e8933f6e47922ba5a82cb7c9d76632e7edefe1`
**Important:** The working tree is modified. Results below are labeled current, historical, static-only, or blocked so that old green runs are not mistaken for verification of later changes.

## Latest current-source evidence — 15 October 2026

All commands below ran against the dirty working tree at the HEAD above. Python/HTTP commands used the already-installed `.venv` and an isolated Docker Compose project. Elevated process permission was needed because the Windows sandbox denied local asyncio/socket operations; no Windows security setting was changed.

| ID | Exact command / working directory | Result | Scope and limit |
|---|---|---|---|
| NOW-WP08 | CWD `services/identity-service`: `& 'C:\Users\besna\OneDrive\Bureau\secure-ssi-platform\.venv\Scripts\python.exe' -m pytest -q -rs tests/integration/test_wp08_remediation_status_security.py tests/integration/test_wp08_policy_evaluation.py tests/integration/test_issuance_interoperability.py` | Exit 0; **48 passed, 0 failed, 0 skipped**, 2 warnings, 87.02 s. | Current R1–R3/status/policy/issuance focus. The earlier 44/4 result was from fixtures that relied on implicit credential-type broadening; the tests now explicitly request the credential they present. |
| NOW-G7 | CWD `services/identity-service`: `& 'C:\Users\besna\OneDrive\Bureau\secure-ssi-platform\.venv\Scripts\python.exe' -m pytest -q -rs tests/integration/test_wp07_wallet_consent_presentation_proof.py tests/integration/test_wp07_legacy_oid4vp_routes.py tests/integration/test_wp02_holder_binding_verification.py tests/integration/test_auth_api.py tests/integration/test_consent_and_privacy.py` | Exit 0; **80 passed, 0 failed, 0 skipped**, 2 warnings, 50.35 s. | Current wallet-bound consent, holder-binding, retired routes, authentication/logout and privacy regression. |
| NOW-ID-01 | CWD `services/identity-service`: `$env:IDENTITY_TEST_MONGODB_URI='mongodb://prototype:change-me@127.0.0.1:37017/admin?authSource=admin'; & 'C:\Users\besna\OneDrive\Bureau\secure-ssi-platform\.venv\Scripts\python.exe' -m pytest -q -rs` | Exit 0; **686 passed, 0 failed, 5 skipped**, 3 warnings, 210.55 s. | Full Identity Service regression. All five skips require a local Hardhat node on port 8545; Mongo tests ran against the isolated validation MongoDB. |
| NOW-MONGO-01 | CWD `services/identity-service`: `$env:IDENTITY_TEST_MONGODB_URI='mongodb://prototype:change-me@127.0.0.1:37017/admin?authSource=admin'; & 'C:\Users\besna\OneDrive\Bureau\secure-ssi-platform\.venv\Scripts\python.exe' -m pytest -q -rs -p no:cacheprovider tests/integration/test_mongo_repositories.py` | Exit 0; **7 passed, 0 failed, 0 skipped**, 1 deprecation warning, 0.84 s. | Real MongoDB indexes, repositories, status, audit, wallet, presentation, and managed-key operations; test fixture drops its uniquely named temporary database. |
| NOW-FE-01 | Repo root: `node --experimental-strip-types apps/web/tests/verifyPresentation_fail_closed.test.ts` | Exit 0; **8 checks passed**. | Frontend result normalization and fail-closed policy boundary. |
| NOW-DC-01 | Repo root: `docker compose -p secure-ssi-platform config --quiet` | Exit 0. | Compose syntax/configuration check; no container state changed. |
| NOW-DC-02 | Repo root: `docker compose -p wp08-validation-20261015 build --pull=false` | Exit 0; all five application images built from current source. Container build ran web lint and TypeScript/Vite production build (1,826 modules). | Docker Desktop 29.8.1; no host packages were installed. |
| NOW-DC-03 | Repo root: `docker compose -p wp08-validation-20261015 up --detach --no-build --wait --wait-timeout 180` | Initial attempt failed because host port 8002 was already allocated. | No unrelated container was inspected or changed. A subsequent stdin-only Compose override remapped this isolated project's ports to loopback ports 13000, 16379, 18000–18003 and 37017; no repository file was created for the override. |
| NOW-DC-04 | Repo root: `docker compose -p wp08-validation-20261015 -f docker-compose.yml -f - up --detach --no-build --wait --wait-timeout 180` with stdin `!override` loopback port mappings | Exit 0; all **7/7** Compose services healthy. `docker compose -p wp08-validation-20261015 ps --all` confirmed health after the Mongo restart below. | Isolated project/network/volumes; stack is left running for local inspection. Mongo/Redis state is not shared with another Compose project. |
| NOW-HTTP-01 | Repo root: GET `/` on `127.0.0.1:13000`; GET `/health` on `127.0.0.1:18000`, `:18001`, `:18002`, and `:18003` | **Web, Gateway, Identity, Fraud, Recovery: HTTP 200**. Repeated after Mongo restart; all remained 200. | Read-only smoke checks; do not prove a browser user journey. |
| NOW-MONGO-02 | Isolated Mongo database `wp08_persistence_validation_20261015`: insert marker `_id=restart-check`, `docker compose -p wp08-validation-20261015 restart mongodb`, read same marker, then drop only this temporary database | Marker survived the container restart; temporary database was dropped. | Verifies the Compose volume retains data across a Mongo container restart; not a production backup/restore test. |
| NOW-GIT-01 | Repo root: `git diff --check`; `git status --short`; `git diff --cached --name-only` | `git diff --check` exit 0 (line-ending notices only); 149 status entries (132 tracked modified, 17 untracked); 0 staged paths. | Confirms worktree remained unstaged; no commit or push. |

The initial host-port collision does not invalidate the passing isolated-port check. WP-08 has current R1/R2/R3 API evidence plus full Identity regression, Mongo repository tests, current-source Compose health, and Mongo restart persistence. This does not establish L4 interoperability, public-chain behavior, suspension restoration, or browser E2E.

## G11/G12 continuation — 15 October 2026

The browser flow used only synthetic local prototype data. The local UI parsed the project's inline OID4VP request, loaded the persisted verifier session and DCQL match, displayed all four claims as included in the complete signed credential, recorded holder consent, and created the holder-bound signed presentation. The user-visible state then showed `Failed to fetch` during Direct Post.

| Command / observation | Result | Scope and limit |
|---|---|---|
| CWD repo root: `docker compose --project-name wp08-validation-20261015 --file docker-compose.yml exec -T identity-service python -m pytest -q tests/integration/test_wp07_wallet_consent_presentation_proof.py::test_wallet_bound_golden_path_uses_complete_signed_credential` | Exit 0; **1 passed, 0 failed, 0 skipped**, 2 deprecation warnings, 0.43 s. | Existing backend wallet-bound consent → signed VP → Direct Post path. TestClient/in-process data; not browser E2E or Mongo restart evidence. |
| CWD repo root: `node --experimental-strip-types apps/web/tests/oid4vpSubmissionError_contract.test.ts` | Exit 0; **7 assertions passed**. | Checks stage-specific network error copy and preserves authoritative server errors; does not mount React or exercise the retry button. |
| CWD `apps/web`: `npx eslint src/pages/holder/PresentationConsentPage.tsx src/utils/oid4vpSubmissionError.ts` | Exit 0; no diagnostics. | Only the changed component/helper; not a repository-wide lint run. |
| CWD `apps/web`: `$env:VITE_API_BASE_URL='http://127.0.0.1:18000'; npm run build -- --configLoader runner` | Exit 0; TypeScript passed and Vite transformed **1,828 modules**. | Production bundle; does not prove runtime UI behavior or accessibility. |
| Read-only CORS preflight from the project's Gateway container to `/api/v1/oid4vp/response`, with `Origin` set to `http://127.0.0.1:5173` and `http://localhost:5173`, `Access-Control-Request-Method: POST`, and request header `content-type` | Both responses were **200** and returned the matching `Access-Control-Allow-Origin`, POST in allowed methods, and `content-type` in allowed headers. | Confirms server CORS configuration for these two origins; does not prove why the browser did not send the actual POST. |
| Sanitized logs for only `api-gateway` and `identity-service` in project `wp08-validation-20261015` after the browser submit | Gateway logged consent and wallet-presentation POSTs as 200, then `OPTIONS /api/v1/oid4vp/response` as 200. No corresponding Direct Post `POST` appeared. | Browser failure occurred before a request reached the Gateway POST handler. Root cause is unresolved; no verifier result was accepted. |
| Read-only local browser GET to `http://127.0.0.1:18000/health` | Gateway returned `{"service":"api-gateway","status":"healthy","version":"0.1.0"}`. | Confirms this browser context can reach the local Gateway; not a POST or full flow. |
| Reload test at `http://127.0.0.1:5173/wallet/consent` | Temporary `nginx:1.27-alpine` static server returned **404 Not Found**. | This disposable server uses the default nginx config; it is not the repository Compose web service. The actual Compose app's `/login` route loaded, but the revised component/retry UI was not verified after rebuild. |

The consent UI now keeps a successfully created VP token only in component memory if Direct Post fails, exposes a retry that reuses that same prepared presentation, blocks re-creating consent/presentation after any earlier-stage error, and marks result/error banners with `status`/`alert` roles. The error banner and consent action row wrap at narrow widths. It does not persist VP material to browser storage. The new helper and production build passed, but the retry control has not been exercised in the browser. The in-app browser ignored a requested 375×812 viewport and remained 1280×720; no mobile breakpoint result is claimed.

**G11 remains PARTIAL.** The backend Golden Path passed 1/1 and the browser reached consent and VP creation, but no browser Direct Post reached the Gateway, no final verifier result was observed, and this flow has no complete Mongo-backed audit/restart trace. CORS preflight was verified and is not accepted as a substitute for POST. **G12 remains PARTIAL:** the focused UI error handling/build passed, but responsive, visual, keyboard/screen-reader, contrast, and revised-browser checks are still open. Current tally: **5 PASS, 11 PARTIAL, 1 BLOCKED, 0 FAIL**; G14 remains BLOCKED.

## G12 visible keyboard focus — 15 October 2026

Added a global `:focus-visible` outline so keyboard focus remains visible on the consent UI and other web controls, including elements whose inline styles set `outline: none`. The rule uses a 3 px amber outline with 3 px offset. This is a code-level improvement only; no WCAG conformance claim is made without browser and assistive-technology review.

| Command / observation | Result | Scope and limit |
|---|---|---|
| Repo root: `npm run lint --prefix apps/web` | Exit 0; ESLint completed without diagnostics. | Full Web source lint, not a visual/accessibility audit. |
| Repo root: `npm run build --prefix apps/web -- --configLoader runner` | Exit 0; TypeScript passed and Vite transformed 1,828 modules. | Production build; does not verify the focus ring in an actual browser or keyboard/screen-reader operation. |
| Normal-sandbox `docker compose ps --format json` and `docker info --format '{{.ServerVersion}}'` | Both were blocked with `permission denied` connecting to `npipe:////./pipe/dockerDesktopLinuxEngine`. |

## Read-only local Compose status — 15 October 2026

The Docker API denial above was caused by the normal command sandbox boundary: the same read-only status checks succeeded with the already-authorized local test permission. Docker Desktop reports version 29.8.1. Project `wp08-validation-20261015` already had all seven services running and healthy; no container was started, stopped, or recreated during this status check.

| Exact command / observation | Result | Scope and limit |
|---|---|---|
| Repo root: `docker info --format '{{.ServerVersion}}'` | Exit 0; `29.8.1`. | Read-only daemon version. |
| Repo root: `docker compose --project-name wp08-validation-20261015 --file docker-compose.yml ps --format json` | Exit 0; api-gateway, fraud-service, identity-service, mongodb, recovery-service, redis, and web all running/healthy (7/7). Published project ports are loopback-only: 13000, 16379, 18000–18003, and 37017. | Inspected this project's Compose status only. |
| Read-only GETs: `http://127.0.0.1:13000/`, `http://127.0.0.1:18000/health`, `:18001/health`, `:18002/health`, `:18003/health` | Web, Gateway, Identity, Fraud, and Recovery each returned HTTP 200. | Health/reachability only; no authenticated browser flow, Direct Post, or UI accessibility result. |

The browser's previously displayed login error is not evidence that Identity is down: its current health endpoint returns 200. The Direct Post POST and full browser/Mongo restart trace remain unverified.

G12 remains **PARTIAL**. The revised error/retry UI and focus rule compile and lint, but their rendered behavior, responsive layout, contrast, keyboard operation, screen-reader announcements, and revoked/expired/empty/success states still need review. Current tally remains **5 PASS, 11 PARTIAL, 1 BLOCKED, 0 FAIL**; G14 remains BLOCKED.

## G8 Recovery continuation — 15 October 2026

All commands used the existing Python 3.11 `.venv`; the Windows sandbox denied the local socket-pair operation used by AnyIO/Starlette `TestClient`, so TestClient-backed pytest commands were rerun with local process permissions. No packages were installed.

| Command / working directory | Result | Scope and limit |
|---|---|---|
| CWD `services/recovery-service`: `& 'C:\Users\besna\OneDrive\Bureau\secure-ssi-platform\.venv\Scripts\python.exe' -m pytest -q -rs tests/unit tests/integration` | Exit 0; **45 passed, 1 skipped**, 1 Starlette/httpx deprecation warning, 1.16 s. | The live-Mongo test skips without `RECOVERY_TEST_MONGODB_URI`; its separate run is below. Unit/API, quorum, invalid/tampered/context-mismatched Guardian proof, cancellation/rejection, parallel decisions, state transitions, audit, and in-memory rotation paths. |
| CWD `services/recovery-service`: `$env:RECOVERY_TEST_MONGODB_URI='mongodb://prototype:change-me@127.0.0.1:37017/admin?authSource=admin'; & 'C:\Users\besna\OneDrive\Bureau\secure-ssi-platform\.venv\Scripts\python.exe' -m pytest -q -rs tests/integration/test_mongo_repository.py -k live_mongo_recovery_decision_and_rotation_survive_repository_restart` | Initial sandbox run failed before test setup with Windows `WinError 10013` on `127.0.0.1:37017`; elevated rerun exit 0, **1 passed, 2 deselected**, 0.68 s. | Uses an isolated random database, three separate Mongo clients, and drops the temporary database. Proves quorum and proof digest persistence, time-lock deadline persistence, and successful successor-DID recovery after repository/client restart. Identity key provider is represented by the Recovery test gateway; this is not a live cross-service Mongo rotation test. |
| CWD `services/identity-service`: `& 'C:\Users\besna\OneDrive\Bureau\secure-ssi-platform\.venv\Scripts\python.exe' -m pytest -q -rs tests/integration/test_wp05_oid4vci_token_and_proof.py` | Exit 0; **19 passed**, 2 deprecation warnings, 3.27 s. | Includes Guardian proof signing by an authenticated account's managed `did:key`, signature/claim validation, and foreign-wallet denial. Does not establish an independent device-held key. |
| CWD `services/identity-service`: `& 'C:\Users\besna\OneDrive\Bureau\secure-ssi-platform\.venv\Scripts\python.exe' -m pytest -q -rs tests/integration/test_recovery_internal_api.py tests/unit/test_recovery_grant_and_managed_key.py` | Exit 0; **6 passed**, 2 deprecation warnings, 0.40 s. | Request-bound service grant, internal recovery ownership/key-rotation API, managed-key successor and idempotency behavior. Test adapters are local; no live Identity+Recovery service pair was deployed for this check. |
| Repo root: `node --experimental-strip-types apps/web/tests/recoveryApi_contract.test.ts` | Exit 0; **22 assertions passed**. | Confirms the web client requests the Identity proof and forwards it in Recovery decisions; not browser E2E. |
| Repo root: `npm run build --prefix apps/web -- --configLoader runner` | Exit 0; TypeScript passed and Vite 6.4.3 transformed 1,826 modules. | Production frontend bundle; not a visual or accessibility audit. |
| CWD `services/recovery-service`: `& 'C:\Users\besna\OneDrive\Bureau\secure-ssi-platform\.venv\Scripts\python.exe' -m ruff check app tests` | Exit 1; `No module named ruff`. | Lint could not run because Ruff is not installed in the authorized runtime; no install attempted. |

The first parallel pytest attempt hung at the Windows asyncio socket-pair setup. It was interrupted and is **not** counted as a result. A verbose/faulthandler reproduction showed the wait in `socket.accept` → `asyncio.windows_events._make_self_pipe` → AnyIO `start_blocking_portal`; the same Recovery and Identity scoped commands passed once permitted to create the local test-process socket. G8 remains **PARTIAL**: the current signer uses a server-managed key, only Ed25519 `did:key` is supported, independent Guardian-device/MFA is absent, and no browser or live cross-service Mongo rotation trace was run. This evidence does not claim production custody or L4 interoperability.

## G9 risk/policy continuation — 15 October 2026

The first scoped run found the Fraud Service evaluation path could automatically write an in-memory quarantine entry, and event ingestion did the same after repeated failures. That conflicted with the disclosed advisory boundary and made repeated seeded synthetic replays depend on prior calls. The scorer now returns risk/recommendation without changing quarantine state; event ingestion only updates the feature store. Explicit prototype quarantine routes remain separate demo state and are not credential status, trust, durable evidence, or a chain receipt.

| Command / working directory | Result | Scope and limit |
|---|---|---|
| CWD `services/fraud-service`: `& 'C:\Users\besna\OneDrive\Bureau\secure-ssi-platform\.venv\Scripts\python.exe' -m pytest -q -rs tests/test_fraud_service.py tests/test_event_pipeline_and_dataset.py tests/test_layer2_fraud_detection.py` | Exit 0; **21 passed**, 2 deprecation warnings, 2.30 s. | Covers model/status disclosure, diagnostic synthetic metrics, repeatable high-risk output with no quarantine mutation, event-ingestion no-auto-quarantine, explicit demo quarantine lifecycle, and legacy heuristic endpoint. |
| CWD `services/identity-service`: `& 'C:\Users\besna\OneDrive\Bureau\secure-ssi-platform\.venv\Scripts\python.exe' -m pytest -q -rs tests/integration/test_oid4vp_ai_policy_matrix.py` | Exit 0; **8 passed**, 2 deprecation warnings, 2.64 s. | Covers crypto/expiry/nonce rejection at low risk, risk tiers, quarantining policy after all gates pass, server-computed fallback provenance, and ignoring caller-supplied score/telemetry. |
| CWD `services/identity-service`: `& 'C:\Users\besna\OneDrive\Bureau\secure-ssi-platform\.venv\Scripts\python.exe' -m pytest -q -rs tests/unit/test_verification_policy.py` | Exit 0; **48 passed**, 1 SQLite deprecation warning, 0.57 s. | Every failed protocol/security gate, including `ISSUER_TRUSTED` and `REVOCATION_STATUS`, remains rejected at zero risk. Policy boundary is unit-tested; G6's separately recorded current integration tests verify actual trust/status resolution. |

These commands passed under the already-installed Python 3.11 environment; TestClient-backed commands required local test-process socket permission on Windows. No package was installed. The current Web TypeScript/Vite build (`npm run build --prefix apps/web -- --configLoader runner`) passed during G8 continuation after the existing G9 UI changes; 1,826 modules. G9 is **PASS at L3 only for the documented synthetic heuristic/policy scope**. It does not establish trained-model validity, independent representative labeled evaluation, fairness, real-world generalization, or production operation; none is claimed. NIST AI RMF validity/reliability context is linked in [Risk Heuristic Architecture](../ai_architecture.md).

## G10 optional blockchain continuation — 15 October 2026

| Command / working directory | Result | Scope and limit |
|---|---|---|
| CWD `blockchain`: `npm test` | Exit 0; **19 passing**, no failures. | Repository-installed Hardhat contracts run on its ephemeral in-process test network. |
| CWD `services/identity-service`: `& 'C:\Users\besna\OneDrive\Bureau\secure-ssi-platform\.venv\Scripts\python.exe' -m pytest -q -rs tests/unit/test_blockchain_anchor.py tests/unit/test_blockchain_api.py tests/unit/test_blockchain_settings.py tests/unit/test_blockchain_contract_directory.py tests/integration/test_blockchain_anchoring.py` (initial chain-free run) | Exit 0; **18 passed, 5 skipped**. | The five skips were the expected live-chain cases because no listener was running; they were rerun against the project’s local Hardhat runtime below. |
| CWD `services/identity-service`: `& 'C:\Users\besna\OneDrive\Bureau\secure-ssi-platform\.venv\Scripts\python.exe' -m pytest -q -rs tests/integration/test_blockchain_anchoring.py`, with `BLOCKCHAIN_ENABLED=true`, chain ID 1337, local RPC, the default disposable Hardhat account and the four addresses deployed in this isolated run | Exit 0; **7 passed, 0 failed, 0 skipped**. | A temporary Hardhat node was bound only to `127.0.0.1`; four existing contract artifacts received successful local deployment receipts. The integration tests verified live local transaction receipts, digest-only DID/status/quarantine/audit payloads, idempotent duplicate revocation, and offline RPC handling. Anchor-record persistence uses the test FakeMongo adapter, not live MongoDB. The node was stopped after the tests. |
| CWD `services/identity-service`: `& 'C:\Users\besna\OneDrive\Bureau\secure-ssi-platform\.venv\Scripts\python.exe' -m pytest -q -rs tests/integration/test_golden_path.py tests/integration/test_oid4_protocols.py` | Exit 0; **8 passed**, 2 deprecation warnings. | An otherwise valid OID4VCI/OID4VP presentation remains `ACCEPTED` with `blockchainAnchored == false`; this is protocol integration coverage without an anchor, not a browser journey. |

Final G10-focused results: **19 Hardhat contract tests + 25 Identity anchor/API/settings/directory/live-integration tests + 8 unanchored Golden Path/protocol tests = 52 passed, 0 failed, 0 final skips**. The first chain-free run’s five skips are disclosed above and were replaced by the 7/7 live local-chain rerun. Python warnings were existing SQLite persistence and Starlette/httpx deprecations. The first temporary Hardhat launch tried to write telemetry consent under the inaccessible user AppData path; no global setting was changed. The retry used `HARDHAT_DISABLE_TELEMETRY_PROMPT=true` and succeeded. An initial combined test invocation used the wrong working directory and collected zero tests; it was corrected and is not included in the totals.

G10 is **PASS at L3 for the local optional-anchor profile**. Offline/pending/reverted/skipped state transitions and the unanchored-valid-credential boundary are covered. No public network, production deployment, durable Mongo anchor store, automated retry worker, or production reliability claim is established.

## Previous checkpoint checks — 14 October 2026 (historical)

| ID | Exact command / working directory | Result | Scope and limit |
|---|---|---|---|
| CUR-PY-01 | CWD `services/identity-service`: `& ..\..\.venv\Scripts\python.exe -m pytest -q tests/integration/test_wp07_wallet_consent_presentation_proof.py tests/integration/test_wp07_legacy_oid4vp_routes.py tests/integration/test_wp02_holder_binding_verification.py tests/integration/test_auth_api.py tests/integration/test_consent_and_privacy.py` | Exit 1 before collection: `uv trampoline failed to spawn Python child process; permission denied (os error 5)`. **Passed 0 / failed 0 / skipped 0 / collected 0 — BLOCKED.** | No test code executed. Do not classify as product failure or pass. |
| CUR-PY-02 | CWD `services/identity-service`: `& ..\..\.venv\Scripts\python.exe -m pytest -q -rs tests/integration/test_wp08_remediation_status_security.py tests/integration/test_wp08_policy_evaluation.py tests/integration/test_issuance_interoperability.py` | Exit 1 before collection with the same `uv trampoline ... permission denied (os error 5)`. **Passed 0 / failed 0 / skipped 0 / collected 0 — BLOCKED.** | Current WP-08 R1–R3 evidence could not be refreshed on the current dirty worktree. |
| CUR-FE-01 | Repo root: `npm run lint --prefix apps/web` | Exit 0; ESLint no diagnostics. | Current frontend source; not visual/browser/a11y acceptance. |
| CUR-FE-02 | Repo root: `npm run build --prefix apps/web -- --configLoader runner` | Exit 0; TypeScript + Vite 6.4.3; 1,826 modules transformed. | Current frontend source. Runner config loader was required to avoid the default loader's sandbox parent-directory denial recorded in earlier progress notes. |
| CUR-FE-03 | Repo root: `node --experimental-strip-types apps/web/tests/authentication_contract.test.ts` | Exit 0; 15 checks passed. | Frontend authentication contract; mocked/local API responses, not backend execution. |
| CUR-FE-04 | Repo root: `node --experimental-strip-types apps/web/tests/oid4vpWallet_contract.test.ts` | Exit 0; 9 assertions passed. | Wallet-bound API client contract only. |
| CUR-FE-05 | Repo root: `node --experimental-strip-types apps/web/tests/verifyPresentation_fail_closed.test.ts` | Exit 0; 8 checks passed. | Frontend policy/result normalization contract only. |
| CUR-FE-06 | Repo root: `node --experimental-strip-types apps/web/tests/recoveryApi_contract.test.ts` | Exit 0; 21 assertions passed. | Recovery API client contract only. |
| CUR-ST-01 | Bundled Python 3.12.14, stdin script calling `ast.parse` on `services/identity-service/app/schemas/oid4_api.py`, `.../test_wp07_wallet_consent_presentation_proof.py`, and `.../test_wp07_legacy_oid4vp_routes.py` | Exit 0; all 3 files parsed. | Syntax only; does not prove Python 3.11 compatibility, importability or runtime behavior. |
| CUR-GIT-01 | Repo root: `git diff --check` | Exit 0; no whitespace errors. Existing LF/CRLF conversion warnings printed. | Formatting hygiene only. |

The frontend scripts reported **53 passed checks/assertions**, not 53 backend tests. Lint/build are successful commands without pytest-style test counts.

## Environment at 14 October checkpoint (historical)

| ID | Exact check | Observed result |
|---|---|---|
| ENV-01 | `& .\.venv\Scripts\python.exe --version` and targeted pytest above | Repository launcher fails to spawn Python with Windows `os error 5`. |
| ENV-02 | Authorized bundled Python at `C:\Users\besna\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe` | Python 3.12.14; prior read-only module probe found `pytest=False`, `fastapi=False`, `pymongo=False`, `cryptography=True`, `sqlite3=True`. Not a project test runtime; no packages installed. |
| ENV-03 | `Get-Command docker`; `Test-Path` for `C:\Program Files\Docker\Docker\Docker Desktop.exe` and `...\resources\bin\docker.exe` | Docker CLI and both standard executable paths absent. No daemon or container was started. |
| ENV-04 | `wsl.exe --list --quiet`; `wsl.exe --status` | Both returned `Wsl/EnumerateDistros/Service/E_ACCESSDENIED`. WSL distributions cannot be verified under current permissions. |

## Historical results — retain as historical only

| Evidence | Reported result | Boundary |
|---|---|---|
| Focused WP-08 command: `..\..\.venv\Scripts\python.exe -m pytest -q -rs tests/integration/test_wp08_remediation_status_security.py tests/integration/test_wp08_policy_evaluation.py tests/integration/test_issuance_interoperability.py`, CWD Identity Service | 48 passed, 0 failed, 0 skipped; 2 deprecation warnings; 84.80 s. | From the 14 Oct WP-08 report before the latest G7 schema/test migration. Not rerun on this exact dirty source state. |
| Root `.venv\Scripts\python.exe run_tests.py` | 788 passed, 12 skipped, 0 failed, 155 subtests. | Earlier checkpoint; 7 real-Mongo cases lacked `IDENTITY_TEST_MONGODB_URI`; 5 live Hardhat skips were rerun separately. Not current-source final regression. |
| Identity focused OID4VCI/OID4VP integration set | 55 passed, 0 failed, 0 skipped. | Earlier source checkpoint; in-process tests only, no browser/independent peer. |
| Recovery Service suite | 46 passed, 0 failed, 0 skipped. | Earlier source checkpoint; no independent Guardian DID signature or real Mongo restart evidence. |
| Local Hardhat suite and Identity live-chain test | 19 Hardhat tests and 7 integration tests passed. | Earlier disposable local chain only; no public/production chain. |
| G9 focused policy/risk suite | 57 passed. | Historical and not acceptance because G6/WP-08 is not accepted. |
| Separate G10 contract/settings checkpoint | 15 passed, 5 skipped. | Five skips were live Hardhat cases when port 8545 was unavailable; separate historical live-chain tests do not change this checkpoint's count. |

## Source fingerprint for 14 October G7 backend evidence (historical)

SHA-256 hashes below identify the current source snapshot relevant to the blocked backend suite. The current test attempt above did not execute against these files.

| File | SHA-256 |
|---|---|
| `services/identity-service/app/api/v1/oid4vp.py` | `74D5E98F3ABDC85D9F3D12A490F0E1607FFB5E9A9C449A470DD51047B6B8C191` |
| `services/identity-service/app/application/services/oid4vp_service.py` | `C256DC526B86AF91A88069D0FD09845E2DC237860DB42A18938E8252C3346BE6` |
| `services/identity-service/app/schemas/oid4_api.py` | `58611895A5205286D48204CF1B9B2B7AACF5A81519AABEE2239F965DF7074C49` |
| `services/identity-service/tests/integration/test_wp07_wallet_consent_presentation_proof.py` | `BA41264E4CA195B689E558378539E9434CC560EA3CD084155FA43740802E71B7` |
| `services/identity-service/tests/integration/test_wp07_legacy_oid4vp_routes.py` | `C346C140E8A211FB1045CB5B91CF820D87B17EB7F9D931E19B040CF76DFFAE87` |
| `services/identity-service/tests/integration/test_auth_api.py` | `2E591A35B68DFE15D00ABC0527AD2B205A27548FDD9727C462EDF04258604789` |

At the 14 October checkpoint, no test was skipped to manufacture a pass. The statements in that checkpoint do not describe the 15 October runs above.

## WP-07 migration coverage review — 14 October (superseded below)

The test-name inventory at `HEAD` had 27 test functions; the migrated file had 22 at that checkpoint. Its note that the valid-holder-proof/tampered-issuer regression remained to be added is superseded by the 15 October G7 execution and coverage note below.

## G7 issuer/holder proof regression — 15 October 2026

The migrated wallet-bound verification test now includes an isolated case that creates a valid holder presentation proof around a credential whose issuer proof was tampered with. The current Identity Service regression passed this case. The verifier rejected the issuer-tampered credential while the holder-binding proof remained valid; this specifically demonstrates that a valid holder proof does not substitute for issuer signature validation.

## G13 targeted security continuation — 15 October 2026

The Gateway review found default Compose host-port mappings exposed on all interfaces and an in-memory rate-limit map without a cardinality bound. Compose now binds all seven service/data ports to 127.0.0.1. The Gateway limiter caps its LRU map at 10,000 clients and derives client identity from the socket peer, not X-Forwarded-For.

| Exact command / working directory | Result | Scope and limit |
|---|---|---|
| CWD services/api-gateway: & 'C:\Users\besna\OneDrive\Bureau\secure-ssi-platform\.venv\Scripts\python.exe' -m pytest -q -rs tests/test_security_hardening.py | Current source: 9 passed, 0 failed, 0 skipped; 2 deprecation warnings; 0.86 s. | Covers security headers, CORS, 429/Retry-After, bounded client state, forwarded-IP spoof resistance, payload-size and JSON depth/encoding limits. One earlier sandbox attempt produced no output for about 40 seconds and was interrupted; the same test was rerun with local TestClient socket permission. |
| CWD services/identity-service: & 'C:\Users\besna\OneDrive\Bureau\secure-ssi-platform\.venv\Scripts\python.exe' -m pytest -q -rs tests/integration/test_auth_api.py tests/integration/test_credential_api.py tests/integration/test_credential_revocation_api.py tests/unit/test_token_revocation.py | 104 passed, 0 failed, 0 skipped; 2 deprecation warnings; 6.84 s. | Authn/authz, strict request envelopes, body limits, logout revocation, role checks, safe errors, and credential/token redaction. |
| CWD services/recovery-service: & 'C:\Users\besna\OneDrive\Bureau\secure-ssi-platform\.venv\Scripts\python.exe' -m pytest -q -rs tests/integration/test_recovery_api.py tests/unit/test_identity_gateway.py tests/unit/test_secret_sharing.py | 14 passed, 0 failed, 0 skipped; 1 deprecation warning; 1.79 s. | Recovery authorization/proof, internal grant handling, and secret-share output/log redaction. |
| Repo root: docker compose config --format json projected to each service's host_ip:published->target, followed by docker compose config --quiet | Exit 0. Web 127.0.0.1:3000->80; Gateway 127.0.0.1:8000->8000; Identity 127.0.0.1:8001->8000; Fraud 127.0.0.1:8002->8000; Recovery 127.0.0.1:8003->8000; Mongo 127.0.0.1:27017->27017; Redis 127.0.0.1:6379->6379. | Resolved configuration only; no service was started. |
| CWD services/api-gateway: & 'C:\Users\besna\OneDrive\Bureau\secure-ssi-platform\.venv\Scripts\python.exe' -m ruff check app/core/middleware.py tests/test_security_hardening.py | Exit 1: No module named ruff. | Ruff was not installed. The focused pytest run imports and exercises the modified module. |
| CWD apps/web: npm audit --offline --audit-level=moderate | Exit 0; found 0 vulnerabilities. | Audited the existing apps/web/package-lock.json only using offline npm audit data; does not cover Python dependencies or application source code. |

G13 is PARTIAL, not complete. The frontend npm audit reported 0 known vulnerabilities; no Python dependency scanner, SAST, secret scan, independent review, or formal critical/high-finding disposition was produced. Gateway limits and token revocation are process-local; Identity and Recovery have no independent rate limiter; production identity, shared limits, monitoring and incident controls remain open. No test is skipped to create a pass.

## G11/G12 isolated Web build correction — 15 October 2026

The running validation Web image had been built with its default Gateway URL of http://localhost:8000, while the isolated validation Gateway was published at 127.0.0.1:18000. The original Dockerfile had no build argument, so runtime environment overrides could not change the static SPA URL. Added VITE_API_BASE_URL as a Docker build argument with the existing localhost:8000 default; Compose passes that variable into the Web build. The default Compose configuration remains unchanged for users running the default 8000 Gateway port.

The Web image for the isolated test project was built with a stdin-only Compose override:

```yaml
services:
  web:
    build:
      args:
        VITE_API_BASE_URL: http://127.0.0.1:18000
    ports: !override
      - 127.0.0.1:13000:80
```

The build command was:

```powershell
$override | docker compose --project-name wp08-validation-20261015 --file docker-compose.yml --file - build --pull=false web
```

The first web-only `up` attempt used a normal YAML ports list, which Compose merged with the base 3000 mapping and failed because host port 3000 was already occupied. No other service was targeted. The web container had been recreated but did not start; it was then started successfully using the validated `ports: !override` setting and `up --detach --no-deps --no-build web`. The final read-only Compose check reported **7/7 services healthy**.

| Read-only observation | Result | Scope and limit |
|---|---|---|
| GET http://127.0.0.1:13000/ and fetch of its referenced JS/CSS bundles | HTTP 200; JavaScript contains http://127.0.0.1:18000; CSS contains the :focus-visible rule and #fbbf24 indicator. | Verifies the deployed static bundle and focus CSS bytes, not keyboard interaction, visual appearance, sign-in, or the consent retry UI. |
| GET http://127.0.0.1:18000/health, :18001/health, :18002/health, :18003/health | Gateway, Identity, Fraud and Recovery each returned HTTP 200. | Health only; no authenticated browser journey. |
| Browser OID4VP Direct Post retry | Not attempted. | The earlier 5173 browser POST failure remains unresolved. The current Web bundle base-URL mismatch explains the separate Compose login issue but does not establish the root cause of the prior Vite-flow Direct Post failure. |

## G15 component performance checkpoint — 15 October 2026

Added JSON result output to the existing Identity and Fraud performance tests so their already-computed measurements are visible and reproducible in pytest output. No application logic or benchmark workload changed. All three targeted performance files passed on Python 3.11.16 / Windows `10.0.26300.0`; the commands ran sequentially from each service directory:

| Exact command | Result | Scope |
|---|---|---|
| CWD `services/identity-service`: `& 'C:\Users\besna\OneDrive\Bureau\secure-ssi-platform\.venv\Scripts\python.exe' -m pytest -q -s tests/performance/test_identity_benchmarks.py` | 3 passed, 0 failed, 0 skipped; 1 SQLite-deprecation warning; 0.49 s. JSON benchmark record printed. | Local canonicalization/Ed25519 signing at 10/100/500 credentials plus 131,072-entry status-list assertions. No API, DB, or concurrency. |
| CWD `services/fraud-service`: `& 'C:\Users\besna\OneDrive\Bureau\secure-ssi-platform\.venv\Scripts\python.exe' -m pytest -q -s tests/performance/test_fraud_benchmarks.py` | 1 passed, 0 failed, 0 skipped; 0.30 s. JSON benchmark record printed. | In-process deterministic rule heuristic (`rule-heuristic-v1`), not trained ML, at 1/10/100/500 evaluations. |
| CWD `services/recovery-service`: `& 'C:\Users\besna\OneDrive\Bureau\secure-ssi-platform\.venv\Scripts\python.exe' -m pytest -q -s tests/performance/test_recovery_benchmark.py` | 1 passed, 0 failed, 0 skipped; 0.57 s. `RECOVERY_BENCHMARK` JSON printed. | 25 in-memory recovery workflows with a fake managed-key gateway. |

Measured percentiles (milliseconds) and throughput from emitted JSON:

| Benchmark | Workload | P50 | P95 | P99 | Throughput |
|---|---:|---:|---:|---:|---:|
| Identity signing | 10 | 0.185 | 0.291 | 0.291 | 4,884 ops/s |
| Identity signing | 100 | 0.183 | 0.501 | 0.761 | 4,159 ops/s |
| Identity signing | 500 | 0.185 | 0.496 | 0.786 | 4,007 ops/s |
| Fraud heuristic | 1 | 0.026 | 0.026 | 0.026 | Single sample |
| Fraud heuristic | 10 | 0.025 | 0.043 | 0.043 | 30,303 ops/s |
| Fraud heuristic | 100 | 0.011 | 0.017 | 0.023 | 67,114 ops/s |
| Fraud heuristic | 500 | 0.011 | 0.016 | 0.109 | 60,145 ops/s |
| Recovery workflow | 25 | — | 4.151 | — | Mean 3.098 ms; max 6.473 ms |

These are serial, in-process component measurements from the tests' direct sorted-array percentile indexes, not interpolated percentiles. Fraud's one-sample percentile values are not statistically useful. CPU/RAM inventory was unavailable because `Get-CimInstance` was denied. `Get-Command locust,k6,wrk,vegeta,ab -ErrorAction SilentlyContinue` returned no available external load tool. No project API load, concurrency, Mongo pool, HTTP error-rate, timeout/retry/idempotency, outage, or recovery experiment was executed; G15 remains PARTIAL. No platform SLA or production performance claim is supported.


## G16 documentation consistency checkpoint — 15 October 2026

The current README, implementation-status inventory, API contracts, architecture, VC profile, credential API, benchmark report, and S23 demo reports were compared with the current gate/evidence record and relevant implementation boundaries. Corrections clarify the backend custody model, process-local Gateway limiter and token revocation, Guardian `did:key` proof scope, credential persistence/status separation, historical benchmark limitations, and dated demo-report status. WP-03 through WP-07 package reports now state that their L3 labels are scoped historical results, not current project-wide acceptance.

A static inline-link scan used `rg --files -g '*.md'` plus Python `pathlib`/`re` against local relative link targets: 80 Markdown files, 201 local relative links, 0 missing targets. It does not verify heading anchors, external links, rendered layout, or whether every historical claim is current. No PDF, DOCX, TeX, thesis, or dissertation artifact exists in this repository, so the thesis itself could not be compared. G16 remains PARTIAL pending thesis-source review and a clean-environment setup/demo reproduction.

## G12/G13 Admin user and Issuer scope continuation — 18 October 2026

Added an Admin-only directory for existing persistent accounts, an issuer-scope option list restricted to active/trusted Trust Registry records with configured signing keys, and a version-checked scope assignment/removal endpoint with an audit event. The Web Admin menu and `Users and institutions` page use the same endpoints. Synthetic fixture accounts are explicitly read-only; no account creation or role-grant behavior was added. The Identity API's persisted `issuerDid` binding remains the authority used by issuer signing, offer, revoke, and history routes.

Exact targeted pytest command:

```powershell
docker run --rm --network none --mount type=bind,source=C:\Users\besna\OneDrive\Bureau\secure-ssi-platform\services\identity-service,target=/workspace,readonly --workdir /workspace --env PYTHONDONTWRITEBYTECODE=1 --env "PYTEST_ADDOPTS=-p no:cacheprovider" --entrypoint python secure-ssi-platform-identity-service:latest -m pytest -q -rs tests/integration/test_admin_users_api.py tests/unit/test_mongo_repositories.py tests/integration/test_auth_api.py tests/integration/test_credential_api.py tests/integration/test_credential_revocation_api.py tests/unit/test_persistence_mappers.py tests/unit/test_persistence_domain.py
```

| Exact command / observation | Result | Scope and limit |
|---|---|---|
| CWD `services/identity-service`: targeted Docker pytest command for `test_admin_users_api.py`, `test_mongo_repositories.py`, `test_auth_api.py`, `test_credential_api.py`, `test_credential_revocation_api.py`, `test_persistence_mappers.py`, and `test_persistence_domain.py` | **151 passed, 0 failed, 0 skipped; 2 deprecation warnings; 4.74 s.** | The container used current source through a read-only bind mount with networking disabled. Covers admin vs non-admin API access, trusted/configured issuer choices, scope update/audit/version checks, legacy mapper compatibility, issuer operation scoping, and Mongo repository pagination. Not a live-Mongo or browser E2E run. |
| CWD `apps/web`: `npm.cmd run lint`; `npm.cmd run build` | Both passed. Vite transformed 1,828 modules. | Static lint and TypeScript/production build only. |
| `docker compose -p wp08-l3-20261013 up -d --build --no-deps identity-service web` | Rebuilt only Identity and Web; other services were left running. Web image build ran its configured `npm install`, lint, and build. npm reported **2 moderate dependency advisories** during install; no packages were auto-updated. | Build output is not a dependency audit disposition. The advisories need a separate package-level review before a security claim. |
| `docker compose -p wp08-l3-20261013 up -d --build --no-deps web` after changing the Web health-check target to `127.0.0.1` | Web image rebuilt; all 7 current project services subsequently reported healthy. | Only Web was recreated for the health-check adjustment. |
| Identity container OpenAPI `GET /openapi.json`; Web bundle search for `No institution assigned` | OpenAPI lists `GET /api/v1/admin/users`, `GET /api/v1/admin/users/issuer-options`, and `PUT /api/v1/admin/users/{user_id}/issuer-scope`; built Web image contains the `AdminUsersPage` bundle. | Confirms route registration and bundle inclusion, not authenticated behavior in the live browser. |
| Web container health check | Initial rebuilt container failed because `localhost` resolved to IPv6 while Nginx listened on IPv4. Changed the Docker health-check target to `127.0.0.1` and rebuilt Web. | This correction addresses the observed local container configuration only. |

The admin directory is available only when `IDENTITY_AUTH_USER_PROVIDER=mongodb`; the Compose default remains synthetic, so this local fixture configuration returns `503` for account management instead of presenting mutable demo identities. No account-creation/initial-admin workflow, authenticated Admin browser screenshot, responsive/accessibility review of the new screen, or live Mongo scope-change trace was executed. G12 and G13 remain **PARTIAL**; this evidence does not change their gate status.
