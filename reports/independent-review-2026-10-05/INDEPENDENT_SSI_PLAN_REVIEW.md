# Independent SSI Plan Review

**Review date:** 5 October 2026  
**Reviewer role:** Independent second-opinion (SSI architecture, protocol/conformance, security, product/UX)  
**Mode:** Planning review only. No application code was changed.  
**Primary sources supplied by the user:**
1. `B210109591 (1).pdf` — Sakarya Applied Sciences University Computer Engineering Design Report, Charaf Eddine Bessanane, January 2026 (academic design report).
2. `SECURE_SSI_PLATFORM_V2_1_MASTER_IMPLEMENTATION_PLAN (1).pdf` — V2.1 Source-Validated Master Implementation Plan (engineering control plan).

**Supplementary repository evidence (not treated as proof of product completion):** existing ADRs, G0 audits, V2.1 onboarding notes, and `docs/standards-baseline.md` in `secure-ssi-platform`.

**Research date for external sources:** 5 October 2026.

---

## 1. Executive verdict

**Overall assessment: PLAN IS SOUND WITH TARGETED REVISIONS.**

This verdict applies to the **V2.1 Master Implementation Plan**, not to the January 2026 academic design report, and not to the current code as a finished product.

- The V2.1 plan correctly defines the product as a **multi-role SSI ecosystem prototype** (Holder Wallet, Issuer Portal, Verifier Portal, Guardian Recovery, Admin Console, SSI Core), not an e-Devlet clone and not a dashboard-only wallet.
- Its **standards baseline is mostly aligned** with currently published Recommendations/Final specifications (W3C VC Data Model 2.0, Data Integrity 1.0, EdDSA cryptosuites 1.0, DID Core 1.0, Bitstring Status List 1.0, OpenID4VCI 1.0 Final, OpenID4VP 1.0 Final with DCQL).
- Its **engineering control model** (L0–L4, evidence types, G0-first, fail-closed crypto, AI/blockchain non-authority, UI truthfulness, explicit non-goals) is professionally defensible for a graduation/prototype SSI platform.
- It is **not yet a complete product plan freeze**: several protocol details still mix **draft-era OpenID4VCI nonce handling** with the Final specification; DID method and issuance proof-type choices are required by the plan itself but not frozen inside the plan document; the academic thesis still asserts a contradictory Indy/Aries/ZKP/eIDAS stack.

The January 2026 thesis is **not suitable as an implementation baseline**. It is useful as problem motivation and as a record of earlier intent, but it overclaims standards, mixes incompatible stacks, and reports performance/security scores that are not independently evidenced in the supplied materials.

**Would a technically knowledgeable SSI / standards / security / software-engineering jury consider V2.1 coherent after the targeted revisions in this package?** Yes, as a **source-validated prototype plan**, provided claims stay inside the frozen profile and G0/G14 evidence is actually produced. It would **not** survive a jury as EUDI-certified, government-integrated, ZKP-enabled, or “fully standards compliant across all optional protocol features.”

Confidence is not 100%. Remaining uncertainty is mainly environment-dependent (Windows test tooling, live interop against walt.id/Multipaz, `did:web` hosting, blockchain RPC availability) and implementation-dependent (whether remaining G0 gaps are closed to L3).

---

## 2. Source handling

