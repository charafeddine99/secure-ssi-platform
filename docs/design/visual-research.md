# Visual research — Secure SSI Platform

**Inspected:** 2026-10-18  
**Purpose:** inform visual hierarchy and interaction patterns only. These products are not technical or conformance references for this prototype.

## Sources inspected

| Source | What was available to inspect | Useful pattern | Limits |
|---|---|---|---|
| [SpruceID](https://spruceid.com/) | Public landing page and its top-level information architecture | Its public page groups identity infrastructure, modernization, and trust/risk; the main message and action are concise. This supports organizing the public experience around clear areas of work. | This was a public marketing page, not an authenticated wallet or credential workflow. No product behavior is inferred from it. |
| [Trinsic](https://www.trinsic.id/) | Public landing page, including an illustrative identity-choice flow | The example makes the verification action and available identity-provider choices explicit. Use clear choice labels and an intelligible next step; do not imply that this prototype supports those providers. | Marketing content and illustrative provider choices are not evidence that this repository integrates them. No logged-in product interface was inspected. |
| [Microsoft Entra Verified ID documentation](https://learn.microsoft.com/en-us/entra/verified-id/) | Documentation landing page and its audience/scenario navigation | Content is grouped for admins, developers, partners, and end users, with distinct setup, tutorial, architecture, and usage paths. Role-aware navigation is useful for a multi-role product. | Documentation is not the Verified ID product UI. Microsoft’s architecture and visual identity are not adopted. |
| [Dock](https://www.dock.io/) | The requested public homepage did not return extractable page content in this inspection. | No product pattern was taken from it. | Unavailable to inspect in this run; no claims are made about its current interface. |
| [Material Design 3](https://m3.material.io/) | The landing page returned no usable design-system content to this inspection. | No detailed Material 3 rule is claimed or copied. | The source could not be sufficiently inspected in this run. |
| [Radix Primitives](https://www.radix-ui.com/primitives) | Public component overview and accessibility descriptions | The docs describe unstyled React primitives and call out keyboard navigation, screen-reader semantics, focus handling, and collision-aware overlays. This supports treating focus and predictable interaction as part of the design system. | This project does not use Radix. No new component package was added. |
| [WCAG 2.2](https://www.w3.org/TR/WCAG22/) | W3C Recommendation | WCAG 2.2 is device-independent and defines testable success criteria. The project can use it as a target, but colors or a successful build alone cannot establish conformance. | This work is not a full WCAG conformance audit. |
| [W3C WAI: Use a Consistent Visual Design](https://www.w3.org/WAI/WCAG2/supplemental/patterns/o1p03-consistent-design/) | Cognitive accessibility design pattern | Repeated headings, controls, focus states, and navigation should look and behave consistently. WAI describes this as helping people learn and recognize controls. | This is supplemental guidance, not a normative WCAG success criterion. |

## Direction selected

The implementation uses an original **Civic Night** direction: deep ink page backgrounds, layered blue-gray surfaces, restrained institutional blue for primary actions, mint for a secondary trust accent, and distinct labeled status treatments. System fonts avoid fetching web fonts at runtime. The existing role-specific information architecture remains in place, while the shared shell, public landing hero, status/focus treatment, and mobile navigation receive the common design language.

This direction fits the repository’s real product boundary: an academic prototype for credential flows, with several role-specific workspaces and visible service limitations. The presentation should feel orderly and calm without using color or language to imply accreditation, EUDI conformance, self-custody, live blockchain anchoring, or a trained fraud model.

## Adaptation decisions

- Keep role portals and their destinations; make the common header and active navigation predictable.
- Retain explicit prototype and service-state labels. A green/blue visual state must not turn unavailable or synthetic data into a success claim.
- Use a system font stack so the core UI does not depend on Google Fonts availability.
- Preserve native browser scrolling and make scrollable areas discoverable; the previous global hidden-scrollbar rule was removed.
- Keep visible keyboard focus and honor reduced-motion preferences.
- Treat WCAG 2.2 AA as a target requiring page and interaction testing. This report does not claim conformance.

