# Secure SSI Platform — Page-by-Page UX/UI Blueprint

**Status:** Blueprint for actual routes and explicitly labeled proposals; not implemented.  
**Route authority:** apps/web/src/routes/AppRoutes.tsx. There are 28 concrete path patterns plus the wildcard route.  
**Shared visual reference:** document 03. Unless a page says otherwise, use its font, spacing, colors, surfaces, buttons, field, focus, motion, and responsive rules.

## Shared page contract

### Shell and navigation

- Public routes use a compact brand header, primary links to Ecosystem and Architecture, and one sign-in action. /login uses a brand header without the public footer.
- Holder routes use the Holder wallet shell; wide screens have top navigation, small screens have an accessible bottom dock with safe-area padding.
- Issuer, Verifier, Guardian/recovery, and Admin pages use the institutional shell. Desktop has a 256 px navigation rail, page title and breadcrumb, signed-in identity and sign-out. Below 1024 px the rail becomes a keyboard- and focus-managed drawer.
- Sidebar items are rendered only when the server-returned permissions allow them. Route guards and APIs remain authoritative. Current Guardian routes are guarded as HOLDER and must not be presented as a separately authenticated Guardian role.
- Every workspace page has one H1, a short task-oriented description, a clear primary action, and a single content grid. Remove protocol disclaimers repeated on every card; keep concise prototype/availability status in the shared shell and put detailed limitations beside the affected operation.

### Data and state rules

- Loading: skeleton the region that is loading and announce it with status/aria-busy. Do not show placeholder metrics as zero.
- Empty: only after a successful API response with no records. State the source or action that can populate the list.
- Error/offline: retain the user’s input where safe, identify the failing operation, preserve the backend error stage, and show retry only for repeatable reads or idempotent actions.
- Pending: use a textual pending label and a persistent state indicator; use polling cadence only where current code already polls.
- Success: only after the authoritative service response. Credential offer created, credential stored, presentation submitted, verification accepted, and anchor confirmed are separate results.
- Unknown/configured-only/synthetic/advisory states must remain explicit. Never fabricate issuer cards, audit events, session history, risk counts, or institution metrics.
- Permission failure: show a clear access-denied page and safe return link; the backend must independently deny the API request.

## Public pages

### / — Public homepage (existing)

- **Role/access:** Public; signed-in accounts get a primary “Open your workspace” link to server-role home.
- **Goal and order:** Header → dark hero with concise proposition on left and local SSI trust-graph/credential/verification composition on right → four entry cards (Individual, Issuer, Verifier, Platform Admin) → three-step Issue/Manage/Verify flow → truthful prototype/standards boundary strip → footer.
- **Components/actions:** Four cards link to /login?profile=holder|issuer|verifier|admin. They set presentation context only. Primary sign-in and explore links remain normal links. No live metric cards.
- **Data/states:** Static content, no endpoint in LandingPage. Authentication state only changes primary link.
- **Responsive/accessibility/acceptance:** Hero stacks with text first below 900 px; four cards become 2 columns then 1; decorative SVG hidden from screen readers; all four links keyboard reachable; no horizontal scroll at 320 px; profile choice never grants access.

### /ecosystem — Public issuer and credential directory (existing)

- **Role/access:** Public read-only view.
- **Goal and order:** Page header and Refresh → registered issuer list → credential configuration list from OID4VCI metadata. Show DID, organization name, trust state, permitted credential types, validity dates, format/configuration as returned.
- **Components/actions:** Refresh button; issuer cards or compact table; copy DID/key only if a real public key is actually provided. Current source has no trust-tier filter or registry mutation action.
- **Data/states:** fetchPublicTrustedIssuers and fetchOid4vciIssuerMetadata run independently; demo-seeded registry rows are filtered. Show separate retryable error per source, loading state, and successful empty state. Do not show a root hash/count unless API returns it.
- **Responsive/accessibility/acceptance:** Cards flow 2→1 columns; long DID wraps and has an accessible copy/reveal affordance if implemented; refresh busy state announced; failed metadata must not hide successful issuer rows and vice versa.

### /docs — Public architecture overview (existing)

