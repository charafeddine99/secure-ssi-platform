# Competitive & Design Research Report
**Document ID:** `DOC-DES-02-RESEARCH`  
**Version:** 1.0  
**Date:** October 2026  
**Status:** Approved Reference Research  

---

## 1. Research Objectives & Methodology

The goal of this research is to ground the **Secure SSI Platform** user experience in established international standards, European digital identity frameworks, and cutting-edge SSI implementations. 

Digital identity platforms carry higher user stakes than standard consumer applications:
- Users make decisions regarding personal data disclosure.
- Cryptographic keys and decentralized identities lack centralized password-reset safety nets without structured recovery.
- Verifiers make legally binding or security-critical trust decisions based on cryptographic proofs.

Therefore, our UX/UI research evaluates each primary reference across six dimensions:
1. **Trust & Authenticity Conveyance:** How the system communicates cryptographic authority and provenance.
2. **Informed Consent & Data Clarity:** How clearly the user understands what data is requested and transmitted.
3. **Error Prevention & Recovery:** How the interface prevents destructive mistakes and guides users through failures.
4. **Information Architecture & Density:** Balance between consumer simplicity and enterprise audit rigor.
5. **Accessibility & WCAG 2.2 Compliance:** Universal design for assistive technology, keyboard navigation, and contrast.
6. **Technical & Cryptographic Honesty:** Ensuring the interface accurately reflects the underlying protocol without misleading security theater.

---

## 2. Primary References Analysis

