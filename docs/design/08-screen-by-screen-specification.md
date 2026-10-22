# Screen-by-Screen UI & Interaction Specification
**Document ID:** `DOC-DES-08-SPECIFICATION`  
**Version:** 2.0  
**Date:** October 2026  
**Status:** Approved Screen Specifications  

---

## 1. Public & Authentication Screens

### 1.1 SCR-PUB-01: Landing Page (`/`)
1. **User Goal:** Understand the value proposition of the Secure SSI Platform, explore its European regulatory compliance (eIDAS 2.0, W3C VC 2.0), and navigate to role portals or documentation.
2. **Key Information Displayed:** Hero headline, cryptographic feature badges (Ed25519, Bitstring Status List, EIP-4337, AI Fraud Detection), live platform health status, portal selection cards.
3. **Primary & Secondary Actions:**
   - *Primary:* "Launch Holder Wallet" (`/wallet`) or "Open Verifier Terminal" (`/verifier`).
   - *Secondary:* "Read Architecture Docs" (`/docs`), "Explore Ecosystem" (`/ecosystem`).
4. **Content Hierarchy:**
   - Top Header (Brand, Ecosystem link, Docs link, Login button)
   - Hero Section (High-impact typography, quick entry CTA)
   - 4 Role Portal Gateways (Holder, Issuer, Verifier, Guardian)
   - Trust & Standards Verification Strip
   - System Architecture Diagram & Technical Highlights
   - Footer (Legal, GitHub, Standards links)
5. **Component Inventory:** `Navbar`, `ModuleCard`, `StatusChip`, `Button`, `Footer`.
6. **Form & Validation:** None.
7. **Responsive Layout:** 3-column portal grid on desktop (`>1024px`), 2-column on tablet (`768px-1024px`), 1-column stacked on mobile (`<768px`).
8. **Accessibility & Keyboard:** All CTA buttons have visible `:focus-visible` rings. Semantic `<main>`, `<section>`, and `<header>` regions.
9. **Backend/API Bindings:** `GET /health` (Gateway health probe), `GET /api/v1/system/stats`.
10. **States & Scenarios:** If the gateway is unreachable, the network indicator displays "Gateway Offline" with graceful fallback.

---

### 1.2 SCR-PUB-02: Ecosystem Explorer (`/ecosystem`)
1. **User Goal:** Explore the decentralized trust registry, inspect active verified issuers, and verify cryptographic public keys.
2. **Key Information Displayed:** Verified Issuer Directory, Trust Registry Root Hash, Total Issued Credentials count, Active Revocation Lists count.
3. **Primary & Secondary Actions:**
   - *Primary:* "Filter by Trust Tier" (Government, Higher Ed, Enterprise).
   - *Secondary:* "Inspect Issuer DID Document", "Copy Issuer Public Key".
4. **Content Hierarchy:** Page title → Trust registry summary metrics → Filter toolbar → Grid of trusted issuer cards → Cryptographic root verification panel.
5. **Component Inventory:** `TrustBadge`, `StatusChip`, `Input` (search), `Button`, `TableEnterprise`.
6. **Form & Validation:** Search input with live debounced filtering (300ms).
7. **Responsive Layout:** Responsive grid adapting from 3 columns desktop to single column mobile.
8. **Accessibility & Keyboard:** Filter pills accessible via `ArrowLeft` / `ArrowRight`. Screen reader announcements on filter change.
9. **Backend/API Bindings:** `GET /api/v1/trust-registry/issuers`, `GET /api/v1/trust-registry/root`.
10. **States & Scenarios:** Empty state displayed if search query matches zero issuers with a "Reset Filter" button.

---

### 1.3 SCR-PUB-03: Architecture Documentation (`/docs`)
1. **User Goal:** Review the technical design specifications, cryptographic standards, and sequence diagrams of the platform.
2. **Key Information Displayed:** Technical specifications covering W3C VC 2.0, OID4VCI, OID4VP DCQL, Bitstring Status List v1.0, and EIP-4337 social recovery.
3. **Primary & Secondary Actions:**
   - *Primary:* "Select Topic" from sidebar menu.
   - *Secondary:* "Copy Code Snippet", "Download Spec PDF".