- **Role/access:** Public; static.
- **Goal and order:** Page title and scope sentence → SSI Core → Gateway/application → advisory risk → optional integrity anchoring. Use a left topic index on wide screens and anchor list on phones if the content grows.
- **Components/actions:** Existing expandable API/source details use native details/summary. Keep copy/download actions absent until implemented. Show exact technology and endpoint labels from the source data.
- **Data/states:** No live API; page is available offline with the application bundle. Clearly separate source files/configuration from deployed/connected status.
- **Responsive/accessibility/acceptance:** One column below 900 px; summary elements keyboard operable; no clipped endpoint strings; no deployment, compliance, model-training, or transaction-success claim without evidence.

### /login — Shared sign-in (existing)

- **Role/access:** Public authentication. Four entry contexts; one credential flow.
- **Goal and order:** Brand → left value/story panel with local illustration and three concise workflow bullets → right form card with context label, email/username, password, submit, backend error. Profile links are a secondary context list and do not grant roles.
- **Components/actions:** Accessible username/password fields, password reveal only if added consistently, submit button with busy state, one clear error region. No “register”, “forgot password”, wallet connection, or role assignment until backend exists.
- **Data/states:** AuthContext login uses Identity Service; correct account is redirected with roleHomePath. Invalid credentials and service unavailable have separate messages. A mismatch between selected context and returned role never grants the selected profile.
- **Responsive/accessibility/acceptance:** Desktop split panel; below 900 px show form first then compact art/context; at 390 px no page-wide vertical artwork that buries form. Preserve input on transient error, announce auth error, keyboard submit works, no autofilled secrets are exposed.

## Holder wallet pages

### /wallet — Wallet dashboard (existing)

- **Role/access:** HOLDER and wallets:read.
- **Goal and order:** Wallet identity/sync state → credential inventory → pending issuance offers → actions to scan, view credential, review consent, and security.
- **Components/actions:** Credential cards show issuer, type, status, issue/expiry values only when present. Offer row offers a claim action only for a claimable server state. Do not use identity graphics as fake credential seals.
- **Data/states:** getOrCreateHolderWallet, fetchCredentials, fetchPendingOffers, claimOid4vciOffer. Separate wallet/credential/offer loading, error, empty and pending states; “claimed” only when issuance flow returns and persists the credential.
- **Responsive/accessibility/acceptance:** 2-column credential cards on desktop, one column on phone, bottom navigation never covers content; owner’s own data only. Negative test another holder’s wallet/credential ID via UI URL and API.

### /wallet/credentials/:id — Credential detail (existing)

- **Role/access:** HOLDER and wallets:credentials:read.
- **Goal and order:** Breadcrumb → credential type/issuer/status summary → claims → proof and status facts → safe actions.
- **Components/actions:** Back link, status badge, metadata definition list, copy only for public identifiers, raw JSON disclosure behind an explicit accessible details control if supported. Do not place raw full credential or secret key on initial view.
- **Data/states:** Current page reads wallet credentials and resolves the requested ID; use real not-found/foreign result, not a demo fallback. Distinguish active, suspended, revoked, expired, and unknown when backend supplies them.
- **Responsive/accessibility/acceptance:** One-column on mobile; long JSON/DID wraps or uses horizontal code panel; page title includes human credential type; foreign ID must not reveal whether another holder owns it.

### /credentials/:id — Canonical credential detail alias (existing)

- **Role/access:** Same as /wallet/credentials/:id.
- **Layout/actions/data/states:** Render the exact same component and authorization behavior in the Holder shell. Keep one source of visual truth; do not maintain alias-specific styling.
- **Acceptance:** Direct navigation, refresh, browser back, unknown ID, and foreign ID match the nested route’s behavior.

### /wallet/scan — Offer/request intake (existing)

