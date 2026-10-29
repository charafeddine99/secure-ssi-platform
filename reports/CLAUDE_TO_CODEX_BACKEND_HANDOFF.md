# Claude → Codex Backend Handoff (matrix validation, 2026-10-29)

Scope: backend, API, security and persistence changes found while validating
`secure-ssi-platform_role-functionality-and-architecture-matrix.xlsx` against
current code and published sources. Claude did **not** change backend code in
this task. Row IDs refer to the validated copy
(`C:\Users\besna\Downloads\SECURE_SSI_MATRIX_VALIDATED.xlsx`) and
`reports/PRODUCT_GAP_MATRIX_VALIDATED.csv`.

Evidence environment: local Compose project `secure-ssi-wp18-local`
(gateway 127.0.0.1:19000, identity :19001, fraud :19002, recovery :19003),
synthetic fixture accounts only. No real personal data or database rows were
opened.

> Disclosure: earlier in this session (2026-10-28/29), at the owner's explicit
> request, Claude changed backend code: the gateway session cookie with CSRF
> checks, gateway error redaction, strict rate limiting on the token routes,
> did:web SSRF hardening with a pinned issuer DID, production-like env fail-closed
> settings, `local_user_seed.py`, and removal of the admin revoke permission
> (the owner decided that only issuers may revoke). Those changes are not
> committed. Please review them as part of this handoff. The identity suite
> passes on that tree: 744 passed, 12 skipped.

## Status update — 2026-10-29 (later): P0-1, P0-2, P0-3 and P1-A fixed by Claude
The owner approved Claude fixing these items directly ("Fix them yourself"). They
are not committed. **Codex: please review the diff; no further work is needed
unless the review finds problems.**

| Item | Change | Tests | Live evidence (local stack) |
|---|---|---|---|
| P0-1 offer read | `oid4vci_service.py`: `offer_id = offer_` + `secrets.token_urlsafe(24)`. New `get_offer_for_principal`: only the issuing authority or the addressed holder; everyone else gets 404. `oid4vci.py`: the GET route requires a principal. Frontend `getOid4vciOffer` now requires a session. | `tests/integration/test_oid4_protocols.py` (owner 200, holder 200, anonymous 401, verifier 404, id length) | Anonymous 401; unrelated user 404 with no code in the body; issuer 200; 38-character random ids |
| P0-2 traversal | Gateway `PathSafetyMiddleware` (`app/core/middleware.py`, registered in `main.py`): any `.`/`..` segment (decoded, so `%2e`/`%2F` are covered) or backslash → 400 `PATH_REJECTED` before routing | `tests/test_session_cookie.py` (encoded traversal and backslash; encoded identifiers still route) | Raw `../` (`curl --path-as-is`), `%2F` and `%2e%2e` → 400; 0 requests reached `/internal/` per the identity log |
| P0-3 audit | `audit.py`: MongoDB only. Failure → 503. `risk_score` is `null` when absent. Unknown filter → empty list. SQLite reader removed (the `/audit_logs` alias and `/audit/stats` share `_load_entries`). | `tests/unit/test_audit_api_authority.py` (4) | `/audit/logs` 200 from Mongo, null risk where absent, unknown filter count 0 |
| P1-A anchoring | `dependencies.get_revocation_anchor_scheduler`: returns `None` unless `BLOCKCHAIN_ENABLED`; otherwise an env-configured `BlockchainBridge` with the Mongo anchor repository. `credentials.py` revoke schedules it as a `BackgroundTasks` job after the response. `cache_and_anchor.BlockchainAnchorClient` reads the environment settings. | `tests/unit/test_revocation_anchor_wiring.py` (3) | Revoke → `CREDENTIAL_REVOCATION` **CONFIRMED**, tx `0x6991…`, block 6 (local chain 1337); revocation and verification results unchanged |

Suites after the fixes:

| Suite | Result |
|---|---|
| Identity | **751 passed**, 12 skipped |
| Gateway | 30 passed |
| Recovery | 52 passed |
| Fraud | 31 passed |
| Web | tsc, lint, 10/10 test files, build |

Regression scripts: `ops.mjs` 33/33, `rev.mjs` PASS, `trust.mjs` 5/5, `fixes.mjs` 8/8.

The P1 table below is still open for Codex. Owner decisions are unchanged.

## P0 — original findings (now fixed, kept for traceability)

