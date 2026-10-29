# WP-08 FINAL ACCEPTANCE GATE REPORT

## Current-source Docker L3 verification — 24 October 2026

This entry supersedes the 23 October `BLOCKED` Docker decision for branch `besna-dev`, HEAD `9e965bb4de7f5e1bb1cbf0f48f30d53ebfb88b73`. The repository source revision did not change. The five application images were rebuilt without cache from the verified Compose contexts and recreated. No application source files were edited during this verification. Docker images do not contain `org.opencontainers.image.revision` or `.source` labels; provenance is established here by the recorded branch/HEAD, exact local no-cache build command, Compose contexts, and matching served/local Web bundle digest, not by OCI attestation.

| Acceptance item | Current result | Evidence and boundary |
|---|---|---|
| R1 — status/persistence fail closed | **PASS in focused integration tests** | The rebuilt Identity container ran the WP-08 remediation suite; unavailable/throwing/timeout/missing persistence and trust inputs reject. |
| R2 — revocation/suspension purpose and enforcement | **PASS in focused integration tests** | Tests cover active and inactive suspension bits, persisted suspended/revoked states, malformed or unsupported purposes, and invalid indices. Suspension restoration/lifecycle transitions are not claimed. |
| R3 — status-list authenticity | **PASS in focused integration tests** | Tests cover proof/signature, issuer/trust, tampered list/proof, malformed credential, publication binding, and index failure cases. No independent peer conformance is claimed. |
| OID4VP session authorization | **PASS in focused integration tests; live unauthenticated probe returned 401** | The integration test verifies authenticated owner access, unauthenticated rejection, a different verifier returning the same 404 as a guessed ID, holder request-context limits, and fail-closed behavior without persisted ownership. The live HTTP probe covered unauthenticated access only; it did not create or submit a live session. |
| Focused WP-08/OID4VP suite | **PASS: 52 passed, 0 failed, 0 skipped, 2 warnings** | Four test files ran inside the rebuilt Identity container; exact command is in the test-evidence register. |
| Full Identity Service regression (24 October follow-up) | **PASS: 708 passed, 0 failed, 12 skipped, 3 warnings** | Ran from current source in an isolated, no-network test container. Seven live-Mongo tests and five Hardhat-dependent tests were skipped; exact evidence is in the test-evidence register. |
| Repository-wide test runner | **Attempted; interrupted without a test summary** | Two attempts did not produce suite totals. An earlier run on the same HEAD reported 820 passed, 13 skipped, 0 failed, plus 246 subtests; that remains historical evidence only. |
| Five current-source application images | **PASS** | Explicit `--no-cache` Compose build exited 0 for `web`, `api-gateway`, `identity-service`, `fraud-service`, and `recovery-service`. The Web build ran lint and TypeScript/Vite production compilation (1,830 modules). |
| Compose recreation and health | **PASS: 7/7 healthy** | The five targets were force-recreated with `--no-build`; MongoDB and Redis were retained, not rebuilt or removed. Both named project data volumes remained present. |
| Web bundle served by the running container | **PASS: exact digest match** | HTTP `GET /` and the referenced JavaScript returned 200. Served `index-C7R2dkgq.js` and `apps/web/dist/assets/index-C7R2dkgq.js` both SHA-256 `211B4531725937B891AF637BAB60B1CF5878E669A3FE6A48FE8A40F1874B2259`. |
| Live API smoke | **PASS: 5 HTTP 200, 2 HTTP 401** | Web `/` and Gateway, Identity, Fraud, Recovery `/health` returned 200. Unauthenticated OID4VP request retrieval through Identity and Gateway returned 401. No mutation API was called. |

### Current-source decision

**WP-08 acceptance for the scoped R1–R3, policy, OID4VP authorization, and current-source Docker L3 checks: PASS.** The full Identity Service regression also passed with the 12 environment-gated skips listed above. The repository-wide runner was attempted twice in the follow-up but did not yield a test summary; its earlier 820-pass result remains historical. The pre-existing current-source `BLOCKED` status is superseded by the successful rebuild and observed runtime results above. No WP-09 code was changed in this verification; G9/WP-09 implementation and a scoped PASS are already recorded in the 15 October plan update. This is not a claim of a full authenticated browser Golden Path, an authenticated live-network owner/cross-organization session trace, suspension restoration, independent L4 interoperability, or production readiness. npm reported 3 dependency advisories during the Web image build (2 moderate, 1 high); package names, dependency paths, advisory identifiers, and fixes were not present in the retained build summary and remain unassessed.

Exact commands, container/image metadata, health results, API probes, and limitations are recorded in `docs/implementation/SECURE_SSI_PLATFORM_TEST_EVIDENCE.md` under the 24 October entry.

## Current-source revalidation — 23 October 2026

This entry supersedes prior WP-08 status claims **for the current source revision only**. Current branch `besna-dev` is at HEAD `9e965bb4de7f5e1bb1cbf0f48f30d53ebfb88b73`, created locally from `main` at that same commit. Local `origin/main` points to the same commit, but no fetch was performed and remote freshness is unknown. The 15 October Docker/L3 acceptance below applies to its then-tested source snapshot (`59e8933...`) and is historical evidence only.

| Acceptance item | Current result | Evidence and boundary |
|---|---|---|
| R1 — status/persistence fail closed | **PASS in executed tests** | Current WP-08 remediation API tests passed in the focused run and in the full Identity suite. |
| R2 — revocation/suspension enforcement | **PASS in executed tests** | Purpose/status enforcement and rejection paths passed. Suspension restoration/lifecycle transitions remain unimplemented and are not claimed. |
| R3 — status-list authenticity | **PASS in executed tests** | Current status proof/authenticity and policy rejection cases passed. No independent peer conformance is claimed. |
| OID4VP session authorization | **PASS in executed tests** | The current `test_oid4vp_session_authorization.py` was included in the focused run; no live current-source Docker API path was exercised. |
| Focused WP-08 + OID4VP authorization | **PASS: 52 passed, 0 failed, 0 skipped, 2 warnings** | Four current Identity integration files, rerun with elevated local-process permission after the sandboxed attempt hung. Pytest emitted runtime `17863.41s`; this unusual duration is not independently validated. |
| Full repository runner | **Previously observed PASS: 820 passed, 13 skipped, 0 failed; 246 subtests passed** | Same unchanged HEAD; not rerun during this continuation. `run_tests.py` did not emit skip reasons. |
| Frontend fail-closed | **PASS: 8 checks** | Current source test `verifyPresentation_fail_closed.test.ts`. |
| Frontend lint/build | **PASS** | `npm.cmd run lint --prefix apps/web` exit 0; `npm.cmd run build --prefix apps/web` exit 0, 1,830 modules transformed. |
| Existing Docker runtime availability | **PASS, runtime only** | Docker Desktop/Engine 29.8.1; the existing target Compose project reports 7/7 healthy. Container-internal Web `/` and Gateway, Identity, Fraud, Recovery `/health` returned HTTP 200 (5/5). Host-side probes were blocked by sandbox `HttpRequestException`. |
| Current-source Docker provenance/L3 | **BLOCKED** | Backend containers were created 18 October, before the 22 October OID4VP security commit, and have no OCI source-revision labels. Running Web references `index-C7R2dkgq.js`; current local build references `index-B6PGGrvY.js`. The exact five-image `--no-cache` build command was rejected before execution by automatic approval review on two attempts. No workaround was attempted; no images or containers were changed. |

### Current-source decision

**WP-08 is PARTIAL at current HEAD: R1–R3 and OID4VP authorization pass the executed tests, but current-source Docker L3 is BLOCKED. Do not start WP-09.** The attached task authorized the build, but automatic approval review rejected the command and explicitly barred an indirect workaround. Direct visible user confirmation may be required before retrying. L4 interoperability, suspension restoration, production readiness, and a browser Golden Path remain unclaimed. No source-code fix was indicated by the tests; no commit or push was made.

Exact commands and observations are recorded in `docs/implementation/SECURE_SSI_PLATFORM_TEST_EVIDENCE.md` under the 23 October current-source revalidation.

## Final validation continuation — 2026-10-13

This dated addendum supersedes the 2026-10-12 status below. The controlling Final Implementation Plan and its G6 criteria are unchanged. **WP-08: PASS for the scoped G6/L3 acceptance evidence below. WP-09 remains gated and has not started. L4 interoperability is not claimed.**

### Acceptance evidence

| Requirement | Result | Current evidence and boundary |
|---|---|---|
| R1 — fail-closed status and persistence | **PASS** | Focused API tests exercise missing/unconfigured/throwing/timed-out status service, missing publication, persistence lookup failure, and quarantine lookup failure; non-acceptance is asserted at the final API policy result. |
| R2 — status purpose and terminal states | **PASS for enforcement** | Revocation/suspension purpose handling, set/unset bits, persisted `REVOKED`/`SUSPENDED`, invalid purpose/index, and bounds are covered. Suspension restoration/lifecycle transitions remain unimplemented and are not claimed. |
| R3 — status-list authenticity | **PASS** | Focused API tests cover signed proof acceptance and tampered/missing/unsupported proof, issuer/trust and verification-method failures, URL/publication mismatch, metadata/time, and index checks before status is trusted. |
| Backend/UI authority | **PASS** | Policy API and frontend fail-closed tests show backend `REJECTED` cannot be overridden by legacy UI fields, and missing status is not rendered as valid. |
| WP-08 focused suite | **PASS: 48 passed, 0 failed, 0 skipped** | The exact three required files were rerun after the final application changes from `services/identity-service`; Python 3.11 existing venv; `-o faulthandler_timeout=15`; fresh scratch `--basetemp`. |
| Identity regression | **PASS: 665 passed, 14 skipped, 0 failed** | Repeated with `-rs`; 5 skips need a live Hardhat node on port 8545, 7 need `IDENTITY_TEST_MONGODB_URI`, and 2 need live Hardhat. Three deprecation warnings remain. These optional integration checks did not run. |
| Frontend fail-closed | **PASS: 8 passed** | `node --experimental-strip-types apps/web/tests/verifyPresentation_fail_closed.test.ts`; frontend source was unchanged after this check. |
| Current-source Docker/runtime | **PASS for app stack** | Compose configuration and app images built successfully; the post-fix Identity image was rebuilt and recreated. All 7 isolated project services report healthy. Gateway, Identity, Fraud, Recovery `/health` and Web `/` each returned HTTP 200. No error/traceback was present in current Identity startup/runtime logs. |