- **Role/access:** HOLDER and wallets:read.
- **Goal and order:** Page title → paste/scan/URI intake controls actually implemented → parsed flow summary → continue to credential-offer claim or presentation consent.
- **Components/actions:** Preserve the current OID4VCI/OID4VP parsing logic and display the parsed scheme/operation before navigation. A QR display and a QR scanner are different capabilities; do not imply camera scanning unless source/API/browser permission flow supports it. Native deep links/DC API remain Master Plan non-goals.
- **Data/states:** A URI/session must be parsed and server validated in its own flow. Invalid/expired/unknown requests show an actionable error and do not create a successful session.
- **Responsive/accessibility/acceptance:** Single-column on phone, paste input and buttons full width, keyboard paste path supported, parsed identifiers wrap. Test valid/invalid OID4VCI offer and OID4VP session paths separately.

### /wallet/consent — OID4VP holder consent (existing)

- **Role/access:** HOLDER and presentations:create.
- **Goal and order:** Verifier identity and purpose → server request/session state → matched wallet credential → exact requested fields/claims → explicit full-credential disclosure notice → approve/reject.
- **Components/actions:** Credential radio/select cards, claims disclosure table, explicit checkbox or equivalent consent action, approve and reject buttons, retry action only for the retained prepared presentation stage. The supported profile sends the complete signed credential; omission from a requested-field list is not cryptographic selective disclosure.
- **Data/states:** Load existing server session, owned wallet, active owned credentials and DCQL evaluation; require pending request, a valid match, explicit consent, and server-bound context. Display request load, no match, approval blocked, rejection, creation failure, Direct Post failure, submitted, and retry states distinctly.
- **Responsive/accessibility/acceptance:** Claim matrix collapses into labeled rows on mobile; no horizontal overflow; screen-reader announces verifier/purpose and failure stage. Approve sends only after the user’s explicit decision; reject never posts a presentation; test replay/expired/foreign-session denial.

### /consent/presentation — Canonical consent alias (existing)

- **Role/access:** Same as /wallet/consent.
- **Layout/actions/data/states:** Identical component, session validation, consent-bound payload, and direct-post/retry behavior. Preserve query/session transfer without trusting caller-supplied identity claims.
- **Acceptance:** Direct link and nested route behave identically for pending, expired, rejected, and already-used sessions.

### /wallet/activity — Holder activity (existing placeholder)

- **Role/access:** HOLDER and presentations:read.
- **Goal and order:** Page title → honest unavailable-state panel explaining the wallet-scoped event feed does not exist → link back to wallet.
- **Components/actions:** No fake timeline, date labels, verifier names, or copied admin audit feed. No refresh action until a holder event endpoint exists.
- **Data/states:** Current page is static and states the feed is unavailable.
- **Responsive/accessibility/acceptance:** One panel and a short explanation; status is not a successful empty feed. Remove the route only through a separately reviewed product decision; current blueprint keeps it and labels the blocker.

### /wallet/security — Wallet security/recovery (existing, partial)

- **Role/access:** HOLDER and wallet:key:read.
- **Goal and order:** Wallet key lifecycle state → recovery policy and assigned guardians → active requests → supported actions and safety explanation.
- **Components/actions:** Read-only key facts; recovery action is shown only when policy/eligibility permits. Confirm cancel/approve/reject with request identity and effect. Never reveal seed phrases/private keys or imply hardware custody.
- **Data/states:** Recovery policy/guardians/requests use current APIs. Show missing policy, no assigned guardian, unavailable service, active request, and supported cancellation distinctly.
- **Responsive/accessibility/acceptance:** Vertical sections on mobile; no key lifecycle action outside its server permission; cross-wallet and unassigned Guardian negative tests; do not claim DID rotation or quorum complete without backend response.

## Issuer pages

### /issuer — Issuer workspace (existing)

- **Role/access:** ISSUER and credentials:sign.
- **Goal and order:** Issuer identity/scope → primary Create offer action → actual recent offers and status.
- **Components/actions:** Real offer table with type/offer ID/created status where returned; link to published metadata configurations; no invented issuance velocity or capacity.
- **Data/states:** fetchIssuerOffers. Unbound/unsupported issuer, loading, empty, and API error are distinct.
- **Responsive/accessibility/acceptance:** Table switches to offer cards on mobile; status text is explicit. Cross-issuer list isolation and no-scope deny tests.

### /issuer/templates — Credential metadata catalogue (existing)

