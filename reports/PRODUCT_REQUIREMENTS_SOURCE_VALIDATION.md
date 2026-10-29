# Product Requirements — Source Validation (2026-10-29)

Input: `secure-ssi-platform_role-functionality-and-architecture-matrix.xlsx`. It was
treated as a candidate catalogue, not as truth.

Outputs:

| Output | Content |
|---|---|
| `C:\Users\besna\Downloads\SECURE_SSI_MATRIX_VALIDATED.xlsx` | The original sheets unchanged, plus 11 validation columns per table and a "Doğrulama Özeti" sheet |
| `reports/PRODUCT_GAP_MATRIX_VALIDATED.csv` | One record per validated row (349) |
| `reports/PRODUCT_OWNER_DECISIONS.csv` | Decisions that only the product owner can make |
| `reports/CLAUDE_TO_CODEX_BACKEND_HANDOFF.md` | Backend changes for Codex |
| `reports/FRONTEND_IMPLEMENTATION_CHECKLIST.md` | Frontend work in Claude's ownership |

## 1. Method
1. **Repository state.** Recorded before any change: branch `besna-dev`, HEAD
   `e26da1e`, 192 status lines, 46 untracked paths, nothing staged. The historical
   audit folder was preserved.
2. **Real API inventory.** Taken from the running services' `/openapi.json`, not
   inferred from the workbook:
   - identity: 74 operations;
   - recovery: 15;
   - fraud: 11;
   - gateway: wildcard proxies per service prefix.
3. **Sources.** Opened the official pages on 2026-10-29: W3C, OpenID, OWASP, NIST,
   SLSA and WCAG. Versions and section numbers are recorded per row. Reference
   implementations were checked through the GitHub API (license, latest release,
   activity).
4. **Per-row validation.** Every requirement-bearing row in all 13 sheets was
   validated: 349 rows. For each row, the decision (applicability) and the
   implementation level are separate fields.
5. **Live evidence.** Collected only from the running local stack with synthetic
   accounts:

   | Check | Result |
   |---|---|
   | 4-role crawl | 24 pages, 0 error states |
   | Browser golden path | ACCEPTED, 8/8 checks |
   | API write and negative-authorization run (`ops.mjs`) | 33/33 |
   | Revoke-then-verify regression (`rev.mjs`) | PASS |

## 2. Results (pre-implementation build)

| Decision | Rows |
|---|---|
| CONFIRMED_APPLICABLE | 255 |
| APPLICABLE_WITH_CHANGE | 40 |
| PROJECT_DECISION_NOT_STANDARD_REQUIREMENT | 13 |
| OWNER_DECISION_REQUIRED | 10 |
| OPTIONAL_FUTURE_SCOPE | 9 |
| OUTDATED_SOURCE_OR_VERSION | 9 |
| NOT_APPLICABLE_TO_FROZEN_SCOPE | 7 |
| CONTRADICTED_BY_CURRENT_SOURCE | 6 |
| UNSUPPORTED_BY_CITED_SOURCE / DUPLICATE_OR_OVERLAPPING | 0 |

Implementation levels:

| Level | Rows |
|---|---|
| L3_VERIFIED | 127 |
| L2_INTEGRATED | 78 |
| NOT_IMPLEMENTED | 28 |
| NOT_RECHECKED | 16 |
| L1_IMPLEMENTED | 15 |
| BLOCKED | 3 |
| N/A_REFERENCE (glossary, sources, summary) | 82 |
| L4_INTEROPERABLE | 0 |

**Post-implementation build** (the final workbook and CSV). The frontend items were
checked in the browser, and the local chain was started and connected:

| Level | Rows |
|---|---|
| L3_VERIFIED | 135 |
| L2_INTEGRATED | 74 |
| NOT_IMPLEMENTED | 27 |
| NOT_RECHECKED | 15 |
| L1_IMPLEMENTED | 12 |
| BLOCKED | 4 (anchor writes: backend wiring defect, handoff P1-A) |
| N/A_REFERENCE | 82 |

Self-correction: ADM-05 was first assessed as "UI missing". It already existed and
was then verified live.

L3 here means the row's acceptance behaviour was observed on the running system in
this session, or covered by a passing integration suite plus a live call. It is not
a claim of conformance. No row has L4 evidence.

## 3. Key disagreements with the workbook
- **"state" is not always required.** OpenID4VP 1.0 §5.2 makes `nonce` REQUIRED.
  `state` is REQUIRED only under §5.3, when presentations without holder binding are
  requested. Rows SEC-05, SCP-03 and the glossary entry were amended.
