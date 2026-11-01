# Secure SSI Platform V2.1 — WP-12 Golden Path, UI Truthfulness and Accessibility

**Checkpoint:** 24 October 2026
**Branch / initial HEAD:** `besna-dev` / `a026df83bcb6b43451cb96a7eaed41877b5e198a`
**Decision:** **PARTIAL (L2)** — source-level truthfulness review and current Web checks passed; the authenticated Golden Path and rendered accessibility checks were not verifiable in the available environment.

## Authority and scope

The revised Master Implementation Plan at `reports/independent-review-2026-10-05/SECURE_SSI_PLATFORM_MASTER_IMPLEMENTATION_PLAN_REVISED.md` controls engineering acceptance and supersedes older sprint ordering. It defines WP-12 as a UI-truthfulness/accessibility package dependent on the Golden Path, and G11/G12 require a real integrated user journey and visual E2E evidence. No master-plan PDF was present in the repository file inventory during this checkpoint; this report therefore cites the revised in-repository plan and the current G0–G16 acceptance register.

This checkpoint inspected actual frontend source, ran current Web tests/lint/build, and attempted local-screen availability checks. It did not change frontend behavior, API/service logic, role authorization, protocol contracts, credential handling, or accessibility styles: the sampled truthfulness disclosures were already present, while no browser evidence was available to justify an implementation claim or an accessibility fix.

## Requirement-to-evidence mapping

| Requirement | Source evidence / check | Result and boundary |
|---|---|---|
| Show the actual scope of credential sharing before consent | `apps/web/src/components/consent/SelectiveDisclosureSheet.tsx` and `apps/web/src/pages/holder/PresentationConsentPage.tsx` state that the complete signed credential is sent and that current Data Integrity does not provide cryptographic claim-level selective disclosure. The component requires the Holder to acknowledge full-credential sharing before approval. | **PASS for source wording and interaction structure.** No browser consent journey was executed in this checkpoint. |
| Distinguish service results from locally inferred results | `apps/web/src/components/verification/NinePointVerificationMatrix.tsx` labels the Identity Service response, says individual values are returned by the session response, marks risk advisory and anchoring optional, and labels returned claims without a selective-disclosure claim. `apps/web/src/pages/verifier/VerifyPresentationPage.tsx` reports the service result/errors and explicitly says the page does not infer checks the API did not return. | **PASS for inspected source wording.** A live verifier result was not exercised. |
| Avoid unsupported standards, assurance, and anchor claims | `apps/web/src/components/common/TrustBadge.tsx` says no conformance certification is claimed, assurance is not assessed, optional anchoring is not a trust/status source, and an anchor requires a verified receipt. | **PASS for inspected badge copy.** No independent certification or chain deployment is claimed. |
| Identify embedded non-production portal behavior | Holder, Issuer, Verifier, Guardian and Admin portal source under `apps/web/src/components/portals/` contains `DEMO SIMULATION`/synthetic-example notices. The Verifier disclosure says its embedded controls use local illustrative state and do not call the backend; it also disclaims EUDI/eIDAS trusted-entity status. Admin risk copy identifies `rule-heuristic-v1` as `NOT TRAINED` and synthetic/advisory. | **PASS for the inspected embedded-portal labels.** This is not a page-by-page rendered audit of every state. |
| Exercise real Issuer → Holder → Verifier Golden Path and negative paths | Existing G11 evidence in `docs/implementation/SECURE_SSI_PLATFORM_GATE_ACCEPTANCE.md` records a browser flow reaching consent and signed presentation but Direct Post did not reach the Gateway; the backend test passed separately. In this checkpoint, ports 3000, 13000, 18000–18003, 4173, 5173 and 5178 had no listener before Vite was started. The local Vite process started on 4173, but the host HTTP request was denied by the Windows socket sandbox. Computer Use stopped before Chrome inspection because it could not determine the current browser URL. | **BLOCKED / not completed.** No authenticated current-source browser flow, final verifier result, durable restart/audit trace, or negative UI journey is claimed. |
| Verify responsive behavior and WCAG 2.2 AA criteria | Web tests, lint and build below are the only checks run. No browser screenshot, viewport/zoom sweep, keyboard-only walk-through, screen reader, automated accessibility scanner, contrast measurement, modal focus test or target-size measurement was performed. | **UNVERIFIED.** No WCAG conformance claim. |

## Current checks

| Exact command / observation | Result |
|---|---|
| `npm.cmd test --prefix apps/web` | Exit 0; **8 test files passed, 0 failed, 0 skipped**. These are Node contract/SSR checks, not browser E2E or a full accessibility test. |
| `npm.cmd run lint --prefix apps/web` | Exit 0; no diagnostics. |
| `npm.cmd run build --prefix apps/web` | Exit 0; TypeScript passed, Vite 6.4.3 transformed 1,831 modules. |
| `npm.cmd run dev --prefix apps/web -- --host 127.0.0.1 --port 4173 --strictPort` | Vite reported ready and printed the local URL. A read-only PowerShell GET failed with a Windows socket permission error; the process was stopped with Ctrl+C. |
| Computer Use browser inspection | **Not completed.** Tool reported that it could not determine Chrome's current URL with enough confidence to enforce policy and stopped for the turn. No click, login or form submission occurred. |

## Accessibility reference

The current normative reference is **WCAG 2.2, W3C Recommendation, 12 December 2024**. The criteria that need actual UI verification include 1.4.3 Contrast (Minimum), 1.4.10 Reflow, 1.4.11 Non-text Contrast, 2.1.1 Keyboard, 2.4.7 Focus Visible, 2.4.11 Focus Not Obscured (Minimum), 2.5.8 Target Size (Minimum), 3.3.8 Accessible Authentication (Minimum), and 4.1.3 Status Messages, as applicable to each page and complete process. W3C's Understanding documents are informative guidance and were updated 11 February 2026; they do not replace the testable success criteria. [WCAG 2.2 Recommendation](https://www.w3.org/TR/2024/REC-WCAG22-20241212/), [W3C Understanding WCAG 2.2](https://www.w3.org/WAI/WCAG22/Understanding/).

## Acceptance decision and next evidence needed

WP-12 remains **PARTIAL (L2)**. Current source copy accurately discloses the sampled prototype limits and the current Web suite builds and lints. G11 remains **PARTIAL** because no successful current-source browser Direct Post/final result or durable full-flow trace was established. G12 remains **PARTIAL** because rendered desktop/mobile, keyboard, focus visibility/unobscured focus, screen-reader status, contrast, reflow and target size were not checked. The app was not left running after the local Vite availability attempt.

To advance acceptance, run the current source with the necessary backend services and an authorized test account in an inspectable browser; exercise the complete real Issuer → Holder → Verifier success and failure paths; then complete viewport, keyboard, focus, contrast, semantic/status-message and assistive-technology checks against WCAG 2.2. Until those checks run, neither the Golden Path nor WCAG AA is accepted. This report records the evidence boundary; it does not claim WP-12 completion or project readiness.
