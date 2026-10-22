# Component Library Specification
**Document ID:** `DOC-DES-06-COMPONENTS`  
**Version:** 2.0  
**Date:** October 2026  
**Status:** Approved Component Specifications  

---

## 1. Interactive Button Components (`Button`)

### 1.1 Specification & Variants
Buttons trigger actions and state transitions. They must provide immediate optical feedback and prevent duplicate submissions.

| Variant | CSS Class | Visual Styling | Primary Use Case |
| :--- | :--- | :--- | :--- |
| **Primary** | `.btn-primary` | Solid `#2563eb`, hover `#1d4ed8`, active `#1e40af`, white text | Primary form submissions, "Approve", "Issue Credential" |
| **Secondary** | `.btn-secondary`| Dark slate `#1e293b`, border `#2d3748`, text `#cbd5e1` | Secondary actions, "Cancel", "Back", "Export" |
| **Danger** | `.btn-danger` | Crimson `rgba(220, 38, 38, 0.15)`, border `rgba(220, 38, 38, 0.4)`, text `#f87171` | "Revoke Credential", "Reject Presentation", "Delete" |
| **Ghost / Icon**| `.btn-ghost` | Transparent, hover `#1e293b`, text `#94a3b8` | Copy buttons, table action triggers, toolbar toggles |

### 1.2 States & Accessibility
- **Hover:** Smooth background transition (150ms ease).
- **Focus (`:focus-visible`):** 3px solid `#61dfd0` outline, 3px offset.
- **Disabled:** `opacity: 0.5; cursor: not-allowed; pointer-events: none;`.
- **Loading:** Displays a spinning Lucide `RefreshCw` icon (`.spin`) with disabled interaction and `aria-busy="true"`.
- **Minimum Target Size:** Mobile 44x44px; Desktop 36px height with minimum 16px horizontal padding.

---

## 2. Form Controls & Validation (`Input`, `Select`, `Textarea`, `Checkbox`)

### 2.1 Text Inputs & Textareas
- **Surface:** Sunken `#070a12`, border `1px solid #1f2937`, radius `8px`.
- **Typographic Scale:** 13px font size, `#f8fafc` text color, `#64748b` placeholder.
- **Focus State:** Border transitions to `#2563eb` with 3px amber `:focus-visible` indicator.
- **Error State:** Border transitions to `#ef4444`, accompanied by an inline icon `AlertCircle` and descriptive error text below the input with `role="alert"`.

### 2.2 Form Label & Helper Pattern
```tsx
<div className="form-group">
  <label htmlFor="subjectDid" className="form-label">
    Subject DID <span className="required-star" aria-hidden="true">*</span>
    <span className="sr-only">(Zorunlu alan)</span>
  </label>
  <input
    id="subjectDid"
    aria-describedby="subjectDid-helper subjectDid-error"
    aria-invalid={hasError}
    className={`form-input ${hasError ? "input-error" : ""}`}
  />
  <p id="subjectDid-helper" className="form-helper">
    Enter the target holder's decentralized identifier (did:jwk or did:key)
  </p>
  {hasError && (
    <p id="subjectDid-error" role="alert" className="form-error">
      <AlertCircle size={14} /> Subject DID format is invalid.
    </p>
  )}
</div>
```

---

## 3. Data Tables & Filters (`TableEnterprise`)

### 3.1 Layout & Visual Structure
- **Container:** Rounded panel with horizontal overflow protection.
- **Header (`th`):** Elevated dark background (`#161f33`), `#94a3b8` uppercase 11px label, 1px solid `#1f2937` bottom border.
- **Body Rows (`td`):** 13px text, `#cbd5e1`, 12px vertical padding. Alternating rows with subtle hover highlight (`rgba(255,255,255,0.02)`).
- **Responsive Handling:** When viewport `< 768px`, data tables collapse into structured vertical cards to prevent horizontal clipping.

---

## 4. Status Badges & Trust Indicators (`StatusChip`, `TrustBadge`)

### 4.1 Canonical Status Chip (`StatusChip`)
Every status chip renders both an icon, text label, and color scheme:

