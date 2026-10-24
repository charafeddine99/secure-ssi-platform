# WP-11 — Windows Test Tooling and Reproducibility

**Checkpoint:** 24 October 2026
**Branch / source:** `besna-dev` at `a026df83bcb6b43451cb96a7eaed41877b5e198a` before this WP-11 change
**Decision:** **PARTIAL (L2)** — the runner fix and selected checks are verified, but the required full Windows Python suite cannot complete on the current host.
**Scope:** Windows test invocation, accurate pytest outcome reporting, and the previously reported `ckzg`/pandas import blockers. This is not a project-wide acceptance or security certification.

## Implementation

`run_tests.py` now resolves test directories relative to its own repository path and sets the child process working directory explicitly. It can select one or more service/test trees with repeated `--service` arguments, keeps running later trees after a failed tree, prints every tree's pytest exit code, and returns the first non-zero code. The report maps pytest exit codes 0–6, including interruption, internal/usage errors, no tests collected, and the maximum-warning threshold.

Added `tests/test_run_tests_runner.py` to check repository-root path resolution, continuing after a failure, returned status, and the pytest exit-code labels. Added the Web `test` script to run all existing `.test.ts` and `.test.mjs` contract tests with Node's built-in test runner. The frontend CI job now uses Node 24 for this native TypeScript test command; the separate Hardhat CI job keeps Node 20. The production build still runs TypeScript type checking separately. No Python or npm package dependency versions or test security controls were changed.

PowerShell command guidance now uses the installed `npm.cmd` and `npx.cmd` command shims instead of `npm.ps1`/`npx.ps1`; the machine exposes both script and `.cmd` launchers. No PowerShell execution policy or other Windows security setting was changed. Existing package scripts remain the source of the frontend and Hardhat commands.

The Identity test `conftest.py` already contains a test-only fallback for an unavailable `ckzg` import. It was left unchanged: this host successfully imports `ckzg`, and no AppLocker-denied import was reproduced here. The fraud-service pandas/NumPy C-API import was also not reproduced in the current environment. No dependency pin was added without evidence of a reproducible incompatible pair.

## Environment evidence

- Repository virtual environment: Python **3.11.16**, pytest **9.1.1**.
- Installed Node.js **24.19.0** and npm **11.17.0**. Node's built-in TypeScript stripping is enabled in this runtime; the `.test.ts` scripts use only erasable TypeScript syntax.
- Current imports succeeded for `pytest`, `pandas 3.0.6`, `numpy 2.4.6`, `ckzg`, `eth_account 0.14.0`, `scikit-learn 1.9.1`, and `xgboost 3.2.0`.
- `.venv\Scripts\python.exe -m pip check` could not run because the virtual environment has no `pip` module (`No module named pip`). This is not a dependency-consistency pass.
- Installed system Python **3.12.7** has pip **24.2** but has no installed pytest or FastAPI. Its `_socket` module also exposes no native `socketpair`; it was not used for application tests and no packages were installed.
- Python 3.11's `socket.socketpair` resolves to CPython's TCP-loopback fallback. The specific Identity `TestClient` hang is reproducible in that fallback's blocking `accept()` call while AnyIO starts Starlette's test portal. The operating-system or security policy was not changed and no socket bypass was attempted.
- `.github/workflows/ci.yml` currently runs Ubuntu jobs; it does not provide a Windows test job. Docker/Compose was not used for this WP-11 checkpoint.
- The CI workflow edit was not executed by GitHub Actions during this checkpoint; only the corresponding local Web tests, lint and build were run.

## Commands and results

Commands below ran against the working tree at this checkpoint. A timeout/interruption without a pytest summary is not counted as pass, failure count, or skip count.