The focused command, run from `services/identity-service`, was:

```powershell
& ..\..\.venv\Scripts\python.exe -m pytest -q -o faulthandler_timeout=15 tests/integration/test_wp08_remediation_status_security.py tests/integration/test_wp08_policy_evaluation.py tests/integration/test_issuance_interoperability.py --basetemp=$base
```

`$base` was a fresh GUID-named directory beneath the authorized Codex scratch directory. The final Identity regression command was `& ..\..\.venv\Scripts\python.exe -m pytest -q -rs --basetemp=$base` from the same directory.

Docker commands executed with isolated project name `wp08-l3-20261013`:

```powershell
docker compose -p wp08-l3-20261013 config --quiet
docker compose -p wp08-l3-20261013 build
docker compose -p wp08-l3-20261013 build identity-service
docker compose -p wp08-l3-20261013 up -d
docker compose -p wp08-l3-20261013 up -d identity-service
docker compose -p wp08-l3-20261013 ps --all
```

The identity blockchain status endpoint returned HTTP 200 with `connected: false`; Gateway system status returned HTTP 200 with Gateway `ONLINE`, Identity/Fraud/Recovery `HEALTHY`, blockchain `DEGRADED`, and overall `PARTIAL`. The optional chain was not configured or started, so no anchor is fabricated. The local web app is left running at `http://localhost:3000` for owner review.

### Broader repository runner — residual failures outside WP-08

The documented root command `& .\.venv\Scripts\python.exe run_tests.py` exited 1: **770 passed, 3 failed, 14 skipped**, plus 147 subtests. Identity (665 passed/14 skipped), Recovery (46), Fraud (22), API Gateway (15), and shared (7 plus 19 subtests) passed. The 3 root failures are:

1. `tests/test_admin_console_integration.py::TestAdminConsoleLiveIntegration::test_system_status_aggregation` expects a connected blockchain; the configured optional node is offline and the truthful aggregate is `PARTIAL`.
2. `tests/test_admin_console_integration.py::TestAdminConsoleLiveIntegration::test_blockchain_status_and_contracts_directory` expects `connected: true`; the endpoint now responds 200 and accurately reports `connected: false` without a live node.
3. `tests/test_admin_console_integration.py::TestAdminConsoleLiveIntegration::test_database_stats_telemetry` calls a legacy database-stats route that currently returns 404. This is outside WP-08 status/trust scope and remains open; no unrelated telemetry API was added.

These root-runner failures do not invalidate the passing WP-08-specific API and runtime evidence, but the repository-wide runner is **not green**. The new Identity Service CI job is present in `.github/workflows/ci.yml`; no remote GitHub Actions run was triggered, so CI execution is not claimed. Docker build/runtime evidence is local to the isolated Compose project; it is not a production deployment claim.

The 2026-10-12 history below is retained as a point-in-time record and is superseded where it conflicts with this addendum.

## Final validation continuation — 2026-10-12

This addendum supersedes the prior 2026-10-12 status below. The controlling revised Master Implementation Plan remains authoritative. **WP-08 status: PARTIAL; its R1–R3 and API policy acceptance tests now pass, but L3 is not closed because current-source Docker build/runtime/health evidence is still unavailable. Do not start WP-09.** L4 interoperability is not claimed.

### Remediation and test corrections

- `services/identity-service/app/services/credential_validator.py` now accepts `credentialStatus` as either one entry object or a non-empty array of entries, validates each entry, and rejects an empty array. This matches the W3C VC Data Model set representation while retaining the project's revocation/suspension profile checks.
- The WP-08 API test helper can create a genuinely signed, intentionally malformed status value by bypassing only status-profile validation during fixture construction. Production validation remains unchanged and rejects those malformed credentials; the API tests then independently verify the fail-closed status decision.
- The Golden Path and OID4 protocol tests previously required `blockchainAnchored=true` even though no receipt-backed anchor was configured. The revised Master Plan makes anchoring optional. The assertions now require the truthful `false` value and preserve `finalPolicyResult=ACCEPTED`; no anchor was fabricated and no anchoring feature was implemented.
- The first API execution exposed five test-fixture failures before the endpoint was reached. The causes were strict profile validation of deliberately malformed fixture data and a status-list URL outside the project's accepted identifier shape. The fixture and URL were corrected; the required suite then passed.

### WP-08 acceptance evidence

| Requirement | Current result | Evidence boundary |
|---|---|---|
| R1 — fail-closed status and persistence | **PASS in focused API tests** | Missing/unconfigured/throwing/timed-out status service, missing publication, persistence lookup failure, and quarantine lookup failure return non-acceptance. This is current in-process API evidence, not container health evidence. |
| R2 — revocation, suspension, and purpose | **PASS for enforcement** | Active revocation/suspension and persisted terminal states reject; inactive suspension is accepted; malformed/unsupported purpose, empty entry set, unsupported type, and invalid indices fail closed. **Suspension restoration is not implemented or claimed.** |
| R3 — status-list authenticity | **PASS in focused API tests** | Signed status-list proof acceptance and tampered list/proof, missing/unsupported proof, wrong/untrusted issuer, unauthorized verification method, URL/publication mismatch, bad metadata, invalid time, and index bounds are covered. |
| Policy and UI result authority | **PASS** | WP-08 policy API tests and frontend regressions pass; a backend `REJECTED` result cannot be overridden by legacy frontend success fields, and missing status remains `UNKNOWN`. |
| WP-08 focused suite | **PASS: 48 passed, 0 failed, 0 skipped** | Exact files: `test_wp08_remediation_status_security.py`, `test_wp08_policy_evaluation.py`, `test_issuance_interoperability.py`. The final run used the existing Python 3.11 virtual environment, `-o faulthandler_timeout=15`, and a fresh `--basetemp` under the authorized Codex scratch directory. |

The focused command was run from `services/identity-service`:

```powershell
& ..\..\.venv\Scripts\python.exe -m pytest -q -o faulthandler_timeout=15 tests/integration/test_wp08_remediation_status_security.py tests/integration/test_wp08_policy_evaluation.py tests/integration/test_issuance_interoperability.py --basetemp=$base
```

`$base` was a fresh GUID-named directory under `C:\Users\besna\.codex\visualizations\2026\10\11\01a12bbb-0e4d-71e2-b270-dfff9dda2ede`. The run required approved elevated local execution because ordinary sandbox execution stalled in Windows `socketpair`/Starlette `TestClient` startup. No Windows security setting was changed.

### Regression and end-to-end results

| Scope | Exact pytest file(s) or command | Result |
|---|---|---|
| Credential status array proof regression | `tests/integration/test_credential_proof_service.py` (run with the WP-08 focus files) | Included in **77 passed, 0 failed, 0 skipped** combined run. |
| WP-01 | `tests/integration/test_wp01_fail_closed_verification.py` | **14 passed**. |
| WP-02 | `tests/integration/test_wp02_holder_binding_verification.py` | **16 passed**. |
| WP-03 | `tests/integration/test_wp03_trust_registry.py` | **16 passed**. |
| WP-04 | `tests/integration/test_wp04_oid4vp_dcql.py` | **19 passed**. |
| WP-05 | `tests/integration/test_wp05_oid4vci_token_and_proof.py` | **18 passed**. |
| WP-06 | No exact WP-06 suite exists. Supporting `tests/test_composite_did_resolver.py`, `tests/test_did_key_resolver.py`, `tests/test_did_web_resolver.py` | **24 passed**; supporting DID evidence only, not a WP-06 acceptance claim. |
| WP-07 | `tests/integration/test_wp07_wallet_consent_presentation_proof.py` | **27 passed**. |
| AI policy guard matrix | `tests/integration/test_oid4vp_ai_policy_matrix.py` | **7 passed**. Test-only regression; no WP-09 implementation started. |
| Golden Path | `tests/integration/test_golden_path.py` | **5 passed** after aligning the optional-anchor assertion. |
| OID4 protocol lifecycle | `tests/integration/test_oid4_protocols.py` | **3 passed** after aligning its optional-anchor assertion. |
| Full Identity Service | `python -m pytest -q --basetemp=$base` from `services/identity-service` | **664 passed, 14 skipped, 0 failed**; 3 deprecation warnings; 144.14 seconds. |
| Repository runner | `.\.venv\Scripts\python.exe run_tests.py` from repository root | **Exit 0**. Identity 664 passed/14 skipped; Recovery 46 passed; Fraud 22 passed; API Gateway 15 passed; shared tests 7 passed/19 subtests; root tests 10 passed/8 skipped/128 subtests. Aggregate: **764 passed, 22 skipped, 0 failed**, plus 147 subtests. |
| Frontend fail-closed | `node --experimental-strip-types apps/web/tests/verifyPresentation_fail_closed.test.ts` | **8 passed**. |
| Frontend lint | `cmd /c "npm run lint --prefix apps/web"` | **Exit 0**, no diagnostics. |
| Frontend build | `cmd /c "npm run build --prefix apps/web"` | **Exit 0**; TypeScript passed; Vite transformed 1,827 modules. |
| Whitespace | `git diff --check` | **Exit 0**, no whitespace errors; only Git LF-to-CRLF notices on existing edited text files. |

