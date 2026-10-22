# Secure SSI Platform — Routes, Roles, and Actions

**Status:** Code-derived inventory and authorization mapping, planning only.  
**Sources:** Revised Master Implementation Plan, current AppRoutes/RoleGuard/AuthContext, Identity Service closed role/permission policy, current API service and current UX status reports.  
**Rule:** A route or desired profile is not proof of a backend capability. The server principal, permission, and object/organization scope remain authoritative.

## 1. Current user-visible entry and authentication model

The public homepage links to four sign-in contexts: Individual/Holder, Issuer Institution, Verifier Institution, Platform Administration. These links reach the same /login page with a profile query parameter. The parameter selects contextual copy only. AuthPage submits the entered username/password through AuthContext to the Identity Service; the service response supplies the role and permissions. A successful login redirects through roleHomePath to /wallet, /issuer, /verifier, or /admin. The browser must not infer or grant role from the selected entry card.

Current backend authentication is a local synthetic/authentication foundation, not production identity. Current documentation describes strict username/password verification, Argon2id, short-lived HS256 access token, current-user lookup, and current-role permission derivation. Registration, refresh tokens, MFA, external IdP, password reset, and production onboarding are absent. Demo fixture credentials are permitted only under explicit Vite development configuration; never expose them as production sign-in helpers.

## 2. Actual backend roles and permissions

The closed Identity Service role enum in services/identity-service/app/domain/permissions.py contains exactly four roles.

| Current role | Current effective permissions | Product evidence and boundary |
| --- | --- | --- |
| admin | All 29 permission enum values: auth:self:read; credentials:revoke, sign, validate, verify; presentations:create, read, verify, reconcile; wallets:create, read, credentials:read; presentation-challenges:create, read; wallet:key:create, read, rotate, suspend, resume, compromise, revoke, destroy, reconcile; admin:key:reconcile; admin:operations:read; admin:users:read, write; trust-registry:read, write. | ADMIN is broad. Do not imply it is least privilege or a read-only role. Object ownership still applies where service logic requires it. |
| issuer | All role-derived permissions except wallet:key:*, admin:*, and trust-registry:write. This includes credentials:sign/revoke and a legacy broad set of non-key wallet/presentation permissions. | Issuer DID is an optional, server-provisioned scope for persistent accounts; unbound accounts are denied issuer-scoped signing, OID4VCI offers, and revocation/history. No Issuer staff/user-management API is evidenced. |
| verifier | auth:self:read; credentials:validate, verify; presentations:read, verify; presentation-challenges:create, read. | No verifier organization-admin role or staff-management API is present. The API must continue to constrain owned/related sessions and presentations; org-wide sharing is not established by the UI. |
| holder | auth:self:read; presentations:create/read; wallets:create/read/credentials:read; presentation-challenges:read; wallet:key:create/read/rotate/suspend/resume/revoke. | Wallet, credential, presentation, and managed-key services enforce owner relationships. Foreign or missing owned-object reads are documented to return the same 404. |

Permission values are lowercase in HTTP/documentation. The frontend additionally enumerates the same permission vocabulary in AuthContext.ts; it maps known backend role names to four frontend roles and discards unknown permission strings.

## 3. Requested eight-profile mapping

The eight-profile list below is a target for evaluation, not the current role model.

| Requested profile | Current classification | Safe interpretation / gap |
| --- | --- | --- |
| Platform Admin | Implemented, broad | Maps to admin. Current role includes platform-wide operations and write permissions; future least-privilege work is separate from visual restyling. |
| Trust Registry Officer | Missing as a distinct role; capability partially exists | trust-registry:read/write exist and API routes enforce trust-registry:write, but both currently derive from admin. There is no separate officer assignment or UI route. |
| Issuer Organization Admin | Partially represented by issuer | Persistent issuerDid binding provides issuer scope, but the model has no separate organization-admin role, staff-management endpoint, or organization settings workflow. |
| Issuer Operator | Partially represented by issuer | Issuer accounts can use issuance/status operations; no separate operator permissions exist. |
| Verifier Organization Admin | Missing | No separate role, organization membership/admin API, or settings workflow is evidenced. |
| Verifier Operator | Partially represented by verifier | The verifier role and request/verification actions exist, but cannot be distinguished from an organization administrator. |
| Holder / Individual User | Implemented | Maps to holder and owned-wallet APIs; selected public profile does not create holder access. |
| Auditor, read-only | Missing | No auditor role. Admin is not read-only. Do not reuse Admin while describing an auditor profile. |