4. **Content Hierarchy:** Sticky doc navigation menu (left) → Document reading pane (center) → On this page table of contents (right).
5. **Component Inventory:** Sidebar navigation, syntax-highlighted code blocks, copy buttons, breadcrumbs.
6. **Form & Validation:** None.
7. **Responsive Layout:** Left sidebar collapses into a drawer on mobile.
8. **Accessibility & Keyboard:** Heading hierarchy (`h1` through `h4`) strictly monotonic.
9. **Backend/API Bindings:** Static Markdown rendering with local fallback.
10. **States & Scenarios:** Network disconnect does not break viewing of already loaded documentation.

---

### 1.4 SCR-PUB-04: Unified Authentication (`/login`)
1. **User Goal:** Authenticate with credentials or decentralized wallet, acquire JWT session token, and route to the appropriate portal.
2. **Key Information Displayed:** Persona selection tabs (`HOLDER`, `ISSUER`, `VERIFIER`, `GUARDIAN`, `ADMIN`), username/password fields, "Connect Hardware/Web3 Wallet" option.
3. **Primary & Secondary Actions:**
   - *Primary:* "Sign In" button.
   - *Secondary:* "Switch Persona Role", "Forgot Keys / Request Social Recovery".
4. **Content Hierarchy:** Centered authentication card → Role selection tab bar → Form inputs → Action buttons → Security disclaimers.
5. **Component Inventory:** `AuthModal` / `AuthPage`, `Button`, `Input`, `StatusChip`.
6. **Form & Validation:** Email/Username required; password minimum 8 chars; role must be selected. Inline validation feedback.
7. **Responsive Layout:** Centered 440px card on desktop; 100% viewport width with 16px margins on mobile.
8. **Accessibility & Keyboard:** Auto-focuses first input on load; supports `Enter` key to submit form; `aria-invalid` on failed login.
9. **Backend/API Bindings:** `POST /api/v1/auth/login`, `POST /api/v1/auth/register`, `GET /api/v1/auth/session`.
10. **States & Scenarios:**
    - *Success:* Stores `secure_ssi_token`, updates `AuthContext`, redirects to target role dashboard.
    - *Error:* Clear alert: "Invalid username or password. Check credentials or try social recovery."

---

## 2. Holder Wallet Screens

### 2.1 SCR-HLD-01: Wallet Dashboard (`/wallet`)
1. **User Goal:** View personal digital identity cards, verify active status, and initiate QR presentations.
2. **Key Information Displayed:** Holder DID (with 1-click copy), total active credentials count, visual credential cards, security alert banner if guardians not configured.
3. **Primary & Secondary Actions:**
   - *Primary:* "Scan QR Presentation" (`/wallet/scan`).
   - *Secondary:* "Click Credential Card" (opens details modal), "Setup Guardians" (`/wallet/security`).
4. **Content Hierarchy:**
   - Top Bar: Holder Avatar & DID Pill with copy trigger
   - Metric Strip: Active Credentials, Expired, Revoked, Pending Requests
   - Guardian Status Warning (if quorum < 2)
   - Credential Card Grid (Sorted by newest issuance date)
   - Recent Activity Stream
5. **Component Inventory:** `CredentialCard`, `CredentialDetailModal`, `StatusChip`, `Button`, `EmptyState`.
6. **Form & Validation:** None.
7. **Responsive Layout:**
   - Desktop: 2-column credential card grid with max 480px width per card.
   - Mobile: 1-column vertically scrollable card stack; sticky bottom dock navigation.
8. **Accessibility & Keyboard:** Cards are keyboard focusable via `Tab`; pressing `Enter` or `Space` opens the detail modal.
9. **Backend/API Bindings:** `GET /api/v1/wallets`, `GET /api/v1/credentials?walletId={id}`.
10. **States & Scenarios:**
    - *Empty State:* "Your wallet is empty. Scan an issuance offer QR from your university or employer to add credentials."

---

### 2.2 SCR-HLD-02: Credential Details (`/wallet/credentials/:id`)
1. **User Goal:** Inspect every individual claim, cryptographic signature, issuer DID, and real-time status list check for a specific credential.
2. **Key Information Displayed:** Full claim key-value pairs, Issuer Trust Seal, Bitstring Revocation status, Expiration timestamp, Raw JSON-LD viewer.
3. **Primary & Secondary Actions:**
   - *Primary:* "Present this Credential via QR".
   - *Secondary:* "Verify Real-time Status", "Export JSON-LD", "Delete from Wallet".