### 2.1 EUDI Wallet Reference Implementation (Architecture and Reference Framework)
- **Primary Source:** European Digital Identity Architecture and Reference Framework (ARF v1.4 / EUDI Wallet Dev Guidelines)  
- **Link:** [https://github.com/eu-digital-identity-wallet/eudi-wallet-reference-architecture](https://github.com/eu-digital-identity-wallet/eudi-wallet-reference-architecture)  
- **Access Date:** October 2026  
- **Screens / Flows Examined:**
  - Issuance Flow (PID / mDL onboarding via OID4VCI)
  - Cross-device and same-device Presentation Flow (OID4VP DCQL request resolution)
  - Relying Party Authenticity & Trust Validation Screen
  - Wallet Lock & Device Binding Biometrics

#### Strengths
- **Trust-First Visual Hierarchy:** Displays the verified legal identity of the Relying Party before any credential data is requested.
- **Clear Separation of Issuer vs Holder vs Verifier:** Establishes unambiguous role boundaries preventing credential forgery confusion.
- **Standardized Presentation States:** Defines clear states for Request Pending, Consent Given, Transmitted, and Verification Confirmed.

#### Weaknesses
- **Governmental Bureaucratic Density:** Can feel dry and intimidating to non-technical citizens if not paired with warm typography and clear progressive disclosure.
- **Complex Exception Paths:** Edge cases (e.g., partial credential expiration or trust chain network timeouts) are often buried in technical error codes rather than actionable user guidance.

#### What Secure SSI Platform Adapts
- **The Verified Relying Party Identity Banner:** When a verifier requests credentials, the verifier's legal name, registered domain, and verified trust status are prominently placed at the top of the consent screen.
- **The 4-Step Presentation Lifecycle:** Explicit transitions across Request Received → Credential Matching → Consent Confirmation → Direct Post Submission.

#### What We Explicitly Reject & Why
- **Overly complex EU legal jargon:** We will not display raw eIDAS 2.0 clause identifiers or EU Commission technical Annex references to end users. Plain-language summaries with optional collapsible technical specs will be used instead.

---

### 2.2 walt.id Open Source SSI Ecosystem
- **Primary Source:** walt.id Documentation, Web Wallet, and Credential Issuance/Verification Portals  
- **Link:** [https://docs.walt.id/](https://docs.walt.id/)  
- **Access Date:** October 2026  
- **Screens / Flows Examined:**
  - Web Wallet Dashboard & Credential Details Modal
  - OID4VCI Offer Acceptance & Scanning Flow
  - Verifier DCQL Request Builder and QR Presentation Console
  - Issuer Credential Template Catalog

#### Strengths
- **Clean Developer & Institutional UX:** Intuitive presentation of JSON-LD / W3C VC structures alongside visual credential badges.
- **Modern Minimalist Layout:** Uses dark neutral surfaces, high-contrast borders, and clear micro-interactions.
- **Unified QR Presentation:** Seamless switching between camera scanning, file upload, and deep links.

#### Weaknesses
- **Selective Disclosure Ambiguity:** Often presents selective disclosure UI checkboxes even when using signature suites that transmit the full credential under the hood, creating potential user confusion regarding cryptographic redaction.
- **Limited Multi-Sig Recovery Interface:** Recovery interfaces lack clear real-time quorum progress tracking for social guardians.

#### What Secure SSI Platform Adapts
- **Credential Card Aesthetics:** Visual credential cards displaying credential title, issuer badge, issuance date, status indicator, and expandable claim fields.
- **The Dual-Pane Verifier Console:** Left pane for DCQL request generation and QR presentation; right pane for live streaming verification results.

#### What We Explicitly Reject & Why
- **Ambiguous Selective Disclosure Checkboxes:** We reject presenting checkboxes that suggest claims can be cryptographically withheld when using `eddsa-jcs-2022`. We provide full-disclosure transparency with an honest warning.

---

### 2.3 W3C & OpenID Foundation (OID4VCI & OID4VP Standards)
- **Primary Sources:**
  - W3C Verifiable Credentials Data Model v2.0 ([https://www.w3.org/TR/vc-data-model-2.0/](https://www.w3.org/TR/vc-data-model-2.0/))
  - OpenID for Verifiable Credential Issuance ([https://openid.net/specs/openid-4-verifiable-credential-issuance-1_0.html](https://openid.net/specs/openid-4-verifiable-credential-issuance-1_0.html))
  - OpenID for Verifiable Presentations ([https://openid.net/specs/openid-4-verifiable-presentations-1_0.html](https://openid.net/specs/openid-4-verifiable-presentations-1_0.html))
- **Access Date:** October 2026  
- **Key Technical Protocols Examined:**
  - Ed25519Signature2020 / eddsa-jcs-2022 Data Integrity Cryptosuite
  - Bitstring Status List v1.0 (Revocation bit allocation)
  - Direct Post & Direct Post.JWT submission mechanisms
  - Digital Credentials Query Language (DCQL)

#### Key Architectural Realities Discovered
1. **Cryptosuite Reality:** `eddsa-jcs-2022` signs a canonical JCS SHA-256 hash of the entire JSON credential document. It does NOT produce ZKP or BBS+ blind signatures.
2. **Consent Requirement:** Consent must explicitly state the exact data transferred, the requesting entity, the stated purpose, and the fact that the complete cryptographic credential will be delivered.
3. **Fail-Closed Principle:** Status resolution, trust registry lookups, and signature checks must strictly fail closed on network partition or cryptographic anomaly.

#### UX Principles Derived
- **Radical Cryptographic Honesty:** The UI must explain protocol constraints in plain language without pretending features exist that are not cryptographically present.
- **Authoritative Status Indicators:** Trust badges must distinguish between:
  - `AUTHORITATIVE VALID` (Cryptographically verified on-chain / in status list)
  - `REVOKED` (Explicit bit set in Bitstring Status List)
  - `EXPIRED` (System clock exceeds expirationDate)
  - `SUSPENDED / QUARANTINE` (AI anomaly threshold triggered or trust registry pending)
  - `UNAVAILABLE / ERROR` (Fail-closed network or verification failure)

---

### 2.4 W3C WCAG 2.2 AA Accessibility Standards
- **Primary Source:** W3C Web Content Accessibility Guidelines (WCAG) 2.2  
- **Link:** [https://www.w3.org/TR/WCAG22/](https://www.w3.org/TR/WCAG22/)  
- **Access Date:** October 2026  

#### Key Requirements & Implementation Strategy

| WCAG 2.2 Guideline | Platform Requirement | Secure SSI Implementation |
| :--- | :--- | :--- |
| **1.4.3 Contrast (Minimum)** | 4.5:1 for normal text, 3:1 for large text | All text tokens calibrated against `#0b0f19` and `#111827` to exceed 7:1 (AAA) or 4.5:1 (AA). |
| **1.4.1 Use of Color** | Color must not be the sole means of conveying information | Every status chip includes both color, an explicit text label (`VERIFIED`, `REVOKED`), and a semantic Lucide icon. |
| **2.4.7 Focus Visible** | Any keyboard operable user interface must have a mode of operation where the keyboard focus indicator is visible | Global `:focus-visible` ring using `#fbbf24` (Amber-400) with 3px solid outline and 3px offset for 100% visibility. |
| **2.4.11 / 2.4.13 Focus Appearance & Not Obscured** | Focus indicator has high contrast and is not obscured by sticky headers/footers | All sticky elements (`enterprise-header`, mobile dock) respect proper `z-index` and padding offsets. |
| **2.5.5 / 2.5.8 Target Size (Minimum)** | Interactive target size minimum 24x24px, preferably 44x44px for touch | All touch targets in Holder layout are minimum 44px height/width with generous padding. |
| **3.2.4 Consistent Identification** | Components that have the same functionality are identified consistently | Canonical component library for `TrustBadge`, `StatusChip`, `CredentialCard`, and `NinePointVerificationMatrix`. |
| **3.3.1 - 3.3.4 Error Identification & Prevention** | Errors are described in text, suggestions provided, and legal/financial actions are reversible or confirmed | Destructive operations (Revocation, Approval, Session Cancellation) require two-step confirmation modals. |

---

### 2.5 Industry Leading Design Systems
- **Primary Sources:**
  - **Atlassian Design System:** Enterprise data density, table filters, token structure, and modal ergonomics.
  - **GitHub Primer:** Dark mode contrast, monospace token formatting, and developer telemetry clarity.
  - **Apple Human Interface Guidelines (Wallet & Apple Pay):** Card pass aesthetics, progressive disclosure of claims, and biometric confirmation mechanics.

#### Key Takeaways Adapted
- **Token Hierarchy:** Separation of Primitive Tokens (Hex/RGB values), Semantic Tokens (`color-danger`, `bg-surface`), and Component Tokens (`card-border`, `input-focus`).
- **Data Table Ergonomics:** Sticky headers, row hover highlighting, right-aligned numbers/actions, and monospace alignment for cryptographic hashes and DIDs.
- **Card Metaphor:** Physical credential cards with embossed subtle gradients, rounded corners (`border-radius: 12px`), and high-contrast credential metadata.

---

## 3. Synthesis & Strategic Design Decisions

1. **GovTech Dark Mode as Canonical Foundation:** A high-contrast dark theme minimizes eye strain in security operations centers, conveys institutional gravity, and makes colorful cryptographic status badges pop with high clarity.
2. **Role-Tailored Information Density:**
   - **Holder / Citizen:** Spacious, friendly, card-centric layout with 16px body text and clear touch targets.
   - **Institutional (Issuer / Verifier / Admin):** Compact, scannable, data-dense layouts with 13px table text, monospace data fields, and side-by-side verification consoles.
3. **Fail-Closed Verification Display:** No ambiguous or optimistic loading results. Verification results are displayed only after authoritative cryptographic confirmation.
