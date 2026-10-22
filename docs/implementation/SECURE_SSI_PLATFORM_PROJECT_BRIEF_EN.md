# Secure SSI Platform — Project Brief

**Purpose:** English-language orientation and presentation brief for project collaborators.  
**Evidence checkpoint:** repository status reports dated 18 October 2026; local web checks rerun on 21 October 2026.  
**Authority:** This brief summarizes the project. It does not replace or change the [Final Implementation Plan](SECURE_SSI_PLATFORM_FINAL_IMPLEMENTATION_PLAN.md), its frozen protocol profile, gate order, or acceptance criteria.

## 1. Project at a glance

**Project topic:** A multi-role, standards-informed Self-Sovereign Identity (SSI) platform prototype for issuing, holding, presenting, and verifying digital credentials.

**Main aim:** Build and evaluate a connected credential lifecycle in which an institution can create a credential offer, a person can receive and manage a credential in a wallet, and a verifier can request and validate a presentation with the holder’s consent.

The platform combines a React web application with backend identity and domain services. It is a **custodial, server-mediated web prototype**. It is not a production government identity system, a hardware-backed self-custody wallet, a certified EUDI wallet, or a native mobile application.

## 2. Problem and project goals

Digital credentials need more than a screen that displays a claim. A usable credential lifecycle must connect the issuer, holder, and verifier while preserving authenticity, authorization, holder consent, status checks, and an auditable decision path.

The project aims to:

1. Issue W3C Verifiable Credentials through a defined OpenID4VCI flow.
2. Bind wallets, credentials, keys, offers, and presentation requests to the authenticated owner and service-side authorization rules.
3. Let a holder review a verifier’s request and explicitly approve or reject it.
4. Verify presentation proofs, holder binding, issuer trust, expiration, status, and request/session properties before producing an authoritative result.
5. Keep advisory risk scoring and optional blockchain anchoring separate from cryptographic validity and credential status.
6. Demonstrate the system with reproducible tests, runtime evidence, and honest limitations rather than claims based only on source code or screenshots.

## 3. Users and responsibilities

| Actor | Intended responsibility | Current implementation boundary |
|---|---|---|
| **Holder / Individual** | Own a wallet experience, manage credentials and offers, review presentation requests, and manage available security/recovery actions. | Holder data must be limited to the authenticated holder and their owned wallet. The current presentation profile sends the complete signed credential; cryptographic claim-level selective disclosure is not implemented. |
| **Issuer institution** | Use published credential metadata, create offers, and review service-reported offer and credential status. | Issuance is limited to configured issuer scope and actual service capabilities. An offer is not itself an issued credential. |
| **Verifier institution** | Create a presentation request and review the verification result returned by the service. | Session and result access must follow authenticated verifier permissions and server-side authorization. Organization-wide team administration is not evidenced as a separate role. |
| **Guardian** | Participate in an assigned recovery request and provide the required recovery proof. | The product plan describes a Guardian surface, but the Identity Service has four roles (Holder, Issuer, Verifier, Admin). Current Guardian routes are guarded as Holder capability; do not describe a separate Guardian login or role as implemented. |
| **Platform Admin** | Review service health, audit data, configured contracts, risk metadata, and available user/issuer-scope administration. | Current user administration is limited; it does not provide general account creation, role assignment, or complete institution/staff management. |
| **SSI Core** | Own authoritative identity, wallet, credential, trust, status, consent, policy, and exchange-session state. | These are backend domain responsibilities; frontend state is not authoritative for protocol or permission decisions. |

## 4. How the platform works

1. **Issuer prepares an offer.** The issuer uses a credential configuration published by the Identity Service and creates an OpenID4VCI offer. The service returns the actual offer details and claim link.
2. **Holder claims the offer.** The holder opens the offer, reviews it, and completes the supported token, proof, and credential steps. The service persists the resulting credential in the holder’s wallet. An offer or QR code alone is not proof of receipt.
3. **Verifier requests a presentation.** The verifier creates an OpenID4VP request with a client, nonce, state, and DCQL query. The request can be transported as a link or QR code.
4. **Holder reviews consent.** The wallet resolves the real request, evaluates available credentials against the query, and shows the verifier and requested information before the holder approves or rejects.
5. **Wallet responds.** For an approved request, the wallet creates the supported signed presentation and sends it to the verifier’s Direct Post endpoint. Rejection must not submit a presentation.
6. **Verifier evaluates the response.** Backend checks validate the request/session, proof, holder binding, issuer trust, expiration, credential status, and policy. Failures must fail closed.
7. **Risk and anchoring remain separate.** A deterministic risk heuristic may add an advisory signal after security checks. Optional blockchain anchoring records approved event hashes; it does not make a credential valid or invalid.
8. **Evidence is retained.** Tests and runtime traces establish what works. Audit availability, persistence, and offline states must be shown truthfully.