4. **Content Hierarchy:** Card visual preview header → Status summary bar → Claim key-value table → Cryptographic signature details → Raw JSON toggle.
5. **Component Inventory:** `CredentialDetailModal`, `TrustBadge`, `StatusChip`, `Button`, `NinePointVerificationMatrix`.
6. **Form & Validation:** Confirmation dialog required before deleting a credential.
7. **Responsive Layout:** 600px max-width centered dialog on desktop; full-screen sheet on mobile.
8. **Accessibility & Keyboard:** Trapped focus; `Escape` closes modal; copyable monospace fields.
9. **Backend/API Bindings:** `GET /api/v1/credentials/{id}`, `GET /api/v1/status-lists/{listId}/status/{index}`.
10. **States & Scenarios:** If the status list check reveals the credential is revoked, the status badge updates to crimson `REVOKED` and presentation triggers are disabled.

---

### 2.3 SCR-HLD-03: Scan QR Page (`/wallet/scan`)
1. **User Goal:** Scan an OID4VP presentation request QR code or paste an OID4VP request URI to initiate the verification and consent flow.
2. **Key Information Displayed:** Live camera scanner viewport, camera permission prompt, manual session ID / request URI input box.
3. **Primary & Secondary Actions:**
   - *Primary:* "Start Camera Scanning" or "Submit Request URI".
   - *Secondary:* "Cancel and Return to Wallet".
4. **Content Hierarchy:** Top instructions → Camera viewport / frame → "Or enter manually" divider → Input text field with "Continue" button.
5. **Component Inventory:** Camera stream component, `Input`, `Button`, `AlertCircle`.
6. **Form & Validation:** Validates that the input URI starts with `openid4vp://` or contains a valid 24+ char hexadecimal session ID.
7. **Responsive Layout:** Centered 480px box on desktop; full viewport camera viewfinder on mobile.
8. **Accessibility & Keyboard:** Full keyboard alternative for manual entry when camera is unavailable or denied.
9. **Backend/API Bindings:** `GET /api/v1/oid4vp/sessions/{sessionId}`.
10. **States & Scenarios:** Camera permission denied displays friendly warning with instructions to allow permissions or use manual entry.

---

### 2.4 SCR-HLD-04: Presentation Consent (`/wallet/consent`)
1. **User Goal:** Review a verifier's presentation request, understand exactly what data will be transmitted, and grant or reject informed consent.
2. **Key Information Displayed:**
   - Verified legal identity of the Verifier (`clientId` / `verifierDid`)
   - Stated purpose of verification
   - Matching credentials in wallet
   - **MANDATORY DISCLOSURE:** *"This profile sends the complete signed credential. The current Data Integrity proof does not support claim-level cryptographic selective disclosure, so unselected claims cannot be hidden."*
   - Claim inventory list with requested badges
   - Session expiration countdown timer
3. **Primary & Secondary Actions:**
   - *Primary:* "Approve full credential" (Disabled until checkbox is checked).
   - *Secondary:* "Reject Request" (Cancels session and returns to wallet).
4. **Content Hierarchy:**
   - Warning banner: Verifier identity & stated purpose
   - Architectural honesty callout box (amber background)
   - Credential selection (if multiple match DCQL query)
   - Claim inventory list (showing all signed claims included)
   - Mandatory consent checkbox
   - Action button bar (Reject vs Approve)
5. **Component Inventory:** `SelectiveDisclosureSheet`, `TrustBadge`, `StatusChip`, `Button`, `AlertTriangle`.
6. **Form & Validation:** Checkbox *"I understand that approving shares this entire signed credential..."* must be checked to enable submission.
7. **Responsive Layout:** Centered 580px card layout on desktop; single-column scrollable sheet on mobile.
8. **Accessibility & Keyboard:** Checkbox is keyboard accessible; error states announced via `aria-live`.
9. **Backend/API Bindings:**
   - `GET /api/v1/oid4vp/sessions/{id}`
   - `POST /api/v1/oid4vp/evaluate`
   - `POST /api/v1/wallets/presentations/oid4vp`
   - `POST /api/v1/oid4vp/direct_post`
10. **States & Scenarios:**
    - *Success:* Transmits signed VP, displays green success checkmark, routes back to wallet.
    - *Network Error:* Detects transmission failure, displays "Retry Submission" button using cached cryptographic proof.

---

### 2.5 SCR-HLD-05: Activity History (`/wallet/activity`)
1. **User Goal:** Review past credential presentations, verifier accesses, and issuance events.
2. **Key Information Displayed:** Chronological audit timeline, Verifier Name, Credential Type, Timestamp, Consent Decision (`APPROVED`, `REJECTED`), Direct Post Status.
3. **Primary & Secondary Actions:**
   - *Primary:* "Filter by Date / Verifier".
   - *Secondary:* "Inspect Presentation Proof Digest".