### P0-1 Enumerable public credential-offer read leaks pre-authorized code and claims
- Rows: HOL-06, ISS-06, API-06, HIST-10, G5, CORE-05, OVR-09
- Evidence:
  - `services/identity-service/app/api/v1/oid4vci.py` `get_credential_offer`
    (GET `/api/v1/oid4vci/offers/{offer_id}`) has no auth dependency. It returns
    `pre_authorized_code` and `subject_data`.
  - `services/identity-service/app/application/services/oid4vci_service.py:153`
    builds `offer_id = f"offer_{ObjectId()}"`. ObjectIds are a timestamp plus
    per-process random bytes plus a counter, so they are predictable from one
    observed id.
- Source:
  - OpenID4VCI 1.0 Final §4.1.1: the pre-authorized code "MUST be short lived
    and single use"; §13.6.1 Replay Prevention.
  - OWASP API Security 2023 API1 (BOLA) and API2.
- Required change (choose one and record it in an ADR):
  1. Make offer references unguessable (≥128-bit `secrets.token_urlsafe`).
     Return `subject_data` only to the authenticated offer owner or the holder.
  2. Require holder authentication for the GET. Keep the credential offer
     (`credential_offer` / `credential_offer_uri`) as the only public artifact.
- Acceptance test: create two offers, derive neighbouring ids, GET as anonymous
  → 404/401 and no code or claims. Expired and reused codes are rejected at
  `/token` (reuse currently returns 400, which is correct).

### P0-2 Gateway forwards dot-segment paths to internal service routes
- Rows: CORE-01, API-01, OVR-21, G3, AUTH-01
- Evidence (live):
  - `GET /api/v1/identity/../../internal/v1/recovery/wallets/<id>/owners/x` → 401
    from the identity service. The identity log shows
    `GET /internal/v1/recovery/...`.
  - `POST .../../../internal/v1/recovery/key-rotation` → 401.
  - Only the internal recovery-grant check stops it. Without traversal these
    routes are unreachable from the gateway.
- Cause: `services/api-gateway/app/api/routes/proxy.py` builds
  `f"{SERVICE}/api/v1/{normalized}"` from the raw path parameter. httpx
  normalises `..`.
- Source: OWASP API Security 2023 API8 (Security Misconfiguration) and API9
  (Improper Inventory Management).
- Required change:
  - Reject (400) any path containing `.`/`..` segments, encoded dot segments
    (`%2e`), or backslashes before forwarding. Prefer an explicit allowlist of
    forwarded prefixes per service.
  - Apply the same to recovery, fraud and blockchain proxies. Also consider
    removing the legacy `/api/{path}` 404 fallbacks.
- Acceptance test: the traversal variants above return 400 at the gateway and
  never reach the services (check the service logs).

### P0-3 Audit API silently merges a deprecated SQLite store and reports SUCCESS
- Rows: OVR-20, CORE-15, SEC-23, HIST-16, API-19, SCP-20, ADM-10, G12
- Evidence: `services/identity-service/app/api/v1/audit.py` `list_audit_logs`
  does all of the following:
  - wraps the Mongo query in `except Exception` and logs only at debug level;
  - always merges `db_get_audit_logs()` from SQLite (`app/database.py`, marked
    deprecated);
  - returns `status="SUCCESS"`;
  - defaults a missing risk score to `5`.
- Source:
  - Project decision SCP-20 (MongoDB authoritative, no silent fallback);
  - NIST SSDF v1.1 PW/RV practices;
  - OWASP API8.
- Required change:
  - Read Mongo only.
  - On persistence failure return 503 `PERSISTENCE_UNAVAILABLE`.
  - Return `riskScore: null` when it is absent.
  - Remove the SQLite read path, or put it behind an explicit, disabled-by-default
    migration flag.
- Acceptance test: stop MongoDB in an isolated test DB, call the route, expect
  503 and no rows; restart and expect Mongo rows only.
- UI note: the admin audit table and charts already render 503 as "unavailable".

## P1

### P1-A Blockchain anchoring is not wired (the chain now runs locally)
- Rows: ADM-09, BC-16, G13, GOLD-24, CORE-14, OVR-17
- Local runtime prepared by Claude (no source change):
  - Hardhat node `127.0.0.1:8546`, chain 1337, started from `blockchain/`;
  - project contracts deployed at the deterministic addresses;
  - `blockchain/deployed-contracts.json` restored byte-for-byte;
  - identity reaches the chain via `host.docker.internal:8546`, set through the
    ignored local override/env files under `apps/web/node_modules/.cache/`.
  - Result: `/blockchain/status` reports `connected: true`, and the admin page
    shows all four contracts "Deployed · verified".
