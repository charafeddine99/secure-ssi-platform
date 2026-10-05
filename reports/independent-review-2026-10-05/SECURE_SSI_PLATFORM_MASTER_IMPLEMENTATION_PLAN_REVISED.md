# Secure SSI Platform — Master Implementation Plan (Revised)

**Document status:** Revised after independent second-opinion review (5 October 2026).  
**Supersedes:** `SECURE_SSI_PLATFORM_V2_1_MASTER_IMPLEMENTATION_PLAN` for engineering control.  
**Does not rewrite:** the product direction of V2.1. Changes are limited to evidence-backed corrections.  
**Academic note:** The January 2026 design report (`B210109591`) is **not** this plan. Thesis text must be aligned to this profile or labeled historical.

**Review research date:** 5 October 2026.

---

## 1. Product definition — frozen baseline

Secure SSI Platform is a **multi-role SSI platform prototype** in which:

- trusted **institutions issue** W3C Verifiable Credentials,
- **holders** manage those credentials in a Wallet,
- **verifiers** request and check presentations with holder consent,
- **guardians** participate in emergency key/identity recovery,
- **admins** operate users, organizations, trust, policy, and health,
- **SSI Core** owns protocol and domain state,
- **AI risk** is an independent, non-authoritative signal,
- **blockchain** is optional integrity anchoring of non-PII event hashes.

It is **not** an e-Devlet clone, **not** an EUDI-certified wallet, and **not** only a Wallet UI.

### 1.1 Prototype class (honest label)

**Custodial/server-mediated web SSI prototype.** The Wallet is a real identity application (keys, DID, credentials, sessions, consent, matching, presentation), implemented as a web app plus backend domain services and a KeyCustody abstraction. It is **not** a hardware-backed mobile wallet.

### 1.2 Required roles

| Role | Product surface | Primary responsibility |
| --- | --- | --- |
| Holder | Wallet App | Keys/DID, credentials, offers, consent, presentations, activity, security, recovery |
| Issuer | Issuer Portal | Organization identity, templates, issuance, lifecycle, revocation/status |
| Verifier | Verifier Portal | Verification request, QR/link, presentation intake, result matrix, history |
| Guardian | Recovery Portal | Recovery request handling, quorum, approve/reject, timelock, history |
| Admin | Admin Console | Users, organizations, trust, fraud, recovery, blockchain, audit, health, policy |
| SSI Core | Backend/domain layer | Identity, DID, Wallet, credentials, verification, trust/status, consent/policy, exchange sessions |

### 1.3 Main user journey

Holder account → Wallet identity → DID/key availability → Issuer credential offer → Offer parsing/validation → Holder consent → OID4VCI issuance (offer → token → nonce/proof as required → credential) → Credential persistence → Verifier request → QR/link transport → Wallet parsing → **DCQL evaluation / credential matching** → Requested-claim consent → Presentation generation → OID4VP `direct_post` response → Verifier protocol validation → Credential Data Integrity validation → Issuer **trust registry** evaluation → Holder binding validation → Expiration → Status/revocation → Challenge/session validation → AI risk signal → Policy decision → Final result → Audit event → Optional blockchain integrity anchor.

### 1.4 Explicit non-goals (V2 core)

Not required unless later promoted with a new ADR:

- Native mobile application
- Hardware HSM / Secure Enclave / Multipaz SecureArea equivalence
- Advanced ZKP / BBS+ cryptographic selective disclosure
- Full EUDI Wallet certification or FCAF passing claims
- Government production integration (e-Devlet, national eID, PID issuance)
- DIDComm / Hyperledger Aries / Hyperledger Indy
- EIP-4337 as an identity or recovery protocol
- Additional credential formats solely for feature count (SD-JWT VC, mDL, JWT-VC) unless chosen for a documented Interop B experiment
- DC API / OS wallet integration

The product UI must honestly expose the implementation level of these items.

---

## 2. Standards baseline and project profile

### 2.1 Normative technology baseline