4. **Content Hierarchy:** Header summary → Filter bar → Activity timeline list with date dividers.
5. **Component Inventory:** Timeline item card, `StatusChip`, `Button`, `EmptyState`.
6. **Form & Validation:** Date range filter validation.
7. **Responsive Layout:** Single vertical timeline column on mobile and desktop.
8. **Accessibility & Keyboard:** Focus navigates sequentially through timeline events.
9. **Backend/API Bindings:** `GET /api/v1/wallets/activity`.
10. **States & Scenarios:** Shows "No activity recorded yet" if brand new wallet.

---

### 2.6 SCR-HLD-06: Security & Guardian Settings (`/wallet/security`)
1. **User Goal:** Configure social recovery guardians, set quorum threshold (e.g., 2 of 3), and manage backup keys.
2. **Key Information Displayed:** Current Guardian Quorum Status (e.g., `Configured: 2 of 3`), list of designated guardian DIDs, recovery status.
3. **Primary & Secondary Actions:**
   - *Primary:* "Save Recovery Configuration" or "Add Guardian".
   - *Secondary:* "Remove Guardian", "Initiate Emergency Recovery Test".
4. **Content Hierarchy:** Quorum overview card → Guardian DID input slots (1, 2, 3) → Quorum threshold dropdown → Save changes button.
5. **Component Inventory:** `Input`, `Select`, `Button`, `StatusChip`, `GuardianQuorumTracker`.
6. **Form & Validation:** Requires exactly 3 valid DIDs and a threshold of 2 or 3. Validates DID format (`did:jwk` or `did:key`).
7. **Responsive Layout:** Stacked form fields with responsive inputs.
8. **Accessibility & Keyboard:** Standard form navigation with explicit label bindings.
9. **Backend/API Bindings:** `GET /api/v1/recovery/config`, `POST /api/v1/recovery/config`.
10. **States & Scenarios:** Successful configuration shows green confirmation badge; duplicate guardian DIDs trigger an inline validation error.

---

## 3. Issuer Portal Screens

### 3.1 SCR-ISS-01: Issuer Dashboard (`/issuer`)
1. **User Goal:** Monitor issuance throughput, active credential volumes, revocation list capacity, and recent issuance logs.
2. **Key Information Displayed:** Total Issued Credentials, Active Status Lists count, Bitstring Utilization percentage, Recent Issuance Events table.
3. **Primary & Secondary Actions:**
   - *Primary:* "Issue New Credential" (`/issuer/issue`).
   - *Secondary:* "Manage Status Lists" (`/issuer/revocations`), "Create Schema Template".
4. **Content Hierarchy:** 4 Metric Cards → Recent Issuances Data Table → Quick Action Panel.
5. **Component Inventory:** `ModuleCard`, `TableEnterprise`, `StatusChip`, `Button`.
6. **Form & Validation:** None.
7. **Responsive Layout:** 4-column metric grid on desktop, 2-column tablet, 1-column mobile.
8. **Accessibility & Keyboard:** Data table is scrollable with accessible focus headers.
9. **Backend/API Bindings:** `GET /api/v1/credentials/stats`, `GET /api/v1/credentials/recent`.
10. **States & Scenarios:** Real-time refresh button triggers smooth data re-fetch with loading indicator.

---

### 3.2 SCR-ISS-02: Credential Templates (`/issuer/templates`)
1. **User Goal:** Manage W3C VC 2.0 schema templates, define required and optional claim fields, and configure status list mappings.
2. **Key Information Displayed:** Template catalog cards (National ID, Higher Education Diploma, Employment Certificate, Clean Driving Record).
3. **Primary & Secondary Actions:**
   - *Primary:* "Use Template to Issue".
   - *Secondary:* "Edit Template Schema", "Clone Template", "Create New Template".
4. **Content Hierarchy:** Category tabs → Template grid → Schema preview modal.
5. **Component Inventory:** Template card, `Modal`, `Button`, `StatusChip`.
6. **Form & Validation:** JSON schema validator when creating new templates.
7. **Responsive Layout:** Responsive 3-column card grid.
8. **Accessibility & Keyboard:** Modal traps focus on schema preview.
9. **Backend/API Bindings:** `GET /api/v1/templates`, `POST /api/v1/templates`.
10. **States & Scenarios:** Pre-loaded with official EU and academic sample templates.

---

