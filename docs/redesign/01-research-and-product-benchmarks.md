# Secure SSI Platform — Research and Product Benchmarks

**Status:** Repository-specific UX research, planning only.  
**Research date:** 19 October 2026.  
**Engineering authority:** The Revised Master Implementation Plan at reports/independent-review-2026-10-05/SECURE_SSI_PLATFORM_MASTER_IMPLEMENTATION_PLAN_REVISED.md. This UX package is subordinate to it and does not reorder G0–G16.  
**No application source, dependency, lockfile, API, or configuration was changed for this research package.**

## Executive decision

Use an original dark, high-contrast “Trust Network” visual identity, built on shadcn/ui open-code components with Radix behavior primitives and the repository’s existing Lucide icons. Keep the brand presentation distinctive and use a locally served SSI trust-network illustration. Use one system-font stack across all routes. Avoid external stock photography, invented service metrics, fictional accreditation, fake activity, and UI labels that imply conformance or operational status not returned by the system.

The plan targets responsive web on desktop, tablet, and mobile. The Revised Master Implementation Plan explicitly excludes a native mobile application and describes this as a custodial/server-mediated web prototype; a phone-sized responsive page must not be presented as a native or hardware-backed wallet.

## Repository evidence inspected

- React 18.3, TypeScript 5.7, Vite 6, React Router 6; frontend entry is apps/web/src/main.tsx and route source is apps/web/src/routes/AppRoutes.tsx.
- Current web dependencies include React, React Router, ethers, qrcode, and lucide-react. No shadcn/ui, Radix, Tailwind build package, component test runner, or chart library is listed in apps/web/package.json.
- Tailwind utility styles are loaded from the external CDN in apps/web/index.html. The application has three global CSS imports, apps/web/src/styles.css, apps/web/src/visual-refresh.css, and apps/web/src/design-system.css. They contain overlapping resets, typography, layout, and focus rules. The global token block is now in design-system.css; existing page-specific CSS and inline styles remain.
- The repository already contains apps/web/src/assets/ssi-trust-network.svg and apps/web/src/components/common/BrandMark.tsx. Reuse and refine these before adding images.
- Current route code defines 28 concrete path patterns plus a catch-all. The old design inventory says 22 screens and the historical UI report counts screenshot states; neither is the current route source.
- The Identity Service has four closed backend roles: admin, issuer, verifier, holder. The Revised Master Plan requires Holder, Issuer, Verifier, Guardian, and Admin. Guardian is not a backend Identity role in the current code; the guardian route group is currently guarded as HOLDER.
- The current login has four context links. Selecting a link supplies a profile query parameter; server-returned role and permissions are the authority and roleHomePath redirects to one of the four frontend role roots.
- The browser application has role-specific public, holder, issuer, verifier, recovery, and admin route groups, but not every route has a data source. In particular, wallet activity and verifier history explicitly show that their feeds are unavailable. Issuer template view reads issuer metadata rather than a template CRUD API.
- User-provided Git baseline at the start of this planning pass: main, HEAD 59e8933f6e47922ba5a82cb7c9d76632e7edefe1, 268 pre-existing status entries (224 modified/staged-status entries and 44 untracked entries; no claim that any are Codex-owned). These entries are preserved.
- No AGENTS.md was found at the repository root, web app, source, pages, docs, or immediate parent location.

## Official design-system research

