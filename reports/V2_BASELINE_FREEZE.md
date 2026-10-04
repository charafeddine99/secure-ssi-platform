# V2 Implementation Baseline Freeze Document

**Repository**: `C:\Users\besna\OneDrive\Bureau\secure-ssi-platform`  
**Date**: October 4, 2026  
**Status**: **FROZEN**  
**Gate**: V2 Gate G0 — Product Reality, Gap Classification & Baseline Freeze  
**Baseline Git Commit**: `cac1217`  
**Tracking Remote**: `https://github.com/charafeddine99/secure-ssi-platform.git` (`origin/main`)  

---

## A. Repository Baseline

- **Repository Path**: `C:\Users\besna\OneDrive\Bureau\secure-ssi-platform`
- **Active Branch**: `main`
- **Frozen Commit SHA**: `cac12179daa07693bfea0b1978fe0d84cd9879d4`
- **Remote Tracking**: `origin/main` (Synchronized at `cac1217`)
- **Working Tree State**: Clean baseline verified. Prior pre-audit unstaged UI edits safely preserved in Git stash (`stash@{0}`).
- **Integrity Rule**: No implementation work may rewrite history, rebase, or force-push. All future remediation commits must branch or advance linearly from this frozen baseline.

---

## B. Product Definition

The Secure SSI Platform is a multi-role Self-Sovereign Identity (SSI) ecosystem prototype designed as a unified platform containing six integrated components:

1. **Holder Wallet**: A web-based identity wallet enabling citizens and students to manage decentralized identifiers (DIDs), keys, inspect credential offers, provide informed consent, store credentials, and generate verifiable presentations.
2. **Issuer Portal**: An institutional portal for accredited organizations (universities, national authorities) to manage schemas, issue verifiable credential offers via OID4VCI, and maintain revocation status.
3. **Verifier Portal**: A relying party portal allowing institutions and third parties to construct verification queries (DCQL / OID4VP), present interactive QR/deep-link flows, evaluate multi-dimensional verification criteria, and record verification history.
4. **Guardian Recovery Portal**: A security enclave managing social recovery, quorum-based guardian authentication ($M$-of-$N$), timelock delays, and identity key rotation.
5. **Admin Console**: A governance dashboard providing cross-role visibility into system health, AI fraud alerts, smart contract integrity anchors, and tamper-evident platform audit logs.
6. **SSI Core**: The foundational backend domain layer managing cryptographic key operations, DID resolution, canonicalization (RFC 8785), status list generation, and protocol state machines.

---

## C. Normative Technology Baseline

The normative specifications governing this platform are frozen as follows:

| Area | Normative Baseline Specification | Status Rule |
| :--- | :--- | :--- |
| **Verifiable Credentials** | W3C Verifiable Credentials Data Model v2.0 (Recommendation) | Strict normative baseline. Draft 2.1 specs are forbidden. |
| **Data Integrity** | W3C Data Integrity 1.0 (Recommendation) | Strict normative baseline. |
| **Signature Suite** | Ed25519 + `eddsa-jcs-2022` | Canonical signing and verification mechanism. |
| **Canonicalization** | RFC 8785 JSON Canonicalization Scheme (JCS) | Mandatory canonicalizer. |
| **DID Methods** | W3C DID Core 1.0 (`did:key` and `did:web`) | `did:key` for holders; `did:web` for issuers and verifiers. |
| **Issuance Protocol** | OpenID for Verifiable Credential Issuance (OID4VCI) 1.0 Final | Normative baseline profile. |
| **Presentation Protocol**| OpenID for Verifiable Presentations (OID4VP) 1.0 Final | Normative baseline profile. |
| **Query Semantics** | Digital Credentials Query Language (DCQL) | Mandatory query model for OID4VP requests. |
| **Revocation & Status** | W3C Bitstring Status List v1.0 (Recommendation) | Mandatory status mechanism. |
| **Smart Contracts** | EVM Solidity 0.8.28 / OpenZeppelin v5 | Append-only integrity and audit anchor layer. |

---

## D. Project Profile Decisions

### 1. DID Method & Resolution Profile
- **Holder DIDs**: Use `did:key` with Ed25519 (`0xed01` prefix, multibase base58-btc encoding). Algorithmically resolved; keys are non-rotatable per DID.
- **Issuer & Verifier DIDs**: Use `did:web`. Must resolve via HTTPS `https://<domain>/.well-known/did.json`. Local fixture resolution (`issuer.did.json`) is permitted solely in offline development mode under `ENVIRONMENT=local_fixture`.

