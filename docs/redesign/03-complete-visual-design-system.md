# Secure SSI Platform — Complete Visual Design System

**Status:** Product-specific design specification; proposed values, not implemented or accessibility-certified.  
**Primary inspiration:** User-provided CyberSafe screenshot composition, adapted into original SSI network artwork.  
**Component foundation:** shadcn/ui open-code components with Radix behavior primitives, subject to the build/dependency gate in document 01.

## 1. Brand and visual language

**Direction name: Trust Network.** Secure SSI should feel like a modern identity infrastructure product: credible, calm, precise, and privacy-aware. Use a deep ink canvas and layered navy work surfaces, a clear cobalt action color, and a restrained mint trust signal. Use a compact local abstract network/credential illustration on public pages. Operational pages prioritize records, task state, and consent clarity over atmosphere.

No competitor logos, copied Behance artwork, unrelated stock photos, fabricated seals, national/eID logos, eIDAS badges, “military-grade” language, or decorative network lines behind dense data.

## 2. Color tokens

| Token | HEX | Intended use |
| --- | --- | --- |
| canvas | #070B14 | Overall page background |
| canvas-raised | #0A1220 | Main content backdrop and dark hero base |
| surface | #101B2C | Sidebar, form cards, primary panels |
| surface-raised | #16243A | Nested cards, selected rows, dialog body |
| surface-overlay | #1C2D46 | Hover/selected control surface and menu |
| input | #091321 | Form fields and code panels |
| border | #283A52 | Card and section edges |
| border-strong | #3C5574 | Input, selected, and higher emphasis separator |
| text-primary | #F5F8FF | Headings, primary value, action labels |
| text-secondary | #C0CBDC | Body copy, table values, field labels |
| text-muted | #93A4BC | Helper text and metadata |
| text-disabled | #71829A | Disabled labels only; pair with disabled control pattern |
| brand-primary | #346CF4 | Main button, active navigation marker |
| brand-hover | #2758D2 | Hover and pressed primary action |
| brand-soft | #79A1FF | Links, icons, and non-button accent text |
| trust-accent | #48D6C2 | Trust/consent emphasis, small decorative accents |
| focus | #67E8F9 | Keyboard focus outline |
| success | #4BD49B | Confirmed success only |
| warning | #F6C35B | Pending, caution, or partial state |
| danger | #FF727F | Failure, reject, destructive action |
| info | #6CB6FF | Neutral informational state |

Use colors semantically, not as a role color palette. Every status includes text or an icon as well as color. A blue “trusted” badge may be shown only when the API returns the corresponding trust record/state.

### Contrast calculations for specified foreground/background pairs

Using the WCAG relative-luminance formula, the proposed pairs are: text-primary on canvas, 18.51:1; text-secondary on surface, 10.55:1; text-muted on surface, 6.81:1; white primary-action text on brand-primary, 4.57:1; trust-accent on surface, 9.61:1; warning on surface, 10.60:1; danger on surface, 6.55:1; info on surface, 8.04:1; focus on canvas, 13.58:1.

These arithmetic pairs do not prove the rendered application meets WCAG 2.2. Recalculate actual composited/hover/disabled states, borders, non-text controls, and text over any gradient/image during implementation.

## 3. Typography

Use one sans stack across all web routes: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI Variable, Segoe UI, sans-serif. This renders platform-native fonts and avoids a runtime web-font dependency. Use a single technical mono stack for DIDs, hashes, protocol identifiers, and raw JSON: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace.

| Role | Desktop/mobile target | Weight and line height |
| --- | --- | --- |
| Public hero display | 60/64 px desktop; clamp to 38/44 px on phones | 650–700, 1.04–1.12 |
| Page H1 | 36/44 px desktop; 30/36 px mobile | 650–700, 1.15 |
| Section H2 | 24/32 px desktop; 21/28 px mobile | 600–650, 1.30 |
| Card H3 | 18/26 px | 600 |
| Body | 16/24 px | 400 |
| Supporting body | 14/21 px | 400 |
| Field label / button | 14/20 px | 550–650 |
| Table header | 12/16 px, uppercase only for short metadata headings | 650 |
| Metadata / caption | 12/18 px | 450–500 |
| Technical value | 13/20 px | 450, mono; wrap long values |

Use tabular numerals for counts and timestamps. Set a consistent heading scale and avoid per-page inline font-size overrides. Do not use a display font for dense tables.

## 4. Layout, spacing, and responsive rules

