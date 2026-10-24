# Secure SSI Platform V2.1 — WP-09 AI Risk Grounding

**Verification date:** 24 October 2026 | **Branch:** `besna-dev` | **Source baseline:** application source at `9e965bb4de7f5e1bb1cbf0f48f30d53ebfb88b73`, plus the UI correction described below
**Decision:** **PASS at L3 for the bounded V2.1 heuristic/synthetic scope**

## Requirement and implementation

The frozen G0/WP-09 definition requires the risk service to be described honestly as an explainable heuristic, every synthetic demo dataset to display the literal `[DEMO LAB / SYNTHETIC]` label, and low AI risk never to override a cryptographic failure. It does not require manufacturing a trained model or claiming production ML.

The Fraud Service still reports `model_type` as a deterministic rule-based heuristic, `model_version=rule-heuristic-v1`, `model_status=NOT_TRAINED`, `evaluation_status=NO_INDEPENDENT_LABELLED_EVALUATION`, `dataset_label=[DEMO LAB / SYNTHETIC]`, and `advisory_only=true`. Its synthetic metric endpoint identifies deterministic replay scope and `trained_model=false`. No dataset provenance, independent real-world labeled evaluation, trained artifact, or performance/generalization claim is invented.

The Admin page had normalized bracketed values for readability, unintentionally changing the required marker. It now preserves that exact marker through the status-value component, while retaining readable formatting for other status codes. The verification policy remains separate from risk scoring: cryptographic, issuer-trust and status failures remain authoritative. No API, risk-scoring, SSI protocol, dependency, model or data-pipeline behavior was changed.

## Standards context

NIST AI RMF 1.0 treats validity and reliability as trustworthiness characteristics assessed against intended use and empirical evidence. The project's deterministic synthetic replay cannot establish operational validity, model accuracy, or generalization; therefore the UI keeps the untrained and advisory disclosures. NIST indicates the AI RMF 1.0 is under revision; this report applies the published 1.0 guidance and does not claim framework conformity. [NIST AI RMF 1.0](https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf), [NIST AI RMF status](https://www.nist.gov/itl/ai-risk-management-framework).

The repository has no trained model pipeline, so scikit-learn model evaluation or train/test-split claims do not apply. If a future approved scope introduces training, the official scikit-learn guidance warns against test-data leakage and requires fitting transformations only on training subsets. [scikit-learn common pitfalls: data leakage](https://scikit-learn.org/stable/common_pitfalls.html).

## Evidence

| Requirement | Evidence | Result / boundary |
|---|---|---|
| Exact synthetic marker is visible in the Admin component | `node apps/web/tests/fraudMonitorLabel.test.mjs` | **3 passed, 0 failed.** SSR rendered `RiskStatusValue` and asserted `<strong>[DEMO LAB / SYNTHETIC]</strong>` exactly, plus `NOT_TRAINED` and missing-value labels. This verifies component markup, not a browser session. |
| Frontend typing and production bundle | `npm.cmd run build --prefix apps/web` | **PASS**, TypeScript and Vite 6.4.3 production build; 1,831 modules transformed. |
| Frontend lint | `npm.cmd run lint --prefix apps/web` | **PASS**, no diagnostics after separating the status component. |
| Fraud heuristic/data disclosure and side-effect boundaries | Prior verified 24 October focused Fraud run in the WP-08 evidence register | **21 passed, 0 failed, 0 skipped, 2 warnings.** Backend code was not changed by WP-09. This is retained same-source evidence, not a fresh run in this follow-up. |
| Low risk cannot override crypto failure; server-owned risk input | Prior verified 24 October `test_oid4vp_ai_policy_matrix.py` run in the WP-08 evidence register | **8 passed, 0 failed, 0 skipped, 2 warnings.** Identity backend code was not changed by WP-09. This is retained same-source evidence, not a fresh run in this follow-up. |
| Fresh Python rerun on this Windows host | `.venv\Scripts\python.exe -m pytest ...` for the Fraud tests and AI-policy matrix | **BLOCKED / no valid summary.** Fraud TestClient stalled on its first `/health` request. Identity's targeted test stalled while AnyIO/Starlette created the Windows asyncio Proactor self-pipe (`socket.accept` from `_make_self_pipe`). A `faulthandler` snapshot confirmed the wait; the process was interrupted. No tests are counted as passed or failed from these attempts. Docker was unavailable (`Docker Desktop Linux Engine` named pipe access denied). |

## Changed files

- `apps/web/src/pages/admin/AiFraudMonitorPage.tsx` — use the dedicated shared status renderer for risk metrics/signals.
- `apps/web/src/pages/admin/RiskStatusValue.tsx` — preserve the exact required synthetic label; keep other values readable.
- `apps/web/tests/fraudMonitorLabel.test.mjs` — render the component through Vite SSR and assert exact output.
- `README.md` — replace the now-fixed WP-09 issue with bounded current evidence and link the package report.
- `docs/implementation/SECURE_SSI_PLATFORM_GATE_ACCEPTANCE.md` — append the G9 current-source result and environment boundary.
- `reports/V2_1_WP09_AI_RISK_GROUNDING.md` — this package evidence report.

## Acceptance limits

WP-09 is accepted only for the defined rule-based synthetic/advisory behavior and truthful UI. There is no trained model, independent representative labeled evaluation, fairness study, real-world performance measurement, production decision authority, or browser screenshot in this follow-up. The fresh Python test rerun remains environment-blocked; the cited 24 October backend results are retained earlier evidence for unchanged backend source. This is not AI certification or production readiness.