### 2. Credential Format & Proof Profile
- **Format**: W3C VC 2.0 with Data Integrity proofs (`DataIntegrityProof`, cryptosuite `eddsa-jcs-2022`).
- **Signature Engine**: Ed25519 private key signing with RFC 8785 JCS canonicalization.
- **Fail-Closed Rule**: Any cryptographic signature verification failure, malformed base58 proof, or unsupported cryptosuite MUST evaluate to `sig_valid = False` and result in immediate presentation rejection.

### 3. OID4VCI Issuance Profile
- **Primary Flow**: Pre-Authorized Code flow (`urn:ietf:params:oauth:grant-type:pre-authorized_code`).
- **Sequence**:
  1. Issuer creates `CredentialOffer` with short-lived pre-authorized code and optional user PIN.
  2. Holder calls OAuth2 `/token` endpoint, presenting the pre-authorized code, receiving an access token and fresh `c_nonce`.
  3. Holder calls `/credential` endpoint, providing access token, target credential configuration, and cryptographic proof of possession (`proof`) bound to `c_nonce`.
  4. Issuer verifies proof of possession and issues the signed W3C VC.

### 4. OID4VP Presentation Profile
- **Query Mechanism**: DCQL (Digital Credentials Query Language) query generation and evaluation.
- **Response Mode**: `direct_post` delivering `vp_token`.
- **Challenge / Nonce Integrity**: The presentation wrapper `vp_token.proof` MUST include the exact matching session `nonce`. If the nonce is missing, mismatched, or replayed, verification MUST immediately fail (`challenge_valid = False`).

### 5. Holder Cryptographic Binding Policy
- Verifier MUST verify that `vp_token.proof` was signed by the private key corresponding to `credentialSubject.id` in the enclosed credential.
- String prefix matching on subject IDs is strictly forbidden as a substitute for cryptographic binding.

### 6. Trust Registry Model
- Trust is established via a dedicated, authoritative local Trust Registry (`trust_registry`).
- Checks issuer DID against registered accredited organizations, authorized credential schemas, and active status.
- Hardcoded string prefix matching (`issuer_did.startswith("did:web:")`) is strictly prohibited.

### 7. Status & Revocation Profile
- Authoritative status is tracked via W3C Bitstring Status List 1.0 (Gzip compressed bitstrings, 131,072 entries).
- Verifier fetches and decodes the bit at `statusListIndex`. If bit is `1`, credential is treated as REVOKED.
- Fail-Closed Policy: If the status list is unreachable or corrupted, verification must fail (`status_valid = False`).

### 8. Claim Minimization vs Selective Disclosure Policy
- Standard W3C Data Integrity (Ed25519) does not support cryptographic attribute-level redaction without breaking signatures.
- Omitting claims from an Ed25519 VC breaks the signature. Therefore, omitting fields in the presentation consent screen is officially designated as **Claim Minimization (Omission)**, NOT cryptographic selective disclosure.
- False labels such as "Zero-Knowledge Proofs (ZKP)", "BBS+ Signatures", and "Salted Commitments" are strictly removed from the UI.

### 9. AI Risk Layer Role
- The AI layer (`fraud-service`) is an independent heuristic risk evaluator providing non-cryptographic anomaly signals (0–100 risk score).
- **Absolute Invariant**: Under NO circumstances can low AI risk override cryptographic, expiration, or revocation failures. If cryptographic verification fails, the presentation is REJECTED.

### 10. Blockchain Integrity Layer Role
- Hardhat EVM smart contracts (`DIDRegistry`, `RevocationRegistry`, `EmergencyRecovery`, `AuditLogger`) provide tamper-evident event anchoring.
- **Fail-Open Policy for Issuance/Verification**: Blockchain network outages or timeouts do NOT block credential issuance or verification.
- **Truthful Status**: Verifier records `blockchain_anchored = True` ONLY when an actual transaction receipt is confirmed by `Web3Bridge`.

---

## E. Explicit Product Non-Goals