- **Role/access:** ISSUER and credentials:sign.
- **Goal and order:** Page intro → configurations published by OID4VCI issuer metadata → configuration details/available create-offer action.
- **Components/actions:** Read-only configuration cards. Use actual format, binding methods, cryptographic algorithms, and proof types returned by metadata. Do not display template builder controls, seeded credential types, or edit/delete buttons without APIs.
- **Data/states:** fetchOid4vciIssuerMetadata; loading, metadata unavailable, and successful empty states. A configuration selected for issuance must remain server-validated.
- **Responsive/accessibility/acceptance:** 2→1 column; configuration IDs wrap; each card has one clear action and keyboard focus.

### /issuer/issue — Create credential offer (existing)

- **Role/access:** ISSUER and credentials:sign, plus server-bound issuer scope/provider.
- **Goal and order:** Select supported metadata configuration → enter required subject/offer inputs → review recipient and configuration → create offer → show returned pending/status and QR/deep link.
- **Components/actions:** Labeled fields from actual API contract; no schema-editor or signing-suite choices unless supported by API. Copy link and create another are secondary actions. Do not present offer creation as credential issuance completion.
- **Data/states:** fetchOid4vciIssuerMetadata, createOid4vciOffer, get/poll offer status. Unavailable configuration, unauthorized/unbound issuer, invalid form, create failure, pending offer, polling failure, returned status are separate.
- **Responsive/accessibility/acceptance:** Single-column form; QR has accessible offer ID/link fallback; buttons remain visible with mobile keyboard. Test actual persisted wallet credential separately from returned offer.

### /issuer/revocations — Credential status and revocation (existing)

- **Role/access:** ISSUER and credentials:revoke, bounded to the issuer.
- **Goal and order:** Find/enter credential identifier → current authoritative status → reason/review → explicit revoke action → refreshed status.
- **Components/actions:** Status detail and confirmation dialog. No bulk bit toggling, index allocation controls, or status-list mutation dashboard unless service exposes it.
- **Data/states:** fetchCredentialStatus, revokeCredential, reload status after mutation. Already revoked, suspended, expired, unknown, not owned, persistence unavailable, and successful revoke are explicit.
- **Responsive/accessibility/acceptance:** ID/decision read in confirmation; no color-only statuses; cross-issuer mutation denied by API and visible state.

## Verifier pages

### /verifier — Verifier workspace (existing, partial)

- **Role/access:** VERIFIER and presentations:verify.
- **Goal and order:** Primary Create request action → supported current tasks → recent history section only if a real API is available.
- **Components/actions:** Avoid static success-rate charts, risk alerts, or recent-session tables when there is no API. Link to create request and verify a presentation.
- **Data/states:** Current component is a dashboard shell without a wired history call. Explain “no data source” as unavailable; do not treat as a zero result.
- **Responsive/accessibility/acceptance:** Responsive action cards and one-column layout; every card opens the named route and is keyboard accessible.

### /verifier/request — Create OID4VP request and QR (existing; generated view is a route state)

- **Role/access:** VERIFIER and presentation-challenges:create.
- **Goal and order:** Request context/purpose → requested credential/claims → review → create server session → present QR/deep link, session ID, state, expiry/status when returned.
- **Components/actions:** Use current supported request contract. Display the exact material the holder will be asked to present. Copy link as secondary action. No schema builder controls for unsupported query types.
- **Data/states:** createOid4vpSession and getOid4vpSession polling. Creating, pending, expired, rejected, verified and service errors derive from response. Generated QR is not a separate route.
- **Responsive/accessibility/acceptance:** Form is one column; QR remains large enough with an accessible URI; polling is announced without stealing focus; invalid fields block request creation; test nonce/state/session one-use behavior.

### /verifier/verify — Verify a presentation (existing)

- **Role/access:** VERIFIER and presentations:verify.
- **Goal and order:** Input/receive supported presentation payload → submit → result summary → returned reason list and detailed evidence only when API returns it.
- **Components/actions:** Form labels, verify button, result status chip, explicit errors. Do not show each of nine gates as successful if endpoint only returns aggregate status/errors.
- **Data/states:** verifyPresentation. Form error, pending, service error, verified, rejected, and partial evidence are distinct; risk is subordinate to protocol, proof, holder, trust, expiry, and status outcomes.
- **Responsive/accessibility/acceptance:** Payload editor is readable and scrollable; result card is announced; a crypto rejection remains rejection even if risk score is low.