The separate Broken Paths suite does not exist; its negative cases are exercised by the WP-01–WP-05, WP-07, WP-08, and AI policy regression files above. The 14 full-service skips and 8 root-test skips are retained as skips, not reported as passes. Common warnings were SQLite's production-target deprecation, Starlette/httpx TestClient deprecation, and Pydantic v2 class-based configuration deprecations.

### Docker and L3 release gate

- `docker version` succeeds under approved elevated execution: Docker Desktop 4.93.0, Engine 29.8.1, `desktop-linux`.
- `docker compose config --quiet` succeeds. Compose declares MongoDB, Identity, Recovery, Redis, API Gateway, Web, and Fraud services.
- Existing application images were created on **2026-10-07**, before the current 2026-10-12 worktree changes, and carry no source-revision label. They cannot prove the current code.
- The project Dockerfiles run `pip install` or `npm install`; rebuilding may install/download packages and base images. The user's existing instruction forbids installing software or downloading runtimes. Therefore no image build, Compose startup, health probe, HTTP smoke test, or container log inspection was run. Existing containers were not started, stopped, or modified.

**L3 remains FAIL / BLOCKED at the Docker current-source runtime gate.** API/TestClient integration and the Golden Path pass, but the plan explicitly requires current Docker health/runtime evidence before L3 closure. To complete that gate, the device owner must authorize the isolated Compose build that runs the Dockerfile package-install steps, or provide fresh images demonstrably built from this worktree. Until then, WP-08 remains **PARTIAL** and WP-09 stays gated. No commit or push was created.

The local environment used Python 3.11.16 and passed the executed regression suites, but several installed package versions differ from the Identity Service pins documented in `requirements.txt`; no dependency was installed or changed. Results are therefore evidence for the current local environment, not a clean pinned-environment reproduction.

## Prior final validation continuation — 2026-10-12 (superseded)

## Remediation continuation — 2026-10-12

This section supersedes the earlier 2026-10-12 revalidation below. Earlier evidence remains historical and has not been relabeled as current. The revised Master Implementation Plan remains authoritative. **Decision: WP-08 is PARTIAL; L3 is FAIL; WP-09 remains blocked.** The newly identified quarantine fail-open path is corrected in source and covered by unit regressions, but the API policy tests and required runtime gates remain blocked.

### Changes made in this continuation

- `services/identity-service/app/application/services/oid4vp_service.py` now represents a missing, throwing, or non-boolean quarantine lookup as indeterminate. The final status/policy gate rejects that result and reports the reason. This path no longer reports `blockchainAnchored=true` without verifying an anchor for the presented credential.
- `services/identity-service/app/infrastructure/cache_and_anchor.py` no longer swallows an on-chain quarantine RPC exception and returns `False`.
- `services/identity-service/tests/unit/test_wp08_quarantine_fail_closed.py` adds four regressions for error, missing/invalid result, boolean result, and on-chain RPC error handling.
- `services/identity-service/tests/integration/test_wp08_remediation_status_security.py` adds API regressions for quarantine timeout, missing publication, document-issuer/publication-metadata mismatch, and Trust Registry timeout. They collected but could not execute in this Windows environment.

| WP-08 gate | Current status | Evidence boundary |
|---|---|---|
| R1 — status/persistence fail-closed | **PARTIAL / API BLOCKED** | Source and lower-level status-policy tests pass; status-service exceptions, missing publication, persistence exceptions, and quarantine failure API decisions are not executed. |
| R2 — revocation/suspension | **PARTIAL / API BLOCKED** | Verifier checks both purposes and persisted terminal states; the 98-test lower-level set passes. The OID4VP presentation decisions remain unverified. Suspension restoration is outside the documented lifecycle and is not claimed. |
| R3 — signed status-list credential | **PARTIAL / API BLOCKED** | Shared proof and bitstring/issuance lower-level tests pass. OID4VP status-list proof, Trust Registry, metadata-binding and final-policy cases remain unexecuted. |
| Trust Registry and policy result consistency | **PARTIAL / API BLOCKED** | Trust Registry source fails closed on repository errors; the pure policy unit suite passes. Credential/status-list issuer outcomes and HTTP result consistency were not executed through the API. |

The existing credential lifecycle explicitly has no suspension/resume endpoint. `docs/credential-revocation.md` permits suspended credentials to transition to revoked or expired, and the revised Master Plan §7 says not to claim restoration until lifecycle transitions are implemented and tested. No restoration transition was invented or claimed.

### Verification performed in this continuation

| Gate / exact command | Working directory | Result |
|---|---|---|
| `$scratchRoot = (Resolve-Path -LiteralPath 'C:\Users\besna\.codex\visualizations\2026\10\11\01a12bbb-0e4d-71e2-b270-dfff9dda2ede').Path; $base = Join-Path $scratchRoot 'wp08-remediation-20261012-unit-pass'; if (Test-Path -LiteralPath $base) { throw 'Refusing to reuse an existing test scratch directory' }; & ..\..\.venv\Scripts\python.exe -m pytest -q tests/unit/test_wp08_quarantine_fail_closed.py tests/unit/test_verification_policy.py tests/unit/test_credential_status_domain.py tests/unit/test_status_list_repositories_and_service.py tests/unit/test_bitstring_status_list.py tests/integration/test_credential_proof_service.py tests/integration/test_issuance_interoperability.py --basetemp=$base` | `services/identity-service` | **PASS: 98 passed, 0 failed, 0 skipped; exit 0.** One SQLite production-target deprecation warning. This verifies lower-level policy, lifecycle, proof, bitstring, status-list, issuance-interoperability, and the new quarantine unit cases; it does not execute the OID4VP status API assertions. |
| `& ..\..\.venv\Scripts\python.exe -m pytest --collect-only -q tests/integration/test_wp08_remediation_status_security.py tests/integration/test_wp08_policy_evaluation.py tests/integration/test_issuance_interoperability.py` | `services/identity-service` | **PASS: 41 collected; exit 0.** Collection only; 0 tests executed by this command. |
| `& ..\..\.venv\Scripts\python.exe -m pytest -vv -s -o faulthandler_timeout=8 tests/integration/test_wp08_remediation_status_security.py -k test_status_service_exception_fails_closed` | `services/identity-service` | **BLOCKED after collection.** One test selected; it stalled before the first request reached the application. Faulthandler showed `socket._fallback_socketpair → socket.accept → asyncio Proactor self-pipe → AnyIO start_blocking_portal → Starlette TestClient`. Interrupted after the 8-second diagnostic dump; exit 1; pytest emitted no pass/fail/skip count. |
| `& ..\..\.venv\Scripts\python.exe -m pytest -vv -s -o faulthandler_timeout=8 tests/integration/test_wp08_remediation_status_security.py tests/integration/test_wp08_policy_evaluation.py tests/integration/test_issuance_interoperability.py` | `services/identity-service` | **BLOCKED.** Pytest collected 41 tests and stalled in the first status-service test at the same Proactor socket-pair startup before application execution. Interrupted after the 8-second diagnostic dump; exit 1; 0 tests completed and no pytest totals were emitted. |
| `& ..\..\.venv\Scripts\python.exe -c "import asyncio, pytest; asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy()); raise SystemExit(pytest.main(['-vv','-s','-o','faulthandler_timeout=8','tests/integration/test_wp08_remediation_status_security.py','-k','test_status_service_exception_fails_closed']))"` | `services/identity-service` | **BLOCKED by the same socket-pair setup** under `WindowsSelectorEventLoopPolicy`; the stack ended in `asyncio.selector_events._make_self_pipe → socket._fallback_socketpair → socket.accept`. Interrupted after the diagnostic dump; exit 1; 0 tests completed. |
| `& ..\..\.venv\Scripts\python.exe -c "import importlib.util; print(importlib.util.find_spec('trio') is not None)"` and a minimal `TestClient(..., backend='trio')` probe | Repository root | **BLOCKED: Trio is not installed.** The probe raised `LookupError: Backend 'trio' is not available`; no package was installed. |
| `& ..\..\.venv\Scripts\python.exe -m pytest -q tests/unit/test_wp08_quarantine_fail_closed.py tests/unit/test_verification_policy.py tests/unit/test_credential_status_domain.py tests/unit/test_status_list_repositories_and_service.py tests/unit/test_bitstring_status_list.py tests/integration/test_credential_proof_service.py tests/integration/test_issuance_interoperability.py` | `services/identity-service` | **ENVIRONMENT ERROR: 96 passed, 2 setup errors, exit 1.** Both errors were `tmp_path` creation under sandbox-protected `AppData\Local\Packages\...\Temp`. Rerunning the same scope with a fresh `--basetemp` inside the authorized Codex visualization workspace produced the 98-pass result above. No application files were changed to work around the temp-path restriction. |
| `node --experimental-strip-types apps/web/tests/verifyPresentation_fail_closed.test.ts` | Repository root | **PASS: 7/7; exit 0.** |
| `cmd /c "npm run lint --prefix apps/web"` | Repository root | **PASS; exit 0**, no lint diagnostics. |
| `cmd /c "npm run build --prefix apps/web"` | Repository root | **PASS; exit 0.** TypeScript passed; Vite transformed 1,827 modules. |
| `$scratchRoot = (Resolve-Path -LiteralPath 'C:\Users\besna\.codex\visualizations\2026\10\11\01a12bbb-0e4d-71e2-b270-dfff9dda2ede').Path; $env:UV_CACHE_DIR = Join-Path $scratchRoot 'uv-cache-wp08-check'; uv pip check --python '.\.venv\Scripts\python.exe'` | Repository root | **PASS: 78 installed packages compatible; exit 0.** This checks installed package metadata; it does not prove the environment matches every pinned version or perform a vulnerability database scan. |
| `git diff --check` | Repository root | **PASS; no whitespace errors.** Git emitted only existing LF-to-CRLF conversion warnings for three already-modified files. |

