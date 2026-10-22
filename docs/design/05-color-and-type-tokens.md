# Color & Typography Token Specification
**Document ID:** `DOC-DES-05-TOKENS`  
**Version:** 2.0  
**Date:** October 2026  
**Status:** Approved Token Specification  

---

## 1. Color Token Matrix & Contrast Verification

Every color token is systematically calibrated against the baseline surface (`--bg-surface: #111827`) and app canvas (`--bg-app: #0b0f19`) to ensure strict compliance with **WCAG 2.2 Level AA (>= 4.5:1 for normal text, >= 3.0:1 for large text/graphical elements)** and **Level AAA (>= 7.0:1)**.

### 1.1 Structural & Surface Tokens

| Token CSS Variable | Hex Value | Usage Purpose | Contrast vs #0b0f19 | WCAG Rating |
| :--- | :--- | :--- | :--- | :--- |
| `--bg-app` | `#0b0f19` | Master viewport foundation | Baseline (1.0:1) | N/A |
| `--bg-surface` | `#111827` | Primary card, table, panel body | 1.15:1 (Surface boundary) | N/A |
| `--bg-surface-elevated`| `#161f33` | Modals, drawers, dropdown menus | 1.35:1 (Elevated boundary) | N/A |
| `--bg-subtle` | `#1e293b` | Inactive table headers, pill backgrounds | 1.72:1 (Subtle boundary) | N/A |
| `--bg-input` | `#070a12` | Form input fields, terminal code blocks | 1.05:1 (Recessed boundary) | N/A |

### 1.2 Typography & Text Tokens

| Token CSS Variable | Hex Value | Role / Application | Contrast vs #111827 | WCAG Compliance |
| :--- | :--- | :--- | :--- | :--- |
| `--text-main` | `#f8fafc` | Primary headings, prominent labels, card titles | **15.4:1** | **AAA Pass** |
| `--text-secondary` | `#cbd5e1` | Body copy, table cell content, input text | **10.2:1** | **AAA Pass** |
| `--text-muted` | `#94a3b8` | Helper text, secondary timestamps, inactive icons | **5.4:1** | **AA Pass** |
| `--text-tertiary` | `#64748b` | Disabled labels, section category headers (uppercase)| **3.2:1** | **AA Large Pass** |
| `--text-mono-accent` | `#38bdf8` | DIDs, cryptographic hashes, session IDs | **8.1:1** | **AAA Pass** |

### 1.3 Border & Focus Tokens

| Token CSS Variable | Hex Value | Role / Application | Visual Ratio / Offset |
| :--- | :--- | :--- | :--- |
| `--border-default` | `#1f2937` | Standard card, divider, and panel outlines | Visible separator against `#0b0f19` |
| `--border-subtle` | `#2d3748` | Nested borders, table row dividers | Subtle internal delimiter |
| `--border-accent` | `#2563eb` | Active input border, selected card outline | High-visibility selection state |
| `--focus-ring` | `#61dfd0` | Universal keyboard focus indicator (Teal-300) | 3px outline, 3px offset; distinct from warning and expiry amber |

### 1.4 Semantic & Cryptographic Status Tokens

| Status Name | Background Token | Border Token | Text / Icon Token | Real Cryptographic Meaning |
| :--- | :--- | :--- | :--- | :--- |
| **VALID / VERIFIED** | `rgba(22, 163, 74, 0.15)` | `rgba(22, 163, 74, 0.45)` | `#4ade80` (Green-400) | Cryptographic signature valid, status bit active, issuer trusted. |
| **REVOKED** | `rgba(220, 38, 38, 0.15)` | `rgba(220, 38, 38, 0.45)` | `#f87171` (Red-400) | Bitstring status list indicates revocation bit is set to 1. |
| **EXPIRED** | `rgba(217, 119, 6, 0.15)` | `rgba(217, 119, 6, 0.45)` | `#fbbf24` (Amber-400) | Current system time exceeds credential `expirationDate`. |
| **QUARANTINE / ANOMALY**| `rgba(234, 88, 12, 0.15)` | `rgba(234, 88, 12, 0.45)` | `#fb923c` (Orange-400) | AI Isolation Forest anomaly score >= 0.65. Requires manual audit. |
| **PENDING / IN_PROGRESS**| `rgba(37, 99, 235, 0.15)` | `rgba(37, 99, 235, 0.45)` | `#60a5fa` (Blue-400) | OID4VP presentation session active, awaiting holder QR scan. |
| **UNAVAILABLE / FAIL-CLOSED**| `rgba(100, 116, 139, 0.15)` | `rgba(100, 116, 139, 0.45)` | `#cbd5e1` (Slate-300) | Network failure or unresolvable status list. Verification failed. |