### 3.3 SCR-ISS-03: Issue Credential Console (`/issuer/issue`)
1. **User Goal:** Populate claim values for a subject DID, sign a W3C VC 2.0 with Ed25519, allocate a status list bit, and output an OID4VCI offer.
2. **Key Information Displayed:** Template selector, Subject DID input, dynamic claim inputs, expiration date picker, status list selector, QR offer display.
3. **Primary & Secondary Actions:**
   - *Primary:* "Cryptographically Sign & Issue Credential".
   - *Secondary:* "Copy OID4VCI Credential Offer URI", "Download QR Code PNG".
4. **Content Hierarchy:** Template dropdown → Subject DID & Expiry section → Dynamic claim fields section → Output preview & QR offer modal.
5. **Component Inventory:** `Input`, `Select`, `Button`, `QRCodeDisplay`, `StatusChip`.
6. **Form & Validation:** Subject DID must be valid format; required claims cannot be empty; expiration date must be in the future.
7. **Responsive Layout:** Two-column split on desktop (Form on left, live VC preview on right); stacked on mobile.
8. **Accessibility & Keyboard:** Step navigation supports `Tab` through all input fields; QR modal has accessible download button.
9. **Backend/API Bindings:** `POST /api/v1/credentials/issue`, `POST /api/v1/oid4vci/offers`.
10. **States & Scenarios:**
    - *Success:* Displays high-contrast QR code and green notification: "W3C VC 2.0 signed with Ed25519 and anchored to Bitstring Status List."

---

### 3.4 SCR-ISS-04: Revocation & Status List Registry (`/issuer/revocations`)
1. **User Goal:** Inspect W3C Bitstring Status Lists, locate credentials by ID or bit index, and execute cryptographic revocation.
2. **Key Information Displayed:** Bitstring Status List ID, Total Bits (e.g., 131,072 bits), Revoked Bits Count, Search by Credential ID, Revocation Confirmation dialog.
3. **Primary & Secondary Actions:**
   - *Primary:* "Revoke Credential" (sets status bit from 0 to 1).
   - *Secondary:* "Anchor Status List to Blockchain", "Export Bitstring Document".
4. **Content Hierarchy:** Status List selector → Capacity visual gauge → Search & Revocation input → Interactive Bit Matrix → Revocation audit log.
5. **Component Inventory:** `TableEnterprise`, `Modal`, `Input`, `Button`, `StatusChip`.
6. **Form & Validation:** Requires two-step confirmation modal with explicit typing of "REVOKE" to prevent accidental revocations.
7. **Responsive Layout:** Full-width institutional console with horizontal overflow containment.
8. **Accessibility & Keyboard:** Destructive action requires keyboard confirmation; screen reader warns: "This action is cryptographically irreversible on-chain."
9. **Backend/API Bindings:** `GET /api/v1/status-lists`, `POST /api/v1/status-lists/{id}/revoke`.
10. **States & Scenarios:** Upon revocation, bit index transitions from 0 to 1, MongoDB record is updated, and EVM anchoring transaction is queued.

---

## 4. Verifier Portal Screens

### 4.1 SCR-VRF-01: Verifier Dashboard (`/verifier`)
1. **User Goal:** Monitor relying party verification sessions, inspect pass/fail ratios, and detect AI anomaly spikes.
2. **Key Information Displayed:** Verification Pass Rate (%), Total Presentations Processed, AI Anomaly / Quarantine Count, Active OID4VP Sessions table.
3. **Primary & Secondary Actions:**
   - *Primary:* "Create New Verification Request" (`/verifier/request`).
   - *Secondary:* "Inspect Failed Verifications", "View Audit Log".
4. **Content Hierarchy:** Summary metric cards → Live verification feed → Quick action toolbar.
5. **Component Inventory:** `ModuleCard`, `TableEnterprise`, `StatusChip`, `Button`.
6. **Form & Validation:** None.
7. **Responsive Layout:** 4-column desktop grid, 1-column mobile.
8. **Accessibility & Keyboard:** Accessible data table with aria-labels on action buttons.
9. **Backend/API Bindings:** `GET /api/v1/oid4vp/stats`, `GET /api/v1/oid4vp/active-sessions`.
10. **States & Scenarios:** Auto-refreshes every 10 seconds with subtle pulse indicator.

---

