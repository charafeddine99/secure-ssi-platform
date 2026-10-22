# Secure SSI Platform — UX/UI Implementation and Acceptance Plan

**Status:** Proposed execution sequence. This document is a G12 UX work package subordinate to the Revised Master Implementation Plan; it does not replace that plan or change G0–G16 ordering.  
**Planning date:** 19 October 2026.  
**Application changes:** None in this planning phase.  
**Commit/push:** None.

## 1. Gate position and entry conditions

The controlling plan places UX professionalization at G12, after the cross-layer Golden Path at G11 is in progress. The latest gate/status documents mark G11 PARTIAL/NOT VERIFIED for the current browser journey and G12 PARTIAL. Therefore:

- Build the UX work from the route/API blueprint now, but do not mark G11 or G12 PASS based on design documents or screenshots.
- Preserve the frozen SSI protocol profile and existing working-tree changes.
- Implement truthful UI for the four actual backend roles first. Map the eight requested permission profiles, but do not mint new role names, organization scopes, or admin tasks in the frontend.
- Resolve the Guardian role discrepancy and verify API organization/ownership scopes before routing/panel changes.
- Keep existing routes and real SSI workflows. Any API, data model, or closed-role-enum change requires its own reviewed authorization change with negative tests.
- Do not use the historical screenshot helper as evidence without a separate review: scripts/capture_live_screens.js contains hard-coded demo identities, role data, and claims that are not the current API contract. The old reports/REAL_UX_UI_COMPLETION_GATE.md explicitly retracts its blanket completion claim. The path it recommends as the current redesign report, reports/VISUAL_REDESIGN_REPORT.md, was not present when checked.

## 2. Priority sequence

### UX-00 — Freeze route, role, and state evidence

**Purpose:** Begin from current code instead of stale inventory or screenshot assertions.  
**Likely files:** apps/web/src/routes/AppRoutes.tsx, RoleGuard.tsx, roleNavigation.ts, context/AuthContext.ts, context/AuthProvider.tsx, services/api.ts; Identity role/permission files; docs/redesign/02 and /04.  
**Acceptance:**
- Every concrete route and canonical alias maps to the actual component, guard, permission, API, and state source.
- The selected login profile is documented as context only; verified backend role owns redirect.
- Guardian guard/API mismatch, absent Auditor/organization roles, and unsupported history screens remain open issues rather than being masked.
- Existing dirty Git paths remain untouched.

### UX-01 — Build-tool and component foundation

**Purpose:** Make a deterministic local component build before introducing the selected component system.  
**Likely files:** apps/web/index.html, package.json and lockfile, vite.config.ts, new Tailwind config/CSS entry and apps/web/src/components/ui/; main.tsx.  
**Acceptance:**
- Replace runtime Tailwind CDN use with the supported local CSS build only after verifying required utilities and generated output across all routes.
- Pin React 18-compatible shadcn/Radix component versions and add only the primitives required by existing pages.
- One font, color, focus, reset, and spacing source wins across all imports; remove CSS-order conflicts by consolidating, not by layering more !important patches.
- Existing build/lint and targeted contract tests pass; no auth/API/SSI behavior changes.
- No dependency install or lockfile edit occurs before implementation authorization.

### UX-02 — Shared brand, shell, and responsive navigation

**Purpose:** Make all pages visibly coherent before per-screen detail.  
**Likely files:** components/common/BrandMark.tsx, components/layout/Navbar.tsx and Sidebar.tsx, layouts/RootLayout.tsx, PublicLayout.tsx, InstitutionalLayout.tsx, HolderLayout.tsx, design-system CSS, app styles.  
**Acceptance:**
- All authenticated/public routes share Trust Network logo, one type scale, correct active navigation, consistent sign-out, and prototype/service state treatment.
- Permission-hidden menu items match server permissions; route and API guards are not weakened.
- Mobile drawer has focus management, escape/outside close, current-page state, and no hidden/overlapping content.
- Holder bottom dock respects safe areas and has accessible labels.

### UX-03 — Public homepage, sign-in, ecosystem, and docs

**Purpose:** Deliver the four entry points and a clear public story without fake features.  
**Likely files:** pages/public/LandingPage.tsx, pages/public/EcosystemPage.tsx, pages/public/ArchitectureDocsPage.tsx, components/auth/AuthPage.tsx, layouts/PublicLayout.tsx, local SVG asset and CSS.  
**Acceptance:**
- One public homepage has exactly four entry links, all leading to one authentication system.
- Successful login redirects using backend role; a mismatched profile query grants no access.
- /ecosystem independently handles issuer and metadata error/empty states with truthful records.
- /docs exposes only current architecture, optional anchoring, deterministic risk limits, and actual endpoints.
- Public and login screens use the same brand, typography, local illustration and responsive rules.

### UX-04 — Holder wallet and consent

