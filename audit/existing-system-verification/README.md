# Existing System Verification – Secure SSI Platform (2026-11-21)

Audit of the features that already exist in the platform: inventory, tests before and after, defects found and fixed, security review and external dependencies. No new features were added.

**Start here: `13_FINAL_REPORT.md`** (2026-11-25). It is the final summary of the audit, the closeout and the owner-stack rebuild.
- `10_FINAL_EXECUTION_REPORT.md` remains the consolidated audit report (2026-11-23, with every claim re-checked against the logs).
- `09_FINAL_SYSTEM_STATUS.md` remains the audit's short status page.

| File | Purpose |
|---|---|
| `00_SYSTEM_BASELINE.md` | Repository state at start, versions, environment, data-safety measures, rollback copy |
| `01_COMPLETE_FEATURE_INVENTORY.md` | Every existing module from code: frontend, backend, database, tests, status, gaps |
| `02_INITIAL_TEST_RESULTS.md` | All test results before any fix |
| `03_BUGS_AND_FINDINGS.md` | Defects and findings with severity |
| `04_FIXES_IMPLEMENTED.md` | What was changed, why, and how it was tested |
| `05_FINAL_TEST_RESULTS.md` | All test results after the fixes, compared with the start |
| `06_MODULE_VERIFICATION_MATRIX.md` | Final status of every module with evidence |
| `07_SECURITY_AUDIT.md` | Security checks, results and remaining risks |
| `08_EXTERNAL_DEPENDENCIES.md` | What needs a phone, a public address, a KMS, a chain node or other outside resources |
| `09_FINAL_SYSTEM_STATUS.md` | Final state, acceptance criteria, readiness per module, next phase |
| `10_FINAL_EXECUTION_REPORT.md` | Consolidated final report: work done, files changed, tests before/after by category, module and security status, data/Docker/Git state, D1–D5 mapping, corrections to earlier reports |
| `11_FINAL_TECHNICAL_CLOSEOUT.md` | Closeout of 2026-11-23: FIX-4/5/6 live, F-06 QR checks, real-MongoDB tests, full regression, Git and Docker state, owner rebuild plan, open issues I-1 to I-11 |
| `12_POST_CLOSEOUT_REBUILD.md` | 2026-11-25: harness watchdog (I-5) and the approved owner-stack rebuild (I-1): backups, configuration check, rollout, checks, rollback |
| `13_FINAL_REPORT.md` | Final summary: verdict, fixes, test results, data safety, what is still open |
| `evidence/` | Raw logs (`initial_*`, `final_*`, `regression_*`), route lists, the test harness (`scripts/`), and the closeout (`closeout/`) and rebuild (`post_closeout/`) evidence |

## How the tests were run

- Isolated compose project `audit-20261121` (ports 29300–29383, own volumes, random test secrets kept outside the repo). The owner stack and its data were never used.
- Unit suites: gateway, recovery and fraud in the local `.venv`; identity in a container with no network and the repo mounted read-only (Windows Smart App Control blocks a native module locally).
- Live stages:
  - `evidence/scripts/stage.sh <log> <script>` resets the isolated stack first;
  - `run_noreset.sh` is for stages that need the previous stage's data;
  - since 2026-11-25, both runners use `run_limited` (`scripts/watchdog.sh`), a time limit that also stops the process tree on Windows.

  The scripts are the WP-31/WP-32 harness, retargeted to the audit stack.
- The owner stack was rebuilt on 2026-11-25 with the owner's approval (report 12). No test suite ran against it; only read-only checks did.
- No secret, token or password appears in any report or log in this folder.

## Rollback

`C:\Users\besna\secure-ssi-audit-rollback-20261121\` (outside OneDrive): `working-tree-now.patch`, `untracked-now.tgz`, `status-now.txt`, `HEAD.txt`, and `restored-old-web-files\` (37 old files that reappeared during the audit and were moved out with the user's approval). The first rollback copy on the Desktop was removed by something outside this session.

Owner-stack rebuild of 2026-11-25:
- backups are in `C:\ssi-backups\2026-11-25\` (outside OneDrive): a database dump, volume tars and container settings;
- rollback images are tagged `secure-ssi-platform-<service>:rollback-20261125`;
- the rollback commands are in report 12, C.9.