## 5. Architecture

```text
Holder Wallet | Issuer Portal | Verifier Portal | Guardian Recovery | Admin Console
                           API Gateway
Identity | Credential | OID4VCI / OID4VP / DCQL | Trust | Status | Consent / Policy
Recovery | Audit | Advisory Risk | Optional Hash Anchoring
MongoDB: durable domain state                 Redis: ephemeral state
```

The repository includes a React 18/TypeScript/Vite web application, a FastAPI API Gateway, Identity, Fraud, and Recovery services, MongoDB, Redis, and optional Solidity/Hardhat components. The plan is domain-first: the number of services is not a product goal.

Key architecture rules:

- The browser calls backend services through the Gateway in the target architecture.
- Credentials, consent, keys/references, protocol sessions, permissions, and policy outcomes are server-side domain state.
- MongoDB is the prototype’s durable store; Redis is for ephemeral state.
- Cryptographic validity, issuer trust, credential status, risk, and blockchain receipt are separate evidence dimensions.
- A `KeyCustody` abstraction does not prove production HSM/KMS custody.
- Demo or seeded data must be labeled. Mock-only screens cannot satisfy the Golden Path.

## 6. Standards and the frozen project profile

The engineering baseline is defined in the Final Implementation Plan. The principal choices are:

- **Credentials:** W3C Verifiable Credentials Data Model 2.0 and Data Integrity 1.0.
- **Proof:** Ed25519 `eddsa-jcs-2022`, using RFC 8785 JSON Canonicalization Scheme (JCS), with the project’s defined verification-method authorization rules.
- **DIDs:** `did:web` for synthetic institutional issuers and `did:key` for holder fixtures, subject to the documented resolver and trust policy.
- **Issuance:** OpenID4VCI 1.0, using the project’s pre-authorized-code/token/nonce/proof flow.
- **Presentation:** OpenID4VP 1.0 with `dcql_query`, a validated client, fresh nonce, required state, and `direct_post`.
- **Credential status:** W3C Bitstring Status List 1.0. Referenced status data must be authenticated and validated before its bits are trusted.
- **Risk:** `rule-heuristic-v1` is deterministic and advisory. Inputs are synthetic; no trained model or independent labeled evaluation is claimed.
- **Blockchain:** Optional hash-only integrity anchoring. Credentials, secrets, keys, and personal data must not be placed on-chain.

Do not silently add draft standards or new credential formats. A profile change requires a documented decision (ADR) with migration, security, privacy, and interoperability impact.

## 7. Scope boundaries and claims to avoid

The following are **not** established product capabilities:

- Native Android/iOS wallet or device-bound hardware key custody.
- EUDI Wallet certification or passing an official wallet conformance assessment.
- Cryptographic selective disclosure using BBS+, ZKP, or equivalent. Hiding fields in a UI is not cryptographic selective disclosure.
- Production government identity integration or production personal identity data.
- A trained AI fraud model, independent model evaluation, or generalization claim.
- Blockchain as the authority for issuer trust, credential validity, revocation, or presentation acceptance.
- Separate Guardian, Auditor, Issuer Organization Admin, or Verifier Organization Admin identity roles unless the backend role and authorization model is explicitly extended and tested.
- Complete account, institution, staff, or role management in the Admin UI.

The interface may be responsive for phone-sized screens, but this does not make the product a native mobile app.

## 8. Engineering roadmap: G0–G16

The existing plan’s gate order remains authoritative. The grouping below is for presentation only; it does not change prerequisites or acceptance criteria.

| Phase | Gates | Focus |
|---|---|---|
| **Baseline and decisions** | **G0–G2** | Audit project reality; reconcile domains and ownership; freeze standards, profiles, and unsupported-feature claims. |
| **Core credential lifecycle** | **G3–G5** | Wallet ownership and keys; issuer/OID4VCI issuance; verifier/OID4VP requests, DCQL, consent-bound presentation, and results. |
| **Trust and user protection** | **G6–G8** | Trust/status/policy and fail-closed verification; consent and data minimization; guardian recovery and lifecycle. |
| **Risk, integrity, and end-to-end proof** | **G9–G11** | Ground advisory risk; optional hash anchoring; run the real cross-layer Issuer → Holder → Verifier Golden Path and Broken Paths. **G9 depends on accepted G6/WP-08.** |
| **Product quality and delivery** | **G12–G16** | Professional UX; security hardening; independent interoperability/conformance; performance/reliability; reproducible documentation, thesis, and demo evidence. |