### Master-plan role reconciliation

The Revised Master Implementation Plan requires five product roles/surfaces: Holder, Issuer, Verifier, Guardian, Admin. Current Identity Service has only four roles. Guardian routes exist but AppRoutes guards them with HOLDER, and the web menu exposes recovery as a Holder capability. Recovery requests and proof APIs exist, but the code does not prove a separately authenticated Guardian principal. This conflicts with the Master Plan’s separate Guardian portal and requires an authorization/product decision before designing a separate Guardian login. Do not disguise this gap with a tab or profile query.

## 4. Data and authorization boundaries

| Data/action | Current enforceable boundary | UI rule and unresolved item |
| --- | --- | --- |
| Holder wallet, credentials, keys, presentations | Authenticated holder principal plus persisted owner/holder relationship in backend services. | Show only the signed-in holder’s data. Every detail URL must preserve API ownership checks. Do not expose platform audit events as holder activity. |
| Issuer offer/sign/status operations | Issuer role plus optional server-provisioned issuerDid binding and configured signing support; domain object checks remain. | Label the current issuer DID/scope only when returned. Empty/unbound scope must be an unavailable/blocked state, not a success. Cross-issuer negative tests are required. |
| Verifier sessions and presentations | Verifier permission plus challenge/presentation service authorization for related objects. | Show own/authorized sessions only. A verifier organization-wide tenant boundary is not established by a distinct org field in the frontend identity profile. Verify API scope before adding team-wide views. |
| Trust Registry reads/writes | Public issuer list/get endpoints; registration/update/suspend/revoke writes require trust-registry:write. | Public Ecosystem is a read view. Admin currently has write capability; there is no dedicated Trust Registry Officer. Writes need server permission and audit, not only a visible button. |
| Persistent Admin user administration | Admin API requires admin:users:read/write; it lists existing persistent users and manages issuer DID scope against trusted/configured options. It does not create accounts or grant roles; synthetic fixture records are read-only. | Describe only issuer-scope assignment. Do not label this as complete user, institution, role, or staff management. |
| Guardian recovery request/decision | Recovery service APIs plus wallet/guardian assignment and proof flow. Browser route-level rule currently says HOLDER; no GUARDIAN role exists in Identity enum. | Require server-authorized guardian assignment/proof on every request and decision; exact cross-service subject binding needs route/API negative tests. |
| Admin service/audit/fraud/chain data | Admin workspace route requires admin:operations:read; individual APIs return service-specific data/status. | Use exact API state; display offline, unavailable, configured-only, heuristic, and unknown honestly. Never render guessed telemetry as zero or healthy. |
| Regional, governmental, or institution hierarchy | Not found as an authorization scope in the inspected web profile/closed Identity roles. | Do not add region/country/agency filtering claims without a product/data model and API contract. |

## 5. Current route inventory

There are 28 concrete path patterns in AppRoutes.tsx plus the wildcard not-found route. The aliases are separate direct paths to the same page component; query/interaction states such as a generated QR are not extra routes.

