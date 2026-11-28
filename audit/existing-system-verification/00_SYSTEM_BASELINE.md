# 00 – System Baseline

Audit start: 2026-11-21 (Europe/Istanbul). Auditor: Claude Code session in the desktop app.

## Repository

| Item | Value |
|---|---|
| Location | `C:\Users\besna\OneDrive\Bureau\secure-ssi-platform` |
| Branch | `besna-dev` (not changed during the audit) |
| HEAD | `9fa97d75b4bec58fdcf5c59d4db26068143b5037` (2026-11-03, "fix: make a fresh docker compose stack fully usable out of the box") |
| Uncommitted work at start | 233 entries: 130 modified, 102 untracked, 1 deleted (`apps/web/src/pages/admin/AiFraudMonitorPage.tsx`) |
| Commits / pushes / branch switches | None. Not allowed by the task. |

The uncommitted work is the WP-28 to WP-32 work (recovery, backup/restore, DR, security intelligence, onboarding, request_uri/JAR, wallet card). It is the state being audited.

## Rollback copy (taken before any test or change)

`C:\Users\besna\OneDrive\Bureau\secure-ssi-audit-rollback-20261121\`

| File | Content |
|---|---|
| `HEAD.txt` | Commit the working tree is based on |
| `status.txt` | `git status --porcelain` at start |
| `working-tree.patch` | `git diff --binary` of all tracked changes |
| `untracked.tgz` | All untracked, non-ignored files |

To roll back a single file: `git checkout -- <file>` and re-apply from the patch. Restoring everything: re-apply `working-tree.patch` on `HEAD` and unpack `untracked.tgz`. Neither was needed.

## Layout

| Part | Path | Technology |
|---|---|---|
| Web app | `apps/web` | React 18.3, TypeScript 5.7, Vite 6.4, Tabler 1.6, React Router 7.18 |
| API gateway | `services/api-gateway` | Python, FastAPI 0.141.1, Pydantic 2.13.5 |
| Identity service | `services/identity-service` | FastAPI; VC 2.0, Data Integrity (eddsa-jcs-2022), OID4VCI, OID4VP, wallets, status lists, trust registry, audit, platform backup, KMS abstraction, WebAuthn (webauthn 3.0.1), TOTP |
| Recovery service | `services/recovery-service` | FastAPI; guardians, M-of-N policy, time lock, Shamir shares |
| Fraud service | `services/fraud-service` | FastAPI; rule-based risk, security intelligence (rules, median/MAD anomalies, incidents), scikit-learn 1.9.1 present |
| Shared package | `packages/shared` | Python helpers |
| Smart contracts | `blockchain/` | Solidity, Hardhat (optional local anchoring) |
| Data | MongoDB 7, Redis 7 | via `docker-compose.yml` |

Registered API operations (from each service's OpenAPI schema, `evidence/routes_*.txt`): identity 117, recovery 25, fraud 21, gateway 44 (mostly proxies). Web routes: 36 (`apps/web/src/routes/AppRoutes.tsx`).

## Run and test environment

| Item | Value |
|---|---|
| OS | Windows 11 Home 10.0.26300 |
| Local Python | `.venv` Python 3.11.16, pytest 9.1.1 |
| Container Python | 3.12.16 (service images) |
| Node | 24.19.0 |
| Docker | Engine 29.8.1, Compose 5.5.1. Docker Desktop was off at start; started with the user's approval on 2026-11-21. |
| Windows Smart App Control | **On** (policy state 1). It blocks unsigned native Python modules (`cbor2`, sometimes scikit-learn) in the local `.venv`. Identity tests therefore run in a container. Security settings were not changed. |

## Database safety

| Rule | How it was kept |
|---|---|
| Owner data untouched | The owner stack (`secure-ssi-platform`, volumes `secure-ssi-platform_*`) was never targeted. Docker restarted it automatically on start-up (its restart policy); it was not stopped, rebuilt, reset or queried. |
| Isolated test stack | New compose project `audit-20261121` with its own network, its own new volumes and ports 29300–29383 (bound to 127.0.0.1). |
| Isolated secrets | A separate env file with freshly generated random test secrets, kept in the session scratch folder (not in the repo). No secret is written to any report. |
| Synthetic users only | Accounts `*@wp31.test` plus the built-in fixture users, random passwords. |
| Resets | `evidence/scripts/reset_audit.sh` empties collections only in the `audit-20261121` MongoDB (checked by compose project label) and clears that stack's ledger anchor file. No volume is removed, no `down -v`. |
| Unit tests | Identity tests run in a container with `--network none` and the repo mounted read-only, so they cannot reach any database. |

## Earlier results (not used as current results)

Reported earlier: WP-28 E2E 110, Identity 792/12 skip, Recovery 57/1 skip, Fraud 32, Gateway 32, Web 16; WP-30 E2E 131, DR 31, Identity 995/12 skip, Browser 20 (interrupted); WP-32 request_uri 11/11, card 24/24 (31/31 final), web 40/40 (42/42 final). All suites were re-run in this audit; see `02_INITIAL_TEST_RESULTS.md`.