- **Holder binding is the default, not universal.** OpenID4VP §6.1
  `require_cryptographic_holder_binding` defaults to true and a verifier may set it
  false. The project profile requires binding, and the live flow shows it passing.
- **OID4VCI.**
  - §4.1.1 says the pre-authorized code "MUST be short lived and single use";
    reuse is rejected (400).
  - The spec does not mandate a public GET for offers by id. The repository's
    public, guessable-id offer read is a project-level weakness (P0-1), not a
    protocol requirement.
- **EdDSA.** The project suite is `eddsa-jcs-2022`. The EdDSA spec also defines
  `eddsa-rdfc-2022`; it is not universal. proofPurpose checking comes from the
  Data Integrity 1.0 verification algorithm, not from the jcs suite text.
- **Bitstring Status List.** §3.5 defines `STATUS_RETRIEVAL_ERROR`, but leaves
  accept/reject on retrieval failure to verifier policy. The project must state
  its policy; it must not be implied by the standard.
- **AI and blockchain.** No SSI standard requires AI risk scoring or anchoring.
  These rows are classed PROJECT_DECISION (SCP-09, SCP-10, BC-01, API-17, SEC-14).
- **Historic notes superseded by current evidence.** Both observations below are
  kept in the validated workbook, with dates.
  - HIST-17/SEC-18 (localStorage token): replaced by the HttpOnly cookie session on
    2026-10-28.
  - HIST-06: the 845 test count is replaced by 2026-10-29 counts.

## 4. Source / URL / version corrections
| Row | Was | Corrected |
|---|---|---|
| SRC-01 | Master plan → `https://www.w3.org/TR/vc-data-model/` | `reports/independent-review-2026-10-05/SECURE_SSI_PLATFORM_MASTER_IMPLEMENTATION_PLAN_REVISED.md` |
| SRC-10 | `https://owasp.org/www-project-api-security/` (HTTP 404 on 2026-10-29) | `https://owasp.org/API-Security/`; the 2023 edition is still current |
| SRC-14, SEC-20 | SLSA v1.1 provenance | SLSA v1.2 (Approved; Build + Source tracks), `https://slsa.dev/spec/v1.2/` |
| SRC-13 | SSDF, version unspecified | SP 800-218 v1.1 Final (Feb 2022). Rev.1 (v1.2) is still an initial public draft: monitor only |
| HIST-06 | 845 passed (WP-18-BE) | identity 744 passed / 12 skipped; gateway 28; recovery 52; fraud 31 |
| HIST-19 | CSS 640 lines / 0 !important | `app.css` 1,827 lines / 43 !important (custom layer over Tabler) |

Sources confirmed current on 2026-10-29:

| Source | Status / version |
|---|---|
| VC DM 2.0 | REC 2025-05-15; v2.1 is a Working Draft only |
| Data Integrity 1.0 | REC |
| EdDSA Cryptosuites 1.0 | REC 2025-05-15 |
| DID Core 1.0 | REC 2022-07-19 |
| Bitstring Status List 1.0 | REC 2025-05-15 |
| OpenID4VCI 1.0 | Final, 2025-09-16 |
| OpenID4VP 1.0 | Final |
| WCAG 2.2 | REC |

Reference implementations (comparators only):

| Project | License | Latest release |
|---|---|---|
| walt.id waltid-identity | Apache-2.0 | v1.2.0, 2026-10-15 |
| Credo TS | Apache-2.0 | v0.7.4, 2026-10-28 (too new to pin) |
| Inji Web | MIT per GitHub | v0.17.0 |

## 5. Contradictions between workbook decisions and current code (P0)
1. **Public credential-offer read.** It returns the pre-authorized code and claims,
   and offer ids are ObjectId-based (guessable): HOL-06, ISS-06, API-06, HIST-10.
2. **Gateway path traversal.** `../` reaches the identity `/internal/...` routes,
   which are still protected by the internal grant: CORE-01, API-01.
3. **Audit API.** It silently merges the deprecated SQLite store and returns
   SUCCESS (SCP-20 / CORE-15 / SEC-23 contradicted).

All three are documented with code and line evidence and acceptance tests in the
Codex handoff. As this task required, they were **not** fixed by Claude.

## 6. Limits of this validation
- **Not run:**
  - WCAG automated or manual testing (SEC-21);
  - the Hardhat chain and anchor E2E (blocked: no chain in the current stack);
  - recovery quorum/timelock live E2E;
  - external interoperability (L4).
- **Formula recalculation.** LibreOffice is not installed. The summary sheet
  formulas were checked in Python, and the workbook is set to recalculate fully
  when opened in Excel.
- **Code-only checks.** Some rows were checked by code inspection only and are
  marked as such (for example HIST-16: no database rows were opened).