### Runtime and unexecuted acceptance gates

The repository virtual environment runs Python 3.11.16 and imports `_sqlite3`; its installed versions include FastAPI 0.141.1, Starlette 1.7.0, Pydantic 2.13.5, httpx 0.28.1, and pytest 9.1.1, which differ from several Identity Service pins. `uv pip check` found the installed set internally compatible. The verified stack localizes the API hang to Windows loopback socket-pair setup before the application request; the same failure occurs with both Proactor and Selector policies. A system Python 3.12.7 exists but has no pytest, FastAPI, or httpx. The `py -0p` launcher reports no registered Python installations.

WSL is present, but both `wsl --status` and `wsl --list --quiet` return `WSL/E_ACCESSDENIED` (exit 1). Docker CLI 29.8.1 selects context `desktop-linux` at `npipe:////./pipe/dockerDesktopLinuxEngine`; `docker version` returns `permission denied` opening that pipe (exit 1). No containers or services were started. No repository-documented dependency vulnerability scanner was found; no network-backed audit was run.

The following gates remain **BLOCKED or NOT RUN**, not passed: R1–R3 OID4VP API outcomes, Trust Registry API behavior, Golden Path, Broken Paths, WP-01–WP-07 API regression, AI policy matrix, full `run_tests.py`, Docker build/runtime/health, and HTTP smoke tests. The exact required set remains the 41 collected tests above. Lower-level passes do not substitute for these end-to-end results. No current L3 acceptance or L4 interoperability claim is made.

Before this continuation, the worktree already contained 22 modified tracked files and four untracked files (the three planning documents and the WP-08 integration test). This continuation edited five files: the existing modified `oid4vp_service.py` and acceptance report, `cache_and_anchor.py`, the existing untracked WP-08 integration test, and the new quarantine unit test. The planning documents and all other prior changes remain intact. No commit or push was created. Current branch remains `main`, HEAD remains `59e8933f6e47922ba5a82cb7c9d76632e7edefe1`.

## Previous WP-08 revalidation — 2026-10-12 (superseded)

This addendum supersedes the 2026-10-11 revalidation below. That earlier section remains unchanged as historical evidence. The repository was already on `main` at `59e8933f6e47922ba5a82cb7c9d76632e7edefe1`; `origin/main`'s local ref matched. Before this revalidation, the worktree already contained 13 modified files and one untracked WP-08 integration test. No pre-existing changes were discarded, reset, stashed, or overwritten. No commit or push was made.

**Executive decision: `WP-08 PARTIAL — DO NOT START WP-09`. L3 is FAIL.** R1–R3 implementation changes and regression cases are present, but the API integration tests stall while initializing Starlette's `TestClient` on this Windows runtime. Docker's CLI is installed but cannot reach its daemon. The required release evidence is therefore incomplete.

### Findings and implementation evidence

| Requirement | Current code change | Evidence and decision |
|---|---|---|
| R1 — status resolver and persistence failures | `oid4vp_service.py` maps persistence/status-service failures to a false status check with deterministic reason text; exception details are limited to exception class names. | Related integration cases collect, but the API tests did not complete. **BLOCKED**, not accepted. |
| R2 — revocation and suspension | The verifier checks `revocation` and `suspension` independently; set bits and persisted `REVOKED`/`SUSPENDED` states reject. Unsupported/malformed purpose and index values reject. The schema/domain now represent both purposes. | Cases collect; none of the OID4VP status API cases completed. **BLOCKED**, not accepted. |
| R3 — signed status-list credential | The verifier validates the status-list VC structure and types, expected id/issuer/purpose, existing Data Integrity proof service, DID verification-method authorization, Trust Registry decision and `validFrom` before decoding `encodedList`. The decoder enforces the W3C multibase prefix, bounded gzip output, minimum length and index bounds. | Static diff review and lower-level proof/decoder tests passed; the OID4VP integration assertions did not execute. **BLOCKED**, not accepted. |
| Frontend status and proof truthfulness | Missing credential status now maps to `UNKNOWN`; demo fallbacks no longer claim active status or fabricated indices. Credential detail views no longer claim signature verification or synthesize a status-list entry. The verifier matrix uses neutral text when backend status details are absent and renders the backend `finalPolicyResult`. | Frontend fail-closed checks, lint and build passed; these results do not prove backend R1–R3. |

### Files recorded at the previous revalidation

At that time, the tracked/untracked inventory below contained 22 modified tracked files and the WP-08 integration test. The three planning documents were separate pre-existing untracked files and were not part of that earlier list.

- `apps/web/src/components/credentials/CredentialCard.tsx`
- `apps/web/src/components/credentials/CredentialDetailModal.tsx`
- `apps/web/src/components/portals/HolderPortal.tsx`
- `apps/web/src/components/portals/IssuerPortal.tsx`
- `apps/web/src/components/verification/NinePointVerificationMatrix.tsx`
- `apps/web/src/pages/holder/CredentialDetailPage.tsx`
- `apps/web/src/pages/holder/WalletDashboard.tsx`
- `apps/web/src/pages/issuer/RevocationRegistryPage.tsx`
- `apps/web/src/pages/verifier/CreateRequestPage.tsx`
- `apps/web/src/pages/verifier/VerifyPresentationPage.tsx`
- `apps/web/src/services/api.ts`
- `apps/web/tests/verifyPresentation_fail_closed.test.ts`
- `reports/V2_1_WP08_FINAL_ACCEPTANCE.md`
- `services/identity-service/app/api/v1/dependencies.py`
- `services/identity-service/app/application/services/credential_proof_service.py`
- `services/identity-service/app/application/services/oid4vp_service.py`
- `services/identity-service/app/application/services/status_list_service.py`
- `services/identity-service/app/domain/bitstring_status_list.py`
- `services/identity-service/app/infrastructure/status_list_document_generator.py`
- `services/identity-service/app/schemas/status_list_api.py`
- `services/identity-service/app/services/credential_validator.py`
- `services/identity-service/tests/unit/test_bitstring_status_list.py`
- `services/identity-service/tests/integration/test_wp08_remediation_status_security.py` (untracked)

The generic VC Data Model makes `credentialStatus` optional. The platform's local issuance flow assigns status entries; this revalidation does **not** turn that into a universal rejection rule for every otherwise valid VC. The verifier evaluates a status entry when one is supplied and reports when none was supplied. The current credential profile validator accepts one status-entry object; it rejects arrays, so multi-entry VC processing is not supported by the pinned local profile. `StatusListService` can publish by either purpose, but the issuance lifecycle currently allocates revocation entries and has no complete suspension restore transition. Suspension restoration is therefore not claimed or tested.

### Standards and reference research

The revised Master Implementation Plan is the engineering authority. Its frozen baseline is VC Data Model 2.0, Data Integrity 1.0, `eddsa-jcs-2022`, and Bitstring Status List 1.0; Bitstring 1.1 is a Working Draft and was not adopted.

