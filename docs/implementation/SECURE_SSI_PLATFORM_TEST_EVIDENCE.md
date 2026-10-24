# Secure SSI Platform — Test Evidence Register

## Current-source WP-10 / G10 authorization and receipt revalidation — 24 October 2026

The current contract source had left `RevocationRegistry.revokeCredential` public even though the operation records a global, irreversible revocation and the contract already declared an unused `onlyOwner` modifier. It now requires the owner; unauthorized calls revert without changing state. The contract suite was re-run after compiling the current Solidity 0.8.28 source.

| Exact command / observation | Result | Scope / limitation |
|---|---|---|
| `npm.cmd test --prefix blockchain` | **20 passing, 0 failing.** Hardhat compiled one Solidity file. | Includes the new non-owner revocation test, owner path and duplicate-revocation path. The required compiler was absent from cache and downloaded by the configured Hardhat command; no project package or lockfile was changed. |
| CWD `services/identity-service`: `..\..\.venv\Scripts\python.exe -m pytest -q tests/unit/test_blockchain_anchor.py` | **8 passed, 0 failed; 1 existing SQLite deprecation warning.** | Unit behavior for canonical hashing/redaction, anchor state transitions, offline, pending and reverted receipt handling. |
| CWD `services/identity-service`: `..\..\.venv\Scripts\python.exe -m pytest -q tests/integration/test_blockchain_anchoring.py`, with process-local `BLOCKCHAIN_ENABLED=true` and the local Hardhat test signer key | **7 passed, 0 failed, 0 skipped; 1 existing SQLite deprecation warning.** | Ephemeral loopback chain 1337; current compiled contracts were deployed at the deterministic local test addresses. The bridge's authorized owner signer received receipts for all tested anchor operations. FakeDatabase only; no public chain or durable Mongo evidence. Node process stopped after the run; no deployment metadata was written. |
| CWD `services/identity-service`: `..\..\.venv\Scripts\python.exe -m pytest -q tests/integration/test_golden_path.py::test_golden_path_complete_lifecycle` | **BLOCKED / interrupted without a pytest summary.** | The test stalled in the Windows TestClient/asyncio Proactor path. It is not counted as pass or failure. Its source asserts unanchored-but-valid verification remains `ACCEPTED`; current-source execution remains unverified. |

The three completed suites total **35 passed, 0 failed, 0 skipped** with two existing SQLite warnings. G10 is **PARTIAL for the current source** until the unaffected-credential Golden Path can be executed. See the [WP-10 report](../../reports/V2_1_WP10_BLOCKCHAIN_ANCHOR_SECURITY.md) for security scope, source changes, deployment caveat, and standards references.

## Current-source WP-08 Docker L3 verification — 24 October 2026

This entry supersedes the 23 October current-source status below, which predates the successful rebuild. **Repository state:** branch `besna-dev`; HEAD `9e965bb4de7f5e1bb1cbf0f48f30d53ebfb88b73`. The four tracked documentation changes and pre-existing untracked audit folder were preserved. No source code or Compose file was edited, no paths were staged, and no commit, push, merge, reset, clean, or volume deletion occurred. Local/remote tracking refs were not fetched during this task, so GitHub freshness is unknown.

### Compose configuration and build

`docker compose -p wp08-l3-20261013 config --format json` exited 0. It resolved these exact targets and build inputs:

| Compose service | Build context | Dockerfile |
|---|---|---|
| `web` | `apps/web` | `Dockerfile` |
| `api-gateway` | `services/api-gateway` | `Dockerfile` |
| `identity-service` | `services/identity-service` | `Dockerfile` |
| `fraud-service` | `services/fraud-service` | `Dockerfile` |
| `recovery-service` | `services/recovery-service` | `Dockerfile` |

Exact build command:

```powershell
docker compose -p wp08-l3-20261013 --progress plain build --no-cache web api-gateway identity-service fraud-service recovery-service
```