**Completion rule:** a gate is accepted only for the scope supported by current implementation and reproducible evidence. Code presence, a successful build, a screenshot, historical results, or a test file alone is not enough. L3 means current running integration/security evidence; L4 means narrowly scoped independent interoperability/conformance evidence.

## 9. Evidence-based project status

The repository’s 18 October 2026 gate checkpoint records:

- **PASS for documented scope:** G0, G6/WP-08, G7, G9, and G10.
- **PARTIAL:** G1–G5, G8, G11–G13, G15, and G16.
- **BLOCKED:** G14, pending an independent peer or applicable conformance evidence.
- **No gate is recorded as FAIL or NOT_STARTED** in that checkpoint.

Important unfinished acceptance work includes:

- **G8:** independent Guardian-device proof/MFA, broader DID-method lifecycle, and cross-service browser/runtime recovery evidence.
- **G11:** successful browser Direct Post, durable persistence/restart and audit trace, and end-to-end Broken Paths. A prior browser Direct Post attempt failed before its POST reached the Gateway; the recorded root cause was unresolved.
- **G12:** full route-by-route desktop/mobile visual review, keyboard and screen-reader operation, contrast review, and complete state coverage.
- **G13:** remaining security scans/review and disposition of findings; independent penetration testing is not established.
- **G14:** independent interoperability/conformance evidence.
- **G15:** project-level API load, concurrency, failure/retry/idempotency, and reliability measurements.
- **G16:** clean-environment reproduction, final demo evidence, and thesis-to-implementation alignment. The completion audit reported that the thesis source was not present in the repository.

On 21 October 2026, local frontend lint and production build passed, as did four frontend contract scripts (43 assertions total). These checks do not change G11 or G12 acceptance: they are not a full browser user journey, complete accessibility review, or backend regression run. See the [gate matrix](SECURE_SSI_PLATFORM_GATE_ACCEPTANCE.md), [test evidence](SECURE_SSI_PLATFORM_TEST_EVIDENCE.md), and [18 October UI/status report](../../reports/UX_UI_REFRESH_AND_PROJECT_STATUS_2026-10-18.md) for the source detail and evidence dates.

## 10. Suggested short presentation introduction

> Our project is the Secure SSI Platform, a web-based prototype for managing the lifecycle of verifiable digital credentials. Institutions can create credential offers, holders can receive credentials and review presentation requests, and verifiers can check signed presentations. The platform uses W3C Verifiable Credentials and OpenID4VCI/OpenID4VP profiles, with backend checks for ownership, consent, issuer trust, expiration, and credential status. Risk scoring is advisory, and blockchain anchoring is optional. The project is a prototype, not a certified wallet or production identity service. Our implementation plan uses gates G0 to G16 so that each claim is supported by current tests and runtime evidence. Several integration, accessibility, interoperability, and reproducibility gates remain open.

## 11. How a collaborator should continue

1. Read the [Final Implementation Plan](SECURE_SSI_PLATFORM_FINAL_IMPLEMENTATION_PLAN.md) first; it controls the scope, frozen profile, gate sequence, and acceptance rules.
2. Use the [route, role, and action inventory](../redesign/02-routes-roles-and-actions.md) and the design documents for UI work. Treat this brief as orientation, not implementation authority.
3. Check the current Git branch, HEAD, and working tree before editing. Preserve existing modified and untracked work; do not reset, clean, overwrite, or mass-revert it.
4. Trace a proposed UI action to the real API, authorization rule, and state transition. Do not invent roles, permissions, test users, or successful API results.
5. Run the smallest relevant tests first. Record exact commands, environment, pass/fail/skip counts, and blockers. A test that could not execute is BLOCKED, not PASS.
6. Update the appropriate evidence report only with results actually observed. Do not commit or push unverified changes.

## 12. Source documents

- [Final Implementation Plan](SECURE_SSI_PLATFORM_FINAL_IMPLEMENTATION_PLAN.md) — controlling scope, standards profile, G0–G16 sequence, and acceptance rules.
- [G0–G16 Gate Acceptance](SECURE_SSI_PLATFORM_GATE_ACCEPTANCE.md) — evidence-based gate status.
- [Test Evidence](SECURE_SSI_PLATFORM_TEST_EVIDENCE.md) — commands, environment, results, skips, and limits.
- [Routes, Roles, and Actions](../redesign/02-routes-roles-and-actions.md) — actual frontend route and role inventory.
- [Page-by-Page UX/UI Blueprint](../redesign/04-page-by-page-ux-ui-blueprint.md) — approved interface direction and page expectations.