| Area | Baseline | Status at 5 Oct 2026 | Rule |
| --- | --- | --- | --- |
| VC | W3C Verifiable Credentials Data Model 2.0 | Recommendation, 15 May 2025 | Normative |
| VC 2.1 | W3C VC Data Model 2.1 | Working Draft, 30 Sep 2026 | Monitor only |
| Data Integrity | W3C VC Data Integrity 1.0 | Recommendation, 15 May 2025 | Normative |
| Signature suite | Data Integrity EdDSA 1.0 `eddsa-jcs-2022` | Recommendation, 15 May 2025 | Project profile (RDFC suite not used) |
| Canonicalization | RFC 8785 JCS | Informational RFC | Required by selected suite |
| CID | W3C Controlled Identifiers 1.0 | Recommendation, 15 May 2025 | Verification methods / relationships |
| DID | W3C DID Core 1.0 | Recommendation, 19 July 2022 | Architecture only |
| DID methods | `did:web` (issuer), `did:key` (synthetic holder fixtures) | Community drafts, not W3C Rec | **Project profile** (ADR 0001) |
| Issuance | OpenID4VCI 1.0 | Final, 16 Sep 2025 | Normative for selected profile |
| Presentation | OpenID4VP 1.0 | Final | Normative for selected profile |
| Query | DCQL (`dcql_query`) | Defined by OID4VP 1.0 | Normative for primary VP flow |
| Status | Bitstring Status List 1.0 | Recommendation, 15 May 2025 | Normative |
| Status 1.1 | Bitstring Status List 1.1 | FPWD, 24 Sep 2026 | Do not adopt silently |
| EUDI ARF | v3.0.0, Jul 2026 | Informative | Reference architecture only |

### 2.2 Frozen protocol profiles

#### DID (project profile)

- Issuer/org: `did:web` with HTTPS `.well-known/did.json` resolution in the target environment; local fixtures allowed only if labeled `DEMO` and equivalent tests exist for the resolver port.
- Holder (prototype): `did:key` **fixtures only**. Not for long-lived production users; no update/deactivate in-method. Recovery must rotate to a new identifier/key, not “update did:key.”
- Method allowlist: reject untrusted methods.
- No custom DID method.
- No ledger DID method.

#### Credential (project profile)

- VC Data Model 2.0 JSON-LD; context `https://www.w3.org/ns/credentials/v2`.
- Proof: `DataIntegrityProof` / `eddsa-jcs-2022` / Ed25519 / `proofPurpose: assertionMethod`.
- Demo types remain allowlisted (e.g. university affiliation). Do not hardcode verifier logic to a single type if DCQL already constrains type.

#### OID4VCI primary profile (project profile on Final spec)

Flow:

1. Credential Issuer metadata (including `credential_configurations_supported`, token endpoint, credential endpoint, **`nonce_endpoint` if proofs require `c_nonce`**).
2. Credential offer with pre-authorized code grant `urn:ietf:params:oauth:grant-type:pre-authorized_code`.
3. Wallet exchanges code at **Token Endpoint** for an access token. Single-use/expiry of the pre-authorized code is mandatory.
4. If key-binding proofs are required (they are, in this profile): Wallet obtains `c_nonce` from the **Nonce Endpoint** (OpenID4VCI 1.0 Final §7). Do **not** treat Token Endpoint `c_nonce` as the Final mechanism.
5. Wallet calls **Credential Endpoint** with access token and key proof.

**Frozen issuance key-proof type:** `jwt` (`openid4vci-proof+jwt`) using EdDSA/Ed25519, with `aud` = Credential Issuer identifier and `nonce` = `c_nonce` when a Nonce Endpoint is advertised.

Rationale (implementation choice, documented): the issued credential remains Data Integrity; JWT proofs at the credential endpoint are the most widely tested OpenID4VCI PoP type and are easier to negative-test than `di_vp`. `attestation` proofs are OPTIONAL/FUTURE (no wallet attestation infrastructure).

Authorization Code + PKCE/PAR: **deferred**, labeled unsupported in the conformance report.

#### OID4VP primary profile (project profile on Final spec)

