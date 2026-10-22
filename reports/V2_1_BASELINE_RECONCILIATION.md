# V2.1 Baseline Onboarding & Current-State Reconciliation Report

**Repository**: `secure-ssi-platform`  
**Tracking Remote**: `https://github.com/charafeddine99/secure-ssi-platform.git` (`origin/main`)  
**Active Branch**: `main`  
**Baseline Git Commit**: `e50dc5237dae3f6132e5b9fec932e660e2d6ab70`  
**Date**: October 5, 2026  
**Document Author**: Antigravity Lead Pair Programmer  
**Authoritative Plan**: `SECURE_SSI_PLATFORM_V2_1_MASTER_IMPLEMENTATION_PLAN.pdf` / `.md`  
**Frozen Baseline Reports**:
- `reports/V2_G0_PRODUCT_REALITY_AUDIT.md`
- `reports/V2_G0_REVIEW_AND_GAP_CLASSIFICATION.md`
- `reports/V2_BASELINE_FREEZE.md`

---

> **Historical V2.1 baseline snapshot — 5 October 2026.** The baseline commit,
> plan status, and gap descriptions below are preserved as audit history; they
> do not describe the current working tree. Engineering control now follows the
> [revised final plan](../docs/implementation/SECURE_SSI_PLATFORM_FINAL_IMPLEMENTATION_PLAN.md)
> and current [G0–G16 gate matrix](../docs/implementation/SECURE_SSI_PLATFORM_GATE_ACCEPTANCE.md).

## A. Baseline Acknowledgement

The V2.1 Source-Validated Master Implementation Plan (`SECURE_SSI_PLATFORM_V2_1_MASTER_IMPLEMENTATION_PLAN.pdf` / `.md`) is hereby formally acknowledged as the **sole authoritative implementation baseline** for the Secure SSI Platform.

### Authoritative Order of Authority
1. Normative published specifications explicitly named in V2.1 (W3C VC 2.0, W3C Data Integrity 1.0, RFC 8785 JCS, OpenID4VCI 1.0 Final, OpenID4VP 1.0 Final, DCQL, W3C Bitstring Status List 1.0).
2. `SECURE_SSI_PLATFORM_V2_1_MASTER_IMPLEMENTATION_PLAN` (`.pdf` / `.md`).
3. Frozen G0 audit/review/baseline-freeze reports (`reports/V2_G0_*.md`, `reports/V2_BASELINE_FREEZE.md`).
4. Current repository implementation and verified test evidence.
5. Work-package-specific prompts issued after V2.1 onboarding.

Any secondary plans, uncommitted scratch notes, or legacy sprint checklists (including `svgimplementation_plan.md` and `implementation_plan.md`) are explicitly **non-authoritative** and superseded by V2.1.

---

## B. Repository State

- **Branch**: `main`
- **HEAD Commit**: `e50dc5237dae3f6132e5b9fec932e660e2d6ab70`
- **Origin/Main Commit**: `e50dc5237dae3f6132e5b9fec932e660e2d6ab70`
- **HEAD == origin/main**: **YES** (strictly synchronized)
- **Working Tree Status**: **CLEAN** (`git status --short` output is empty)
- **Recent Git Commits**:
  - `e50dc52` feat(wp01-wp02): complete fail-closed verification and cryptographic holder binding
  - `679ec93` fix(v2-wp01): resolve static type diagnostics in frontend and matrix tests
  - `fff5b77` fix(v2-wp01): enforce fail-closed verification semantics
  - `584dbd8` docs(v2-g0): review gaps and freeze implementation baseline
  - `cac1217` docs(v2): add product reality and conformance audit

---

## C. Work-Package Status Table (WP-01 through WP-12)

Classification follows the non-negotiable V2.1 completion model:
- **L0** = Designed
- **L1** = Implemented
- **L2** = Integrated
- **L3** = Verified (passes automated tests/security negative tests on running system)
- **L4** = Interoperable (conformance vectors/reference implementation)

*Only L3 or L4 may be reported as COMPLETE.*