Exit 0. All five images built from the current working-tree contexts. Package downloads occurred as authorized. The Web build ran ESLint and Vite/TypeScript production build, transforming 1,830 modules. npm emitted `3 vulnerabilities (2 moderate, 1 high)` and a deprecated ESLint notice; no dependency/lockfile remediation was attempted. The retained build summary did not include package names, dependency paths, advisory identifiers, affected version ranges, or fix availability.

Safe local advisory check:

```powershell
npm audit --offline --json --prefix apps/web
```

Exit 0; the offline report returned an empty `vulnerabilities` object for 264 listed dependencies. It supplied no advisory details and cannot reconcile or clear the three aggregate advisories from the Docker build. No online audit was run, because that would submit dependency metadata to the configured registry. The lockfile SHA-256 remained `00FABE9935085757C1C3731B4C8B5967E1DAA1975630E659F23C743A76FA3E0A`; no dependency version or lockfile change was made. To identify the advisories without an online scan from this workspace, the required safe input is the full npm audit JSON/output captured during the image build, including `via`, `range`, `nodes`, and `fixAvailable`; otherwise the user must explicitly authorize an online registry audit after reviewing what package metadata it submits.

Exact recreation command:

```powershell
docker compose -p wp08-l3-20261013 up -d --no-build --force-recreate --wait --wait-timeout 180 web api-gateway identity-service fraud-service recovery-service
```

Exit 0. Only the five application targets were recreated. MongoDB and Redis remained in place; no volume was deleted. The existing volumes `wp08-l3-20261013_mongodb_data` and `wp08-l3-20261013_redis_data` were still present after recreation. `docker compose -p wp08-l3-20261013 ps --all` showed all seven services healthy.

### Rebuilt container evidence

All five containers were `running` and `healthy` when inspected. Creation times are UTC. OCI revision/source labels were empty on all five images, so image metadata alone does not attest a source revision. The Compose build was invoked from this repository at the HEAD recorded above; the served Web asset was independently compared to the local build.

| Service | Container created (UTC) | Image ID | Health | OCI revision/source label |
|---|---|---|---|---|
| `web` | `2026-10-24T14:45:24.344874322Z` | `sha256:2b759827baf9c61e57387d1e28714ec7794c69d0d88c8c7c4616c2d30a760c49` | `healthy` | absent |
| `api-gateway` | `2026-10-24T14:45:23.780530531Z` | `sha256:588d78686ef64bfc0011e66d88e16f91eafc9c040f8b182cc11f85fa3f17bf39` | `healthy` | absent |
| `identity-service` | `2026-10-24T14:45:21.772351819Z` | `sha256:cb02624dc82bccdfa651515534d0f53f3f9c1f6234030ead8fbcb7c0b33263fe` | `healthy` | absent |
| `fraud-service` | `2026-10-24T14:45:21.564177586Z` | `sha256:3d32f3ddeb9f08412cd4d4d2a050f6904d3c3c757062546c3ffc037646dc7a83` | `healthy` | absent |
| `recovery-service` | `2026-10-24T14:45:22.898963193Z` | `sha256:e5019d55dcbc882f7247a3e018c3dd96617fab28f39ed92df76116d49b5cbd75` | `healthy` | absent |

### Tests and live HTTP probes

Exact focused test command, executed in the rebuilt Identity container (working directory `/app`):

```powershell
docker exec -e PYTHONDONTWRITEBYTECODE=1 wp08-l3-20261013-identity-service-1 python -m pytest -q -rs -p no:cacheprovider tests/integration/test_wp08_remediation_status_security.py tests/integration/test_wp08_policy_evaluation.py tests/integration/test_issuance_interoperability.py tests/integration/test_oid4vp_session_authorization.py
```

Exit 0: **52 passed, 0 failed, 0 skipped**, 2 deprecation warnings, 2.22 seconds. This runs service integration tests in-process inside the rebuilt image; it is not an authenticated browser/network E2E run. OID4VP tests verify owner polling, unauthenticated rejection, a different verifier receiving the same `404` as a guessed session ID, holder-only request context, and fail-closed access when session ownership is missing. They do not test an organization/tenant claim beyond exact user ownership.

The local frontend checks also passed:

```powershell
npm.cmd run lint --prefix apps/web
$env:VITE_API_BASE_URL='http://127.0.0.1:8000'; npm.cmd run build --prefix apps/web
```

Both exited 0; lint had no diagnostics and Vite 6.4.3 transformed 1,830 modules. The running Web root and bundle were fetched with `Invoke-WebRequest`: `GET http://127.0.0.1:3000/` -> 200 and `GET http://127.0.0.1:3000/assets/index-C7R2dkgq.js` -> 200. Both local and served bundle SHA-256 values were `211B4531725937B891AF637BAB60B1CF5878E669A3FE6A48FE8A40F1874B2259`.

Container metadata was read with `docker compose -p wp08-l3-20261013 ps -q <service>` followed by `docker inspect <container-id>`. Recent logs were checked with `docker compose -p wp08-l3-20261013 logs --since 30m api-gateway identity-service fraud-service recovery-service`; startup was normal and no matched `Traceback`, `ERROR`, or `Exception` entries were present. The volumes were enumerated with `docker volume ls --format '{{.Name}}'`.

The read-only API smoke probes were:

```powershell
Invoke-WebRequest -Uri http://127.0.0.1:8000/health -UseBasicParsing
Invoke-WebRequest -Uri http://127.0.0.1:8001/health -UseBasicParsing
Invoke-WebRequest -Uri http://127.0.0.1:8002/health -UseBasicParsing
Invoke-WebRequest -Uri http://127.0.0.1:8003/health -UseBasicParsing
Invoke-WebRequest -Uri 'http://127.0.0.1:8001/api/v1/oid4vp/requests/wp08-live-smoke-random-20261024' -Method Get -UseBasicParsing
Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/v1/oid4vp/requests/wp08-live-smoke-random-20261024' -Method Get -UseBasicParsing
```

Web `/` and the four `/health` routes returned HTTP 200; the two unauthenticated OID4VP retrieval probes returned HTTP 401. The requests did not create, approve, submit, or alter an OID4VP session. Recent backend logs showed normal application startup and no matched `Traceback`, `ERROR`, or `Exception` entries.

**Decision:** the current-source Docker runtime and scoped WP-08/OID4VP L3 checks **PASS**. The follow-up evidence below adds a full Identity regression and targeted WP-09 service/policy tests. No WP-09 code was changed in this verification; G9/WP-09 implementation and its scoped PASS were already recorded on 15 October. This does not claim an authenticated live owner/cross-organization browser journey, suspension restoration, independent L4 interoperability, production readiness, or a resolved npm advisory. The repository-wide runner was attempted twice in the follow-up but was interrupted without a pytest summary; the same-HEAD 820-pass result remains historical evidence only.

## Final scoped regression and WP-09 readiness review — 24 October 2026

These checks extend the current-source evidence above without changing application code, dependencies, test files, Compose configuration, or Git history. Temporary test copies were made only inside disposable, no-network container tmpfs filesystems from a read-only repository mount. The Compose stack and its data volumes were not changed by these test runs.