| Document | Title / version / date | Type | Authority for this review |
| --- | --- | --- | --- |
| `B210109591 (1).pdf` | Secure Self-Sovereign Identity with AI-Based Fraud Detection and Emergency Recovery on Blockchain; January 2026; student: CHARAF EDDINE BESSANANE; advisor: Dr. A. F. M. Suaib Akhter | Academic design / literature / proposed architecture | **Non-authoritative for protocol and implementation.** Authoritative only for academic problem statement, original intended differentiators (AI fraud + guardian recovery + integrity anchoring), and claims that must be downgraded. |
| V2.1 Master Implementation Plan PDF | Secure SSI Platform — V2.1 Source-Validated Master Implementation Plan | Project-specific engineering plan / proposal | **Authoritative product and control baseline**, subject to the targeted corrections in this review. |
| Repository ADRs `0001`, `0002`; `docs/standards-baseline.md` | 23 July 2026 | Project profile decisions | **Authoritative for DID methods and VC/proof profile** unless this review finds a standards conflict (it does not). |
| `reports/V2_G0_PRODUCT_REALITY_AUDIT.md` and G0 review (4 Oct 2026) | Product reality audit | Evidence about **code**, not about whether V2.1 is a good plan | Used to validate that V2.1’s “do not treat file existence as completion” rule is justified. Not used to declare the plan complete. |
| `reports/V2_1_BASELINE_RECONCILIATION.md` (5 Oct 2026) | Work-package status | Project claim about code | Treated as **CLAIMED**. WP-01/WP-02 L3 claims were not independently re-executed in this review. |

### 2.1 Product extracted from sources

**V2.1 (authoritative):** a prototype SSI ecosystem in which trusted institutions issue verifiable credentials, holders manage them in a Wallet, and relying parties verify presentations with holder consent, plus risk, recovery, audit, and optional blockchain integrity layers.

**Thesis (non-authoritative for stack):** a four-layer system (blockchain, SSI/Indy+Aries, AI fraud, emergency recovery) claiming Hyperledger Indy ledger, ACA-Py/DIDComm, Ethereum EIP-4337 account abstraction, zk-SNARK ZKP, GNN/XGBoost/autoencoder fraud detection, and full W3C/NIST/eIDAS/KVKK compliance.

### 2.2 Document disagreements (decision log)

| ID | Disagreement | Authoritative source | Resolution | Reason |
| --- | --- | --- | --- | --- |
| D1 | Credential exchange: DIDComm/Aries vs OID4VCI/OID4VP | V2.1 non-goals + current OpenID Final specs + walt.id v2 / EUDI protocol practice | **OID4VCI 1.0 + OID4VP 1.0.** DIDComm/Aries/Indy are out of V2 core. | Final OpenID issuance/presentation specs exist; V2.1 already excludes Indy/Aries; thesis stack is dated relative to the 2025 Final OpenID specifications. |
| D2 | Ledger: Hyperledger Indy DID registry vs EVM integrity anchor vs no ledger DID | V2.1 integrity domain + ADR 0001 | **No ledger DID method.** EVM used only for optional non-PII integrity anchors. | DID Core does not require a blockchain; ADR 0001 already rejects ledger DIDs for the prototype. |
| D3 | ZKP / cryptographic selective disclosure | V2.1 non-goals + actual Data Integrity `eddsa-jcs-2022` profile | **Claim minimization / omission only.** No BBS+/zk-SNARK claim. | `eddsa-jcs-2022` signs the canonical document; omitting claims breaks the issuer proof unless a cryptographic SD mechanism is used. |
| D4 | “Full eIDAS / EUDI / NIST compliance” | V2.1 non-goals + EUDI ARF v3.0.0 (informative) | **Architectural reference only. No certification claim.** | Conformance requires notified wallet solutions, trusted lists, CIR alignment, and FCAF — none are in prototype scope. |
| D5 | AI as trained ML vs heuristic | V2.1 G9 + G0 audit | **Label as heuristic unless reproducible model artifacts exist.** | G0 reports handcrafted formulas, not persisted trained models. |
| D6 | Thesis past-tense “system was implemented and measured” vs V2.1 G0-first | V2.1 evidence model | **Do not treat thesis numbers as experimental results.** | No reproducible lab notebook, dataset, or test harness is attached to those tables in the supplied PDF. |
| D7 | OID4VCI `c_nonce` from Token Endpoint (V2.1 / G0 language) vs Nonce Endpoint (Final spec) | OpenID4VCI 1.0 Final, 16 September 2025 | **Nonce Endpoint is normative for freshness of key proofs when the issuer requires `c_nonce`.** Token Endpoint remains required for the pre-authorized-code grant. | Draft-era token `c_nonce` is a hangover; GitHub issue #677 in OpenID4VCI records this explicitly. |