---

## 2. Typography Token Specification

### 2.1 Font Families
- **Interface Font (`--font-sans`):** `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`
- **Monospace Font (`--font-mono`):** `'JetBrains Mono', 'Fira Code', monospace`

### 2.2 Typographic Hierarchy Scale

| Role / Token | Size | Line Height | Weight | Letter Spacing | Target Usage |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `display-1` | `32px` (`2.0rem`) | `1.2` (`38px`) | `800` (ExtraBold) | `-0.025em` | Landing hero headline, primary portal banners |
| `title-page` | `24px` (`1.5rem`) | `1.25` (`30px`)| `700` (Bold) | `-0.02em` | Screen titles (`h1`), modal header titles |
| `title-section`| `18px` (`1.125rem`)| `1.3` (`24px`) | `600` (SemiBold) | `-0.01em` | Panel titles (`h2`), card group headings |
| `title-card` | `15px` (`0.938rem`)| `1.4` (`21px`) | `600` (SemiBold) | `0em` | Credential card titles, table column headers |
| `body-normal` | `14px` (`0.875rem`)| `1.5` (`21px`) | `400` / `500` | `0em` | Standard interface text, descriptions, table cells |
| `body-compact`| `13px` (`0.813rem`)| `1.45` (`19px`)| `400` / `500` | `0em` | Institutional table contents, secondary meta |
| `label-strong`| `12px` (`0.75rem`) | `1.3` (`16px`) | `600` (SemiBold) | `0.02em` | Form labels, badge text, toggle indicators |
| `caption-meta`| `11px` (`0.688rem`)| `1.3` (`14px`) | `500` (Medium) | `0.04em` | Category tags, sub-timestamps, breadcrumbs |
| `code-mono` | `12px` (`0.75rem`) | `1.4` (`17px`) | `500` (Medium) | `0.01em` | DIDs, session IDs, base64 hashes, DCQL queries |

---

## 3. Cryptographic String Handling & Overflow Rules

DIDs (`did:jwk:eyJhbG...`), transaction hashes (`0x8f93b...`), and raw cryptographic signatures exceed normal line lengths and require specific truncation and copying mechanics:

```css
/* Standard Truncation for Cryptographic Strings */
.crypto-truncate {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-mono-accent);
  max-width: 280px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: inline-block;
  vertical-align: middle;
}

/* Full View in Code Inspection Panels */
.crypto-full-wrap {
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.5;
  color: #93c5fd;
  word-break: break-all;
  overflow-wrap: anywhere;
  background-color: var(--bg-input);
  padding: 10px 12px;
  border-radius: 6px;
  border: 1px solid var(--border-default);
}
```

---

## 4. Internationalization (i18n) & Text Expansion Accommodations

The platform supports **Turkish (TR)** and **English (EN)** content strings:
- **Character Set Support:** Full UTF-8 support including Turkish specific glyphs (`ğ, Ğ, ı, İ, ö, Ö, ş, Ş, ü, Ü, ç, Ç`).
- **Text Expansion Ratio:** Turkish interface labels average 20% to 35% longer than English equivalents.
  - *Example:* "Verify" (6 chars) → "Doğrula" (7 chars); "Revocation Registry" (19 chars) → "İptal Durumu Sicili" (20 chars); "Consent Required" (16 chars) → "Kullanıcı Onayı Gereklidir" (26 chars).
  - *Design Rule:* Fixed-width buttons are prohibited. All interactive buttons, badges, and card titles use fluid flexbox layouts with `min-width` and automatic wrapping to prevent clipping.