The following capabilities are explicitly classified as out of scope for the V2 core prototype:
1. **Native Mobile Wallet Application**: The wallet is implemented as a mobile-responsive Progressive Web Application (PWA). Native iOS/Android builds are not required.
2. **Hardware HSM / Secure Enclave Equivalence**: Production FIPS 140-2 Level 3 hardware HSM integration is a non-goal; keys are managed via software memory providers and secure environment variables.
3. **Advanced ZKP / BBS+ Cryptographic Selective Disclosure**: Pure zero-knowledge predicate proofs (Groth16/PLONK) and BBS+ signatures are non-goals. The system relies on standard W3C Data Integrity Ed25519.
4. **DIDComm v2 / Hyperledger Aries Wire Protocol**: DIDComm v2 is not used for primary transport; OpenID4VCI and OpenID4VP Direct Post are the sole transport protocols.
5. **Government Production eIDAS Federation**: Production integration with live government systems (e.g. e-Devlet, EUDI Architecture Reference Framework production pilots) is not required; localized mock/lab institutions are used.

---

## F. Completion Model

Every feature and requirement must adhere to the 5-level completion hierarchy:

```
L0 — Designed
     The requirement, UX behavior, protocol/state model, data contract, and acceptance criteria are written.
  ↓
L1 — Implemented
     Source code and unit-level tests exist.
  ↓
L2 — Integrated
     Real frontend, backend, persistence, protocol state, and authorization paths are connected.
  ↓
L3 — Verified
     Passes automated end-to-end, integration, and security negative tests against the running system.
  ↓
L4 — Interoperable
     Validated against reference implementations or standards conformance test vectors.
```

**Rule of Truth**: Only **L3 (Verified)** or **L4 (Interoperable)** may be reported as COMPLETE. L0, L1, and L2 states must be labeled as designed, implemented, or integrated, never complete.

---

## G. G0 Exit Condition

Before remediation implementation work begins:
1. This baseline freeze document (`reports/V2_BASELINE_FREEZE.md`) and the review report (`reports/V2_G0_REVIEW_AND_GAP_CLASSIFICATION.md`) must be reviewed and approved.
2. All 15 audit gaps must be mapped to the locked remediation backlog.
3. Remediation must proceed strictly according to the frozen work package sequence (`WP-01` through `WP-12`), starting with foundational fail-closed security.

---

## H. Locked Remediation Backlog

| Work Package | Title | Priority | Gaps Addressed | Dependencies |
| :--- | :--- | :--- | :--- | :--- |
| **WP-01** | Fail-Closed Verification Foundation | **P0** | GAP-01, GAP-03, GAP-07 | None |
| **WP-02** | Cryptographic Holder Binding | **P0** | GAP-05 | WP-01 |
| **WP-03** | Authoritative Trust Registry | **P0** | GAP-04 | WP-01 |
| **WP-04** | OID4VP 1.0 + DCQL Engine | **P1** | GAP-02 | WP-01, WP-02 |
| **WP-05** | OID4VCI 1.0 Profile & PoP Handshake | **P1** | GAP-08 | WP-01, WP-02 |
| **WP-06** | Dynamic DID Resolution & Key Management | **P1** | GAP-09 | WP-01 |
| **WP-07** | Wallet Consent & Real Presentation Proof | **P0** | GAP-06 | WP-01, WP-02 |
| **WP-08** | Status & Trust Policy Integration | **P1** | GAP-03, GAP-04 | WP-01, WP-03 |
| **WP-09** | AI Risk Layer Grounding | **P2** | GAP-10 | WP-01 |
| **WP-10** | Blockchain Evidence Grounding | **P2** | GAP-11 | WP-01 |
| **WP-11** | Test Suite & Windows Tooling Unblocking | **P1** | GAP-12 | WP-01 |
| **WP-12** | Product UX Truthfulness & E2E Golden Path | **P0/P1** | GAP-06, GAP-13, GAP-14, GAP-15 | All preceding |

---

## I. Known Claims That Must NOT Be Made Yet

The following claims are currently unsupported by technical evidence and must NOT be made in reports, UI badges, or thesis documentation until verified:
1. **"Full OpenID4VP 1.0 Compliance"**: Prohibited until DCQL query syntax and cryptographic holder binding are implemented.
2. **"Cryptographic Selective Disclosure / Zero-Knowledge Proofs"**: Prohibited because Ed25519 signatures cover the entire credential and pseudo-ZKP checks are non-mathematical.
3. **"Trained Deep Learning Anomaly Detection Model"**: Prohibited because the fraud engine operates on handcrafted heuristic rules.
4. **"Government Accredited Trust Authority"**: Prohibited because issuer trust is evaluated via string prefix matching without a governance registry.
5. **"Hardware-Backed Key Protection"**: Prohibited because keys are software-managed in server memory or browser local storage.
6. **"Independent External Interoperability"**: Prohibited until validated against official EUDI or OpenID conformance suites.

---

*Baseline officially frozen at commit `cac1217` on October 4, 2026.*