| Route | Current page/status | Current intended role / route permission | Current data/action evidence and gap |
| --- | --- | --- | --- |
| / | Existing | Public; authenticated accounts should go to roleHomePath | Static product landing and four links to login contexts. No health/metrics API in LandingPage. |
| /ecosystem | Existing, data-backed | Public | Loads public trusted issuers and OID4VCI issuer metadata independently, filters known demo-seeded records, supports refresh/error/empty states. No administration write UI. |
| /docs | Existing, static | Public | Four architecture/service sections and expandable API/source detail. No PDF download, code-copy, live docs backend, or full documentation portal is evidenced. |
| /login | Existing | Public | Shared username/password form and profile context links. Actual role and redirect are server-derived. No registration, password reset, MFA, or separate auth system. |
| /wallet | Existing | HOLDER; wallets:read | Creates/resolves the holder wallet and reads credentials/offers; can claim an OID4VCI offer. |
| /wallet/credentials/:id | Existing | HOLDER; wallets:credentials:read | Credential detail finds owner wallet credentials; backend ownership remains required. |
| /wallet/scan | Existing | HOLDER; wallets:read | URI/session intake and navigation. This is a web QR/URI flow, not a native wallet/deep-link app. |
| /wallet/consent | Existing | HOLDER; presentations:create | Loads pending verifier session, wallet-owned active credentials, evaluates DCQL, records explicit consent, creates/submits or rejects a presentation; full signed credential disclosure must be stated. |
| /wallet/activity | Existing placeholder | HOLDER; presentations:read | Explicitly says wallet-scoped event feed is unavailable; no holder feed API is wired. Do not populate with admin audit data. |
| /wallet/security | Existing, partial | HOLDER; wallet:key:read | Shows available wallet/recovery policy, guardians, and request state. Key UI/API completeness and guardian identity authorization need verification. |
| /credentials/:id | Existing alias | HOLDER; wallets:credentials:read | Direct canonical alias to credential detail within Holder shell. |
| /consent/presentation | Existing alias | HOLDER; presentations:create | Direct canonical alias to consent page within Holder shell. |
| /issuer | Existing | ISSUER; credentials:sign | Reads offer list and displays pending/recent offers; creates navigation to metadata/templates and issuance. Counts must derive from response. |
| /issuer/templates | Existing metadata catalogue | ISSUER; credentials:sign | Reads issuer OID4VCI metadata/configurations. No template CRUD/builder API is evidenced. |
| /issuer/issue | Existing | ISSUER; credentials:sign | Reads metadata, creates OID4VCI offer, displays QR/deep link, polls actual offer state, supports copy/reset. Direct signing is unavailable when issuer scope/provider cannot support it. |
| /issuer/revocations | Existing | ISSUER; credentials:revoke | Reads credential status and requests revocation, then reloads the status. Do not present arbitrary list/bit editing that is absent. |
| /verifier | Existing, partial | VERIFIER; presentations:verify | Dashboard shell and navigation exist. No dashboard history endpoint or metrics were found on this component. |
| /verifier/request | Existing | VERIFIER; presentation-challenges:create | Creates OID4VP session and QR/deep link, polls session state, exposes request fields. Create and generated QR are states of one route. |
| /verifier/verify | Existing | VERIFIER; presentations:verify | Submits presentation to verification service, shows returned result/errors. It must not infer per-gate success absent endpoint evidence. |
| /verifier/history | Existing unavailable-state page | VERIFIER; presentations:read | Page explicitly says the current API does not provide account history; no list endpoint is wired. |
| /guardian | Existing, authorization mismatch | AppRoutes allows HOLDER; no GUARDIAN role/permission | Loads assigned guardians/recovery requests and can act on a request via API. Must prove guardian assignment, signed actor, owner, and recovery state with negative tests. |
| /guardian/requests | Existing, authorization mismatch | AppRoutes allows HOLDER; no explicit nested permission | Lists recovery requests, reads current user/guardian assignments, offers supported cancellation. No generic Guardian role. |
| /guardian/approve/:id | Existing, authorization mismatch | AppRoutes allows HOLDER; no explicit nested permission | Loads a request/guardian and submits approve/reject proof. Must not be exposed as any-holder authority. |
| /admin | Existing | ADMIN; admin:operations:read | Loads gateway, blockchain, contracts, fraud, database, and audit endpoints. Partial/offline responses must remain explicit. |
| /admin/users | Existing, partial | ADMIN; admin:users:read (write operation needs admin:users:write) | Reads persistent users and issuer scope options; can update existing issuer DID scope. It cannot create users, assign roles, or manage general institutions. |
| /admin/contracts | Existing | ADMIN parent guard: admin:operations:read | Reads optional chain connectivity, configured contracts, and anchor records. Configured addresses are not proof of deployment/receipt. |
| /admin/audit | Existing | ADMIN parent guard: admin:operations:read | Reads audit logs and filter. No claim of immutable or independently verified tamper-proof storage without matching evidence. |
| /admin/fraud-monitor | Existing | ADMIN parent guard: admin:operations:read | Reads fraud service/model metadata. Current documented service is a deterministic advisory heuristic over synthetic inputs, not a trained model or independent evaluation. |
| * | Existing not-found | Public fallback | Accessible not-found view; it must retain public shell, explain unavailable path, and link home/sign-in. |

