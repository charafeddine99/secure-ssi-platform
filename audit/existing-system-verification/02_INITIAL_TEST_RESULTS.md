# 02 – Initial Test Results (before any fix)

Date: 2026-11-21. Code: working tree of `besna-dev` as found (see `00_SYSTEM_BASELINE.md`). Logs: `evidence/initial_*.log`.

## Unit and integration suites

| Suite | Command | Environment | Passed | Failed | Skipped | Time | Log |
|---|---|---|---|---|---|---|---|
| API gateway | `pytest -q` | local `.venv` | 48 | 0 | 0 | 26 s | `initial_api-gateway.log` |
| Recovery | `pytest -q` | local `.venv` | 131 | 0 | 1 | 4 s | `initial_recovery-service.log` |
| Fraud | `pytest -q` | local `.venv` | 90 | 0 | 0 | 4 s | `initial_fraud-service.log` (first attempt: collection error, Smart App Control blocked a scikit-learn DLL once) |
| Identity | `pytest -q -rs tests` | container, `--network none`, repo read-only | 1083 | 0 | 12 | 62 s | `initial_identity-service.log` |
| Identity, real MongoDB repositories | `pytest tests/integration/test_mongo_repositories.py` | container on the audit network, throwaway database | 7 | 0 | 0 | 3 s | `initial_identity_mongo_integration.log` |
| Shared package | `unittest discover packages/shared/tests` | local | 5 | 0 | 0 | <1 s | `initial_shared_pkg.log` |
| Root tests | `unittest discover tests` | local | 3 | 0 | 0 | 11 s | `initial_root_tests.log` |
| Web unit | `npm test` | Node 24 | 42 | 0 | 0 | 6 s | `initial_web_unit.log` |
| Web build | `npm run build` (`tsc -b` + Vite) | Node 24 | exit 0 | | | 18 s | `initial_web_build.log` |
| Web lint | `npm run lint` | Node 24 | exit 0 | | | | `initial_web_lint.log` |

The 12 identity skips: 7 real-MongoDB tests (run separately above, 7/7) and 5 blockchain tests that need a local Hardhat node on port 8545 (not running; external dependency).

## Live stages on the isolated `audit-20261121` stack

Harness: the WP-31/WP-32 scripts, copied to `evidence/scripts/` and retargeted. Each stage starts on a reset stack unless it needs the previous stage's data.

| Stage | Covers | Passed | Failed | Notes |
|---|---|---|---|---|
| E2E (`wp31_e2e.mjs`) | Auth, MFA/step-up, issuance (OID4VCI), presentation, revocation, ledger tamper resistance, guardians, recovery, wallet backup/restore, QR | 130 | 2 | The 2 failures are outdated pre-WP-32 QR expectations (F-06). Earlier tries: 128/132 with the default public origin (F-01), 36/46 before the step-up secrets matched (F-02). *Correction 2026-11-23: the saved log `initial_e2e_run2_stepup403.log` shows 41 passed checks and then an abort with a step-up 403 on the guardian policy step; the figure 36/46 is not backed by a saved log.* |
| Gaps (`wp31_gaps.mjs`) | Expired offers, audit chain tamper detection, misc. | 38 | 0 | |
| Post (`wp31_post.mjs`) | State after E2E | 15 | 0 | Run directly after E2E (an earlier run after a reset was invalid by design: 6/15) |
| Onboarding (`wp32_onboarding.mjs`) | Registration, applications, invitations, role allow-lists | 40 | 0 | |
| Scenarios (`wp31_scenarios.mjs`) | Security intelligence: synthetic attack scenarios, rules, incidents | 41 | 0 | |
| OID4VP security (`wp32_oid4vp_security.mjs`) | Replay, nonce, audience, expiry, tampering, foreign request_uri | 16 | 0 | |
| request_uri scan (`wp32_scan_request_uri.mjs`) | Scan page with request_uri links, JSON parsing, double-encoding regression | 11 | 0 | |
| Wallet card UI (`wp32_card.mjs`) | Green card, no clipping, Issuer status, Present, Attributes, Details, keyboard focus | 31 | 0 | |
| Cross-device (`wp32_cross_device.mjs`) | Two browsers, QR decoded from the canvas with jsQR, consent, verdict, re-scan | 13 | 0 | First run stalled after 9 passes (test timing); second run 13/13. **Not a physical phone.** |
| Browser (`wp31_browser.mjs`) | Full UI flows in headless Edge | 40 | 0 | |
| Pages (`wp31_pages.mjs`) | 62 page/viewport combinations | 62 pages | 0 | axe violations 0, console errors 0, horizontal overflow 0 |
| DR drill (`wp31_dr.mjs`) | Platform backup, archive verify, dual-control restore into a separate mongod, restored stack boots and works | 32 | 0 | First run passed 19 checks, then could not build images because OneDrive kept a `node_modules` file online-only; re-run with the already-built images: 32/32 |
| UI / wp32 UI | Security intelligence tabs, registration and account security UI | see `05` | | First runs were in the wrong order (no synthetic data yet; admin already enrolled); re-run in order |

## Compared with earlier reports

| Area | Earlier | Now |
|---|---|---|
| Identity | 1080 + 3 rerun (WP-32) | 1083 / 12 skip |
| Recovery | 131 (WP-32) | 131 / 1 skip |
| Gateway | 48 | 48 |
| Fraud | 90 | 90 |
| Web unit | 42/42 | 42/42 |
| E2E | 132 (WP-31) | 130 + 2 outdated checks |
| DR | 32 | 32 |
| Card / scan / cross / security | 31 / 11 / 13 / 16 | 31 / 11 / 13 / 16 |
| Browser | 40 | 40 |