### 4.2 SCR-VRF-02: Create DCQL Request (`/verifier/request`)
1. **User Goal:** Build a Digital Credentials Query Language (DCQL) request, generate an OID4VP session, and display a high-contrast QR code.
2. **Key Information Displayed:** Required Credential Type selector, Requested Claim checkboxes, Purpose description input, Generated QR Code, Live Session Status polling (`PENDING` → `PRESENTED` → `ACCEPTED`).
3. **Primary & Secondary Actions:**
   - *Primary:* "Generate Verification QR Code".
   - *Secondary:* "Copy Request URI", "Cancel Session".
4. **Content Hierarchy:** Dual-pane layout: Left pane for DCQL configuration form; Right pane for high-contrast QR terminal and real-time status monitor.
5. **Component Inventory:** `Input`, `Select`, `Button`, `QRCodeDisplay`, `StatusChip`.
6. **Form & Validation:** At least one claim and credential type must be selected; purpose description is required.
7. **Responsive Layout:** Side-by-side desktop; stacked vertically on mobile/tablet.
8. **Accessibility & Keyboard:** QR code includes alternative text and a "Copy Link" button for keyboard/screen reader users.
9. **Backend/API Bindings:** `POST /api/v1/oid4vp/sessions`, `GET /api/v1/oid4vp/sessions/{id}`.
10. **States & Scenarios:** When holder scans and submits consent, the screen automatically transitions to SCR-VRF-03 (Verification Matrix).

---

### 4.3 SCR-VRF-03: Verify Presentation Console (`/verifier/verify`)
1. **User Goal:** Execute or inspect the authoritative 9-point cryptographic verification pipeline on a received Verifiable Presentation.
2. **Key Information Displayed:**
   - Master Verification Outcome (`ACCEPTED`, `REJECTED`, `QUARANTINE`)
   - Complete 9-point checklist with status icons and execution latency
   - AI Fraud Risk Score (< 0.65 threshold)
   - Extracted Credential Claims
   - Fail-closed cryptographic evidence
3. **Primary & Secondary Actions:**
   - *Primary:* "Approve Admission / Access".
   - *Secondary:* "Flag for Forensic Review", "Export Verification Receipt PDF".
4. **Content Hierarchy:**
   - Master Outcome Banner (Top: Green / Red / Amber)
   - 9-Point Verification Checklist (Gate-by-gate breakdown)
   - Disclosed Claims Table
   - AI Fraud & Threat Telemetry Box
   - Cryptographic Digest & Raw Signature Accordion
5. **Component Inventory:** `NinePointVerificationMatrix`, `StatusChip`, `Button`, `AlertCircle`.
6. **Form & Validation:** None.
7. **Responsive Layout:** Responsive layout with expandable detail drawers.
8. **Accessibility & Keyboard:** Accordions operate via `Enter` / `Space`; status announcements via `aria-live`.
9. **Backend/API Bindings:** `POST /api/v1/presentations/verify`.
10. **States & Scenarios:**
    - *Fail-Closed Guarantee:* If any check fails (e.g., status check returns HTTP 500 or revocation bit is 1), the master outcome immediately locks to `REJECTED`.

---

### 4.4 SCR-VRF-04: Verification History (`/verifier/history`)
1. **User Goal:** Search and review past verification decisions for regulatory compliance and dispute resolution.
2. **Key Information Displayed:** Session ID, Credential Type, Holder DID (truncated), Outcome (`ACCEPTED` / `REJECTED`), Timestamp, Auditor ID.
3. **Primary & Secondary Actions:**
   - *Primary:* "Filter by Outcome / Date".
   - *Secondary:* "Inspect Verification Audit Trail".
4. **Content Hierarchy:** Search toolbar → Filter pills → Verification logs table → Detail flyout.
5. **Component Inventory:** `TableEnterprise`, `StatusChip`, `Input`, `Button`.
6. **Form & Validation:** Search input with instant filtering.
7. **Responsive Layout:** Table switches to vertical cards on mobile viewports.
8. **Accessibility & Keyboard:** Full keyboard table row navigation.
9. **Backend/API Bindings:** `GET /api/v1/verifications`.
10. **States & Scenarios:** Empty state if no verifications match active filters.

---

## 5. Guardian Recovery Screens

### 5.1 SCR-GRD-01: Guardian Dashboard (`/guardian`)
1. **User Goal:** Review assigned protected identities, active recovery requests, and cryptographic signing keys.
2. **Key Information Displayed:** Assigned Protectees count, Active Quorum Requests count, Signed Approvals history.
3. **Primary & Secondary Actions:**
   - *Primary:* "Review Pending Requests" (`/guardian/requests`).
   - *Secondary:* "Update Guardian Signing DID".