---

## 3. Reconstructed product model

### 3.1 What Secure SSI Platform is

A **combination**: institutional issuer + holder wallet + verifier/relying party + guardian recovery + admin/governance + supporting SSI core, with optional AI risk and blockchain integrity. It is **not** only a wallet and **not** a national identity system.

**Prototype class (honest label):** custodial/server-mediated **web** SSI platform prototype. Keys are managed through a project key-custody abstraction, not a mobile Secure Area / HSM. This is a project-profile limitation, not a standards violation.

### 3.2 Roles

| Role | Surface | Owns | Protocol actions | UI | Security |
| --- | --- | --- | --- | --- | --- |
| Holder | Wallet App | Keys/DID (via custody abstraction), credentials, consent records, activity | OID4VCI receive; OID4VP present; DCQL evaluate | Offers, credentials, consent, requests, recovery status | Private-key non-exposure; consent bound to payload |
| Issuer | Issuer Portal | Org identity, templates, issuance sessions, status lists | OID4VCI metadata, offer, token, nonce, credential | Templates, offers, issued credentials, revocation | Issuer key custody; no issuance without authz |
| Verifier | Verifier Portal | Verification sessions, DCQL queries, results | OID4VP request + `direct_post` response validation | Request builder, QR/link, matrix, history | Session/nonce/state; fail-closed verification |
| Guardian | Recovery Portal | Approvals only; not holder credentials | Recovery quorum protocol (project-specific) | Request, approve/reject, timelock, history | Guardian authn; no single-guardian takeover |
| Admin | Admin Console | Users, orgs, trust registry, policy, health | Not a credential protocol actor | Trust, fraud, recovery oversight, audit | RBAC; object-level authz |
| Trust/governance | Trust domain + Admin | Trust records and evidence | Lookup during verification | Explainable trust status | Distinct from blockchain anchors |
| SSI Core | Backend domains | Identity, wallet, credential, exchange, status, consent, policy, risk, recovery, audit, integrity | Implements protocol state machines | None directly | Fail-closed crypto; secrets; rate limits |

### 3.3 Main lifecycle (intended)

Holder identity → credential offer → offer validation → token (pre-authorized code) → nonce/proof as required → credential endpoint → persist credential → verifier request (DCQL) → wallet match → consent → presentation → cryptographic verification → trust → status → policy → risk signal → decision → audit → optional integrity anchor.

V2.1 is correct that **this lifecycle is the product**, and that several of these steps were historically UI-shaped rather than protocol-complete.

---

## 4. What is correct in V2.1

1. Product definition and explicit non-goals (native mobile, HSM, BBS+/ZKP, EUDI certification, government integration, DIDComm/Indy).
2. Domain-first architecture; microservice count is not a goal.
3. Wallet as identity component with explicit state, not a dashboard.
4. VC 2.0 Recommendation baseline; VC 2.1 left as Working Draft (confirmed WD 30 September 2026).
5. Data Integrity + `eddsa-jcs-2022` as a legal cryptosuite choice (W3C Rec 15 May 2025).
6. OpenID4VCI/OID4VP **1.0 Final** rather than draft 11–20.
7. DCQL as the OID4VP 1.0 query language for the primary profile.
8. Bitstring Status List 1.0 as status profile; 1.1 is a later draft (FPWD 24 September 2026) and must not silently replace 1.0.
9. Trust registry ≠ blockchain anchor; AI ≠ cryptographic validator.
10. L0–L4 completion ladder; only L3/L4 may be called COMPLETE.
11. UI fidelity / truthfulness rules (no fake verified, no ZKP label, no EUDI/government implication).
12. G0 read-only audit before further feature work — empirically justified by G0 findings (fail-open nonce, proof-structure-as-signature, DID-prefix trust, DIF PE instead of DCQL, UI auto-pass).
13. Pre-authorized code as the **controlled demo** issuance profile, with authorization-code+PKCE labeled partial/deferred.