- `dcql_query` (Wallet **evaluates** DCQL; no DIF Presentation Exchange as the primary request language).
- `client_id` present and validated.
- Fresh `nonce` per session.
- `state` **required unconditionally** (project tightening).
- `response_mode=direct_post`.
- Transport: **cross-device QR** and **same-browser link** (web prototype). Native deep link and DC API: non-goals.
- Holder binding: cryptographic, fail-closed.
- Replay: nonce/session single-use.

#### Trust / status / consent / AI / chain

Unchanged from V2.1: trust registry with evidence; Bitstring Status List 1.0; consent bound to payload; claim omission ≠ cryptographic SD; AI cannot override crypto failure; blockchain non-authoritative; no PII/keys on chain.

---

## 3. Canonical architecture

Domain-first. Service split may follow domain ownership; microservice count is not a goal.

```
SECURE SSI PLATFORM (web prototype)
  Holder Wallet | Issuer Portal | Verifier Portal | Guardian Portal | Admin Console
                         HTTPS / API Gateway (authn, RBAC, validation, rate limit)
  IDENTITY | CREDENTIAL | EXCHANGE (OID4VCI/OID4VP sessions, DCQL)
  TRUST | CONSENT/POLICY | RISK (AI signal)
  RECOVERY | AUDIT | INTEGRITY (SHA-256 → optional EVM anchor)
  MongoDB durable domain state | Redis ephemeral nonce/session/cache only
```

Architecture rules (kept from V2.1, plus custody):

1. Browser does not call internal services except via the API Gateway.
2. Wallet/protocol/consent/credential/session state is domain state, not UI-only.
3. Trust evidence ≠ blockchain anchoring.
4. AI risk ≠ cryptographic validity.
5. Blockchain failure does not change cryptographic verification; UI shows `anchor_status`.
6. MongoDB is the prototype’s durable store (**implementation choice**). Redis is ephemeral only.
7. KeyCustody is a port: software KMS/local key store. No HSM claim.
8. Demo environment labeling is mandatory on public and authenticated shells.

Reference alignment: role split resembles EUDI/walt.id **architecturally**. This is not certification or interop by default.

---

## 4. Completion model and evidence

### 4.1 Levels

| Level | Meaning | May say COMPLETE? |
| --- | --- | --- |
| L0 Designed | Requirement, UX, protocol/state, contract, acceptance | No |
| L1 Implemented | Code + unit-level behavior | No |
| L2 Integrated | UI + backend + persistence + authz + protocol state connected | No |
| L3 Verified | Integration/E2E/security tests on running system + evidence | Yes |
| L4 Interoperable | Independent implementation or spec test vectors | Yes |

### 4.2 Evidence types (E1–E12)

Unchanged from V2.1. Screenshot ≠ protocol. Unit test ≠ E2E. Endpoint 200 ≠ user journey.

### 4.3 UI Fidelity Gate

Backend + protocol + persistence + UI representation + tests must agree. A later polish gate may restyle; it may not leave false protocol/security labels.

---

## 5. Product gates (revised sequence)

**Current control point (5 Oct 2026):** G0 artifacts exist. Do not rerun a blocking identical G0 unless HEAD materially diverges. Remaining work starts at **G2 freeze ingestion**, then P0 security/product gaps.