4. **Content Hierarchy:** Summary metric strip → Actionable alerts → Protected identity registry.
5. **Component Inventory:** `ModuleCard`, `TableEnterprise`, `Button`, `StatusChip`.
6. **Form & Validation:** None.
7. **Responsive Layout:** Standard institutional desktop / tablet layout.
8. **Accessibility & Keyboard:** Accessible alert banners with role="status".
9. **Backend/API Bindings:** `GET /api/v1/recovery/guardian/stats`.
10. **States & Scenarios:** If an active recovery request exists, a prominent amber notification banner appears at the top.

---

### 5.2 SCR-GRD-02: Recovery Requests Queue (`/guardian/requests`)
1. **User Goal:** Inspect incoming requests from lost wallets seeking guardian multi-sig authorization.
2. **Key Information Displayed:** Request ID, Recoveree DID, Ephemeral Target DID, Quorum Status (`1 of 3 Approved`), Time Remaining (e.g., `38h left`).
3. **Primary & Secondary Actions:**
   - *Primary:* "Review & Sign Approval" (`/guardian/approve/:id`).
   - *Secondary:* "Decline / Flag Suspicious Request".
4. **Content Hierarchy:** Filter tabs (`PENDING`, `APPROVED`, `EXPIRED`) → Requests queue table.
5. **Component Inventory:** `TableEnterprise`, `Button`, `StatusChip`, `GuardianQuorumTracker`.
6. **Form & Validation:** None.
7. **Responsive Layout:** Responsive table collapsing to cards on mobile.
8. **Accessibility & Keyboard:** Row action buttons clearly labeled with request ID for screen readers.
9. **Backend/API Bindings:** `GET /api/v1/recovery/guardian/requests`.
10. **States & Scenarios:** Displays "No active recovery requests" empty state when queue is clear.

---

### 5.3 SCR-GRD-03: Approve Recovery Console (`/guardian/approve/:id`)
1. **User Goal:** Verify the identity of the recoveree through off-band confirmation, review cryptographic proofs, and sign the recovery authorization.
2. **Key Information Displayed:** Recoveree Original DID, New Target DID, Security Warnings, Current Quorum Progress Bar, Cryptographic Signature preview.
3. **Primary & Secondary Actions:**
   - *Primary:* "Sign & Authorize Identity Recovery" (triggers cryptographic key signature).
   - *Secondary:* "Reject Request as Fraudulent".
4. **Content Hierarchy:**
   - Critical Identity Verification Notice
   - Quorum Progress Bar (e.g., 1 of 3 signed)
   - Protectee Details Card
   - Two-step confirmation checkbox
   - Action buttons (Reject vs Authorize)
5. **Component Inventory:** `Modal`, `Button`, `GuardianQuorumTracker`, `AlertTriangle`.
6. **Form & Validation:** Mandatory checkbox: *"I have verified the identity of the requester through an out-of-band secure channel."*
7. **Responsive Layout:** Centered 560px verification panel.
8. **Accessibility & Keyboard:** Focus lands on security warning; approval button requires explicit confirmation.
9. **Backend/API Bindings:** `POST /api/v1/recovery/guardian/approve/{id}`.
10. **States & Scenarios:**
    - *Success:* Signs proof with Guardian private key, increments quorum to 2 of 3, displays green execution banner.

---

## 6. System Administrator & Security Cockpit Screens

### 6.1 SCR-ADM-01: Admin Cockpit (`/admin`)
1. **User Goal:** Monitor overall platform health, microservice latency, API Gateway throughput, and database connectivity.
2. **Key Information Displayed:** Microservice Status (Identity, Recovery, Fraud, Gateway), Gateway Error Rates, System CPU/Memory, Active Users.
3. **Primary & Secondary Actions:**
   - *Primary:* "View Threat Matrix" (`/admin/fraud-monitor`).
   - *Secondary:* "Inspect Smart Contracts", "Export System Diagnostic Bundle".
4. **Content Hierarchy:** System Status Alert Strip → 4 Microservice Telemetry Cards → Gateway Traffic Chart → Infrastructure Event Log.
5. **Component Inventory:** `ModuleCard`, `TableEnterprise`, `StatusChip`, `Button`.
6. **Form & Validation:** None.
7. **Responsive Layout:** Grid layout with responsive column wrapping.
8. **Accessibility & Keyboard:** Screen reader updates for service degradation alerts.
9. **Backend/API Bindings:** `GET /api/v1/system/health`, `GET /api/v1/gateway/metrics`.
10. **States & Scenarios:** If a microservice drops offline, card pulses red with immediate error classification.