---

## 5. What is wrong, weak, ambiguous, outdated, or overstated

### 5.1 High-confidence defects in V2.1 (plan-level)

**W1 — OID4VCI nonce modeled as a Token Endpoint `c_nonce` handshake (outdated relative to Final).**  
OpenID4VCI 1.0 Final (16 September 2025) defines a **Nonce Endpoint**. If the issuer requires `c_nonce` in key proofs, it **MUST** offer that endpoint; wallets obtain `c_nonce` there. Draft-era optional `c_nonce` on the Token/Credential responses is not the Final model. V2.1, G0 remediation text, and `V2_BASELINE_FREEZE.md` still describe “token returns `c_nonce`.” That is a **standards-alignment error**, not a product-direction error. Token Endpoint remains required for exchanging the pre-authorized code.

**W2 — DID method not frozen inside the master plan.**  
DID Core 1.0 requires a method specification. V2.1 correctly says method choice must precede implementation, then leaves the table as “explicitly selected DID method specifications” without naming them. ADR 0001 already selected `did:web` (issuer) and `did:key` (synthetic holder fixtures only). The revised plan must freeze this or it will be re-litigated as if undecided.

**W3 — OID4VCI key-proof type not frozen.**  
Final spec proof types include `jwt`, `di_vp`, and `attestation`. V2.1 says “declare and test” but does not pick. Without a freeze, implementers will mix Data Integrity credential proofs with undefined issuance PoP.

**W4 — Wallet custody model under-specified.**  
“Real wallet” is correct, but the plan does not say this is a **web/custodial prototype**. Multipaz/EUDI wallets assume device SecureArea and wallet attestation. Leaving this implicit invites overclaim (“secure wallet” as if hardware-backed).

**W5 — Same-device vs cross-device is mentioned, not profiled.**  
walt.id Verifier2 treats `cross_device` / `same_device` / DC API as first-class flow types. A web prototype should freeze: cross-device QR + same-browser link; **DC API and native deep links are OPTIONAL/FUTURE**.

**W6 — Gate sequence still written as if G0 has not run.**  
As of 4–5 October 2026, G0 artifacts exist. The revised plan should start from “G0 executed; remaining gates G2+ with open gaps,” or agents will re-audit forever and delay DCQL/OID4VCI.

### 5.2 Weak but not blocking in V2.1

- Interop B is underspecified (which external stack? which credential format?).
- Recovery is a **project-specific security protocol**, not an OpenID/W3C normative flow; the plan is good on state machines but should not imply SSI-standard recovery.
- “MongoDB authoritative, Redis ephemeral” is an implementation choice presented with architecture-rule force — acceptable for the prototype if labeled as such.
- Performance gate G15 is premature until Golden Path L3 exists.
- `state` required unconditionally is a valid **project profile** tightening of OID4VP; it is not a universal MUST in every spec condition.

### 5.3 Academic thesis — not an implementation plan

The thesis is **internally inconsistent with V2.1 and with current SSI practice**. Material issues:

| Thesis claim | Problem |
| --- | --- |
| System uses Hyperledger Indy + Aries + DIDComm | Contradicts V2.1 non-goals; Indy/Aries is a different protocol family from OID4VCI/VP 1.0. |
| Full compliance with W3C, NIST, eIDAS, KVKK | Unverifiable; EUDI ARF is informative and legally non-binding; no conformance evidence. |
| ZKP / zk-SNARKs compatible with VC 2.0 | VC 2.0 does not imply zk-SNARKs; project cryptosuite does not provide ZKP. |
| EIP-4337 as identity/recovery | Account abstraction is an Ethereum UX/gas pattern, not a DID method or VC status mechanism. |
| Dual ledger (Indy + Ethereum) | Unnecessary complexity; no justification that both are required for VC validity. |
| Table 2.2 “Tam” compliance vs uPort/Sovrin/Entra | Marketing comparison, not a conformance matrix. |
| VC Data Model v2.0 cited as March 2023 Recommendation | **Factually wrong.** VC 2.0 became a W3C Recommendation on **15 May 2025**. |
| Performance tables (94.3% accuracy, 2.7 s recovery, 25–30 TPS, OWASP 9.2/10) | Presented as experimental fact without attached datasets, seeds, or independent test logs in the supplied PDF. Treat as **unverified / likely illustrative**. |
| Past tense “modules completed, Docker deployed, tests passed” | Conflicts with G0 product reality. |