- Defect: `services/identity-service/app/infrastructure/cache_and_anchor.py`:
  - `BlockchainAnchorClient.__init__` calls
    `load_blockchain_settings({"BLOCKCHAIN_RPC_URL": rpc_url})` with the hard-coded
    default `http://127.0.0.1:8545`. Passing a dict instead of the environment
    drops `BLOCKCHAIN_ENABLED`, `BLOCKCHAIN_PRIVATE_KEY` and the real RPC URL.
  - The module singleton `blockchain_anchor = BlockchainAnchorClient()` is used only
    by `oid4vp_service.py` (quarantine read/write, ~lines 1431 and 1661).
  - Credential revocation, status-list publication and audit events never call
    `anchor_*`.
  - Result: after a live revoke, `/blockchain/anchors` stays empty.
- Required change:
  - Build the bridge from `get_blockchain_bridge()` (environment settings).
  - Call anchoring at the allowlisted transitions (revocation, status-list
    version, critical audit events) as an **optional, non-blocking** step.
  - Persist PENDING → CONFIRMED / FAILED with the receipt.
  - Never change the verification decision.
- Acceptance test: with the chain up, revoke → an anchor record with txHash, block
  and CONFIRMED status. With the chain down, revoke still succeeds, the anchor is
  FAILED/UNAVAILABLE, and the verification result is unchanged.

| ID | Item | Evidence | Required change | Acceptance |
|---|---|---|---|---|
| HOL-03, API-03, CORE-04, HIST-11, G6 | No owner-scoped "current wallet" API | Routes are `POST /wallets` and `GET /wallets/{id}` only. The web client caches the id in localStorage, so a new browser creates a new empty wallet (observed). | `GET /api/v1/wallets?owner=me` (or `/wallets/current`), owner taken from the principal. Make wallet creation idempotent per user. | Fresh browser shows the same wallet and credentials; cross-user returns 403. |
| ISS-07 | No issuer-scoped issued-credential list | `routes.txt` | List with minimal fields (id, type, status, issuedAt), issuer DID scope | Issue → listed; another issuer gets 403. |
| VER-07, HOL-12, HIST-12 | No verifier or holder history API | `routes.txt` | Scoped, minimal session/audit query | Action → event → list. |
| SEC-04, GOLD-07 | `tx_code` brute-force limiting not evidenced | `oid4vci.py` accepts `user_pin`/`tx_code`; the gateway's strict tier (30/min) now covers `/oid4vci/token` | Per-offer attempt counter with lockout | 6th wrong PIN → offer invalidated. |
| AI-09 | Quarantine scope and persistence not documented | fraud `POST/DELETE /quarantine/{did}` | Document the scope (DID); persist; audit | Restart keeps quarantine. |
| AI-12 | Fraud-service outage semantics not live-tested | n/a | Fault-injection test: unavailable ≠ LOW | Fraud down → explicit state; crypto-invalid still REJECT. |
| AI-13 | Client IP / user-agent passed to risk evaluation | `oid4vp.py process_direct_post(client_ip, user_agent)` | Document retention, minimise storage | Event field review. |
| SEC-19, HIST-18 | CSP added in `apps/web/nginx.conf` but not captured from a rebuilt container | Dockerfile injects the API origin | Rebuild `web`, capture headers, adjust `connect-src` | `curl -I` shows the CSP. |
| G11, REC-* | Recovery E2E not run live | recovery tests 52 pass | Live quorum, timelock and replay run | Negative transitions rejected. |

## Owner decisions needed before backend work
See `reports/PRODUCT_OWNER_DECISIONS.csv`: organizations (ISS-02, ADM-04),
verifier/AI policy versioning (VER-08, ADM-12, AI-10, API-18), DIDRegistry vs
off-chain trust (BC-05, HIST-14), DID hash salting (BC-13, HIST-15).

## Verified in this task (no change needed)
- Client-supplied `aiRiskScore` is ignored: `oid4vp.py` passes
  `ai_risk_score=None` (AI-02, RISK-02).
- Revocation:
  - issue → present = ACCEPTED;
  - the same VP after revoke = **REJECTED** ("Credential revoked (status bit set)");
  - the wallet refuses to present a revoked credential (400);
  - rows REV-02, SEC-07, ISS-09.
- Only the issuer can revoke. Live: admin 403, holder 403, issuer 200 (ISS-09,
  ADM-06).
- Anonymous call → 401; holder → admin users → 403; the session ends after
  sign-out (AUTH-01, CORE-02).