- Spacing scale: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80 px.
- Maximum public/workspace content width: 1360 px. Reading text width: 70–76 characters.
- Desktop page gutter: 32 px; tablet: 24 px; mobile: 16 px.
- Institutional sidebar: 256 px expanded, fixed within the app viewport, with independent content scroll only where needed. At widths below 1024 px, use a focus-managed Sheet/drawer; close on Escape, outside action, route change, and explicit close.
- Shared top bar: 68 px desktop, 60 px compact/mobile; brand always remains visible. Account controls collapse into a menu without hiding sign-out.
- Holder navigation: desktop top navigation; mobile bottom navigation with safe-area inset and a visible active label. Reserve page padding so the dock never covers actions.
- Breakpoints: 480 px small phones; 640 px wide phone; 768 px tablet portrait; 1024 px desktop/sidebar threshold; 1280 px wide dashboard.
- Cards: 16 px radius, 20–24 px desktop padding, 16 px mobile padding. Controls: 10 px radius. Pill radius reserved for concise status badges.
- Grid: public entry cards 4→2→1; operational cards 2→1; no fixed-width child that forces horizontal page scrolling.
- Tables: preserve a table on wide screens; on mobile use a deliberate labeled row-card/list representation or a horizontally scrollable table with an announced scroll area. Never clip DID/address text without a reveal/copy path.
- Safe areas: use viewport-fit=cover, env(safe-area-inset-*) for fixed bottom navigation and dialogs.
- Only one dark theme is proposed for this phase. Do not expose an incomplete theme toggle. Revisit a light theme only after product/user testing and define a complete token set before adding it.

## 5. Components and interaction rules

| Component | Standard treatment |
| --- | --- |
| Primary button | 44–48 px minimum height; cobalt fill, white label, 14/20 semibold; one primary action per task area; hover/pressed/disabled/busy states; preserve action label while busy. |
| Secondary button | Dark surface with clear border and text; no competing saturated fill. |
| Destructive action | Danger label plus explicit confirmation dialog naming the exact credential/session/request and irreversible effect. No destructive color-only cue. |
| Icon button | 44×44 px target, accessible name, tooltip only as supplementary information. |
| Input | 48 px target height, label outside field, neutral border; focus uses 3 px cyan ring; validation text is persistent and linked with aria-describedby. |
| Select/check/radio | Native semantics or accessible Radix primitives; never rely on hover/mouse-only role selection. |
| Card | One clear title, one purpose, optional status and one next action; avoid nested cards used only as decoration. |
| Table/list | Consistent column alignment, visible heading, row action at end, no overflow, zero-state distinct from load/error. |
| Status badge | Text + optional icon + semantic foreground/background; unknown/offline is neutral or warning, never green. |
| Breadcrumb | Show workspace and current section on deep pages; current item is text/current-page, not a dead link. |
| Dialog/sheet | Focus enters and returns, Escape closes when safe, title/description announced, mobile sheet height and scroll controlled. |
| Alert/toast | Important errors persist in context; success feedback follows actual server response; no toast that hides a backend error. |
| Empty state | Say which data is absent and why known; primary action only if the backend supports the next step. |
| Loading state | Skeleton or concise live status; aria-busy on the affected region; never show placeholder metrics as real values. |

## 6. Illustration, logo, and background

- Reuse the existing BrandMark shield/node symbol and apps/web/src/assets/ssi-trust-network.svg. Confirm SVG source and license from repository history/docs before editing or extending it.
- Public hero: dark gradient plus local SVG trust links, issuer node, credential card and verifier path; keep the hero text in a separate high-contrast column. Use the visual idea of a real network/credential flow, not a face or unrelated phone stock image.
- Authentication: same illustration/crop as home, lower contrast than the sign-in form, no security claims embedded in artwork.
- Workspaces: flat dark canvas, low-opacity trust-network corner motif at most; do not set photos behind tables, consent claims, QR codes, audit events, or forms.
- Credential cards: use data returned from issuer/credential type and status, with a restrained document icon; do not invent issuer seals.
- QR codes are functional data, not decorative imagery. Provide their request/offer purpose in text and an accessible copy/open path.
- Avoid remote font/image dependencies; provide alt text for meaningful artwork and aria-hidden for decoration.

## 7. Motion and accessibility

Use 120–180 ms for focus/hover and small route-entry feedback. No animated scanning result or fabricated activity. Respect prefers-reduced-motion: reduce. Do not put essential status behind animation.

Target WCAG 2.2 AA review with keyboard-only flows, visible/not-obscured focus, correct heading/name/description relationships, 200% text zoom, 320 px reflow, status announcements, contrast, touch target review, and screen-reader testing for dialog/drawer and tables. Acceptance is based on actual testing, not this specification.