```tsx
<StatusChip 
  status="ACTIVE" | "REVOKED" | "EXPIRED" | "QUARANTINE" | "PENDING" | "UNKNOWN" 
/>
```
- **Active:** Green pill, `ShieldCheck` icon, text "Active / Doğrulandı"
- **Revoked:** Crimson pill, `XCircle` icon, text "Revoked / İptal Edildi"
- **Expired:** Amber pill, `Clock` icon, text "Expired / Süresi Doldu"
- **Quarantine:** Orange pill, `AlertTriangle` icon, text "Quarantine / Anomali"
- **Pending:** Blue pill, `RefreshCw` icon, text "Pending / Beklemede"

### 4.2 Issuer Trust Seal (`TrustBadge`)
Renders the verified status of an issuing authority against the platform Trust Registry.
- Displays the issuer's registered legal identity, trust tier (`GOVERNMENT`, `ACADEMIC`, `FINANCIAL`), and cryptographic public key fingerprint.

---

## 5. Domain-Specific Identity Components

### 5.1 Credential Card (`CredentialCard`)
Physical-digital credit card metaphor:
- Dimensions: Responsive width (max 480px), aspect ratio ~ 1.58:1.
- Visuals: Dark glassmorphism gradient (`linear-gradient(135deg, #1e293b 0%, #0f172a 100%)`), 1px solid border, subtle status-colored left border strip.
- Header: Issuer logo badge, credential title (`National Student ID`), status chip.
- Center: Core identity claims (Subject Name, ID Number, Issue Date, Expiry).
- Footer: Monospace credential ID (with copy trigger) and QR presentation trigger.

### 5.2 Nine-Point Verification Matrix (`NinePointVerificationMatrix`)
The authoritative verifier audit component:
- Renders a 9-row live checklist corresponding to each cryptographic verification gate.
- Each row contains:
  1. Check Name (e.g., `W3C Schema Validation`, `Ed25519 Cryptographic Signature`, `Bitstring Status List Check`, `Holder Binding Proof`, `AI Fraud Anomaly Score`).
  2. Status Icon & Label (`PASS`, `FAIL`, `QUARANTINE`).
  3. Execution Latency (e.g., `12ms`).
  4. Expandable diagnostic details showing raw public keys, status bit indexes, and nonce match evidence.
- Top banner: Master outcome badge (`PRESENTATION ACCEPTED`, `PRESENTATION REJECTED`, `SESSION QUARANTINED`).

### 5.3 Consent & Full-Disclosure Sheet (`SelectiveDisclosureSheet`)
- Rendered as an accessible modal with `role="dialog"` and `aria-modal="true"`.
- Features a prominent amber notice box:
  > *"This profile sends the complete signed credential. The current Data Integrity proof does not support claim-level cryptographic selective disclosure, so unselected claims cannot be hidden."*
- Full inventory of all signed claims in the credential, marking which ones match the verifier's requested DCQL query.
- Mandatory confirmation checkbox: *"I understand that approving shares this entire signed credential, including every claim listed above."*
- Two explicit action buttons: "Cancel" (neutral) and "Approve full credential" (primary blue, enabled only after checkbox check).

### 5.4 Guardian Quorum Tracker (`GuardianQuorumTracker`)
- Used in Social Recovery setup and approval flows.
- Visual progress bar showing quorum completion (e.g., `2 of 3 Guardians Approved`).
- Detailed card for each configured guardian showing DID, approval timestamp, and cryptographic signature digest.

---

## 6. Feedback & Notification Components (`Toast`, `Modal`, `EmptyState`)

### 6.1 Modal Dialog (`Modal`)
- **Structure:** Overlay backdrop (`rgba(0,0,0,0.75)` with `backdrop-filter: blur(4px)`), centered content box (`--bg-surface-elevated: #161f33`), sticky header with title and close `X` button, scrollable body, sticky action footer.
- **Accessibility:** Traps focus within modal, closes on `Escape` key, restores focus to triggering element upon close.

### 6.2 Empty State (`EmptyState`)
- Displayed when credential lists, audit logs, or requests are empty.
- Contains a muted vector icon, clear title (e.g., "No credentials in wallet yet"), helpful explanation, and a primary call-to-action button (e.g., "Scan Issuance Offer").

### 6.3 Loading Skeletons
- Pulsing dark placeholders (`@keyframes pulse`) for card and table loading states, preventing layout shifts (CLS) during API fetches.