| Source actually inspected | Findings that apply here | Boundary |
| --- | --- | --- |
| [shadcn/ui documentation](https://ui.shadcn.com/docs) | Components are distributed as editable project code rather than a closed package; the docs expose common patterns including fields, buttons, dialogs, tables, sidebars, and empty states. This makes a branded, incremental design-system layer practical. | Not installed in this repository. Its component set does not automatically fix application workflows or authorization. |
| [Radix Primitives introduction](https://www.radix-ui.com/primitives/docs/overview/introduction) | The project describes its primitives as unstyled, incrementally adoptable, and oriented around WAI-ARIA patterns, focus management, and keyboard navigation. Those behaviors matter for consent, confirmation, drawers, and menus. | Not installed. Do not introduce Radix as a second competing visual library alongside shadcn; use it only as the underlying behavior layer of the selected approach where generated components require it. |
| [Material 3 canonical layouts](https://m3.material.io/foundations/layout/canonical-examples/overview) and [typography roles](https://m3.material.io/styles/typography/applying-type) | The official material surfaced feed, list-detail, and supporting-pane layouts and semantic display/headline/title/label/body roles. Apply the list-detail pattern to credential and audit review and use semantic type tokens instead of arbitrary page-by-page font sizes. | The Material homepage returned a JavaScript-only shell during this inspection. Only the linked official reference pages/search extraction were readable. Material is not the selected component library. |
| [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/) | The Recommendation applies across desktop and mobile device classes and uses testable criteria. Design acceptance must include contrast, keyboard operability, focus visibility, reflow, target sizing, and accessible names. | A token table, lint result, or screenshot does not prove WCAG conformance. No conformance claim is made. |

## Digital-identity product research

| Source actually inspected | Concrete pattern used in the plan | Boundary |
| --- | --- | --- |
| [Microsoft Entra Verified ID documentation](https://learn.microsoft.com/en-us/entra/verified-id/) | The documentation deliberately routes IT admins, developers, partners, and end users into different setup, integration, and use journeys. The Secure SSI public entry cards should state the job context, then let the authenticated server role choose the actual workspace. | This is documentation, not an inspected authenticated product UI. Microsoft roles or service capabilities are not imported into this product. |
| [SpruceID government digital-wallet page](https://spruceid.com/solutions/digital-wallets) | The page explains the wallet as a single place for credentials and emphasizes user control and privacy in the sharing journey. Use a clear wallet overview and make the verifier, purpose, and exact disclosed material visible before consent. | This is a product/marketing page. The repository currently transmits a complete signed credential in the supported presentation profile; do not claim cryptographic selective disclosure from the web page or UI. |
| [Dock credential-platform page](https://www.dock.io/vc-ads-landing-page) | The page makes two distinct jobs legible: issuer credential creation/delivery and verifier request/QR verification. This supports separated Issuer and Verifier workspaces and clear state transitions. | The page is marketing material with product mockups, not an operational interface audit. Dock’s features are not evidence of Secure SSI functionality. |
| User-provided CyberSafe Behance screenshot | The visible composition is a dark blue, high-contrast security hero with a short proposition and a compact interface illustration. Adapt the composition only: use Secure SSI’s own trust graph, credential card, and verification flow. | Only the user’s screenshot was inspected; the Behance project was not opened as a live product. Do not copy the artwork, logo, copy, or brand. |

## Technical standards used as UX constraints

- [W3C Verifiable Credentials Data Model 2.0](https://www.w3.org/TR/vc-data-model-2.0/) is the project’s structural standard. The UI must separate credential contents, proof/verification outcome, issuer trust, and status rather than reducing them to one “valid” badge.
- [OpenID4VCI 1.0 Final](https://openid.net/specs/openid-4-verifiable-credential-issuance-1_0-final.html) constrains the issue/offer flow. The interface must display actual offer/session states returned by the service and must not call an offer a stored credential.
- [OpenID4VP 1.0 Final](https://openid.net/specs/openid-4-verifiable-presentations-1_0-final.html) constrains the request, holder-consent, and response flow. Keep request, consent, creation, direct-post, and verifier result states distinct.
- These standards are protocol references, not a visual endorsement or a claim that the application has independent conformance certification.

## Selected component foundation

**Choose shadcn/ui as the single visual component foundation, using Radix-backed behavior only for primitives that need complex accessible interaction.** It fits the existing React/TypeScript/Vite application and lets the team own the source and brand styles. Reuse lucide-react instead of introducing a second icon set.

Adopt or adapt only components needed by actual screens: Button, Field/Label/Input, Select, Checkbox, Radio Group, Card, Badge, Alert, Dialog/Alert Dialog, Sheet/Drawer, Tabs, Table, Breadcrumb, Skeleton, and Tooltip. Do not add chart components until an API provides a real metric to chart.

**Dependency and build caveat:** the app has no local Tailwind toolchain or Radix/shadcn components today; the CDN script in index.html is the current utility source. Before adding components, implementation must confirm a React 18-compatible shadcn/Radix generation path, replace CDN dependence with a pinned local CSS build, and update package.json plus the lockfile in a dedicated, reviewable step. The current planning phase makes none of those changes. Do not run an unpinned “latest” install. Existing workflows must be visually and functionally smoke-tested after the build migration.

## Design direction and content rules

- Use deep ink backgrounds, layered blue-gray surfaces, bright cobalt primary actions, and a restrained mint trust accent. Keep operational dashboards calm and legible; use the dramatic gradient and trust-network illustration mainly in public and authentication surfaces.
- Use a local abstract trust graph and credential/QR compositions rather than unrelated stock photos or remote images. Keep data pages free of text-obscuring artwork.
- Use one platform-native sans-serif stack on every route and one mono stack only for DIDs, hashes, protocol codes, and JSON.
- Maintain the prototype/environment indicator and explicit offline/unknown status. “Connected”, “trusted”, “verified”, “issued”, and “anchored” must be tied to returned evidence and scoped to exactly what that evidence proves.
- Never display invented organization-wide metrics, template editing, completed verification history, trained-AI claims, crypto selective-disclosure claims, certification, or deployed-contract claims.
- Do not present entry-point selection as role selection or access grant. The session response from Identity Service determines the allowed route.
- The five-role Master Plan and eight requested permission profiles are mapped in document 02. Missing profiles remain product/authentication work, not decorative tabs.

## Existing evidence and plan drift

The current route code supersedes older route counts in docs/design/07-screen-inventory-and-flows.md and the historical blanket-pass statements in reports/REAL_UX_UI_COMPLETION_GATE.md; that report itself warns it is not a valid completion gate. Existing docs/design/visual-research.md and docs/design/visual-design-system.md are useful prior work but are not a substitute for route/API checks against current source. Current design tasks belong under Master Plan G12 and must not create a false G11 Golden Path pass.

## Sources not fully inspected

- Material Design’s top-level site required JavaScript and yielded no page body. The cited official canonical-layout and typography references were inspected separately.
- SpruceID and Dock pages were inspected as public product pages; no authenticated administration UI or wallet app was inspected.
- The user’s Behance reference was a screenshot only.
- No native mobile application or academic thesis artifact was inspected in this repository pass; the Master Plan defines native mobile as a non-goal.
