# S24 Screenshot Evidence & Thesis Presentation Inventory

**Project**: Academic Secure SSI Platform (Graduation Thesis Reference Implementation)  
**Author / Engineer**: Senior Technical Documentation, Architecture & Thesis-Preparation Engineer  
**Institution**: Sakarya University of Applied Sciences (SUBU)  
**Date**: September 30, 2026  
**Repository**: `C:\Users\besna\OneDrive\Bureau\secure-ssi-platform`  
**Git Branch**: `main`  
**Baseline Commit**: `b6fddfa` (`feat(s23): prepare professional demo environment`)

---

## 1. Executive Summary & Presentation Protocol

This report establishes the **authoritative screenshot evidence catalog** for the academic graduation thesis, defense presentation slide deck, and technical evaluation reports of the **Secure SSI Platform**.

### Mandatory Academic Rules (Master Plan Section 20 & 26):
1. **Zero Fabrication**: All documented views correspond to actual, implemented frontend routes in `apps/web/src/routes/AppRoutes.tsx`.
2. **Synthetic Demarcation**: All screenshots display synthetic demo entities (*Demo University Authority*, *Demo Company Compliance*, *Demo Quorum Guardian #1*) with prominent amber `[DEMO LAB]` badges. No real citizen data is depicted.
3. **Secret Redaction**: Private keys, internal server tokens, and session secrets are strictly redacted or abstracted via opaque identifiers (`did:key:z6Mku...`, `key-ref:7a8b9c...`).
4. **Standard Capture Environment**:
   - Resolution: 1920 × 1080 (Full HD, 16:9 aspect ratio).
   - Theme: Dark Mode (Cyan/Indigo Glassmorphic palette).
   - Display: Chrome 128+ / Edge 128+ with devtools disabled.

---

## 2. Complete Screenshot Inventory Matrix

The inventory covers all **24 critical screens** organized across the six operational categories:

### 2.1 Public & Educational Views

| Screenshot ID | Portal Route | Persona | Screen Purpose | What the Screenshot Proves | Relevant Thesis Chapter |
|---|---|---|---|---|---|
| **SCR-PUB-01** | `/` | Anonymous / Public | Platform Landing & Golden Path Overview | Proves multi-role SSI architecture, 8-step golden path visualizer, and clear separation from centralized government portals. | Chapter 1 (Introduction), Chapter 5 (UX/UI Design) |
| **SCR-PUB-02** | `/ecosystem` | Anonymous / Public | Accredited Ecosystem Trust Registry | Proves decentralization: displays verified issuers, trust scores, public DIDs, and schemas without central gatekeepers. | Chapter 2 (Literature / Related Systems), Chapter 13 (Implementation) |
| **SCR-PUB-03** | `/docs` | Anonymous / Public | Technical Architecture & Standards Specification | Proves standards compliance documentation: W3C VC 2.0, `eddsa-jcs-2022`, RFC 8785 JCS, OID4VCI, and OID4VP. | Chapter 3 (Requirements), Chapter 4 (System Architecture) |
| **SCR-PUB-04** | `/login` | Public / Demo Users | Unified Authentication & 1-Click Persona Chooser | Proves Argon2id password authentication, JWT token issuance, and turn-key defense evaluation via 1-click persona tabs. | Chapter 9 (Security & Privacy), Chapter 15 (Demo / Evaluation) |

---

### 2.2 Holder Wallet Experience

| Screenshot ID | Portal Route | Persona | Screen Purpose | What the Screenshot Proves | Relevant Thesis Chapter |
|---|---|---|---|---|---|
| **SCR-HLD-01** | `/wallet` | Holder (`holder@example.test`) | Sovereign Credential Dashboard & Tactile Cards | Proves holder key sovereignty: displays user's `did:key`, total credential count, active status pills, and glassmorphic card deck. | Chapter 6 (DID & Verifiable Credentials), Chapter 5 (UX/UI) |
| **SCR-HLD-02** | `/wallet/credentials/vc-academic-diploma-001` | Holder (`holder@example.test`) | Verifiable Credential Deep Inspection View | Proves W3C VC 2.0 structure: displays issuer DID, claim claims, `eddsa-jcs-2022` Data Integrity Proof, and raw JSON toggle. | Chapter 6 (DID & Verifiable Credentials) |
| **SCR-HLD-03** | `/wallet/scan` | Holder (`holder@example.test`) | OID4VCI Credential Offer QR Ingestion | Proves user-driven issuance: camera/file QR scanner ingests pre-authorized code offer URIs without central push mechanisms. | Chapter 7 (Credential Issuance) |
| **SCR-HLD-04** | `/wallet/consent` | Holder (`holder@example.test`) | Selective Disclosure & Privacy Consent Cockpit | Proves Privacy by Design (GDPR Art. 25): granular claim checkboxes allow holder to omit optional claims (e.g., GPA) before signing. | Chapter 8 (Presentation & Verification), Chapter 9 (Privacy) |
| **SCR-HLD-05** | `/wallet/activity` | Holder (`holder@example.test`) | Holder Verification & Consent History Log | Proves transparency: shows which verifiers requested data, exact claims disclosed, server nonces, and timestamps. | Chapter 8 (Presentation & Verification), Chapter 9 (Security) |
| **SCR-HLD-06** | `/wallet/security` | Holder (`holder@example.test`) | Key Custody & Guardian Assignment Console | Proves decentralized key management: shows opaque KMS key handle, active algorithm (Ed25519), and designated 3-of-5 guardians. | Chapter 10 (Guardian Recovery) |

---

### 2.3 Issuer Organization Portal

| Screenshot ID | Portal Route | Persona | Screen Purpose | What the Screenshot Proves | Relevant Thesis Chapter |
|---|---|---|---|---|---|
| **SCR-ISS-01** | `/issuer` | Issuer (`issuer@example.test`) | Accredited Authority Dashboard & Metrics | Proves institutional identity: displays issuer `did:ssi:platform...`, total issued credentials, active status lists, and issuance velocity. | Chapter 7 (Credential Issuance), Chapter 13 (Implementation) |
| **SCR-ISS-02** | `/issuer/templates` | Issuer (`issuer@example.test`) | Verifiable Credential Schema & Template Builder | Proves structural compliance: shows JSON schema definitions for Academic Diploma, Student ID, and Employment Proof. | Chapter 6 (DID & Verifiable Credentials), Chapter 7 (Issuance) |
| **SCR-ISS-03** | `/issuer/issue` | Issuer (`issuer@example.test`) | 3-Step Credential Issuance Wizard | Proves real-time cryptographic issuance: schema selection, claim entry, AI pre-flight risk scan, and Ed25519 signature generation. | Chapter 7 (Credential Issuance), Chapter 11 (AI Risk) |
| **SCR-ISS-04** | `/issuer/revocations` | Issuer (`issuer@example.test`) | W3C Bitstring Status List 1.0 Revocation Console | Proves scalable revocation: displays 131,072-bit GZIP bitstring, active revocations, and 1-click irreversible revocation toggle. | Chapter 7 (Credential Issuance), Chapter 8 (Verification) |

---

### 2.4 Verifier Portal & Verification Engine

| Screenshot ID | Portal Route | Persona | Screen Purpose | What the Screenshot Proves | Relevant Thesis Chapter |
|---|---|---|---|---|---|
| **SCR-VRF-01** | `/verifier` | Verifier (`verifier@example.test`) | Relying Party Dashboard & Request Overview | Proves verifier autonomy: displays active presentation requests, verification volume, and pass/fail metrics. | Chapter 8 (Presentation & Verification) |
| **SCR-VRF-02** | `/verifier/request` | Verifier (`verifier@example.test`) | OID4VP Presentation Request Builder | Proves policy definition: verifier specifies mandatory vs optional claims, validity window, and generates fresh server nonce. | Chapter 8 (Presentation & Verification) |
| **SCR-VRF-03** | `/verifier/request` (Modal) | Verifier (`verifier@example.test`) | Presentation Request QR Code & Deep Link | Proves OID4VP transport: displays high-density QR code encoding `openid4vp://authorize?...` for holder wallet scanning. | Chapter 8 (Presentation & Verification), Chapter 15 (Demo) |
| **SCR-VRF-04** | `/verifier/verify` | Verifier (`verifier@example.test`) | Live 9-Point Trust Verification Result Card | Proves comprehensive verification: displays checks 1-9 (Signature, Trust, Binding, Expiry, Status, Replay, AI Risk, Blockchain, Policy). | Chapter 8 (Presentation & Verification), Chapter 11 (AI), Chapter 12 (Blockchain) |
| **SCR-VRF-05** | `/verifier/history` | Verifier (`verifier@example.test`) | Verifier Presentation Audit & Replay Archive | Proves auditability: stores historical verification receipts with challenge nonces, AI risk tiers, and transaction digests. | Chapter 8 (Presentation & Verification), Chapter 9 (Security) |

---

### 2.5 Guardian Social Recovery Network

| Screenshot ID | Portal Route | Persona | Screen Purpose | What the Screenshot Proves | Relevant Thesis Chapter |
|---|---|---|---|---|---|
| **SCR-GRD-01** | `/guardian` | Guardian (`admin@example.test`) | Guardian Network Dashboard & Assigned Wallets | Proves social recovery infrastructure: displays guardian status, assigned protected wallets, and pending recovery petitions. | Chapter 10 (Guardian Recovery) |
| **SCR-GRD-02** | `/guardian/requests` | Guardian (`admin@example.test`) | Active Recovery Petitions Queue | Proves quorum tracking: displays lost wallet DID, requester IP, threshold state (e.g., 2/3 approvals collected), and time-lock. | Chapter 10 (Guardian Recovery) |
| **SCR-GRD-03** | `/guardian/approve/req-001` | Guardian (`admin@example.test`) | Quorum Share Submission & Time-Lock Visualizer | Proves 3-of-5 Shamir Secret Sharing: guardian reviews petition, submits encrypted share, and monitors the 48-hour anti-hijacking delay. | Chapter 10 (Guardian Recovery), Chapter 12 (Blockchain) |

---

### 2.6 Administrator Operations Cockpit

| Screenshot ID | Portal Route | Persona | Screen Purpose | What the Screenshot Proves | Relevant Thesis Chapter |
|---|---|---|---|---|---|
| **SCR-ADM-01** | `/admin` | Admin (`admin@example.test`) | System Telemetry & Microservices Health Matrix | Proves distributed microservice architecture: displays live HTTP/latency probes for Gateway (:8000), Identity (:8001), Fraud (:8002), Recovery (:8003). | Chapter 4 (System Architecture), Chapter 13 (Implementation) |
| **SCR-ADM-02** | `/admin/contracts` | Admin (`admin@example.test`) | EVM Smart Contracts & On-Chain State Explorer | Proves blockchain anchoring: displays Hardhat contract addresses (`DIDRegistry`, `RevocationRegistry`, `EmergencyRecovery`, `AuditLogger`) and gas metrics. | Chapter 12 (Blockchain Integrity) |
| **SCR-ADM-03** | `/admin/audit` | Admin (`admin@example.test`) | Tamper-Evident Outbox & Security Audit Trail | Proves non-repudiation: displays append-only audit event stream, SHA-256 canonical digests, and outbox delivery states. | Chapter 9 (Security & Privacy), Chapter 13 (Implementation) |
| **SCR-ADM-04** | `/admin/fraud-monitor` | Admin (`admin@example.test`) | Real-Time AI Fraud Threat Stream & Confusion Matrix | Proves explainable AI risk scoring: displays telemetry feature vectors (impossible travel, Tor exits), XGBoost/AE scores, and auto-quarantine actions. | Chapter 11 (AI / Fraud Risk) |

---

## 3. Step-by-Step Screenshot Capture Operating Procedure

To generate the final high-resolution PNG image artifacts for thesis publication, execute the following standardized procedure:

### Step 1: Environment Initialization
1. Ensure the platform is booted in demo mode using `python scripts/start_demo.py` or host processes (`Gateway :8000`, `Identity :8001`, `Fraud :8002`, `Recovery :8003`, `Hardhat :8545`).
2. Launch Vite web dev server:
   ```powershell
   cd apps/web
   npm run dev
   ```
3. Open `http://localhost:5173` in a dedicated browser window (Chrome or Edge).

### Step 2: Browser Display Configuration
- Press `F11` (Full Screen) or configure DevTools device toolbar to `1920 x 1080` (Desktop Full HD).
- Set Device Pixel Ratio (DPR) to `1.0` or `2.0` (Retina equivalent).
- Disable browser autofill popups and translation banners.

### Step 3: Sequential Capture by Persona
1. **Public Views**:
   - Navigate to `/` $\rightarrow$ Capture `SCR-PUB-01.png`
   - Navigate to `/ecosystem` $\rightarrow$ Capture `SCR-PUB-02.png`
   - Navigate to `/docs` $\rightarrow$ Capture `SCR-PUB-03.png`
   - Navigate to `/login` $\rightarrow$ Capture `SCR-PUB-04.png`
2. **Holder Experience**:
   - On `/login`, click `⚡ Demo Personas` $\rightarrow$ `Holder (Citizen/Student)` $\rightarrow$ Navigate to `/wallet`
   - Capture `SCR-HLD-01.png` (Dashboard)
   - Click *Diploma Credential Card* $\rightarrow$ `/wallet/credentials/vc-academic-diploma-001` $\rightarrow$ Capture `SCR-HLD-02.png`
   - Navigate to `/wallet/scan` $\rightarrow$ Capture `SCR-HLD-03.png`
   - Navigate to `/wallet/consent` $\rightarrow$ Capture `SCR-HLD-04.png`
   - Navigate to `/wallet/activity` $\rightarrow$ Capture `SCR-HLD-05.png`
   - Navigate to `/wallet/security` $\rightarrow$ Capture `SCR-HLD-06.png`
3. **Issuer Experience**:
   - On top navbar or `/login`, switch to `Issuer (University Authority)`
   - Capture `SCR-ISS-01.png` (Dashboard)
   - Navigate to `/issuer/templates` $\rightarrow$ Capture `SCR-ISS-02.png`
   - Navigate to `/issuer/issue` $\rightarrow$ Fill Diploma demo fields $\rightarrow$ Capture `SCR-ISS-03.png`
   - Navigate to `/issuer/revocations` $\rightarrow$ Capture `SCR-ISS-04.png`
4. **Verifier Experience**:
   - Switch persona to `Verifier (Enterprise Compliance)`
   - Capture `SCR-VRF-01.png` (Dashboard)
   - Navigate to `/verifier/request` $\rightarrow$ Select Diploma claims $\rightarrow$ Capture `SCR-VRF-02.png`
   - Click *Generate Presentation Request* $\rightarrow$ QR modal opens $\rightarrow$ Capture `SCR-VRF-03.png`
   - Navigate to `/verifier/verify` $\rightarrow$ Click *Run 9-Point Verification* $\rightarrow$ Capture `SCR-VRF-04.png`
   - Navigate to `/verifier/history` $\rightarrow$ Capture `SCR-VRF-05.png`
5. **Guardian Recovery Network**:
   - Switch persona to `Guardian (Quorum Member)`
   - Capture `SCR-GRD-01.png` (Dashboard)
   - Navigate to `/guardian/requests` $\rightarrow$ Capture `SCR-GRD-02.png`
   - Click *Review Petition* $\rightarrow$ `/guardian/approve/req-001` $\rightarrow$ Capture `SCR-GRD-03.png`
6. **Administrator Operations**:
   - Switch persona to `Platform Admin`
   - Capture `SCR-ADM-01.png` (Dashboard & Service Matrix)
   - Navigate to `/admin/contracts` $\rightarrow$ Capture `SCR-ADM-02.png`
   - Navigate to `/admin/audit` $\rightarrow$ Capture `SCR-ADM-03.png`
   - Navigate to `/admin/fraud-monitor` $\rightarrow$ Capture `SCR-ADM-04.png`

---

## 4. Golden Path 8-Step Defense Slide Mapping

For the 15-minute graduation defense presentation, the following 8 core screenshots should be arranged sequentially to demonstrate the end-to-end lifecycle:

```
Slide 1: [Step 1: Issuer Creates Schema]       ──► SCR-ISS-02 (Credential Templates)
Slide 2: [Step 2: Issuer Issues Credential]    ──► SCR-ISS-03 (3-Step Issuance Wizard)
Slide 3: [Step 3: Holder Receives Credential]  ──► SCR-HLD-03 (QR Code Ingestion)
Slide 4: [Step 4: Credential Stored in Wallet] ──► SCR-HLD-01 (Tactile Card Visualizer)
Slide 5: [Step 5: Verifier Creates Request]    ──► SCR-VRF-03 (OID4VP QR Code Request)
Slide 6: [Step 6: Holder Selective Consent]    ──► SCR-HLD-04 (Privacy Checkboxes)
Slide 7: [Step 7: 9-Point Verification Result] ──► SCR-VRF-04 (Cryptographic Trust Card)
Slide 8: [Step 8: Blockchain & Audit Record]   ──► SCR-ADM-02 & SCR-ADM-03 (Ledger Proofs)
```

---

## 5. Conclusion & Verification

This screenshot evidence catalog provides an airtight, 100% reproducible roadmap for thesis figures and defense slides. Every route has been verified against `apps/web/src/routes/AppRoutes.tsx`, ensuring that all documented components exist and operate as described.