**Purpose:** Preserve the holder’s real owned-wallet/offer/presentation workflow.  
**Likely files:** pages/holder/*, components/credentials/*, components/consent/*, components/dashboard/CredentialVault.tsx, layouts/HolderLayout.tsx.  
**Acceptance:**
- Owned credentials and offers are clearly separated; offer pending is not credential stored.
- Credential detail verifies ownership through backend; foreign IDs reveal no record.
- OID4VP page names verifier and purpose, shows exact requested claims, states full-credential disclosure, requires explicit consent, and preserves failure-stage/retry behavior.
- /wallet/activity remains explicitly unavailable until a wallet event API exists.
- Security/recovery actions reflect current policy, owner, key custody and server authorization; no secret material is displayed.

### UX-05 — Issuer workspace

**Purpose:** Make metadata, offer creation, and revocation/status readable as distinct tasks.  
**Likely files:** pages/issuer/*, InstitutionalLayout.tsx, common field/status/dialog/table components.  
**Acceptance:**
- Template page is labeled metadata/configuration catalogue, not a builder.
- Offer creation renders the actual returned offer and state; unbound issuer or missing configuration is blocked.
- Revoke requires clear ID/reason confirmation and authoritative re-fetch.
- Persistent Issuer DID scoping remains backend-owned; test an issuer cannot list/sign/revoke across issuer bindings.

### UX-06 — Verifier workspace

**Purpose:** Clarify request construction, session monitor, and authoritative verification.  
**Likely files:** pages/verifier/*, verification components, common QR/status/alert components.  
**Acceptance:**
- Request values and QR are derived from a server-created session; generated screen is not treated as a separate route.
- Verification shows aggregate status and only the gate-level evidence returned from the service.
- Risk/advisory state cannot visually override protocol, proof, trust, holder, expiry, or status rejection.
- /verifier/history remains unavailable until a verifier-scoped history API exists.
- Test wrong client/state/nonce/replay and a verifier cannot inspect another verifier’s session.

### UX-07 — Guardian/recovery surface

**Purpose:** Show recovery policy and decisions without assigning a role in the browser.  
**Likely files:** pages/guardian/*, pages/holder/SecuritySettingsPage.tsx, recovery components, InstitutionalLayout.tsx, backend auth/recovery tests only if authorization is separately approved.  
**Acceptance:**
- Product decision documents whether Guardian becomes a distinct Identity role or remains an assigned Holder capability.
- Every list/detail/decision is authorized by server-side wallet/guardian/request binding and signed actor proof.
- Unassigned, foreign-wallet, expired, replayed, insufficient-quorum, and failed proof cases are denied with clear status.
- No fake seed phrase, share, or successful rotation is shown.

### UX-08 — Admin operations, users, and trust registry

**Purpose:** Keep operations truthful and make current admin scopes distinguishable.  
**Likely files:** pages/admin/*, new Admin trust-registry page if accepted, services/api.ts only for already-defined endpoints, Institution layout and common table/dialog/status components.  
**Acceptance:**
- /admin/users states that it manages existing persistent Issuer scope only; it does not create accounts or assign roles.
- Contracts distinguish configured, connected, submitted, and receipt-backed evidence.
- Audit shows endpoint errors and does not claim immutable storage without evidence.
- Risk page says deterministic heuristic, synthetic/advisory, and not independently evaluated.
- Proposed Trust Registry screen uses existing write APIs and server permission; all changes are audited and non-admin attempts fail.
- No role split is simulated with UI controls.

### UX-09 — Route-by-route visual, responsive, accessibility, and functional acceptance

**Purpose:** Complete G12 evidence without declaring G11 complete.  
**Likely files:** all routed pages and shared components, web tests, screenshot/evidence manifest and implementation status only after runs.
**Acceptance:**
- Review every concrete route at 1440×900, 768×1024, and 390×844 (plus 320 px reflow and 200% text zoom where tooling allows).
- Validate keyboard-only path, focus visibility/not obscured, labels/errors/status announcements, reduced motion, contrast for rendered state pairs, and touch targets.
- Exercise happy path, empty, offline, timeout, invalid input, unauthorized URL/API, and cross-user/cross-issuer cases.
- Capture screenshots from the live app using real backend responses. Screenshots document appearance only, not protocol/backend acceptance.
- Record exact browser, viewport, source revision, test command/output, account role (never password/token), backend mode, and any blocked service.
- Update G0–G16 evidence only with observed outcomes. G11/G12 remain PARTIAL or BLOCKED until their own plan criteria pass.

## 3. Likely file impact map

| Concern | Likely files |
| --- | --- |
| Build/component foundation | apps/web/package.json, lockfile, index.html, vite.config.ts, local Tailwind config/CSS, src/components/ui/*, src/main.tsx |
| Global identity/system | src/design-system.css, styles.css, visual-refresh.css, assets/ssi-trust-network.svg, components/common/BrandMark.tsx |
| Public and auth | layouts/PublicLayout.tsx, components/auth/AuthPage.tsx, pages/public/LandingPage.tsx, EcosystemPage.tsx, ArchitectureDocsPage.tsx |
| Shell/navigation | layouts/RootLayout.tsx, InstitutionalLayout.tsx, HolderLayout.tsx, components/layout/Navbar.tsx, Sidebar.tsx, routes/roleNavigation.ts |
| Holder | pages/holder/*, components/credentials/*, components/consent/*, components/dashboard/* |
| Issuer | pages/issuer/* |
| Verifier | pages/verifier/*, components/verification/* |
| Guardian/recovery | pages/guardian/*, components/guardian/*, Recovery API only if role/scope decision changes |
| Admin | pages/admin/*, services/api.ts for already-defined endpoints, proposed trust-registry page |
| Verification | apps/web/tests/*, browser evidence, docs/implementation/* after real execution |

Avoid simultaneous global CSS rewrites and component rewrites; migrate a page family at a time and keep old behavior behind unchanged handlers/API calls.

## 4. Verification matrix

| Area | Existing targeted evidence/command | Required execution during implementation |
| --- | --- | --- |
| TypeScript/Vite production build | npm.cmd run build --prefix apps/web | Run after every page family and at final G12 checkpoint. |
| Frontend lint | npm.cmd run lint --prefix apps/web | Run after shared components and final routes. |
| Auth/session contract | node --experimental-strip-types apps/web/tests/authentication_contract.test.ts | Exercise invalid login, unavailable identity service, profile mismatch, backend role redirect, logout revoke. |
| Ecosystem API contract | node --experimental-strip-types apps/web/tests/ecosystem_api_contract.test.ts | Verify independent issuer/metadata loading, abort/timeout, error vs empty, refresh. |
| OID4VP request and errors | node --experimental-strip-types apps/web/tests/oid4vpRequestUri_contract.test.ts; node --experimental-strip-types apps/web/tests/oid4vpSubmissionError_contract.test.ts | Test valid/invalid/expired request URI, creation/direct-post/update failure and retry stage. |
| Holder wallet OID4VP | node --experimental-strip-types apps/web/tests/oid4vpWallet_contract.test.ts; node --experimental-strip-types apps/web/tests/verifyPresentation_fail_closed.test.ts | Consent-bound presentation, no send after reject, duplicate/replay, fail-closed result, truthful disclosure. |
| Recovery API | node --experimental-strip-types apps/web/tests/recoveryApi_contract.test.ts | Current API contract only; pair with service negative tests for guardian assignment/proof and foreign wallet. |
| Route/AuthZ | Identity Service focused integration tests under services/identity-service/tests/integration, especially test_auth_api.py, test_admin_users_api.py, holder binding and OID4VP policy files | Run with the repository-supported Python 3.11 environment and required service fixtures. Test each direct route and API with allowed/denied roles and cross-object scope. Do not run the full suite as a substitute. |
| Responsive browser | No package E2E script is declared in apps/web/package.json | Add or use an already-authorized browser runner only after availability is verified. Capture live routes at desktop/tablet/mobile. No simulated AuthContext user injection as proof. |
| Accessibility | No automated accessibility package/script is listed in apps/web/package.json | Keyboard/screen-reader/zoom/contrast/target review per route family; report tested criteria and untested items, no blanket WCAG claim. |
| Deployment/API | Docker/compose and live Gateway evidence are separate from frontend | Only check current authorized services; frontend HTTP 200 alone is not API or workflow acceptance. |

The web package currently defines only dev/build/lint scripts and no test script. The direct Node test commands above are file-level commands found in existing project status/evidence, not a package-wide test runner. Node 24.19.0 was available during this planning pass; no tests were executed. Python environment or service prerequisites must be checked again before targeted backend tests; prior reports document environment-dependent blocks.

## 5. Dependencies, decisions, and risks

- **Build dependency:** local Tailwind + shadcn generation requires a deliberate package/lockfile change. Do not leave Tailwind CDN as the production foundation.
- **Role model:** eight requested profiles exceed the actual closed Identity role enum and the five-role Master Plan. Decide separately whether trust registry, organization admin/operator, auditor, and Guardian become distinct persisted roles; define permissions and data scopes before exposing routes.
- **Guardian mismatch:** current route guards allow HOLDER while the Master Plan requires Guardian. Must be reconciled with API proof/assignment before a distinct panel is accepted.
- **Organization scope:** only issuerDid binding is explicitly evidenced. Verifier organization tenancy and staff memberships are not confirmed; do not build group views until API scope is proved.
- **Unavailable feeds:** Holder activity and verifier history must remain honest placeholders unless an authenticated, owner-scoped event endpoint is implemented and tested.
- **Current user worktree:** 268 changes existed before this plan. All remain uncommitted and must be preserved. No commit/push is part of this plan.
- **External/demo boundary:** current service labels, synthetic data, optional chain, and heuristic-risk limits remain visible wherever relevant.

## 6. Completion reporting template

For each implementation slice report: routes covered; files changed; API/permission data source; exact commands; pass/fail/skip/block counts; viewport/screenshots actually captured; accessibility checks performed; known failures and remaining gaps; Git state; whether G11 or G12 changed status under the Revised Master Plan.

**Plan result only:** This document is a proposed G12 execution sequence. It does not mean G12 has started, passed, or completed.