| Gate | Objective | Prerequisites | Outputs | Domain | Backend | UI | Persistence | Security tests | E2E | Evidence | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| G0 | Product reality audit | Repo | Gap matrix | All | Read-only | Read-only | Read-only | Record existing | Record | E3/E4/E7 as found | **Executed 4 Oct 2026.** Re-run only on material drift. |
| G1 | Domain re-baseline | G0 | Domain/entity/state maps, ADRs | All | Contracts | IA map | Ownership | n/a | n/a | E2 | Ingest existing ADRs; do not redesign by service count. |
| G2 | Standards lock | G1 | This profile frozen | DID, VC, VCI, VP, trust | Metadata | No false labels | Keys/DID docs | Vector tests planned | n/a | E1/E2 | **Must include Nonce Endpoint + jwt PoP + DID methods.** |
| G3 | Wallet-first core | G2 | Wallet states in §6 | Wallet, Identity | Wallet APIs | Wallet screens | Credentials/keys | Key leak tests | Offer→store | E7/E8 | Credential stored ≠ issuance HTTP 200. |
| G4 | Real Issuer + OID4VCI | G3 | Offer/token/nonce/credential | Exchange, Credential | Metadata, token, nonce, credential | Issuer portal | Offers, tokens, credentials | Reuse code, bad proof | Issue→wallet | E6/E9 | Final nonce model. |
| G5 | Real Verifier + DCQL | G3–G4 | DCQL request/response | Exchange | OID4VP + DCQL engine | Request + QR/link | Sessions | Wrong nonce/state/client, replay | Present | E6/E9 | Remove PE as primary. |
| G6 | Verification engine, trust, status, policy | G4–G5 parallelizable from G2 | Matrix + registry | Trust, Status, Policy | Registry + bitstring | Explainable matrix | Trust records, status lists | Untrusted issuer, revoked, expired | Re-verify | E5/E8 | **P0: no DID-prefix trust.** |
| G7 | Consent / minimization | G5 | Consent→payload | Consent | Presentation builder | Consent UI | Consent records | Over-disclosure, deny path | Deny path | E7/E8 | Terminology gate. |
| G8 | Guardian recovery | G3 | Recovery SM | Recovery | Quorum/timelock/rotation | Recovery portal | Recovery docs | Abuse paths | Recovery path | E5 | Project protocol. |
| G9 | AI risk layer | G6 | Heuristic/ML honesty | Risk | Fraud service | Risk panel | Events, model version | Crypto fail + low risk → reject | High-risk path | E4 | Synthetic data labeled. |
| G10 | Blockchain integrity | G6 | Anchor pipeline | Integrity | Hash + EVM | Anchor status | Anchor records | Retry/fail visible | Optional | E8 | Non-blocking for verify. |
| G11 | Golden Path ecosystem | G3–G10 as applicable | One reproducible journey | All | All | All panels | All | Negative set | Full GP | E11/E12 | Primary acceptance. |
| G12 | UX professionalization | G11 in progress | Truthful IA | All UI | None except copy/API alignment | All | n/a | No auto-pass | Visual E2E | E7 | Demo naming ban. |
| G13 | Security hardening | G11 | Threat evidence | Security | Authz, limits | Errors | n/a | Every control has a negative | n/a | E5 | |
| G14 | Interop/conformance | G11 | Conformance report | Protocol | Profile only | n/a | n/a | Vectors | Interop A required | E9/E10 | Interop B optional. |
| G15 | Performance/reliability | G11 L3 | Limits report | Ops | Timeouts, idempotency | Timeout UX | n/a | Rate limit | Load | E12 | **After** Golden Path. |
| G16 | Docs/thesis/demo evidence | G11–G14 | Thesis aligned to this profile | Docs | n/a | Screenshots from real UI | n/a | n/a | Demo script | E11/E12 | Thesis must drop Indy/ZKP/eIDAS-full claims. |

### 5.1 P0 order inside G3–G6

1. Fail-closed verification (if not independently re-verified on current HEAD).
2. Cryptographic holder binding (same).
3. Trust registry (replace prefix matching).
4. OID4VCI token + nonce endpoint + jwt PoP.
5. DCQL replace DIF PE.
6. Wallet persist + consent-bound VP using the stored credential.

---

## 6. Wallet required state

WalletCreated → KeyAvailable → DIDAvailable → OfferReceived → OfferValidated → AwaitingConsent → IssuanceInProgress → CredentialStored → CredentialStatusKnown → VerificationRequestReceived → RequestValidated → CredentialMatchComputed → AwaitingPresentationConsent → PresentationCreated → PresentationSubmitted.

Capabilities unchanged from V2.1 (DID/key display without private key, storage, detail, status, offers, matching, consent, activity, recovery/security status).

---

## 7. Verification decision hierarchy (normative for this profile)

```
Protocol/security violation            => REJECT
Cryptographic invalidity               => REJECT
Wrong holder / audience / session      => REJECT
Expired                                => REJECT
Revoked/suspended per status policy    => REJECT (or documented non-acceptance)
Else                                   => trust + policy + risk
```