| Scope | Exact test invocation / environment | Result | Boundary |
|---|---|---|---|
| Identity Service full regression | `python -m pytest -q -rs -p no:cacheprovider` from a temporary copy of current `services/identity-service`, inside the existing local Identity image; `IDENTITY_MONGO_ENABLED=false`, blank `IDENTITY_TEST_MONGODB_URI`, `--network none`, repository mounted read-only. | **708 passed, 0 failed, 12 skipped, 3 warnings**, 16.21 s. | Five tests skipped because local Hardhat port 8545 was unavailable; seven live-Mongo tests skipped because no test Mongo URI was configured. The suite includes five `test_golden_path.py` tests, all of which passed; this is service/test-client evidence, not a real browser E2E flow. |
| Identity container-only full-suite attempt | The same `python -m pytest -q -rs -p no:cacheprovider` invocation run directly in `/app` of the service image, before creating the temporary source copy. | **Collection failed; 0 tests executed.** The image does not include repository-root `ssi_layer3_service` and root layout expected by the current tests. | This packaging/layout limitation was resolved for the test run by using a disposable tmpfs source copy; the image itself and repository were not modified. |
| Fraud Service targeted regression | `python -m pytest -q -rs -p no:cacheprovider tests/test_fraud_service.py tests/test_event_pipeline_and_dataset.py tests/test_layer2_fraud_detection.py` from a temporary copy of current `services/fraud-service` inside the existing Fraud image; `--network none`, repository mounted read-only. | **21 passed, 0 failed, 0 skipped, 2 warnings**, 1.15 s. | Direct execution in the service image first failed collection because the image does not include the service-root `standalone_fraud_api` module. The temporary source copy supplied the expected layout; it did not change image contents or project files. |
| Identity AI policy matrix | `python -m pytest -q -rs -p no:cacheprovider tests/integration/test_oid4vp_ai_policy_matrix.py` inside the rebuilt Identity service; Mongo disabled and test URI blank. | **8 passed, 0 failed, 0 skipped, 2 warnings.** | Tests the AI-policy boundary; it is not model-quality, fairness, or independent labeled-data evidence. |
| Repository-wide runner, attempt 1 | `& .\.venv\Scripts\python.exe run_tests.py` with Mongo disabled, test Mongo URIs blank, `PYTHONDONTWRITEBYTECODE=1`, and `PYTEST_ADDOPTS='-p no:cacheprovider -rs'`. | **Interrupted; no test summary or counts.** The process emitted no output for about one minute and was stopped with Ctrl+C (exit 1). | Not a pass or an assertion failure. No database file was created. |
| Repository-wide runner, attempt 2 | `& .\.venv\Scripts\python.exe -u run_tests.py` with the same environment. | **Interrupted; no test summary or counts.** It printed `Running tests for services/identity-service`, then stalled; Ctrl+C exit code `-1073741510`. | Not a pass or an assertion failure. The runner's aggregate behavior remains unresolved; the earlier 820/13/0 result is historical only. |

The focused R1–R3/OID4VP tests (52 passed), full Identity regression (708 passed, 12 environment skips), policy matrix (8 passed), frontend contract (8 checks), lint/build, current-source Docker health (7/7), HTTP probes (5×200 and 2×401), and Web bundle digest comparison jointly support **WP-08/G6 PASS for the documented L3 scope**. They do not establish suspension restoration, live authenticated browser/tenant flow, external L4 interoperability, or production readiness. The full repository runner has no fresh aggregate result.

The full-service test runs used these exact disposable-container wrappers (PowerShell CWD was the repository root); the bind mount was read-only, package pulls were disabled, networking was disabled, and all source copies/output remained in the container's temporary filesystem:

```powershell
docker run --rm --pull=never --network none --tmpfs /tmp:rw,nosuid,nodev,size=1g --mount "type=bind,source=$((Get-Location).Path),target=/source,readonly" --workdir /tmp --entrypoint sh wp08-l3-20261013-identity-service -c "mkdir -p /tmp/secure-ssi-platform/services && cp -a /source/services/identity-service /tmp/secure-ssi-platform/services/identity-service && cp /source/docker-compose.yml /tmp/secure-ssi-platform/docker-compose.yml && cp /source/.env.example /tmp/secure-ssi-platform/.env.example && cd /tmp/secure-ssi-platform/services/identity-service && PYTHONDONTWRITEBYTECODE=1 IDENTITY_MONGO_ENABLED=false IDENTITY_TEST_MONGODB_URI= PYTEST_ADDOPTS='-p no:cacheprovider' python -m pytest -q -rs -p no:cacheprovider"

docker run --rm --pull=never --network none --tmpfs /tmp:rw,nosuid,nodev,size=512m --mount "type=bind,source=$((Get-Location).Path),target=/source,readonly" --workdir /tmp --entrypoint sh wp08-l3-20261013-fraud-service -c "mkdir -p /tmp/secure-ssi-platform/services && cp -a /source/services/fraud-service /tmp/secure-ssi-platform/services/fraud-service && cd /tmp/secure-ssi-platform/services/fraud-service && PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='-p no:cacheprovider' python -m pytest -q -rs -p no:cacheprovider tests/test_fraud_service.py tests/test_event_pipeline_and_dataset.py tests/test_layer2_fraud_detection.py"
```