| Command | Result | Interpretation |
|---|---|---|
| `.\.venv\Scripts\python.exe -m pytest tests/test_run_tests_runner.py -q` | **3 passed, 0 failed** | Runner regression tests. |
| From `$env:TEMP`: `& "$repo\.venv\Scripts\python.exe" "$repo\run_tests.py" --service packages/shared/tests` | **7 passed; 19 subtests passed; exit 0** | Demonstrates the runner resolves repository paths when invoked outside the repository working directory. |
| `.\.venv\Scripts\python.exe -m pytest --collect-only -q services/identity-service` | **720 tests collected; exit 0; 3 warnings** | Collection only. Does not execute those tests. |
| `.\.venv\Scripts\python.exe -m pytest services/identity-service/tests/test_health.py -vv -s` via a Python `faulthandler.dump_traceback_later(20)` wrapper | **Interrupted after 30 seconds; no pytest summary.** Trace showed `socket.py:_fallback_socketpair` blocked at `accept`, via AnyIO `run_blocking_portal` and `starlette.testclient`. | Environment-level Windows loopback socketpair blocker; this is not a test pass. |
| `.\.venv\Scripts\python.exe run_tests.py` | **Interrupted after 60 seconds while Identity Service was running; runner exit 1; no suite summary.** | The required whole-runner result is **BLOCKED / unverified**. The first suite did not finish. |
| `.\.venv\Scripts\python.exe -m pytest services/fraud-service/tests/test_event_pipeline_and_dataset.py -q` | **Interrupted after 30 seconds; no pytest summary.** | No counts can be reported. A separate pure calculation test below passed. |
| `.\.venv\Scripts\python.exe -m pytest services/fraud-service/tests/test_event_pipeline_and_dataset.py::test_impossible_travel_haversine_calculation -q` | **1 passed, 0 failed; 2 warnings** | Confirms one non-HTTP fraud test imports/uses the current NumPy/pandas dependency set; it does not validate the whole Fraud API suite. |
| `.\.venv\Scripts\python.exe -m pytest services/recovery-service/tests/unit/test_secret_sharing.py -q` | **8 passed, 0 failed** | Selected pure Recovery unit tests only. |
| `npm.cmd run lint --prefix apps/web` | **Passed; exit 0** | Frontend ESLint. |
| `npm.cmd test --prefix apps/web` | **8 test files passed, 0 failed, 0 skipped; exit 0** | Runs the existing TypeScript/ESM contract scripts through Node's built-in test runner. Type checking remains in `npm.cmd run build`. |
| `npm.cmd run build --prefix apps/web` | **Passed; exit 0**; TypeScript build and Vite 6.4.3, 1,831 modules | Frontend production build. |
| `node apps/web/tests/fraudMonitorLabel.test.mjs` | **3 passed, 0 failed** | Existing WP-09 SSR label regression. |
| `npm.cmd test --prefix blockchain` | **20 passing, 0 failing** | Existing Hardhat contract suite. |

The earlier reports contain other dated test runs. Those remain historical results and are not substituted for the interrupted current whole-runner attempt above.

## Reproduction commands

From PowerShell, substitute the local repository root:

```powershell
$repo = 'C:\path\to\secure-ssi-platform'
& "$repo\.venv\Scripts\python.exe" "$repo\run_tests.py"
& "$repo\.venv\Scripts\python.exe" "$repo\run_tests.py" --service services/identity-service --service services/recovery-service
npm.cmd run lint --prefix "$repo\apps\web"
npm.cmd test --prefix "$repo\apps\web"
npm.cmd run build --prefix "$repo\apps\web"
npm.cmd test --prefix "$repo\blockchain"
```

The Python runner covers six independent pytest roots: Identity, Recovery, Fraud, API Gateway, shared package tests, and repository-level tests. Integration cases may require MongoDB or a local Hardhat node as specified by their fixtures; the runner does not start services, manufacture successful responses, or convert skips into passes. The current default run is not yet reproducible to completion on this Windows environment because Starlette/AnyIO's test portal stalls while CPython's loopback fallback socket pair waits in `accept()`.

## Official tooling references consulted

- pytest stable reference, **Exit codes**: code 0 means all collected tests passed; codes 1–6 represent test failure, interruption, internal error, usage error, no tests collected, and warning-threshold exceeded. The runner preserves and describes these statuses rather than interpreting a non-summary run as success: <https://docs.pytest.org/en/stable/reference/exit-codes.html>.
- npm CLI v11, **Scripts / Exiting**: npm runs package scripts through `cmd.exe` by default on Windows, and a non-zero script exit aborts the npm run. This supports using the `.cmd` shim in PowerShell and retaining npm's exit result: <https://docs.npmjs.com/cli/v11/using-npm/scripts/>.
- Node.js v24 documentation, **Modules: TypeScript**: built-in type stripping is enabled by default from v22.18 and is stable in v24.12; it executes erasable TypeScript syntax but does not type-check. The Web test script therefore uses Node 24 in CI, and the separate production build continues to run `tsc -b`: <https://nodejs.org/api/typescript.html>.
- Hardhat Runner v2, **Testing contracts**: the documented command runs the project's Hardhat test task; this repository exposes that task as its `test` package script: <https://v2.hardhat.org/hardhat-runner/docs/guides/test-contracts>.

## Acceptance and limitations

WP-11 remains **PARTIAL (L2)**. The path-resolution defect in the runner is fixed and regression-tested; current installed `ckzg`, pandas and NumPy imports work; PowerShell-specific npm commands are documented; and the selected checks above passed. The V2.1 WP-11 completion requirement—`python run_tests.py` completing with all Windows service suites passing—remains **BLOCKED** by the reproduced TestClient/AnyIO socketpair hang. No full-suite totals are available for this current run. A supported Windows Python runtime or administrator-approved resolution for the loopback socket-pair restriction is needed before claiming full Windows-suite reproducibility. No AppLocker policy, firewall, execution policy, or package version was changed.