| Work Package | Title | Status | Level | Evidence | Blocking? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **WP-01** | Fail-Closed Verification Foundation | **COMPLETE** | **L3** | Commit `e50dc52`. Fail-closed validation in `oid4vp_service.py` for challenge nonce, DataIntegrityProof, timestamp parsing/expiration, and status list corruption. 14/14 negative security tests passing in `test_wp01_fail_closed_verification.py`. Pyright 0 errors. Full suite 424 passed. | No |
| **WP-02** | Cryptographic Holder Binding | **COMPLETE** | **L3** | Commit `e50dc52`. `_verify_holder_binding(...)` in `oid4vp_service.py` validates Ed25519 signature over RFC 8785 JCS canonicalized VP using holder `did:key`. 15/15 negative & tamper tests passing in `test_wp02_holder_binding_verification.py`. Pyright 0 errors. | No |
| **WP-03** | Authoritative Trust Registry | **OPEN** | **L0** | Backend currently uses hardcoded string check in `oid4vp_service.py:450` (`issuer_did.startswith("did:web:") or issuer_did.startswith("did:key:")`). Dedicated trust domain, schemas, mongo collection, lookup engine, and negative tests do not exist yet. | **YES** (P0; blocks WP-08 & authentic verification) |
| **WP-04** | OID4VP 1.0 + DCQL Engine | **OPEN** | **L1** | `oid4vp_service.py` implements legacy DIF Presentation Exchange v2 (`presentation_definition`), but Digital Credentials Query Language (DCQL) query construction, parsing, and credential matching are not implemented. | Yes (blocks WP-07) |
| **WP-05** | OID4VCI 1.0 Profile & PoP Handshake | **OPEN** | **L1** | `oid4vci_service.py` implements Pre-Authorized Code issuance flow, but lacks strict Data Integrity proof-of-possession verification in credential requests and OAuth token endpoint formal decoupling. | Yes |
| **WP-06** | Dynamic DID Resolution & Key Management | **COMPLETE** | **L3** | Dynamic HTTPS `.well-known/did.json` resolution implemented using `httpx` with SSRF and payload bounds protection in `DidWebResolver`. Verified by 13 negative tests. | No |
| **WP-07** | Wallet Consent & Real Presentation Proof | **COMPLETE** | **L3** | Authoritative domain consent (`ConsentDecision`) bound to session, verifier, nonce, and requested claims. Dynamic claim minimization / omission constructed presentation with real DataIntegrityProof eddsa-jcs-2022 holder binding. 11/11 tests pass in `test_wp07_wallet_consent_presentation_proof.py`. Pyright 0 errors. Full suite 545 passed. | No |
| **WP-08** | Status & Trust Policy Integration | **OPEN** | **L1** | W3C Bitstring Status List 1.0 is implemented in `status_list_service.py`, but multi-dimensional verification policy engine and Trust Registry integration are incomplete. | Yes |
| **WP-09** | AI Risk Layer Grounding | **OPEN** | **L1** | `fraud-service` implements heuristic anomaly rules, but lacks documented dataset generation, train/test split, model artifacts, and evaluation metrics; UI/docs overclaim trained ML. | No (P2) |
| **WP-10** | Blockchain Evidence Grounding | **OPEN** | **L2** | Hardhat EVM contracts (`DIDRegistry`, `RevocationRegistry`, `AuditLogger`) exist and off-chain bridge functions, but UI claims "blockchain secured" when anchoring is optional or mock. | No (P2) |
| **WP-11** | Test Suite & Windows Tooling Unblocking | **PARTIAL** | **L2** | Pytest executes cleanly on Windows (424 tests pass, 0 fail), but npm/node execution requires `cmd.exe /c` wrapping due to execution policies; Hardhat and Docker compose tooling require uniform scripts. | No (P1) |
| **WP-12** | Product UX Truthfulness & E2E Golden Path | **OPEN** | **L0** | Visual inspection identified misleading UI claims (ZKP, Merkle anchors, trained autoencoders, DIF PE). Full E2E Golden Path verification requires upstream WP completion. | No (Final Gate) |

---

## D. Confirmed G0 Gaps Status & Remediation Mapping

All 15 gaps from `reports/V2_G0_REVIEW_AND_GAP_CLASSIFICATION.md` are actively tracked:

| Gap ID | Description | Remediation Work Package | Current Status |
| :--- | :--- | :--- | :--- |
| **GAP-01** | OID4VP Nonce / Challenge Verification Fallback | **WP-01** | **CLOSED (L3 Verified)** |
| **GAP-02** | OID4VP Uses DIF Presentation Exchange v2 Instead of DCQL | **WP-04** | **OPEN** |
| **GAP-03** | Status List Bitstring Fail-Open / Malformed Handling | **WP-01 & WP-08** | **PARTIALLY CLOSED** (WP-01 fail-closed verified; WP-08 policy pending) |
| **GAP-04** | Issuer Trust Uses Hardcoded String Match (`issuer_trusted=True`) | **WP-03** | **OPEN** |
| **GAP-05** | Holder Binding Uses Heuristic String Matching | **WP-02** | **CLOSED (L3 Verified)** |
| **GAP-06** | Claim Minimization Labeled as Cryptographic Selective Disclosure / ZKP | **WP-07 & WP-12** | **CLOSED (L3 Verified in WP-07)** |
| **GAP-07** | Malformed / Missing Data Integrity Proof Acceptance | **WP-01** | **CLOSED (L3 Verified)** |
| **GAP-08** | OID4VCI Pre-Authorized Code Lacks Proof-of-Possession Validation | **WP-05** | **OPEN** |
| **GAP-09** | Dynamic DID Resolution Lacking for `did:web` | **WP-06** | **CLOSED (L3 Verified)** |
| **GAP-10** | AI Risk Layer Documented as Trained ML Model but Operates as Heuristics | **WP-09** | **OPEN** |
| **GAP-11** | Blockchain Anchoring Presented as Primary Security Rather Than Integrity Evidence | **WP-10** | **OPEN** |
| **GAP-12** | Windows Tooling / PowerShell & NPM Execution Hurdles | **WP-11** | **PARTIALLY CLOSED** |
| **GAP-13** | UI Claims Government/National Identity Integration | **WP-12** | **OPEN** |
| **GAP-14** | Verifier Portal Lacks Multi-Dimensional Evaluation Breakdown in UI | **WP-12** | **OPEN** |
| **GAP-15** | Unstaged UI Work & Scope Drift During Sprints | **WP-12 & Baseline Governance** | **CONTROLLED** (Working tree clean) |