### /verifier/history — Verification history unavailable state (existing placeholder)

- **Role/access:** VERIFIER and presentations:read.
- **Goal and order:** Page title → explicit unavailable-state panel → link to verify/create request.
- **Components/actions:** No fictitious archive, audit trail, filters, or replay inspector.
- **Data/states:** Current page says the API does not provide account history and imports no history service.
- **Responsive/accessibility/acceptance:** Single compact panel on mobile; no “empty history” claim unless an endpoint confirms empty; keep until endpoint/product decision.

## Recovery pages

### /guardian — Recovery dashboard (existing, authorization mismatch)

- **Role/access:** Current route guard allows HOLDER; no Identity GUARDIAN role. Revised Master Plan expects a Guardian surface.
- **Goal and order:** Identity and assigned-guardian context → only the requests assigned to this authenticated actor → safe actions with proof/policy state.
- **Components/actions:** Assignment and request cards with protected wallet, threshold, expiry, current state, and decision link only if backend permits. Do not label an account Guardian based on a route or demo screenshot.
- **Data/states:** Current API reads guardians/requests/current user and may approve via proof. Server assignment and actor proof must determine list/actions.
- **Responsive/accessibility/acceptance:** Cards on phone; missing assignment is an access-denied/empty-assignment state. Test Holder without assignment, assigned actor, wrong actor, foreign wallet, expired/replayed decision.

### /guardian/requests — Recovery request list (existing, authorization mismatch)

- **Role/access:** Same current HOLDER route guard; no separate role.
- **Goal and order:** Filter supported request states → request identity/policy/deadline → permitted cancel/open action.
- **Components/actions:** State filter only if backed by loaded data; cancellation confirmation names the exact request.
- **Data/states:** fetchRecoveryRequests, fetchGuardians, fetchCurrentUserId; cancel only when API permits. Show load/empty/error/expired/terminal states truthfully.
- **Responsive/accessibility/acceptance:** Replace table with labeled cards on mobile; no arbitrary wallet IDs or other users’ requests; negative scope test per request.

### /guardian/approve/:id — Recovery decision (existing, authorization mismatch)

- **Role/access:** Same current HOLDER route guard; API must enforce assigned Guardian proof.
- **Goal and order:** Request and protected wallet identity → policy, threshold, expiry, recovery effect → approve/reject choice → signed proof request → authoritative result.
- **Components/actions:** Distinct approve and reject; reason if API supports it; final confirmation before signing/decision. Explain that operation cannot restore a key unless service returns that state.
- **Data/states:** fetchRecoveryRequestById, fetchGuardians, fetchCurrentUserId, approveRecoveryPetition/rejectRecoveryPetition. Unknown, foreign, expired, no guardian assignment, proof failure, conflict, and accepted decision are separate.
- **Responsive/accessibility/acceptance:** Decision controls stacked and touch-sized; confirmation has focus management; negative actor/replay tests required.

## Administration pages

### /admin — Platform operations (existing)

- **Role/access:** ADMIN and admin:operations:read.
- **Goal and order:** Current overall service availability → service health cards → authoritative persistence telemetry → optional chain state → recent audit links → risk-service metadata.
- **Components/actions:** Refresh telemetry triggers the existing APIs. Each card shows timestamp/source when available and exact ONLINE/OFFLINE/UNKNOWN/PARTIAL status.
- **Data/states:** Gateway, blockchain, contracts, fraud, database, and audit calls. Partial failure is local to its card; no all-green inference from one health endpoint.
- **Responsive/accessibility/acceptance:** Two-column desktop → one-column tablet/phone; contract IDs wrap. Test Gateway unavailable, Identity unavailable, Mongo unavailable, chain offline; no fake zero values.

### /admin/users — Persistent account and issuer-scope view (existing, partial)