At final report refresh, a read-only re-query of `docker compose -p wp08-l3-20261013 ps --all` could not connect to Docker Desktop's Linux Engine named pipe (`permission denied while trying to connect to the Docker API at npipe:////./pipe/dockerDesktopLinuxEngine`). Therefore the 7/7 healthy status above is the observed snapshot from the successful rebuild/verification, not a claim that the containers remain running now; current Docker availability is **BLOCKED** by that permission error.

### WP-09 readiness (inspection only)

G9/WP-09 implementation and **scoped L3 PASS** predate this verification and are recorded in the 15 October evidence. No WP-09 implementation was performed here. The targeted Fraud (21/21) and Identity AI-policy (8/8) tests passed. The implementation remains explicitly a deterministic `rule-heuristic-v1`, `NOT_TRAINED`, synthetic-data, advisory-only service with no independent labeled evaluation. One UI acceptance detail remains: `apps/web/src/pages/admin/AiFraudMonitorPage.tsx` passes `stats.dataset_label` through `readableStatus`, which strips the square brackets, so the exact required `[DEMO LAB / SYNTHETIC]` marker is not preserved on that page. This is a static code inspection, not browser verification. WP-09 is **READY AFTER CONDITIONS** for any further delivery that requires the literal marker: preserve the exact label in that UI and add a focused assertion; do not reinterpret the already recorded scoped G9 PASS as model validation.

### Dependency advisory disposition

The retained Web image-build output reports three npm advisories (two moderate, one high), but it contains no package names, dependency paths, advisory identifiers, affected version ranges, or fix availability. `npm.cmd audit --offline --json --prefix apps/web` exited 0 and returned an empty `vulnerabilities` object for the 264 listed dependencies; offline metadata cannot resolve the build-time aggregate. No package data was submitted to an external registry, and no dependency changes were made. To complete triage without an online request, the full audit JSON from the image build (including `via`, `range`, `nodes`, and `fixAvailable`) is required. Alternatively, the user can explicitly authorize a registry audit after reviewing its metadata transmission.

## Current-source revalidation — 23 October 2026 (continued)

This continuation corrects the earlier 23 October checkpoint after safe local branch migration and a second focused test run. Current branch is `besna-dev`, HEAD `9e965bb4de7f5e1bb1cbf0f48f30d53ebfb88b73`. The branch was created from local `main` at the same commit; local `origin/main` also points there, but no fetch was performed, so remote freshness is unknown. The source commit did not change. Older 15 October results remain historical evidence.