## 6. Permission-to-screen action matrix

| Action | Current UI location | Current required server permission/role | Acceptance requirement |
| --- | --- | --- | --- |
| Log in / logout | /login and shared shell | Public token endpoint; logout revokes current bearer token | Selected profile never changes server claims. Invalid login and unavailable service are distinct and visible. |
| View wallet/credentials | Holder routes | holder plus wallets:read / wallets:credentials:read | Test own record 200 and foreign ID denied/not found through both API and direct URL. |
| Accept issuance offer | /wallet | Holder-owned wallet, offer state, issuance API contract | Offer accepted must end with persisted credential; show pending/failure separately. |
| Issue credential offer | /issuer/issue | issuer, credentials:sign, bound issuer DID/provider | Cross-issuer attempt denied; only real returned offer/QR and status shown. |
| Revoke credential | /issuer/revocations | issuer, credentials:revoke, issuer scope | Confirm exact credential and reason; reload authoritative status after response; test foreign issuer. |
| Create verification request | /verifier/request | verifier, presentation-challenges:create | Show actual session, client, requested fields, nonce/state as appropriate; only real service result produces QR. |
| Consent / reject presentation | /wallet/consent | holder, presentations:create; server session, wallet ownership, consent binding | Distinguish approve/reject; complete credential disclosure copy; no presentation sent on reject. |
| Verify presentation | /verifier/verify | verifier, presentations:verify | Show only returned service result/reasons; crypto/security failure cannot be overridden by risk display. |
| Guardian approve/reject | /guardian/approve/:id | Current route only checks HOLDER; backend guardian assignment/proof required | Deny unassigned holder, foreign request, replay, expired request, or wrong actor. |
| Read/write Trust Registry | Public Ecosystem / currently no admin route | Public GET; write requires trust-registry:write | Public view read-only. Proposed management UI needs negative tests for non-admin and audit record checks. |
| Manage issuer DID binding | /admin/users | admin:users:read for view; admin:users:write for mutation | Existing persistent Issuer only; no claim of account creation or role assignment. |
| Read system/audit/chain/risk | /admin routes | ADMIN plus admin:operations:read route guard and endpoint policy | Offline/unknown/configured-only/heuristic states remain non-success states. |

## 7. Proposed page/profile boundaries

A Trust Registry management screen under the Admin workspace is justified by existing authenticated trust-registry write endpoints and the trust-registry:read/write permission vocabulary. It is **missing from the frontend** and could be proposed as an Admin capability now; a separate Trust Registry Officer role still requires an authorization model change.

Organization staff/admin pages for Issuer and Verifier, an Auditor dashboard, and a distinct Guardian sign-in are **not implemented and not safe to infer**. They require business decisions plus server role/permission assignments, organization membership/tenant scoping, audit policy, and negative API tests before routes are proposed as working features.