---

### 6.2 SCR-ADM-02: Smart Contracts & EVM Bridge (`/admin/contracts`)
1. **User Goal:** Manage Sepolia blockchain anchoring contracts, inspect on-chain root hashes, and monitor gas balances.
2. **Key Information Displayed:** Contract Addresses (`StatusListRegistry.sol`, `RecoveryQuorum.sol`), Sepolia Network ID, Latest Block Height, Gas Balance, Transaction Hash History.
3. **Primary & Secondary Actions:**
   - *Primary:* "Anchor Pending Root Hash to Sepolia".
   - *Secondary:* "View on Etherscan", "Top-up Gas Relayer".
4. **Content Hierarchy:** Blockchain Network Status Bar → Deployed Contracts Table → Recent Anchoring Transactions Table.
5. **Component Inventory:** `TableEnterprise`, `StatusChip`, `Button`, `ExternalLink`.
6. **Form & Validation:** Validates contract address formats (`0x...`).
7. **Responsive Layout:** High-density institutional layout.
8. **Accessibility & Keyboard:** Monospace addresses with 1-click clipboard triggers.
9. **Backend/API Bindings:** `GET /api/v1/blockchain/contracts`, `POST /api/v1/blockchain/anchor`.
10. **States & Scenarios:** Pending transactions display animated spinner until confirmed on-chain.

---

### 6.3 SCR-ADM-03: Audit Explorer (`/admin/audit`)
1. **User Goal:** Query immutable, tamper-evident audit logs and verify SHA-256 cryptographic hash-chain integrity.
2. **Key Information Displayed:** Event ID, Event Type, Actor DID, Resource Target, Timestamp, Previous Hash, Current Hash, Hash-Chain Verification Status (`CHAIN VALID` / `TAMPER DETECTED`).
3. **Primary & Secondary Actions:**
   - *Primary:* "Verify Entire Audit Chain Cryptography".
   - *Secondary:* "Filter by Event Type", "Export Audit Trail to JSON-LD".
4. **Content Hierarchy:** Cryptographic Integrity Banner (Top: Green shield if chain intact) → Search & Filter Toolbar → Audit Log Data Table → Forensic Payload Inspector.
5. **Component Inventory:** `TableEnterprise`, `StatusChip`, `Input`, `Button`.
6. **Form & Validation:** Event query filters.
7. **Responsive Layout:** Data table with horizontal scrolling protection.
8. **Accessibility & Keyboard:** Table row selection via keyboard to expand forensic payload.
9. **Backend/API Bindings:** `GET /api/v1/audit/logs`, `POST /api/v1/audit/verify-chain`.
10. **States & Scenarios:**
    - *Integrity Verified:* Displays green banner: "54,210 events verified. SHA-256 hash-chain intact."
    - *Tamper Detected:* Flashes bright red alert identifying the exact mismatched block index.

---

### 6.4 SCR-ADM-04: AI Fraud & Threat Cockpit (`/admin/fraud-monitor`)
1. **User Goal:** Monitor real-time anomaly scores generated by the Isolation Forest engine, adjust quarantine thresholds, and review high-risk presentation sessions.
2. **Key Information Displayed:** Current Anomaly Threshold (default `0.65`), Recent Anomaly Detections list, Threat Distribution chart, Feature Importance weights (Velocity, Geo-distance, Signature Latency).
3. **Primary & Secondary Actions:**
   - *Primary:* "Inspect Quarantined Presentation".
   - *Secondary:* "Manually Release Session", "Retrain Anomaly Weights".
4. **Content Hierarchy:** Real-time Threat Gauge → Active Quarantine Queue Table → Model Parameter Configuration Card.
5. **Component Inventory:** `ModuleCard`, `TableEnterprise`, `StatusChip`, `Button`, `RiskScorePanel`.
6. **Form & Validation:** Threshold slider between 0.00 and 1.00 with live numerical display.
7. **Responsive Layout:** 2-column desktop console (Queue on left, forensic telemetry on right).
8. **Accessibility & Keyboard:** Slider accessible via arrow keys; high risk items flagged with text badges.
9. **Backend/API Bindings:** `GET /api/v1/fraud/detections`, `POST /api/v1/fraud/quarantine/{id}/resolve`.
10. **States & Scenarios:** Quarantined sessions display deep forensic radar with exact feature anomaly scores.