| ID | Exact command / working directory | Result | Scope and limit |
|---|---|---|---|
| CUR-WP08-01 | Initial sandboxed focused pytest run from `services/identity-service`: `& 'C:\Users\besna\OneDrive\Bureau\secure-ssi-platform\.venv\Scripts\python.exe' -m pytest -q -rs -o faulthandler_timeout=15 tests/integration/test_wp08_remediation_status_security.py tests/integration/test_wp08_policy_evaluation.py tests/integration/test_issuance_interoperability.py tests/integration/test_oid4vp_session_authorization.py` | **Interrupted, no pytest summary.** The process hung in Windows asyncio/AnyIO `socketpair` setup and was stopped with Ctrl+C; not counted as a test failure or pass. | Environment permission limitation; no test-scope expansion. |
| CUR-WP08-02 | Elevated rerun, same CWD and four test files: `$base = Join-Path $env:TEMP ('secure-ssi-wp08-focused-elevated-' + [guid]::NewGuid().ToString('N')); New-Item -ItemType Directory -Path $base | Out-Null; & 'C:\Users\besna\OneDrive\Bureau\secure-ssi-platform\.venv\Scripts\python.exe' -m pytest -q -rs -o faulthandler_timeout=15 tests/integration/test_wp08_remediation_status_security.py tests/integration/test_wp08_policy_evaluation.py tests/integration/test_issuance_interoperability.py tests/integration/test_oid4vp_session_authorization.py --basetemp=$base; exit $LASTEXITCODE` | Exit 0; **52 passed, 0 failed, 0 skipped, 2 warnings**. Pytest reported `17863.41s` (about 4 h 57 min); this unusually high reported duration is recorded as emitted, not independently validated wall time. | Current R1–R3, policy/issuance and OID4VP session authorization. In-process TestClient tests; not current-source Docker/API or browser E2E. Warnings: SQLite production-target deprecation and Starlette/httpx TestClient deprecation. |
| CUR-ROOT-01 | Repo root: `& .\.venv\Scripts\python.exe run_tests.py` | **Previously observed on the same unchanged HEAD:** exit 0; 820 passed, 13 skipped, 0 failed, plus 246 subtests. Not rerun in this continuation. | Runner did not emit skip reasons. Host test evidence, not Docker runtime evidence. |
| CUR-FE-01 | Repo root: `node --experimental-strip-types apps/web/tests/verifyPresentation_fail_closed.test.ts` | Exit 0; **8 checks passed**. | Fail-closed frontend result-normalization contract. |
| CUR-FE-02 | Repo root: `npm.cmd run lint --prefix apps/web` | Exit 0; no ESLint diagnostics. | Static lint only. |
| CUR-FE-03 | Repo root: `npm.cmd run build --prefix apps/web` | Exit 0; TypeScript/Vite 6.4.3; **1,830 modules transformed**. | Current local production build; does not prove the running image contains it. |
| CUR-DC-01 | Read-only Docker/Compose inspection: `docker compose -p wp08-l3-20261013 ps --all` and image/container metadata | Docker Desktop/Engine 29.8.1 available; existing target project **7/7 containers healthy**. Backend containers were created 18 October, before the 22 October OID4VP security commit; no OCI source-revision labels were present. | Health and image metadata only. No container was recreated. Other project's containers and both named project data volumes were left untouched. |
| CUR-HTTP-01 | Read-only HTTP probes executed inside the running containers: Web `/`; Gateway, Identity, Fraud and Recovery `/health` | **5/5 HTTP checks returned 200.** | Existing images only, not proof of current source. Host-side `Invoke-WebRequest` probes were blocked by sandbox `HttpRequestException`; no state-changing or authenticated security API smoke test was sent. |
| CUR-DC-02 | Read-only artifact comparison | Running Web references `index-C7R2dkgq.js`; current local build references `index-B6PGGrvY.js`. Backend images have no revision labels and predate current backend source. | The served runtime does not match the current local frontend bundle; backend source provenance is not established. |
| CUR-DC-GATE | Exact requested build attempt: `docker compose -p wp08-l3-20261013 --progress plain build --no-cache web api-gateway identity-service fraud-service recovery-service` | **BLOCKED before execution by automatic approval review, on two attempts.** No image was built, package downloaded, cache mutated, or service restarted by these rejected attempts. | The review required direct visible confirmation despite the attached task's build authorization and explicitly prohibited workaround/indirect execution. No alternate build path was attempted. |
| CUR-GIT-01 | Repo root: `git status --short --branch`; `git rev-parse HEAD`; `git diff --cached --name-only`; `git diff --check` | Branch `besna-dev`; HEAD and local `main`/`origin/main` refs all `9e965bb4de7f5e1bb1cbf0f48f30d53ebfb88b73`; four tracked documentation files modified, one pre-existing untracked audit directory retained, no staged paths; `git diff --check` exit 0 (line-ending notices only). | No fetch was done, so remote freshness is unknown. No code files changed, no commit, push, or merge. |

**Current decision:** R1, R2, R3, and OID4VP session authorization are **PASS in the executed focused-test scope**. Current-source Docker L3 is **BLOCKED**, so overall WP-08 remains **PARTIAL** and WP-09 must not start. Current container health is not current-source provenance. Suspension restoration, L4 interoperability, production readiness, and browser Golden Path are not claimed. No application code changed; no commit, push, or staging occurred.

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