- **Role/access:** ADMIN. Read uses admin:users:read; issuer-scope mutation requires admin:users:write.
- **Goal and order:** Persistent account list → role and current issuer scope → trusted/configured issuer options → confirm scope update.
- **Components/actions:** Search/filter only against fetched users; select current trusted/configured issuer; optimistic version conflict shown explicitly. No create-user, role grant, disable, or staff controls.
- **Data/states:** fetchAdminUsers, fetchAdminIssuerScopeOptions, updateAdminIssuerScope. Synthetic-provider mode is read-only/unavailable; no accounts means an explicit empty state.
- **Responsive/accessibility/acceptance:** Table becomes one account card per user; buttons only show by permission and API returns 403 to direct mutation; audit result comes from server.

### /admin/contracts — Optional integrity anchor directory (existing)

- **Role/access:** ADMIN and parent admin:operations:read.
- **Goal and order:** Connection state → configured contract directory → receipt-backed anchors where available → explanatory boundary.
- **Components/actions:** Read-only contract cards with name, address, chain ID, configuration/receipt status and copy action for public address. No deploy/upgrade controls unless separately implemented.
- **Data/states:** fetchBlockchainStatus, fetchBlockchainContracts, fetchBlockchainAnchors. Configured-only, offline, unavailable height, receipt-backed, and no records remain distinct.
- **Responsive/accessibility/acceptance:** Address wraps and can be copied; long values use mono and accessible details. Contract source/config is not deployment evidence.

### /admin/audit — Audit explorer (existing)

- **Role/access:** ADMIN and parent admin:operations:read.
- **Goal and order:** Filter controls → returned audit event list → event detail panel with actor/event/time/request ID and payload only to authorized admin.
- **Components/actions:** Refresh/filter as supported; payload details collapsed by default; no chain immutability claim without proof.
- **Data/states:** fetchAuditLogs with actual filter/limit. Empty after successful response differs from unavailable; API persistence error is visible.
- **Responsive/accessibility/acceptance:** Mobile event cards with a separate detail dialog; row focus and filters keyboard accessible; test unavailable persistence and unauthorized API.

### /admin/fraud-monitor — Advisory risk metadata (existing)

- **Role/access:** ADMIN and parent admin:operations:read.
- **Goal and order:** Service/model status → reported configured signals → scope/training/evaluation boundary → recent assessments only if returned.
- **Components/actions:** refresh; status metadata; no synthetic risk-event feed, confusion matrix, or trained-model chart.
- **Data/states:** fetchFraudStats. Display deterministic heuristic, synthetic/advisory scope and NO_INDEPENDENT_LABELLED_EVALUATION as actual metadata where returned. Unavailable remains unavailable.
- **Responsive/accessibility/acceptance:** Signal list wraps; status uses text; no low-risk “approved” outcome can override verifier policy.

### /admin/trust-registry — Proposed Admin capability, not an existing route

- **Status/role:** Proposed only; justified by current trust-registry read/write API and permissions. Current role is ADMIN, not a Trust Registry Officer.
- **Goal and order:** Registry records → exact DID/name/status/validity/source/trust anchor/types → add/update/suspend/revoke workflows with reason and review.
- **Components/actions:** Data table with search/status filters, detail sheet, create/edit form, explicit confirmation for suspend/revoke; no fake accreditation tiers. Optimistic conflicts/409 preserve edits and require reload.
- **Data/states:** GET issuer list/detail is public; POST/PUT/suspend/revoke requires trust-registry:write. Show loading, empty, error, duplicate, invalid, conflict, success. Verify audit record after successful mutation.
- **Responsive/accessibility/acceptance:** Use row cards on mobile and accessible status labels. Test public read, admin write, non-admin write denied, duplicate DID conflict, foreign/unknown DID, expired trust, and suspend/revoke fail-closed behavior. A dedicated Officer role requires later backend role design.

## Not-found route

### * — Not found (existing)

- **Role/access:** Public fallback. Use a concise “Page not found” heading, route context only if safe, and links to Home and Sign in.
- **States and acceptance:** Avoid exposing private route/resource existence. Keyboard-accessible links; preserve the requested path only as inert text.
