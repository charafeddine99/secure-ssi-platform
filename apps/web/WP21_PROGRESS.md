# WP-21 Tabler integration — progress checkpoint

Resume from the first unchecked item. Do not stage, commit, push or switch branches.

## Decision (done)
- Selected theme: **Tabler** — https://github.com/tabler/tabler · demo https://preview.tabler.io · MIT (LICENSE read).
- Installed exact pins: `@tabler/core@1.6.1` (2026-09-28), `@tabler/icons-react@3.48.0` (2026-09-22). 1.7.1 skipped (published 4 days before selection).
- Rejected: shadcnstore/shadcn-dashboard-landing-template (MIT, but vite-version needs React 19, Tailwind 4, Vite 8, RR7, TS 6, ESLint 10);
  wilocampo/tailadminlte-react (MIT, 0 stars, last push 2026-03, Tailwind 4 / Vite 8 / RR7).
- Current stack kept: React 18.3, Vite 6, RR 6.28, TS 5.7, plain CSS.

## Plan
- [x] main.tsx imports `@tabler/core/dist/css/tabler.min.css` + small `styles/app.css` (brand + a11y only)
- [x] Rewrite components/ui/* internals to Tabler markup, keep their props APIs (new helpers: Page, Grid in PageHeader.tsx; DataGrid, Table in Card.tsx)
- [x] AppShell -> Tabler vertical layout (navbar-vertical navbar-expand-lg, page-wrapper, page-header, page-body, container-xl)
- [x] PublicLayout -> Tabler horizontal navbar + footer; LoginPage -> page-center / container-tight / card-md (login route moved outside PublicLayout, same path)
- [x] components/ssi/* (BrandMark, CredentialCard, RecoveryProgress, VerificationMatrix), RoleGuard, public pages, holder pages
- [x] Pages converted: issuer/*, verifier/*, guardian/*, admin/*
- [x] Prototype/demo copy removed (BrandMark tag, AppShell/PublicLayout footers, LoginPage "Prototype accounts", Landing, index.html meta, ScanQr/Security copy, oid4vpRequestUri errors)
- [x] lucide-react uninstalled; old styles/{index,tokens,base,layout,components}.css no longer imported (left on disk: untracked WP-18 files, not deleted)
- [x] tsc -b 0, lint 0, test 0 (fail 0), build 0
- [x] Fix: AppShell sets html[data-bs-navbar-position=vertical] (Tabler 1.6 hides the sidebar otherwise); desktop account bar moved inside page-wrapper
- [x] Browser check 1440x900, 1280x800, 390x844 — landing, login, holder wallet, issuer overview + issue form, verifier request + pending result, admin health, trust registry, audit log; mobile nav, account dropdown. Used user's dev server http://127.0.0.1:5173 (gateway CORS allows only :5173; API at :19000)
- [x] Review fixes: Suspense inside layouts (sidebar no longer vanishes on lazy load), dropdown right-anchored, admin health cards natural height, .table-responsive overflow-y hidden
- [x] Gates re-run after fixes: tsc 0, lint 0, tests 8/8, build 0
- Not inspected with data: Recovery & security, Guardian pages (blocked by recovery 401 below); accepted/rejected verifier result (needs a holder credential)
- BLOCKER (backend/Codex): /api/v1/recovery/* returns 401 for a valid holder token while /identity/* returns 200; http.ts treats 401 as session expiry -> Recovery & security and Guardian pages sign the user out.

## Round 2 (user: "still looks like a prototype; nicer colours, same font, symmetric, background image, little text")
- [x] Inter (@fontsource-variable/inter 5.2.8, OFL) self-hosted; tabler-themes.min.css with html[data-bs-theme-base=slate][data-bs-theme-primary=blue]
- [x] Restored the project's own brand art src/assets/ssi-trust-network.svg (deleted in WP-18, restored from HEAD) as the background image
- [x] Tabler navbar-overlap band on every Page (navy + artwork), dark public top bar, landing hero, sign-in-cover layout
- [x] Sidebar account menu moved to the sidebar bottom (desktop top bar removed)
- [x] Copy cut down: short page descriptions, most card subtitles removed, long notes shortened
- [x] Symmetry: row-deck on split rows, 2-per-row stats on phones
- [x] Gates: tsc 0, lint 0, tests 8/8, build 0

## Round 3 (user: "more professional, cinematic, new themes and backgrounds")
- [x] Appearance panel (Tabler offcanvas "Customize" pattern): mode dark/light, 8 accent colours (tabler-themes), base palette, corner radius, background (Aurora animated / Trust network / Grid / Plain); saved in localStorage key ssi_appearance
- [x] Files: src/theme/{appearance.ts, AppearanceProvider.tsx, AppearancePanel.tsx}; App.tsx wraps AppearanceProvider; buttons in sidebar, mobile header, public navbar, sign-in
- [x] Cinematic default: dark + indigo + aurora; glass cards, accent glows from var(--tblr-primary), page/card entrance animation, reduced-motion fallback
- [x] Gates: tsc 0, lint 0, tests 8/8, build 0

## Round 4 (user: "background images on all pages, project-related designs, more designed")
- [x] Original SSI illustrations: src/assets/art/{wallet,issuer,verifier,guardian,admin}.svg (+ existing ssi-trust-network.svg for public pages)
- [x] html[data-ssi-area] set from the route (theme/appearance.ts areaForPath/useArtArea); band + fixed floating .ssi-scene show the area art on every page; "Plain" backdrop hides it
- [x] Decorative detail: accent edge highlight on cards, glowing ring behind empty-state icons, accent wash on stat tiles, taller desktop band
- [x] Light mode uses solid cards; band shade lighter on small screens so the art shows
- [x] Gates: tsc 0, lint 0, tests 8/8, build 0

## Round 5 (user: transparent account menu bug, "more errors", stronger modern design -> chose "Cinematic dark")
- [x] Fix: account menu solid (.ssi-account-menu) and top bars z-index 1030 so menus sit above the band
- [x] Sweep (overflow, tap targets, error states) at 390/1280 for public, holder, issuer, verifier, admin pages
  - fixed: breadcrumb tap target 17px -> 24px; trust registry table 25px overflow at 1280; scene art hidden on phones
  - BLOCKER (backend/Codex): GET /api/v1/identity/admin/users and /issuer-options return 503
- [x] Ctrl/Cmd+K command palette (components/ui/CommandPalette.tsx) + glass command bar with search and live workspace pill
- [x] Cinematic: band aurora animation, neon title underline, glowing stat numbers, neon card edges, illustrated empty states
- [x] Appearance storage key bumped to ssi_appearance_v2 (cinematic dark default once)
- [x] Gates: tsc 0, lint 0, tests 8/8, build 0

## Round 6 (user: "nothing changed" on sign-in) — root cause: in-app pane is 689px CSS wide (dpr 2), below lg/md
- [x] Sign-in below lg: full-screen brand artwork + glass form card (selector html[data-bs-theme] .ssi-auth-panel)
- [x] Band taller with visible art below lg; scene art kept at 576-767px
- [x] Tables: Table stackBelow prop, default sm; wide tables (ecosystem, trust registry, audit, recovery requests, users, anchors) md
- [x] Entrance animation shortened to 0.3s
- [x] Gates: tsc 0, lint 0, tests 0, build 0

## Round 7 (user: "still plain; dark and light mode not done on all pages")
- [x] Theme-aware bars: sidebar, command bar, public bar use data-bs-theme={mode}; frosted white in light
- [x] Light band: soft accent gradient + dark text; band art moved to .ssi-band-art and recoloured (invert+hue-rotate) in light; scene and empty-state art too
- [x] theme/ModeToggle.tsx (sun/moon) in command bar, mobile header, public bar, sign-in
- [x] components/ssi/QuickActions.tsx tiles on holder, issuer, verifier, admin dashboards (real routes only)
- [x] components/ssi/TrustTriangle.tsx diagram on landing
- [x] Headless Edge capture script (scratchpad shoot.mjs) for 24 pages x 2 modes
- [x] Gates: tsc 0, lint 0, tests 8/8, build 0

## Round 9 (user approved: wallet pass, animated verification, charts)
- [x] components/ssi/CredentialCard.tsx: flip wallet pass (hue per type, QR of credential ID, honest stored status, attributes on back)
- [x] VerificationMatrix: checks reveal one by one; PolicyBanner is an animated verdict seal card (also on holder consent outcome)
- [x] components/ui/Charts.tsx (SVG DonutChart, BarChart): issuer offer-status donut; admin audit-per-day bars + event-mix donut (real fetchAuditLogs data)
- [x] Gates: tsc 0, lint 0, tests 8/8, build 0
- [ ] Live visual check NOT done: Docker Desktop stopped (19000/8000 refused). Re-run scratchpad flow.mjs after backend is up (issuer offer -> holder claim -> verifier request -> holder share -> screenshots)
- [x] Docker Desktop restarted on user OK; secure-ssi-wp18-local stack (gateway 19000) came back healthy on its own
- [x] Live: admin charts and issuer donut verified with real data (scratchpad/flow/33,34)
- BLOCKER (backend/Codex): OID4VCI offer creation accepts subjects the issuance validator later rejects (programCode must match ^SYN-..., degree allowlist) -> offers that can never be claimed
- BLOCKER (backend/Codex): credential request returns HTTP 500 'internal error' for a valid UniversityAffiliationCredential offer (programCode SYN-CS-301, Bachelor of Science); no log output
- [ ] Wallet pass + verdict seal not yet seen with live data (needs a stored credential; blocked by the 500)
- Test data created in local stack: 3 pending issuer offers, 1 verifier OID4VP session
- Frontend follow-up: issuer form should show the allowed values (degree list, SYN- programCode) as a select/hint
- [x] Issuer form: structured fields for UniversityAffiliationCredential (affiliation/degree selects, SYN- programme code, year 2000-2100), Edit-as-JSON toggle; parseOfferDraft applies the same rules + rejects extra keys (issuerLogic.ts)
- [x] tests/issuerProfile.test.ts (13 assertions); gates: tsc 0, lint 0, tests 9/9 files, build 0

## Round 10: security hardening, user approved backend scope (2026-10-28)
Findings: B1 recovery 401 = IDENTITY/RECOVERY JWT secrets differ in apps/web/node_modules/.cache/secure-ssi-wp20.env (stack secure-ssi-wp18-local, compose: docker-compose.yml + .cache/secure-ssi-wp20.override.yml);
B2 credential request 500 (no logs); B3 offer creation vs credential_validator mismatch (programCode ^SYN-, degree allowlist);
B4 admin users 503 by design (fixture user provider); B5 shared HS256 + dev fallback secret in recovery config;
F1 token in localStorage (gateway has NO cookie session; docs page wrongly claims it); F2 react-router 6 CVEs (fix 7.18.5); F3 vite<=6.4.3 high + dev host 0.0.0.0; F4 nginx lacks CSP/Permissions-Policy; F5 docs copy
- [x] B1 compose feeds IDENTITY_* secrets to recovery (docker-compose.yml, .env.example note); recovery container recreated; recovery API 200 with holder token
- [x] B5 fail-closed env allowlist {development,dev,local,test,testing} + reject published dev secrets (identity auth_settings, recovery_grant_settings, recovery config) + tests
- [x] B2 root cause: own issuer did:web resolved over network (regression a23f54d, allow_insecure_http=True hard-coded, no SSRF check). Fix: PinnedDidWebResolver + hardened DidWebResolver (HTTPS, all-address SSRF check, IP pinning w/ SNI, no redirects, http only for allowlisted dev hosts via IDENTITY_DID_WEB_ALLOW_INSECURE_HTTP/IDENTITY_DID_WEB_INSECURE_HOSTS, refused in prod); DidResolutionError -> 502 DID_RESOLUTION_FAILED; unexpected errors log type+location (no message)
- [x] B3 offer creation enforces SYN- programCode + year 2000-2100 (shared PROGRAM_CODE_PATTERN)
- identity tests: 735 pass; 3 pre-existing consent-policy failures (tests don't record consent; new WP08 rule), not touched
- [ ] F1 gateway cookie session, F2-F5, rebuild stack + live flow

## Round 11 — security hardening (backend + frontend, user-approved scope) — 2026-10-28
- [x] Gateway HttpOnly session: `__Host-ssi_session` (Secure, HttpOnly, SameSite=Strict, Path=/, no Domain, Max-Age from expiresIn) set when `X-SSI-Client: web`; token removed from the sign-in JSON; cookie -> Bearer only when no explicit Authorization; Cookie/X-SSI-Client never forwarded upstream; cleared on revoke and upstream 401 (services/api-gateway/app/core/session.py, proxy.py)
- [x] CSRF for cookie requests: custom header + Origin allowlist + Sec-Fetch-Site != cross-site -> 403 CSRF_REJECTED
- [x] CORS: removed any-localhost-port regex; explicit methods/headers
- [x] 502 BAD_GATEWAY no longer echoes exception text
- [x] Strict 30/min tier now covers /identity/auth/token, /oid4vci/token (PIN guessing), /oid4vci/credential
- [x] Frontend: no token in localStorage (marker `ssi_session_active` only; legacy token keys purged); fetch credentials include; sign-out always revokes (bug found live and fixed)
- [x] react-router-dom 7.18.4, vite 6.4.4 (exact, >=2 weeks old); npm audit 0; dev binds 127.0.0.1; Dockerfile npm ci
- [x] nginx: CSP (connect-src self + API origin injected at build), Permissions-Policy, COOP, CORP, server_tokens off
- [x] Admin users 503 explained (sample accounts read-only)
- [x] 3 identity tests fixed by recording holder consent (tests/support/consent.py)
- Results: gateway 28 passed; identity 738 expected (3 fixed files 29/29; full run before fix 735 passed + those 3); recovery 52 passed; web tsc/lint/9 tests/build OK
- Live: login -> cookie (not JS-visible), reload keeps session, sign-out -> /me 401; curl CSRF probes 403/403/200; OID4VCI credential claim 200 (was 500)
- launch.json: added `web-local-stack` (port 5174, API 19000). User's own :5173 dev server still runs pre-upgrade code -> restart it.
- [x] Live flow re-run on cookie session (5174 -> 19000): issuer offer -> holder claim (stored, Active) -> verifier request -> holder share -> verdict ACCEPTED, 8/8 checks passed; wallet pass front/back, admin charts, issuer donut screenshots in scratchpad flow/

## Round 12 — "nothing works / sign-in" (2026-10-29)
- Root causes: Docker Desktop had stopped (no backend); dev server on :5173 called http://127.0.0.1:8000 (nothing there) and localhost vs 127.0.0.1 broke the SameSite cookie.
- [x] Docker restarted; vite.config.ts proxies /api -> VITE_DEV_API_TARGET (default http://127.0.0.1:19000); in dev the client uses same-origin /api (http.ts). Works on localhost and 127.0.0.1.
- [x] Admin users 503 fixed for local stack: app/infrastructure/persistence/local_user_seed.py (dev-only, hashes only, idempotent, refuses production; tests/unit/test_local_user_seed.py) seeded Mongo; local env file now IDENTITY_AUTH_USER_PROVIDER=mongodb.
- [x] Crawl: 4 roles, 24 pages, 0 error states, 0 unexpected API failures. E2E flow ACCEPTED 8/8. ops.mjs: 30 write/security operations, 29 pass + 1 = admin may revoke (RBAC ADMIN has all permissions by design; reported, not changed).
- Tests: identity 740 passed 0 failed; gateway 28; recovery 52; fraud 31; web tsc/lint/9 tests/build OK; npm audit 0.

## Round 13 — only issuers revoke (user decision 2026-10-29)
- [x] RBAC: ADMIN = all permissions except credentials:revoke (app/domain/permissions.py)
- [x] Revocation service: no admin override, no account-name exceptions; caller's bound issuer DID must equal credential issuer
- [x] History (read-only audit): issuer (credentials:revoke) or admin (admin:operations:read) via new require_any_permission; account-name exceptions removed
- [x] Tests updated + 5 negative cases; live ops.mjs 33/33 (admin revoke 403, admin history 200)

## Round 14 — matrix validation + admin fixes (2026-10-29)
- [x] Workbook validated row by row (349 rows) -> C:\Users\besna\Downloads\SECURE_SSI_MATRIX_VALIDATED.xlsx; reports/PRODUCT_* + CLAUDE_TO_CODEX_BACKEND_HANDOFF.md + FRONTEND_IMPLEMENTATION_CHECKLIST.md
- [x] P0 for Codex: public guessable offer read (code+claims), gateway '../' traversal to /internal, audit SQLite merge; P1-A anchoring not wired (cache_and_anchor ignores env)
- [x] Frontend: wallet key list (keys.ts), credential status history (status.ts + RevocationRegistryPage), ethers removed, stat-card text sizing fix (user screenshot)
- [x] Runtime: Hardhat node 127.0.0.1:8546 via launch.json "chain"; identity BLOCKCHAIN_* via local override/env -> admin anchoring page Connected
- [x] Live: rev.mjs (revoked VP REJECTED), trust.mjs (suspend/revoke), ops.mjs 33/33; scripts in session scratchpad
- Not run: axe/WCAG, recovery live E2E, external interop (L4); LibreOffice absent (workbook recalcs on open in Excel)

## Round 15 — owner approved: Claude fixes backend P0s + anchoring (2026-10-29) — IN PROGRESS
Resume order (tick as done):
- [x] P0-1 offer read: random offer ids (secrets.token_urlsafe(24)); GET /oid4vci/offers/{id} needs auth, only issuing authority or addressed holder, else 404 (oid4vci_service.get_offer_for_principal, oid4vci.py); test_oid4_protocols updated; frontend issuance.ts getOid4vciOffer now auth required. 32 offer tests pass.
- [x] P0-2 gateway traversal: PathSafetyMiddleware (app/core/middleware.py, main.py) rejects '.'/'..' segments + backslash -> 400 PATH_REJECTED; tests in test_session_cookie.py; gateway 30/30. TODO live: curl --path-as-is /api/v1/identity/../../internal/... -> expect 400 after gateway rebuild.
- [x] P0-3 audit (done: Mongo-only, 503, risk null; tests/unit/test_audit_api_authority.py): identity app/api/v1/audit.py list_audit_logs -> Mongo only, 503 on persistence failure, riskScore null when absent, remove SQLite merge (+ legacy alias /audit_logs same handler). Frontend admin.ts fetchAuditLogs reads risk_score number|null already.
- [x] P1-A anchoring CODE DONE (dependencies.get_revocation_anchor_scheduler + credentials.py BackgroundTasks; cache_and_anchor env settings; tests/unit/test_revocation_anchor_wiring.py; 68 related tests pass). NOT yet live-verified. Original plan: identity app/infrastructure/cache_and_anchor.py BlockchainAnchorClient must use env settings (load_blockchain_settings() / get_blockchain_bridge); call optional non-blocking anchor on credential revocation (credential_revocation_service) + persist record (MongoBlockchainAnchorRepository) PENDING->CONFIRMED/FAILED; never change verification decision.
- [x] Run suites (identity 751 passed, gateway 30, recovery 52, fraud 31, web OK): identity (~4 min, run_in_background), gateway, recovery, fraud; web tsc/lint/test/build
- [x] Rebuild stack (done; Docker had stopped again, restarted): docker compose -p secure-ssi-wp18-local -f docker-compose.yml -f apps/web/node_modules/.cache/secure-ssi-wp20.override.yml --env-file apps/web/node_modules/.cache/secure-ssi-wp20.env up -d --build api-gateway identity-service
- [x] Chain running (redeployed contracts; deployed-contracts.json restored): preview_start name "chain" (.claude/launch.json, 127.0.0.1:8546); identity env LOCAL_CHAIN_* in the .env cache file already set
- [x] Live verify (fixes.mjs 8/8 incl. anchor CONFIRMED block 6; ops 33/33; rev PASS; trust 5/5; traversal 400): scratchpad scripts ops.mjs, rev.mjs, trust.mjs (session scratchpad), traversal curl, offer anon 401 / other 404, revoke -> /api/v1/blockchain/anchors shows CONFIRMED
- [x] Update reports (handoff status section, matrix regenerated: 0 Critical left)/CLAUDE_TO_CODEX_BACKEND_HANDOFF.md (mark P0-1..3, P1-A fixed by Claude) + regenerate validated matrix (scratchpad xl/build.py post; vdata3.py overrides) + FRONTEND checklist
- PAUSED by user 2026-10-29 ('dur'): next = full suites, stack rebuild (gateway+identity), live checks, report updates. User said (2026-10-29): continue directly when the session/token renews — no need to ask.
- Round 15 COMPLETE 2026-10-29. Note: Vite (:5173) and chain (:8546) run as app preview servers; after an app restart start them with preview_start 'web' and 'chain' (redeploy contracts with scratch hardhat.local8546 config).

## Round 16 — continue open items (2026-10-30) — IN PROGRESS
- [x] HOL-03 current wallet (done; 56 wallet/golden tests pass): identity GET /api/v1/wallets (owner-scoped list) + frontend wallet.ts getOrCreateHolderWallet uses it before POST
- [x] SEC-04 tx_code attempt limit (done: MAX_TX_CODE_ATTEMPTS=5, compare_digest, repo record_pin_failure; tests pass). Note flaky STATUS_LIST_NOT_YET_VALID timing test (pre-existing) -> per offer (oid4vci token endpoint)
- [x] Suites + rebuild identity + live checks (round16.mjs 5/5; regressions pass) (start preview 'web' + 'chain' if app restarted)
- [x] axe-core 4.14.0 devDependency (user approved): 24 pages x light/dark = 0 violations after fixes (search button label-in-name, light-mode contrast, card-status layer). Manual AT pass still open. Also vite 6.4.4 -> 6.4.5 (GHSA-8g5g-mxqh-grgj, security patch exception to 2-week rule).
- [x] Update handoff/checklist/matrix (scratchpad xl/vdata3.py + build.py post)