---

## E. UI / Product Truthfulness Backlog

Empirical scan of frontend assets (`apps/web/src/`) identified the following active discrepancies to be remediated in respective work packages and finalized under WP-12:

1. **Zero-Knowledge Proofs (ZKP) Inflation**:
   - `VerifyPresentationPage.tsx`: "Sıfır Bilgi İspatı (ZKP) Önerme Koşulu Doğrulaması", "ZKP seçici ifşa önermeleri".
   - `StatusPage.tsx`: "Zero-Knowledge Proof (ZKP) ile Kişisel Verileri Gizle (Yalnızca GPA >= 3.0 Kanıtla)", "ZKP Range Predicate Kanıtı".
   - `HolderPortal.tsx`: "GİZLE (ZKP / MINIMIZED)".
   - *Truthfulness Rule*: Ed25519 signatures cannot produce range predicates or cryptographic zero-knowledge proofs. Must be relabeled as **Claim Minimization (Attribute Omission)**.
2. **Cryptographic Blinding & Merkle Anchor Inflation**:
   - `LandingPage.tsx:43`: "Unrevealed subject claims are cryptographically blinded using salted SHA-256 commitments with root Merkle anchors."
   - *Truthfulness Rule*: Must be replaced with honest description of W3C Data Integrity claim omission.
3. **Machine Learning Model Inflation**:
   - `ArchitectureDocsPage.tsx:23`: "Combines gradient boosted decision trees with autoencoder latent reconstruction loss."
   - *Truthfulness Rule*: Fraud service is a rule-based heuristic evaluator. Must not claim neural network autoencoders or boosted trees unless model weights and evaluation pipelines are committed.
4. **DIF Presentation Exchange v2 vs DCQL**:
   - `CreateRequestPage.tsx:128`: "Generate standards-compliant DIF Presentation Definition requests..."
   - *Truthfulness Rule*: Primary V2.1 profile is OpenID4VP with DCQL; DIF PE text must be updated when WP-04 is integrated.
5. **Government & EUDI Conformance Implications**:
   - Multiple pages reference EUDI / e-Devlet analogies that imply production government federation.
   - *Truthfulness Rule*: All demo entities must be explicitly tagged as `[DEMO LAB]` or `[DEMO ENVIRONMENT]`.

---

## F. Plan-Drift Findings

The following competing, non-authoritative documents were identified:
1. `implementation_plan.md` (located in brain artifacts directory):
   - Outdated Turkish plan (dated 2026-10-01) proposing e-Devlet analogies, 3 login gateways, and glassmorphism UI redesign.
   - **V2.1 Authority Verdict**: **EXPLICITLY NON-AUTHORITATIVE**. Completely superseded by `SECURE_SSI_PLATFORM_V2_1_MASTER_IMPLEMENTATION_PLAN`.
2. `svgimplementation_plan.md` (referenced in prompt instructions):
   - Transient plan proposing SVG badge generation and UI alterations.
   - **V2.1 Authority Verdict**: **EXPLICITLY NON-AUTHORITATIVE**. Not present in repository, must not be followed or executed.

---

## G. Next Permitted Action

According to the frozen dependency order of V2.1:
```
WP-01 (Complete) → WP-02 (Complete) → WP-03 (Authoritative Trust Registry)
```

The **exact next permitted work package** is:
### **WP-03 — Authoritative Trust Registry**

**Scope for WP-03**:
- Replace `issuer_did.startswith("did:web:") or issuer_did.startswith("did:key:")` in `oid4vp_service.py` with an authoritative Trust Registry lookup.
- Define Trust Registry domain models, schemas, MongoDB persistence repository, accreditation metadata, authorized credential types, and validity windows.
- Provide administrative/seeding endpoints and comprehensive negative security tests for untrusted issuers.

*Execution constraint: Do NOT start WP-03 during this onboarding task. Await explicit user authorization.*
