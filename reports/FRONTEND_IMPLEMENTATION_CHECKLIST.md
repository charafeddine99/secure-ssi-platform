# Frontend Implementation Checklist (validated, 2026-10-29)

Only requirements validated as applicable **and** backed by an existing backend route.
Owner: Claude (apps/web). Route names come from the live OpenAPI schemas.
Each item lists its matrix IDs.

Priority order:
1. P0 security
2. Issuance/presentation golden path
3. Persistence and authorization
4. Role-page capabilities
5. AI/blockchain
6. Polish

## Done earlier in this session (verified)

| IDs | Item | API | Evidence |
|---|---|---|---|
| PUB-05, CORE-02, SEC-18, HIST-17 | HttpOnly cookie session (no token in JS), CSRF header | `/identity/auth/token`, `/auth/me`, `/auth/revoke` | Live sign-in, reload and sign-out; `document.cookie` empty; CSRF probes 403 |
| HIST-05, HIST-28 | Dev server reaches the backend under localhost and 127.0.0.1 | Vite `/api` proxy → gateway | 4-role crawl, 24 pages, 0 error states |
| ISS-05, ISS-06 (UI), GOLD-03..09 | Issuer offer form with allowed-value selects matching backend validation | `/oid4vci/offers` | Browser flow; `tests/issuerProfile.test.ts` (13) |
| HOL-10, HOL-11, GOLD-14..22 | Consent with truthful full-disclosure notice; verdict + 8 check rows from the backend | `/oid4vp/*` | Browser flow, ACCEPTED 8/8 |
| ADM-02 | Users and issuer scope (persistent store) | `/identity/admin/users*` | ops.mjs |
| PUB-01, SEC-24, HIST-23 | No "prototype" product copy; environment markers kept | n/a | Copy scan |
| SEC-20 (part) | Patched react-router-dom 7.18.4 / vite 6.4.4, npm audit 0 | n/a | `npm audit` |

## Implemented in this task

| Priority | IDs | Item | Backend route (exists) | Test |
|---|---|---|---|---|
| P1 | HOL-02, API-04 | Holder: read-only wallet key list (state, algorithm, fingerprint, version, created); no private material | `GET /identity/wallets/{wallet_id}/keys` | `tests/walletKeys_contract.test.ts` + browser (Ed25519 · Presentation signing · Active) |
| P1 | ISS-08 | Issuer: credential status history timeline on the Status & revocation page | `GET /identity/credentials/{credential_id}/history` | `tests/walletKeys_contract.test.ts` (history parser + route) + browser (signed → verified → revoked → rejected) |
| P1 | User report 2026-10-29 | Admin stat cards: text and badge values (engine name, data scope, node state) use a readable size instead of the 30px KPI size | n/a (CSS `.ssi-stat-value:has(*)`) | Browser: Risk engine, Optional anchoring |
| P2 | HIST-20, SEC-20 | Remove the unused `ethers` dependency (no imports in apps/web) | n/a | tsc/lint/tests/build pass; npm audit 0 |

Correction: ADM-05 (trust registry suspend/revoke) was first listed as missing, but
the UI already had it (`TrustRegistryPage.tsx:106-107`). It was verified live
through the API instead (`trust.mjs`):

| Step | Result |
|---|---|
| Create record | 201 |
| Issuer suspend | 403 |
| Admin suspend | 200 |
| Evaluate suspended issuer | 422, not trusted |
| Admin revoke | 200 |

Runtime: the admin "Optional anchoring" page now shows **Connected** (local Hardhat
node, contracts verified). Anchor records stay empty until Codex wires anchoring
(handoff P1-A).

## Blocked on backend (see `CLAUDE_TO_CODEX_BACKEND_HANDOFF.md`)
- HOL-03 / G6: stable wallet across browsers. Needs a current-wallet API.
- HOL-12, VER-07, ISS-07: history and list pages. Needs scoped APIs; the UI keeps honest
  "not available" states.
- ADM-10: audit authority (SQLite merge). The UI renders the backend result as-is.

## Not started (owner decision or optional)
- OD-01 organizations (ISS-02, ADM-04, ISS-11)
- OD-02 policy editor (VER-08, ADM-12)
- OD-05 quarantine actions (ADM-07)
- OD-06 multi-session list (HOL-13)
- OD-07 notifications and extra history views
- HOL-04 search/filter (P2)
- HOL-08 camera scanning (P2)

## Still to verify (frontend)
- SEC-21 / HIST-21: run axe-core and a manual keyboard/screen-reader pass. Until
  then there is no WCAG conformance claim.
- SEC-19: capture CSP headers from a rebuilt `web` container.