AI must never convert cryptographic invalidity into ACCEPTED.  
Blockchain failure must never erase cryptographic results.  
`issuerTrusted=true` is insufficient; expose DID, trust source, status, validity, policy, record id.

---

## 8. Consent / recovery / AI / blockchain

Kept from V2.1:

- Consent binds verifier, purpose, session, credential(s), claims, decision, timestamp, optional window; decision must change the presentation payload.
- Recovery states: RecoveryRequested → … → DID/identity rotation → audit; negative paths required.
- AI outputs `riskScore`, `riskLevel`, `modelVersion`, `signals`; synthetic data labeled; if no artifact, say **heuristic**.
- Anchor classes: issuance/lifecycle, revocation, recovery completion, trust-registry critical mutation, critical security event. Prohibited: keys, raw VC JSON, PII, secrets.

---

## 9. UX truthfulness (additions)

Unchanged V2.1 bans, plus:

- No hostnames, DIDs, or org names implying `europa.eu`, `eudi`, national eID, or e-Devlet.
- Visible `[DEMO ENVIRONMENT]` / `[DEMO LAB]`.
- Classification of every primary screen: `REAL_BACKEND` | `DEMO_SEEDED_REAL_BACKEND` | `MOCK_ONLY`. Mock-only cannot pass Golden Path.

---

## 10. Interoperability gates

| Level | Requirement |
| --- | --- |
| Interop A | Own Issuer → Own Wallet → Own Verifier on this profile |
| Interop B | Optional. Only against a peer that supports **W3C VC + Data Integrity `eddsa-jcs-2022`** (or a separately ADRed format experiment). walt.id Wallet/Issuer/Verifier v2 is the preferred peer **if** format is aligned. |
| Interop C | W3C Data Integrity / Bitstring test suites or OpenID conformance where feasible |

Never report “full OID4VCI/OID4VP compliance.” Report **profile coverage** and an unsupported-feature list (authorization code, PAR, attestation proofs, DC API, SD-JWT, mDL, PE, etc.).

---

## 11. Definition of done, priority, release

Unchanged from V2.1 in spirit:

- COMPLETE only after plan → design → implement → integrate → test → security → real E2E → protocol check → document → evidence.
- P0: broken Golden Path, wallet not using stored credential, protocol-state defects, invalid crypto, wrong-holder, replay, revoked accepted, authz bypass, false UI claims, unexplainable trust.
- P1: consent quality, recovery robustness, audit, AI honesty, error states, a11y, reproducible demo, thesis alignment.
- P2: SD, native mobile, HSM, extra formats, scale.

Release candidate “PRODUCT COMPLETE” only if the V2.1 §10 checklist holds **and**:

- Nonce Endpoint is implemented or explicitly unused because proofs are not required (proofs **are** required here, so Nonce Endpoint is required).
- Conformance report lists unsupported OpenID features.
- Thesis/demo language matches this profile.

---

## 12. Required repository artifacts

Keep V2.1 report set. Add/retain:

- `docs/architecture/V2_OID4VCI_PROFILE.md` (token, nonce, jwt proof)
- `docs/architecture/V2_OID4VP_DCQL_PROFILE.md`
- `reports/independent-review-2026-10-05/` (this review package)

---

## 13. First execution instruction (revised)

Do **not** start a new feature sprint from a blank G0.

1. Confirm HEAD vs G0 gap list (read-only delta).
2. Close G2 by committing the frozen profile in this document (Nonce Endpoint, jwt PoP, DID methods, custody label) as ADRs if not already identical.
3. Independently re-run WP-01/WP-02 tests on current HEAD if they will be cited as L3.
4. Execute P0 remaining: trust registry, OID4VCI Final handshake, DCQL, wallet consent-bound VP.
5. Stop at evidence; do not declare COMPLETE without L3 artifacts.

---

## 14. Success condition

A clean environment can reproduce:

> Holder, Issuer, Verifier, Guardian, Admin, protocol, trust, security, status, consent, risk, recovery, audit, and integrity layers operating together as one **reproducible SSI platform prototype** under the frozen OpenID4VCI/OID4VP 1.0 profile.

Everything else is a labeled limitation or future enhancement.