- **STANDARD REQUIREMENT:** VC Data Model 2.0 permits `credentialStatus` to be omitted. When Bitstring Status List 1.0 is used, verify the list credential and proof before relying on its encoded data, match the entry purpose, and reject invalid indices. Revocation is irreversible; suspension is temporary and reversible. [VC Data Model 2.0](https://www.w3.org/TR/vc-data-model-2.0/), [Bitstring Status List 1.0](https://www.w3.org/TR/vc-bitstring-status-list/), [Data Integrity 1.0](https://www.w3.org/TR/vc-data-integrity/).
- **PROJECT PROFILE:** Local issuance binds credentials to the project's W3C Bitstring Status List 1.0 service. Proof verification uses `DataIntegrityProof` with `eddsa-jcs-2022`, Ed25519 and `assertionMethod`, as frozen by the revised plan. The general VC optionality is preserved; status is not made universally mandatory by this remediation. [EdDSA Cryptosuites 1.0](https://www.w3.org/TR/vc-di-eddsa/).
- **IMPLEMENTATION CHOICE:** Status-list issuer identity is checked against the publication and evaluated through the existing Trust Registry; it need not equal the credential issuer. Shared proof infrastructure is reused rather than adding another Ed25519 verifier. Local publication id, issuer, purpose and list-length comparisons bind the response to stored publication metadata.

Reference evidence was kept distinct from normative requirements. The [walt.id status-service documentation](https://docs.walt.id/enterprise-stack/services/credential-status-service/manage) and [repository release notes](https://github.com/walt-id/waltid-identity/releases) were inspected; they do not replace this project's proof/trust acceptance evidence. The [EUDI status-list service](https://github.com/eu-digital-identity-wallet/eudi-srv-statuslist-py) describes ASL/ARL behavior based on other status-list profiles and was not treated as proof of W3C Bitstring conformance. The [Multipaz repository](https://github.com/openwallet-foundation/multipaz) and changelog were inspected; no W3C Bitstring Status List 1.0 implementation evidence was used to assert interoperability.

### Runtime and test results

The authorized repository virtual environment launched as Python 3.11.16, pytest 9.1.1, SQLite 3.53.1, FastAPI 0.141.1, Pydantic 2.13.5, httpx 0.28.1 and cryptography 50.0.1. Several installed dependency versions differ from the Identity Service pins; nothing was installed or changed to resolve the mismatch.

| Command and working directory | Result |
|---|---|
| From `services/identity-service`: `& ..\..\.venv\Scripts\python.exe -m pytest --collect-only -q tests/integration/test_wp08_remediation_status_security.py tests/integration/test_wp08_policy_evaluation.py tests/integration/test_issuance_interoperability.py` | Exit 0; **37 collected** (28 remediation cases, 7 policy API cases, 2 interoperability cases); no tests executed. One SQLite deprecation warning and one Starlette/httpx TestClient deprecation warning. |
| From `services/identity-service`: `& ..\..\.venv\Scripts\python.exe -c "import asyncio,pytest; asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy()); raise SystemExit(pytest.main(['-vv','-s','-o','faulthandler_timeout=8','tests/integration/test_wp08_remediation_status_security.py','tests/integration/test_wp08_policy_evaluation.py','tests/integration/test_issuance_interoperability.py']))"` | **BLOCKED.** Collection completed; execution entered `test_status_service_exception_fails_closed`, then stalled in `_verifier_headers` while `TestClient`/AnyIO created its asyncio portal. Faulthandler showed the local socket-pair fallback in `socket.accept`. It was interrupted. **0 completed; no pytest passed/failed/skipped totals were emitted.** This is not a test failure or pass. The same socket-pair block was observed under the default Proactor loop and an in-process ASGI transport attempt. |
| From `services/identity-service`: `$scratchRoot = (Resolve-Path -LiteralPath 'C:\Users\besna\.codex\visualizations\2026\10\11\01a12bbb-0e4d-71e2-b270-dfff9dda2ede').Path; $base = Join-Path $scratchRoot 'wp08-regression-20261012-final'; if (Test-Path -LiteralPath $base) { throw 'Refusing to reuse existing basetemp' }; & ..\..\.venv\Scripts\python.exe -m pytest -q tests/unit/test_verification_policy.py tests/unit/test_credential_status_domain.py tests/unit/test_status_list_repositories_and_service.py tests/unit/test_bitstring_status_list.py tests/integration/test_credential_proof_service.py tests/integration/test_issuance_interoperability.py --basetemp=$base` | Exit 0; **94 passed, 0 failed, 0 skipped**, one SQLite production-target deprecation warning. The dedicated scratch directory was removed after the run. This includes the two `test_issuance_interoperability.py` tests, but not the blocked WP-08 OID4VP API cases. |
| From repository root: `node --experimental-strip-types apps/web/tests/verifyPresentation_fail_closed.test.ts` | Exit 0; **7/7 passed**, including authoritative `finalPolicyResult=REJECTED` overriding legacy `valid=true`/`status=VERIFIED`, and missing credential status mapping to `UNKNOWN`. |
| From repository root: `cmd /c "npm run lint --prefix apps/web"` | Exit 0; no lint errors or warnings. |
| From repository root: `cmd /c "npm run build --prefix apps/web"` | Exit 0; TypeScript build passed and Vite transformed 1,827 modules. |
| From repository root: `docker version` | Exit 1 after reporting Docker CLI 29.8.1; daemon connection to `npipe:////./pipe/dockerDesktopLinuxEngine` returned **permission denied**. No compose or container command was run. |

The historical baseline `616 passed, 14 skipped, 0 failed` was **not reproduced**. The 94-test subset is not the full suite, and the added integration cases were collected but not executed. No count comparison is inferred from the blocked run.

### Other required regression gates

The repository documents Identity Service tests as `python -m pytest -q` from `services/identity-service`; the root full runner is `.\.venv\Scripts\python.exe run_tests.py` from repository root. The runner includes unrelated service suites, so it was not started after the focused API test demonstrated the Windows TestClient socket-pair blocker. The exact discovered suites not run were:

- WP-01: `services/identity-service/tests/integration/test_wp01_fail_closed_verification.py`
- WP-02: `services/identity-service/tests/integration/test_wp02_holder_binding_verification.py`
- WP-03: `services/identity-service/tests/integration/test_wp03_trust_registry.py`
- WP-04: `services/identity-service/tests/integration/test_wp04_oid4vp_dcql.py`
- WP-05: `services/identity-service/tests/integration/test_wp05_oid4vci_token_and_proof.py`
- WP-06: no exact WP-06 suite found; DID resolver unit files exist but were not presented as WP-06 coverage.
- WP-07: `services/identity-service/tests/integration/test_wp07_wallet_consent_presentation_proof.py`
- AI policy matrix: `services/identity-service/tests/integration/test_oid4vp_ai_policy_matrix.py`
- Golden Path: `services/identity-service/tests/integration/test_golden_path.py`
- Broken Paths: no standalone suite found; relevant negative cases are distributed across the WP/AI suites above.

These were not run after the focused API integration suite stalled. The historical run count is not used as current evidence.

### Security sweep and scope review

The relevant status/proof path was searched and reviewed in `oid4vp_service.py`, `credential_proof_service.py`, `status_list_service.py`, `status_list_document_generator.py`, `credential_validator.py`, the frontend API adapter, and verifier/wallet status views. Status-service and persistence exceptions now produce non-success results; unsupported purposes and malformed entries reject; the status-list proof is checked before `encodedList` is decoded. The decoder and lower-level proof service passed within the 94-test set. Frontend status fallbacks and fabricated proof/status copy were corrected.

One pre-existing out-of-scope issue remains visible in the policy path: if loading or reading the blockchain quarantine store raises, `is_already_quarantined` becomes `False`; a missing anchor module also leaves `blockchain_anchored=True`. These are separate from the status-service exception path and were not changed because blockchain work is excluded. The first fallback can bypass a quarantine lookup, so the overall security sweep is **BLOCKED**, not PASS. Docker logs and live service behavior could not be inspected. `git diff --check` returned no whitespace errors; Git reports existing LF-to-CRLF normalization warnings for edited text files.

### Current final acceptance matrix

| Requirement | Status | Evidence |
|---|---|---|
| R1 status exceptions | **BLOCKED** | Implementation present; OID4VP API case stalls before endpoint execution. |
| R2 revocation | **BLOCKED** | Implementation and test source present; API test not executed. |
| R2 suspension / restoration | **BLOCKED** | Enforcement case collected but not executed; persistent restoration lifecycle is not implemented. |
| R2 purpose handling | **BLOCKED** | Malformed and unsupported purpose cases collected but not executed. |
| R3 status-list proof validation | **BLOCKED** | Shared proof service and decoder pass lower-level coverage; required API cases did not execute. |
| R3 tampering | **BLOCKED** | Tampered list/proof cases collected; no OID4VP execution evidence. |
| Trust Registry | **BLOCKED** | Status-list issuer trust case collected; runtime result unavailable. WP-03 regression not run. |
| Fail-closed policy | **BLOCKED** | 94 unit/lower-level tests pass; final API decision for R1–R3 was not exercised. |
| WP-01 regression | **BLOCKED** | Backend suite not run; frontend GAP-07 test passed 7/7. |
| WP-02 regression | **BLOCKED** | Required backend suite not run. |
| WP-03 regression | **BLOCKED** | Required Trust Registry suite not run. |
| WP-04 regression | **BLOCKED** | Required DCQL suite not run. |
| WP-05 regression | **BLOCKED** | Required OID4VCI suite not run. |
| WP-06 regression | **BLOCKED** | No exact WP-06 test suite found; full regression not run. |
| WP-07 regression | **BLOCKED** | Required suite not run. |
| Golden Path | **BLOCKED** | Required scenario not run. |
| Broken Paths | **BLOCKED** | No standalone suite; distributed negative suites not run. |
| AI policy matrix | **BLOCKED** | Required suite not run. |
| Full backend regression | **BLOCKED** | Documented `run_tests.py` not run; historical 616/14 baseline unverified. |
| Frontend lint | **PASS** | 0 errors, 0 warnings. |
| Frontend build | **PASS** | TypeScript and Vite production build succeeded; 1,827 modules. |
| Docker build | **BLOCKED** | Daemon pipe denied; compose build not run. |
| Docker runtime | **BLOCKED** | No containers started. |
| Health checks and HTTP smoke tests | **BLOCKED** | Daemon unavailable; endpoints not exercised. |
| Logs | **BLOCKED** | No containers started; logs unavailable. |
| Security sweep | **BLOCKED** | Status path source findings addressed; integration/runtime proof absent and unrelated quarantine lookup fallback remains. |
| Acceptance report | **PASS** | This addendum records current evidence and limitations. |
| Git release gate | **BLOCKED** | No commit/push because mandatory test and Docker gates remain blocked; worktree is not clean. |

**Current L3 decision: FAIL — `WP-08 PARTIAL — DO NOT START WP-09`.** L4 remains **NOT CLAIMED**; no independent external interoperability was exercised. HEAD and the local `origin/main` ref still match at `59e8933f6e47922ba5a82cb7c9d76632e7edefe1`; there was no fetch, commit or push. Existing and current working-tree changes remain uncommitted.

## Current remediation revalidation — 2026-10-11

This section records the current working-tree remediation attempt and supersedes the L3 decision in the historical 2026-10-08 evidence below. The revised Master Implementation Plan remains the engineering source of truth. No WP-09 work, commit, or push was performed.

**Current decision: `WP-08 PARTIAL — DO NOT START WP-09`. L3 is not complete.** R1–R3 remediation code and regression cases are present in the working tree, but Python tests could not start and the Docker release gate is blocked. Consequently R1, R2, R3, Trust Registry integration, and fail-closed policy are **not marked PASS** in this revalidation.

### Remediation present in the working tree

| Area | Current change | Evidence status |
|---|---|---|
| R1 — status lookup failures | Missing status service and exceptions from `get_publication` leave the status result false and include an unavailable/error reason. Regression cases cover an exception, timeout, and unconfigured service. | Code inspected; tests not executed |
| R2 — revocation and suspension | Persistence rejects non-active states; both status purposes are evaluated, active bits reject, and unsupported/malformed purpose or index values fail closed. Regression cases cover active/inactive suspension, persisted suspension/revocation, active revocation bit, and malformed purpose/index. | Code inspected; tests not executed |
| R3 — status-list proof | OID4VP validates the existing status-list response schema, publication id/issuer/purpose and document URL; it calls `CredentialProofService.verify_data_integrity_document` for the project's `eddsa-jcs-2022` proof path, then checks Trust Registry and `validFrom` before using the signed `encodedList`. The status-list issuer is checked against its publication and registry, not forced to equal the credential issuer. The status-bit decoder rejects an index outside the encoded bitstring. | Code inspected; tests not executed |
| Security regression coverage | The new WP-08 remediation test file covers R1–R3, including malformed documents, tampered list/proof, missing/unsupported proof, invalid proof, wrong/untrusted publication issuer, accepted/rejected bit values, and an index outside the encoded bitstring. | Test source inspected; tests not executed |
| Frontend result authority | The verification API adapter now uses backend `result.finalPolicyResult` whenever supplied, so legacy `valid`/`status` fields cannot override a backend rejection. The result matrix continues to render backend policy/status fields. | Lint/build pass; source inspected |

The R3 cryptographic implementation calls the existing credential proof service and signer/canonicalizer/DID-key authorization path; it no longer implements Ed25519 verification inside the status-list OID4VP method. Trust Registry is evaluated for the status-list credential issuer after proof validation.

### Standards and profile decisions

- **STANDARD REQUIREMENT:** Validate the referenced status-list credential and its proof before trusting `encodedList`; bind the entry's `statusPurpose` to the list purpose; treat an out-of-range status index as an error. See [W3C Bitstring Status List 1.0](https://www.w3.org/TR/vc-bitstring-status-list/) and [W3C Data Integrity 1.0](https://www.w3.org/TR/vc-data-integrity/).
- **PROJECT PROFILE:** VC Data Model 2.0 with `DataIntegrityProof`, `eddsa-jcs-2022`, Ed25519, and `assertionMethod`, consistent with the revised Master Implementation Plan and [W3C EdDSA Cryptosuites 1.0](https://www.w3.org/TR/vc-di-eddsa/).
- **IMPLEMENTATION CHOICE:** Require the signed document id to match the requested status-list URL and the document issuer to match the local publication's issuer metadata; evaluate that issuer through Trust Registry. Do not require the status-list issuer to equal the credential issuer, which the Bitstring Status List model permits to differ.

### Current validation results

| Gate | Result | Evidence |
|---|---|---|
| WP-08 targeted tests | **BLOCKED before collection** | Command: `& ..\..\.venv\Scripts\python.exe -m pytest -q tests/integration/test_wp08_remediation_status_security.py tests/integration/test_wp08_policy_evaluation.py tests/integration/test_issuance_interoperability.py` from `services/identity-service`. The uv trampoline could not start Python: `permission denied (os error 5)`. Collected: 0; passed: 0; failed: 0; skipped: 0. |
| WP-01…WP-07, AI matrix, Golden Path, Broken Paths, full backend suite | **NOT RUN** | Same authorized Python runtime blocker; no unrelated or broader test command was attempted. Historical `616 passed, 14 skipped` remains historical and is not evidence for this remediation. |
| Frontend lint | **PASS** | `cmd /c "npm run lint --prefix apps/web"` — exit 0; ESLint reported no errors or warnings. |
| Frontend production build | **PASS** | `cmd /c "npm run build --prefix apps/web"` first failed in the sandbox because esbuild could not read an ancestor directory (`Access is denied`); the same command was rerun with approved elevated execution and succeeded. TypeScript build passed; Vite transformed 1,827 modules and completed the production build. |
| Docker build/runtime/health | **DOCKER GATE BLOCKED** | Docker CLI is not available (`Get-Command docker` returned no command). No daemon check, compose build/up/down, container health check, HTTP smoke test, or log inspection was run. |
| Frontend status truthfulness | **PASS** | The adapter gives `result.finalPolicyResult` precedence when present; `NinePointVerificationMatrix.tsx` displays backend `finalPolicyResult` and `revocationStatusClear`. Lint/build both pass. |
| Git / whitespace | **PASS for preservation check** | Branch remains `main`, HEAD remains `59e8933f6e47922ba5a82cb7c9d76632e7edefe1`, and `git diff --check` returned no findings. Existing user changes remain present. No commit or push was made. |

### Current requirement matrix and decision

| Requirement | Current status |
|---|---|
| R1 status exception fail-open | Implemented in current diff; **test evidence blocked** |
| R2 suspension enforcement | Implemented in current diff; **test evidence blocked** |
| R3 status-list proof verification | Implemented through shared proof service; **test evidence blocked** |
| Trust Registry integration / fail-closed policy | Present in code; **test evidence blocked** |
| Golden Path / Broken Paths / full regression | **NOT RUN** |
| Frontend lint / build | **PASS** |
| Docker build / runtime / health checks | **DOCKER GATE BLOCKED** |
| L3 | **NOT COMPLETE** — mandatory Python and Docker gates are unverified/blocked |
| L4 | **NOT CLAIMED** — no external interoperability test was run |

**Residual risks:** Python security/regression tests have not run against these changes; full-suite compatibility and the regression count are unknown. Docker release evidence is absent. External interoperability remains unverified. The repository's existing modified and untracked files must be preserved when validation resumes.

**Next:** Keep WP-08 partial and do not start WP-09 until an authorized Python 3.11-compatible runtime and an available Docker runtime allow the mandatory gates to run.

**Commit under review:** `8073460` + test-fixture patch  
**Evaluated:** 2026-10-08  
**Evaluator:** Independent acceptance gate (no feature implementation performed)

> **NOTE:** The canonical project report is written to
> `reports/V2_1_WP08_FINAL_ACCEPTANCE.md` in the workspace.

---

## 1. GIT STATE VERIFICATION

| Check | Result |
|---|---|
| HEAD commit | `8073460` WP-08: Status & Trust Policy Integration |
| origin/main synced | ✅ Pushed `099de5c..8073460  main → main` |
| Working tree | ✅ Clean (test-fixture patch staged for commit below) |
| Commit exists on origin/main | ✅ Confirmed |

**Test-fixture patch:** `urn:uuid:wp08-*` human-readable slugs → valid RFC 4122 UUIDs required by `CredentialValidator`. Policy engine and evaluator untouched.

---

## 2. REQUIREMENT MATRIX

| # | Requirement | Status | Evidence |
|---|---|---|---|
| 1 | Bitstring Status List 1.0 | **PASS** | `status_list_document_generator.py`: gzip+base64url `"u"` prefix, type `BitstringStatusListCredential`, `statusPurpose=revocation`, signed with `eddsa-jcs-2022` |
| 2 | `credentialStatus` processing | **PASS** | `oid4vp_service.py:857–876`: reads `statusPurpose`, `statusListIndex`, `statusListCredential` |
| 3 | Revocation | **PASS** | Two-layer: DB `CredentialStatus.REVOKED` (line 850–854) + Bitstring index bit-lookup (line 864–874); either → REJECTED |
| 4 | Suspension | **NOT IMPLEMENTED** | `statusPurpose=suspension` branch absent in `oid4vp_service.py`; only `"revocation"` is handled |
| 5 | Unknown / unavailable / error semantics | **PARTIAL** | Malformed index → REJECTED (line 875–876); but status list service exception → **silently passes** (line 873 `except Exception: pass`) |
| 6 | Freshness | **PASS** | `ttl_seconds` embedded in document; content-hash fingerprint caching; LRU decompression cache |
| 7 | Status URL security / SSRF | **PASS** | Status resolved through local `StatusListService` — no outbound HTTP during verification |
| 8 | Status proof validation | **PARTIAL** | Document signed at publication time; proof **not re-verified** during `process_direct_post` |
| 9 | Status-list issuer validation | **PARTIAL** | Entry issuer consistency checked within publication; not cross-referenced against credential issuer in verifier |
| 10 | WP-03 Trust Registry integration | **PASS** | `oid4vp_service.py:777`: calls `TrustRegistryService.evaluate_issuer_trust()`; fail-closed on unconfigured/unavailable/malformed DID |
| 11 | Deterministic policy evaluation | **PASS** | `VerificationPolicyEvaluator.evaluate()` is a pure class method |
| 12 | Fail-closed decision hierarchy | **PASS** | 9 crypto gates → REJECTED; AI gate only after all pass; 48 unit tests prove this |
| 13 | Holder-binding preservation | **PASS** | WP-02 `_verify_holder_binding()` unchanged; wired as `PolicyCheckName.HOLDER_BINDING` |
| 14 | DCQL preservation | **PASS** | WP-04 `DcqlEngine.evaluate()` unchanged; wired as `PolicyCheckName.DCQL_SATISFACTION` |
| 15 | Canonical OID4VP integration | **PASS** | `process_direct_post()` single entry point; `NinePointVerificationResult` contract preserved |
| 16 | Structured evidence | **PASS** | `VerificationPolicyResult.to_audit_dict()`, `first_failure`, `quarantine_reason`, `crypto_checks` |
| 17 | Privacy / data minimization | **PASS** | `disclosedFields`, `hiddenFields`, `disclosureRatio` in response; consent enforcement unchanged |
| 18 | Frontend truthfulness | **PASS** | `finalPolicyResult` from `policy_result.decision.value`; no UI override path |
| 19 | Golden Path | **PASS** | `test_golden_path.py` 13-step lifecycle passes |
| 20 | Broken Paths | **PASS** | `test_wp01`, `test_wp02`, `test_oid4vp_ai_policy_matrix`, `test_wp08` cover all failure branches |
| 21 | Security tests | **PASS** | SSRF guard in `did_resolver.py`; replay/nonce bound; quarantine lockout |
| 22 | Regression | **PASS** | **616 passed, 14 skipped, 0 failures** (full suite post fixture fix) |
| 23 | Lint | **PASS** | `npm run lint --prefix apps/web` → exit 0, 0 errors, 0 warnings |
| 24 | Frontend build | **PASS** | `npm run build --prefix apps/web` → exit 0, 1827 modules, 3.04 s |
| 25 | Docker build | **BLOCKED** | Docker Desktop daemon not running; user skipped |
| 26 | Docker runtime health | **BLOCKED** | Daemon not running |
| 27 | Documentation / report | **PASS** | This file |
| 28 | L3/L4 classification | See §11 |

---

## 3. CRITICAL AI CHECK

| AI Invariant | Result |
|---|---|
| AI never overrides failed crypto | ✅ PASS — gate order lexically enforced: all 9 crypto checks evaluated before AI |
| AI never converts REJECTED → VERIFIED | ✅ PASS — no such code path |
| AI is only an independent risk signal | ✅ PASS |
| CRITICAL triggers quarantine | ✅ PASS — `quarantine_triggered=True`; `blockchain_anchor.anchor_quarantine()` called as side-effect |
| AI cannot create crypto PASS | ✅ PASS |
| AI cannot create issuer trust | ✅ PASS |
| AI cannot create credential status ACTIVE | ✅ PASS |

**AI GATE: ✅ PASS**

---

## 4. STATUS LAYER CHECK

> WP-08 policy layer implemented. Status list revocation processing exists and functions.

| Component | Status |
|---|---|
| `statusListCredential` field read | ✅ |
| `statusListIndex` parsed as int | ✅ |
| `statusPurpose=revocation` branch | ✅ |
| `encodedList` gzip decoded + bit lookup | ✅ |
| Status proof re-verification | ⚠️ NOT DONE |
| Suspension (`statusPurpose=suspension`) | ❌ MISSING |
| Status unavailable → fail-closed | ❌ DEFECTIVE (`except Exception: pass`) |
| Malformed index → fail-closed | ✅ |

**Conclusion:**  
> _WP-08 policy layer implemented, but full status layer is incomplete._

---

## 5. TRUST CHECK

| Check | Result |
|---|---|
| DID prefix trust | ✅ ABSENT |
| Hostname trust | ✅ ABSENT |
| String matching | ✅ ABSENT |
| Duplicated trust registry | ✅ ABSENT |
| Frontend trust | ✅ ABSENT |
| Trust from WP-03 `TrustRegistryService.evaluate_issuer_trust()` | ✅ CONFIRMED |
| Fail-closed on unconfigured | ✅ `UNCONFIGURED` → `is_trusted=False` |
| Fail-closed on exception | ✅ `TRUST_REGISTRY_UNAVAILABLE` → `is_trusted=False` |

**TRUST CHECK: ✅ PASS**

---

## 6. FAIL-CLOSED CHECK

| Scenario | Result |
|---|---|
| Invalid crypto → never VERIFIED | ✅ |
| Invalid holder binding → never VERIFIED | ✅ |
| Unknown issuer → never VERIFIED | ✅ |
| Revoked credential → never VERIFIED | ✅ |
| Suspended credential → never VERIFIED | ❌ NOT ENFORCED |
| Unknown status → never VERIFIED | ✅ (malformed index) |
| Status unavailable → never VERIFIED | ❌ SILENTLY PASSES |
| Trust registry unavailable → never VERIFIED | ✅ |
| DCQL failure → never VERIFIED | ✅ |
| AI CRITICAL cannot override crypto failure | ✅ |

---

## 7. TEST EVIDENCE

| Suite | Result |
|---|---|
| `test_verification_policy.py` (unit) | **48/48 PASS** |
| `test_wp08_policy_evaluation.py` (integration) | **7/7 PASS** (post fixture fix) |
| `test_wp01_fail_closed_verification.py` | PASS |
| `test_wp02_holder_binding_verification.py` | PASS |
| `test_wp03_trust_registry.py` | PASS |
| `test_wp04_oid4vp_dcql.py` | PASS |
| `test_wp05_oid4vci_token_and_proof.py` | PASS |
| `test_wp07_wallet_consent_presentation_proof.py` | PASS |
| `test_oid4vp_ai_policy_matrix.py` | PASS |
| `test_golden_path.py` | PASS |
| **Full suite** | **616 passed, 14 skipped, 0 failures** |

---

## 8. FRONTEND

| Check | Result |
|---|---|
| `npm run lint --prefix apps/web` | ✅ 0 errors, 0 warnings |
| `npm run build --prefix apps/web` | ✅ 1827 modules, 3.04 s, exit 0 |

---

## 9. DOCKER

**BLOCKED** — Docker Desktop daemon not running during this gate.  
WP-08 introduces no new Dockerfile layers or system dependencies.

---

## 10. RESIDUAL RISKS

| Risk | Severity |
|---|---|
| R1: Status unavailable → fail-open (`except Exception: pass`) | **HIGH** |
| R2: Suspension not enforced at verification | **MEDIUM** |
| R3: Status list credential proof not re-verified | **MEDIUM** |
| R4: Status list issuer not cross-checked | LOW |
| R5: Docker gate not verified | LOW |

---

## 11. FINAL DECISION

```
WP-08 PARTIAL — POLICY ENGINE COMPLETE, FULL WP-08 NOT COMPLETE
```

**What is complete:**
- VerificationPolicyEvaluator — 9-gate fail-closed hierarchy ✅
- AI cannot override crypto ✅
- WP-03 trust registry integration ✅
- All WP-01…WP-07 invariants preserved ✅
- 616 tests passing, 0 failures ✅
- Frontend lint + build ✅

**What prevents L3 COMPLETE:**
1. **R1 (HIGH):** Status service unavailable silently passes — fail-open defect
2. **R2 (MEDIUM):** `statusPurpose=suspension` not enforced at verification
3. **R3 (MEDIUM):** Status list credential proof not re-verified at presentation time

**L4 NOT CLAIMED** — no external interoperability evidence.

---

## 12. REMEDIATION REQUIRED FOR L3 COMPLETE

| Fix | Location | Change |
|---|---|---|
| FIX-1 | `oid4vp_service.py:873` | Replace `except Exception: pass` with `revocation_status_clear = False` |
| FIX-2 | `oid4vp_service.py:860` | Add `elif status_purpose == "suspension":` branch → `revocation_status_clear = False` |
| FIX-3 (optional for L3) | `process_direct_post` | Re-verify `BitstringStatusListCredential` proof before trusting `encodedList` |

## Current verification addendum — 14 October 2026

This entry supersedes prior test totals and prior “runtime blocked before execution” wording where newer evidence conflicts. Earlier entries remain historical. The authoritative Master Plan’s broader gate criteria remain unchanged.

### Current WP-08 acceptance evidence

| Acceptance item | Current result | Evidence and boundary |
|---|---|---|
| R1 — status/persistence failures fail closed | **PASS in tested scope** | The focused three-file WP-08 command passed 48 tests with no skips. The current source preserves a rejecting/unknown policy outcome when referenced status resolution is unavailable or invalid. This remains in-process evidence, not a live Mongo outage test. |
| R2 — status purpose and suspension | **PASS in tested scope** | The same 48-test acceptance command covers purpose matching, revocation/suspension behavior, malformed and out-of-range status data, and final policy rejection. Suspension restoration/lifecycle is not claimed. |
| R3 — status-list authenticity | **PASS in tested scope** | The same command covers status-list proof/signature and trust checks, including tampered or unsupported cases. No independent peer verification is claimed. |
| Backend policy and issuance regression | **PASS in tested scope** | The focused command includes policy evaluation and issuance interoperability regression tests; 48/48 total. Local tests do not prove L4 interoperability. |
| Full repository regression | **PASS with disclosed skips** | `run_tests.py`: 788 passed, 12 skipped, 0 failed, 155 subtests. Seven real-Mongo tests were skipped. Five live Hardhat tests skipped in that run were separately rerun as 7 passing integration tests on a disposable local node. |
| Docker/current deployment runtime | **NOT VERIFIED** | No Docker daemon/current-source Compose build or health result. |

Exact focused command (working directory `services/identity-service`):

```powershell
..\..\.venv\Scripts\python.exe -m pytest -q -rs tests/integration/test_wp08_remediation_status_security.py tests/integration/test_wp08_policy_evaluation.py tests/integration/test_issuance_interoperability.py
```

Result: exit 0; **48 passed, 0 failed, 0 skipped**, two deprecation warnings, 84.80 seconds.

### Decision

**WP-08 R1–R3 implementation and focused test acceptance: PASS. Full project G6/WP-08 runtime closure: PARTIAL pending real Mongo repository and Docker/Compose evidence. L4 and production readiness are NOT CLAIMED.** Do not use the historical sections above as a claim that Mongo/Docker acceptance has passed.

## Current dirty-source rerun status — 14 October 2026

The above 48/48 result is retained for the source snapshot on which it ran. After subsequent G7/authentication changes in the dirty working tree, the exact three-file command was attempted again from `services/identity-service`:

```powershell
..\..\.venv\Scripts\python.exe -m pytest -q -rs tests/integration/test_wp08_remediation_status_security.py tests/integration/test_wp08_policy_evaluation.py tests/integration/test_issuance_interoperability.py
```

It exited 1 before test collection: `uv trampoline failed to spawn Python child process; Caused by: permission denied (os error 5)`. Current-source result: **0 passed, 0 failed, 0 skipped, 0 collected — BLOCKED**. The historical 48/48 run remains useful scoped evidence, but current R1–R3 acceptance is not refreshed on this dirty source state. No test was skipped or bypassed.

## Current-source G6/WP-08 closure — 15 October 2026

This addendum supersedes the 14 October blocked rerun and pending-Mongo/Docker decision above. It applies to the dirty working tree at branch `main`, HEAD `59e8933f6e47922ba5a82cb7c9d76632e7edefe1`; no commit was created.

### Required WP-08 evidence

| Acceptance item | Current result | Evidence and boundary |
|---|---|---|
| R1 — fail-closed status/persistence handling | **PASS in tested scope** | The current focused WP-08/API test file covers unavailable, throwing, malformed, missing and persistence-failure cases; the final policy result remains non-acceptance. The focused test command passed. |
| R2 — revocation/suspension purpose and status | **PASS in tested scope** | Current tests cover distinct `revocation`/`suspension` purposes, active/unset bits, suspended/revoked persistence, malformed purpose/index and range checks. Suspension restoration transitions are not claimed. |
| R3 — status-list authenticity | **PASS in tested scope** | Current tests cover valid proof acceptance and tampered, unsupported, missing, untrusted or mismatched issuer/verification-method cases before trusting `encodedList`. No independent peer is claimed. |
| Policy/UI boundary | **PASS in tested scope** | Policy tests and the current frontend fail-closed test prove rejection cannot be upgraded by legacy success fields and missing status does not default to active. |
| Focused WP-08 command | **PASS: 48 passed, 0 failed, 0 skipped** | Current three-file command below; 2 deprecation warnings; 87.02 seconds. |
| Identity Service regression | **PASS: 686 passed, 0 failed, 5 skipped** | Current `pytest -q -rs`; 5 skips are exclusively live Hardhat tests because port 8545 is unavailable. Three deprecation warnings. Mongo repository tests ran in the same regression with the isolated database URI. |
| Real MongoDB repositories | **PASS: 7 passed, 0 failed, 0 skipped** | `tests/integration/test_mongo_repositories.py`; 1 deprecation warning. The fixture uses a uniquely named test database and drops it afterward. |
| Current-source Compose build and health | **PASS** | Compose config passed; all five application images were built from the current source; web image ran ESLint and TypeScript/Vite production build. With temporary stdin-only loopback port overrides, all 7 services reported healthy. Web `/`, Gateway `/health`, Identity `/health`, Fraud `/health`, Recovery `/health` each returned HTTP 200. |
| Mongo persistence across restart | **PASS** | A temporary marker in the isolated Compose Mongo volume remained after restarting only that Mongo container; the temporary validation database was then dropped. |

The Python and HTTP checks required the already-installed Python 3.11 virtual environment and elevated test-process permission because the ordinary Windows sandbox denied TestClient/local socket operations. Docker Desktop 29.8.1 was already installed and was started after the user’s prior explicit authorization. No Windows security settings changed, no host packages were installed, and no repository Compose file was modified for the port override. The first default-port Compose start attempt stopped at host port 8002 (`port is already allocated`); the project was then run in isolation using loopback mappings: web 13000, Redis 16379, Gateway 18000, Identity 18001, Fraud 18002, Recovery 18003 and MongoDB 37017. The isolated stack remains available for local inspection.

### Exact commands

From `services/identity-service`:

```powershell
& 'C:\Users\besna\OneDrive\Bureau\secure-ssi-platform\.venv\Scripts\python.exe' -m pytest -q -rs tests/integration/test_wp08_remediation_status_security.py tests/integration/test_wp08_policy_evaluation.py tests/integration/test_issuance_interoperability.py
$env:IDENTITY_TEST_MONGODB_URI='mongodb://prototype:change-me@127.0.0.1:37017/admin?authSource=admin'; & 'C:\Users\besna\OneDrive\Bureau\secure-ssi-platform\.venv\Scripts\python.exe' -m pytest -q -rs
$env:IDENTITY_TEST_MONGODB_URI='mongodb://prototype:change-me@127.0.0.1:37017/admin?authSource=admin'; & 'C:\Users\besna\OneDrive\Bureau\secure-ssi-platform\.venv\Scripts\python.exe' -m pytest -q -rs -p no:cacheprovider tests/integration/test_mongo_repositories.py
```

From the repository root:

```powershell
docker compose -p secure-ssi-platform config --quiet
docker compose -p wp08-validation-20261015 build --pull=false
docker compose -p wp08-validation-20261015 -f docker-compose.yml -f - up --detach --no-build --wait --wait-timeout 180
docker compose -p wp08-validation-20261015 ps --all
node --experimental-strip-types apps/web/tests/verifyPresentation_fail_closed.test.ts
```

The successful `up` command received this YAML on stdin; it was not written to the repository:

```yaml
services:
  web: { ports: !override ["127.0.0.1:13000:80"] }
  api-gateway: { ports: !override ["127.0.0.1:18000:8000"] }
  identity-service: { ports: !override ["127.0.0.1:18001:8000"] }
  fraud-service: { ports: !override ["127.0.0.1:18002:8000"] }
  recovery-service: { ports: !override ["127.0.0.1:18003:8000"] }
  mongodb: { ports: !override ["127.0.0.1:37017:27017"] }
  redis: { ports: !override ["127.0.0.1:16379:6379"] }
```

### Decision

**WP-08 / G6: PASS at L3 for the scoped R1–R3, policy/UI, current Identity regression, real-Mongo, and isolated Compose runtime evidence above.** The five Hardhat skips are outside WP-08 and are not counted as passes. L4 interoperability, suspension restoration, public-chain receipt behavior, production readiness, and a browser Golden Path are not claimed. G9 is no longer blocked by WP-08; continue in the controlling Master Plan order, with G8 next.

## 25 October 2026 — current-source L3 evidence addendum

This addendum supersedes the 15 October “current-source build and health” block for the present source revision. It preserves earlier evidence as historical. Branch `besna-dev`, source HEAD `e26da1e49c80c6b157e5f6d5697c43a455bf7542`; the working tree includes eight modified Identity integration test files and a pre-existing untracked audit directory. No application code was modified in this verification.

| Acceptance item | Observed result | Boundary |
|---|---|---|
| R1 — fail-closed status and persistence | **PASS in tested scope** | Current focused remediation/policy tests passed as part of the 74-test in-container set and the 125-test host set. |
| R2 — revocation, suspension purpose, status purpose | **PASS in tested scope** | Focused tests passed. Suspension restoration lifecycle is not established. |
| R3 — status-list authenticity/signature verification | **PASS in tested scope** | Focused security tests passed; no independent external verifier is claimed. |
| OID4VP session authorization | **PASS in tested scope** | Targeted authorization tests are included in the 74-test in-container run; unauthenticated retrieval through Gateway and Identity returned HTTP 401. Authenticated cross-organization browser journey remains unverified. |
| Focused running-container suite | **PASS: 74 passed, 0 failed, 0 skipped, 2 warnings** | Python 3.12 inside the freshly rebuilt Identity service; includes WP-05, WP-08, issuance interoperability test module, and OID4VP session authorization. This test-module result alone does not prove independent L4 interoperability. |
| Host Identity regression | **PASS: 719 passed, 0 failed, 12 skipped, 7 warnings** | Python 3.11.16 venv. Skips are environment-gated and not counted as passing. |
| Current-source Compose runtime | **PASS: 7/7 healthy** | Five app images built `--no-cache`; only five app services recreated. Existing MongoDB/Redis containers and volumes remained. Web and four service health endpoints returned 200. |
| Unauthorized request smoke | **PASS: HTTP 401** | Fake OID4VP session retrieval tested through Gateway and directly through Identity; this is a negative unauthenticated probe, not an authenticated owner/tenant journey. |

Exact focused running-container command:

```powershell
docker compose --project-name wp08-l3-20261013 --file docker-compose.yml exec -T identity-service python -m pytest -q -rs tests/integration/test_wp05_oid4vci_token_and_proof.py tests/integration/test_wp08_remediation_status_security.py tests/integration/test_wp08_policy_evaluation.py tests/integration/test_issuance_interoperability.py tests/integration/test_oid4vp_session_authorization.py
```

All five images lack OCI `org.opencontainers.image.revision` and `.source` labels. The build was invoked with `--no-cache` from this current working tree; container creation times and image IDs are recorded in the execution evidence, but the OCI metadata does not independently attest the revision. The Docker-served frontend bundle (`index-7Lu304ao.js`, SHA-256 `A372A08253EEA13E0B7DC2D5DD1406773B0A49CA90ECAB9583E0A65457054152`) differs from the host Node 24.19.0 build (`index-37arp1TW.js`, SHA-256 `8148FB8F061EA8B4185790388805CB551B4A2BC34273C1BB05231CD6557106D1`). Exact bundle equivalence is therefore **unverified**; Docker build uses Node 20 Alpine, but no controlled same-runtime comparison was performed.

**Decision:** WP-08 / G6 is **PASS at L3 for the scoped R1–R3, policy, targeted authorization, full Identity suite, and current-source Compose health/negative HTTP evidence above**. Overall project acceptance remains **PARTIAL**. L4 interoperability, suspension restoration, authenticated cross-organization browser flow, rendered Golden Path/accessibility, public-chain receipt behavior and production readiness are not claimed. Do not infer that passing a test module alone constitutes external interoperability.