**Jury implication:** submitting the thesis unchanged alongside V2.1 will look like two different projects. The thesis must be rewritten to the V2.1/revised profile or explicitly labeled historical design.

---

## 6. Standards findings (researched 5 October 2026)

| Source | Version / date | Normative status | Implication for this project |
| --- | --- | --- | --- |
| [W3C VC Data Model 2.0](https://www.w3.org/TR/vc-data-model-2.0/) | Rec 15 May 2025 | Recommendation | Correct V2 baseline. Use `@context` `https://www.w3.org/ns/credentials/v2`. |
| [W3C VC Data Model 2.1](https://www.w3.org/TR/vc-data-model-2.1/) | WD 30 September 2026 | Working Draft | Do not implement as baseline. |
| [W3C Data Integrity 1.0](https://www.w3.org/TR/vc-data-integrity/) | Rec 15 May 2025 | Recommendation | Embedded proofs: `DataIntegrityProof`, `proofPurpose`, `verificationMethod`; verification failure is failure. |
| [W3C Data Integrity EdDSA 1.0](https://www.w3.org/TR/vc-di-eddsa/) | Rec 15 May 2025 | Recommendation | `eddsa-jcs-2022` (JCS / RFC 8785) and `eddsa-rdfc-2022` are defined. Project selection of JCS is a **profile choice**, not “the only” EdDSA suite. |
| [RFC 8785 JCS](https://www.rfc-editor.org/rfc/rfc8785) | June 2020 | Informational RFC | Required **because** of `eddsa-jcs-2022`, not because JCS is an Internet Standard. |
| [W3C DID Core 1.0](https://www.w3.org/TR/did-core/) | Rec 19 July 2022 | Recommendation | Architecture and resolution interface; **does not specify `did:web` or `did:key`**. |
| [W3C Controlled Identifiers 1.0](https://www.w3.org/TR/cid-1.0/) | Rec 15 May 2025 | Recommendation | Verification methods (`Multikey`, `JsonWebKey`) and relationships. Align DID documents with CID where Data Integrity is used. |
| [W3C Bitstring Status List 1.0](https://www.w3.org/TR/vc-bitstring-status-list/) | Rec 15 May 2025 (`REC-vc-bitstring-status-list-20250515`) | Recommendation | Correct status baseline. Minimum uncompressed bitstring size and GZIP+multibase encoding are normative. Fail-closed on corrupt lists is project policy on top of retrieval rules. |
| [Bitstring Status List 1.1](https://www.w3.org/TR/vc-bitstring-status-list-1.1/) | FPWD 24 September 2026 | Working Draft | Do not silently adopt. |
| [OpenID4VCI 1.0](https://openid.net/specs/openid-4-verifiable-credential-issuance-1_0.html) | Final, 16 September 2025 | Final Specification | Offer → (pre-authorized code) Token Endpoint → Credential Endpoint; **Nonce Endpoint** when proofs require `c_nonce`; metadata-driven proof types. |
| [OpenID4VP 1.0](https://openid.net/specs/openid-4-verifiable-presentations-1_0-final.html) | Final | Final Specification | `dcql_query` is the 1.0 query mechanism; `client_id`, `nonce`, `response_mode` including `direct_post`; Wallet **evaluates** DCQL. DIF Presentation Exchange is **not** the 1.0 primary query language. |
| [EUDI ARF v3.0.0](https://github.com/eu-digital-identity-wallet/eudi-doc-architecture-and-reference-framework/releases/tag/v3.0.0) | 21–23 July 2026 | Informative architecture (ARF text states it is not legally binding) | Role separation Wallet / Issuer / Relying Party; trusted lists (ETSI TS 119 612) and LoTEs (ETSI TS 119 602); FCAF at conformance.eudi.dev. **Reference only.** |

Classification reminder: “We use pre-authorized code and `direct_post`” is **PROJECT PROFILE**. “DCQL exists in OID4VP 1.0” is **NORMATIVE** for that specification. “MongoDB is the store” is **IMPLEMENTATION CHOICE**.

---

## 7. Comparable-project findings

### 7.1 walt.id Community Stack (reference implementation, not a standard)

Inspected: current docs for Issuer2, Verifier2, Wallet API v2 (pages last updated 26 August 2026 in search results).

- New projects are directed to **Issuer2 / Verifier2 / Wallet API v2** implementing **OID4VCI 1.0 and OID4VP 1.0**. Original APIs are **deprecated draft-era**.
- Wallet v2: DCQL matching; formats include SD-JWT VC, W3C VC, mDL; Ed25519 among algorithms.
- Verifier2: `dcql_query` on session create; `cross_device` / `same_device` / DC API flow types; **policies** separate signature, expiry, schema, trust.
- Alignment with V2.1: role split, DCQL, 1.0 protocols, policy vs signature separation.
- Do **not** copy walt.id’s multi-format surface. Extra formats are feature-count, not required.
- Interop caution: walt.id tutorials often use `jwt_vc_json`. This project’s ADR 0002 uses **Data Integrity `eddsa-jcs-2022`**. Interop B against walt.id is **not automatic**; it requires a shared format/profile or an explicit “own-stack only” Interop A.

### 7.2 OpenWallet Foundation / Multipaz (reference implementation)

- Kotlin Multiplatform wallet SDK: mdoc, SD-JWT VC, OpenID4VCI, OpenID4VP 1.0 (DCQL), SecureArea / Cloud Secure Area, wallet/key attestation.
- Architecture lesson: **key abstraction (SecureArea)** and **wallet backend vs wallet app trust** are explicit. This project should keep a **KeyCustody port**, not pretend to be Multipaz.
- Native Android/iOS is **out of V2 scope**. Multipaz is a future-work benchmark, not a sprint.

### 7.3 EUDI ecosystem

- Wallet Provider, PID/EAA issuers, Relying Parties, and trust lists are distinct.
- User-controlled wallet and registered relying parties are regulatory architecture, not a student portal RBAC.
- Honest mapping: this prototype **imitates the three-party model** and a **local trust registry**. It does **not** implement Member State trusted lists or wallet unit attestation.

### 7.4 What not to copy

- Hyperledger Indy/Aries from the thesis (wrong era for this plan).
- EIP-4337 as identity.
- Extra microservices because walt.id has many APIs.
- SD-JWT / mDL / BBS+ to look like EUDI.

---

## 8. Domain-by-domain audit of V2.1

| Domain | Verdict | Notes |
| --- | --- | --- |
| A. Product architecture | Sound | Domain-first; gateway boundary; Mongo durable / Redis ephemeral as prototype choice. |
| B. Wallet | Sound with custody label | State machine is good; must persist credential used later in VP. |
| C. DID | Incomplete freeze | DID Core vs method split is correct; freeze `did:web` + `did:key` fixture policy. |
| D. Credential | Sound | VC 2.0 + allowlisted types; avoid schema hardcoding beyond demo types. |
| E. Data Integrity | Sound | Fail-closed rules match Data Integrity; G0 proved why the rule exists. |
| F. OID4VCI | Targeted revision | Token+credential correct; **Nonce Endpoint** missing; proof type unfrozen. |
| G. OID4VP/DCQL | Sound | DCQL, nonce, `direct_post`, wallet-side evaluation. Implementation still DIF PE — that is a **code gap**, not a plan error. |
| H. Trust | Sound | Explicit evidence model; prefix matching forbidden. |
| I. Status | Sound | Bitstring 1.0; freshness and fail-closed are profile policies. |
| J. Consent/privacy | Sound | Claim omission ≠ cryptographic SD. |
| K. Recovery | Sound as project protocol | Quorum/timelock/rotation; not an SSI standard. |
| L. AI | Sound | Heuristic vs trained; cannot override crypto. |
| M. Blockchain | Sound | Non-authoritative integrity; zero PII on-chain. |
| N. Security | Sound | Threat list and negative tests; object-level authz must remain in DoD. |
| O. Testing/evidence | Sound | E1–E12; screenshot ≠ protocol. Interop A/B/C is the right ladder. |

---

## 9. Implementation sequence audit

V2.1 Product Gates G0–G16 are the right **control sequence**. Recommended adjustments:

1. **Acknowledge G0 complete** (artifacts dated 4 Oct 2026). Do not block remaining work on a second identical G0 unless the tree changes materially.
2. **G2 must be executed as a written freeze** including: DID methods (ADR 0001), VC/proof (ADR 0002), OID4VCI proof type, Nonce Endpoint, same/cross device, custody model. G3–G5 should not start without that freeze (several ADRs already exist; the master plan must ingest them).
3. **Do not reorder Wallet-first (G3) after Issuer (G4).** A credential that cannot be stored and later presented is not issued. Keep G3 → G4 → G5.
4. **Trust registry (conceptually G6) is P0** even if numbered after VP. Prefix-matching trust makes Golden Path “success” meaningless. Parallelize trust data model with G4/G5, not after a fake green verification UI.
5. **G15 performance after G11 Golden Path L3.** Measuring TPS on a non-conformant verifier is theatre (thesis failure mode).
6. **G14 Interop A is mandatory; Interop B optional** and format-constrained.

Completion ladder: KEEP L0–L4. Existing WP COMPLETE labels in reconciliation notes are **out of scope for this plan review** except as a warning: only independently re-run tests count.

---

## 10. UI / UX review (plan + known evidence)

V2.1 UX rules are the correct professional standard. Against G0/reconciliation evidence, the **current UI** (not the V2.1 plan) still risks:

- ZKP / selective disclosure language for field omission.
- Government / EUDI visual implication (`did:web:trust.eudi.europa.eu` appears in demo QR fixtures).
- Frontend verification auto-pass on API failure (G0).
- “Blockchain secured” / trained autoencoder copy.
- DIF PE shown as if it were OID4VP 1.0.

The plan’s G12 is sufficient **if enforced**. Add an acceptance rule: **demo DIDs, org names, and QR hosts must not use `europa.eu`, `eudi`, `turkiye.gov`, or `e-devlet` identifiers.**

Accessibility, empty/error/revoked states, and role IA in V2.1 should be kept.

---

## 11. Plan vs product (traceability status)

No full independent re-audit of HEAD was repeated in this review. Using G0 + reconciliation as **last recorded product reality**:

| Area | Status vs V2.1 plan |
| --- | --- |
| Fail-closed nonce/signature | CLAIMED L3 (WP-01); **NOT YET VERIFIED by this review** |
| Holder binding crypto | CLAIMED L3 (WP-02); **NOT YET VERIFIED by this review** |
| Trust registry | MISSING / prefix match |
| DCQL | MISSING (DIF PE present) |
| OID4VCI token + nonce + PoP | PARTIAL / MISSING vs Final |
| Consent-bound presentation | PARTIAL |
| AI labeled heuristic | MISREPRESENTED in UI/docs historically |
| Blockchain as integrity-only | PARTIAL / MISREPRESENTED in UI |
| Interoperability | MISSING |
| Thesis performance claims | MISREPRESENTED as measured fact |

---

## 12. Overclaims register

| Claim | Where | Supported? | Truthful wording |
| --- | --- | --- | --- |
| EUDI compliant / government integrated | Thesis; UI fixtures | No | “Three-party SSI prototype inspired by EUDI role separation; not an EUDI Wallet and not connected to government systems.” |
| Full W3C/NIST/eIDAS/KVKK compliance | Thesis Table 2.2, §1.4 | No | “Designed with W3C VC/DID Recommendations in mind; KVKK/GDPR treated as privacy principles; no certification.” |
| Zero-knowledge / cryptographic selective disclosure | Thesis §3.5.5; UI | No | “Holder may omit claims from a presentation payload (claim minimization). This is not a zero-knowledge proof.” |
| Trained ML / 94.3% accuracy | Thesis §3.6 | Not evidenced | “Heuristic risk scoring on synthetic events unless a versioned model artifact and evaluation report exist.” |
| Immutable / blockchain verified credential | Thesis blockchain module | Overstated | “Optional EVM anchor of a SHA-256 event digest; credential validity is determined by Data Integrity verification, status, and trust — not by the chain.” |
| 100% secure / OWASP 9.2/10 | Thesis §3.8.6 | Not evidenced | Omit numeric OWASP scores unless a named methodology and raw results are archived. |
| Fully OID4VCI/OID4VP compliant | Risk in future reports | Only if profile-scoped | “Implements the documented Pre-Authorized Code + `direct_post` + DCQL profile of OpenID4VCI/VP 1.0. Unsupported features listed in the conformance report.” |
| EAL / hardware security | Not strongly claimed in V2.1; forbidden by non-goals | N/A | Do not introduce. |

---

## 13. Recommended changes (summary)

See the revised plan, design report, decision matrix, and change log in this folder.

**MUST CHANGE (blocking for a defensible plan):** W1 Nonce Endpoint; W2 freeze DID methods; W3 freeze VCI proof type; document authority (thesis ⊀ implementation); Interop format caveat; demo naming ban for government/EUDI; G0 already-run sequencing.

**SHOULD CHANGE:** custody/web-wallet label; same/cross-device profile; G6 trust parallel with issuance; G15 after Golden Path; ingest ADR 0001/0002 into the master plan.

**MAY CHANGE:** Interop B against walt.id on a **shared** format later; native wallet / SecureArea as future work; SD-JWT as future work.

**KEEP AS-IS:** product roles, non-goals, L0–L4, evidence types, AI/blockchain boundaries, DCQL primary VP profile, Bitstring 1.0, UI truthfulness, G0 philosophy, fail-closed crypto rules.

---

## 14. Final verdict format

### Overall assessment

**PLAN IS SOUND WITH TARGETED REVISIONS** (V2.1).  
**PLAN IS NOT SUITABLE** as an implementation baseline (January 2026 thesis), without a rewrite that adopts the revised profile.

### Scorecard

| Area | Verdict | Confidence | Main reason |
| --- | --- | --- | --- |
| Product definition | Sound | High | Multi-role ecosystem; non-goals honest |
| Architecture | Sound | High | Domain-first; justified boundaries |
| Wallet | Sound w/ custody label | High | State owner required; web prototype |
| DID | Targeted freeze | High | Core vs method split correct; methods in ADR not in plan |
| Credential | Sound | High | VC 2.0 Rec; 2.1 WD excluded |
| OID4VCI | Targeted revision | High | Token/credential OK; nonce model outdated |
| OID4VP/DCQL | Sound | High | Matches Final spec; code still lags |
| Trust | Sound | High | Registry vs prefix vs chain distinguished |
| Status | Sound | High | Bitstring 1.0 Rec confirmed |
| Consent/privacy | Sound | High | Omission vs SD distinguished |
| Recovery | Sound (project protocol) | Medium | Good state machine; not a standard |
| AI | Sound | High | Bounded risk signal |
| Blockchain | Sound | High | Integrity-only |
| Security | Sound | High | Fail-closed + negative tests |
| UX/UI | Sound as rules | Medium | Rules good; current UI historically overclaims |
| Testing/evidence | Sound | High | L3/L4 + E1–E12 |
| Interoperability | Weak freeze | Medium | Interop A clear; B needs format |

### MUST CHANGE / SHOULD CHANGE / MAY CHANGE / KEEP

See §13 and `SSI_PLAN_CHANGE_LOG.md`.
