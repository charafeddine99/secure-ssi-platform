# Secure SSI Platform — Standards and Reference Evidence Register

## Current implementation evidence — 15 October 2026

At branch `main`, HEAD `59e8933f6e47922ba5a82cb7c9d76632e7edefe1`, the working tree remains dirty and preserved. Current WP-08/G6 evidence is **PASS at L3 for the scoped acceptance**: focused status/policy/issuance tests 48/48; Identity regression 686 passed with 5 Hardhat-only skips; real Mongo repository tests 7/7; current-source Compose build; 7/7 isolated services healthy; 5 HTTP 200 smoke checks; and Mongo data persisted across a container restart. Current G7 wallet-consent/auth/privacy tests passed 80/80, including the isolated valid-holder-proof/tampered-issuer rejection case. Details, exact commands, and boundaries are recorded in the [WP-08 acceptance report](V2_1_WP08_FINAL_ACCEPTANCE.md), [G0–G16 matrix](../docs/implementation/SECURE_SSI_PLATFORM_GATE_ACCEPTANCE.md) and [test evidence register](../docs/implementation/SECURE_SSI_PLATFORM_TEST_EVIDENCE.md).

Current tally: G0, G6, G7, G9 and G10 PASS for their recorded scopes; 11 PARTIAL; G14 BLOCKED; no FAIL. G11 is PARTIAL after a local browser trace reached consent and VP creation but its Direct Post did not reach the Gateway. The five Identity-suite skips require a local Hardhat endpoint and do not count as WP-08 passes. L4 interoperability, suspension restoration, public-chain behavior, production readiness, complete browser E2E and full project completion are not claimed.

## Previous implementation evidence — 13 October 2026 (historical)

This execution update supplements the standards/source inventory below; it does not change the selected standards profile. The controlling plan's scoped G6/WP-08 acceptance is **PASS at L3**: the three focused tests passed 48/48, Identity regression passed 665 with 14 environment-gated skips, frontend fail-closed passed 8/8, and all seven services in the isolated current-source Compose stack are healthy with HTTP 200 smoke results. Detailed commands, R1–R3 mapping, residual repository-runner failures, and limitations are in [WP-08 Final Acceptance](V2_1_WP08_FINAL_ACCEPTANCE.md).

Evidence boundaries: `run_tests.py` exited 1 with 770 passed, 3 failures and 14 skips (plus 147 subtests); failures are two assertions that expect an optional live blockchain and one legacy database-stats route. CI workflow configuration now includes Identity tests, but no GitHub Actions run was performed. Blockchain remains offline/optional; system status correctly reports it degraded. L4, suspension restoration, production deployment, and WP-09 are not claimed or started.

**Audit date:** 12 October 2026

**Use:** Supporting evidence for the [plan reconciliation audit](IMPLEMENTATION_PLAN_RECONCILIATION_AUDIT.md) and [final implementation plan](../docs/implementation/SECURE_SSI_PLATFORM_FINAL_IMPLEMENTATION_PLAN.md).

**Evidence rule:** Findings below state what a source establishes and what it does not. Primary specifications define standards requirements; project profile choices are separately labeled. GitHub `main` pages are mutable and must be pinned to a commit before they are used as acceptance evidence.

## 1. Primary standards and protocols

| ID | Primary source / version | Relevant section or direct evidence | What it supports | What it does not support / project impact |
|---|---|---|---|---|
| S-01 | [W3C Verifiable Credentials Data Model 2.0](https://www.w3.org/TR/vc-data-model-2.0/) — Recommendation, 15 May 2025 | Status section and credential properties / `credentialStatus` semantics | VC DM 2.0 is a stable normative baseline; status is represented through `credentialStatus` and may be processed using external mechanisms. | Does not select this project’s proof suite, DID method, status mechanism or trust registry. Generic status optionality means this plan does not impose status on every external VC. |
| S-02 | [W3C Verifiable Credential Data Integrity 1.0](https://www.w3.org/TR/vc-data-integrity/) — Recommendation, 15 May 2025 | Data Integrity Proof model and verification algorithms | Proof options and secured documents must be verified under the selected cryptosuite. | Does not itself choose EdDSA, issuer trust policy, or this platform’s local profile. |
| S-03 | [W3C Data Integrity EdDSA Cryptosuites v1.0](https://www.w3.org/TR/vc-di-eddsa/) — Recommendation, 15 May 2025 | §3.3 `eddsa-jcs-2022` and §3.3.1–3.3.5 proof creation/verification | The selected `eddsa-jcs-2022` suite canonicalizes with RFC 8785 JCS before hashing/signing. It provides the standards basis for reusing shared proof verification rather than implementing an independent raw Ed25519 check. | The standard suite does not mean the project is interoperable; DID key resolution, verification-method authorization, issuer trust, time rules and proof suite allowlisting remain project acceptance controls. |
| S-04 | [RFC 8785 — JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785) | Sections 3–4 | Defines deterministic JSON canonicalization relevant to the frozen EdDSA proof suite. | JCS alone does not establish credential authenticity, authorization or issuer trust. |
| S-05 | [RFC 8032 — Edwards-Curve Digital Signature Algorithm (EdDSA)](https://www.rfc-editor.org/rfc/rfc8032) | Ed25519 algorithm sections | Defines the signature primitive selected by the profile. | Does not define the VC proof envelope, JCS processing, DID verification method or trust policy. |
| S-06 | [W3C Bitstring Status List v1.0](https://www.w3.org/TR/vc-bitstring-status-list/) — Recommendation, 15 May 2025 | §1 conceptual framework; §2.1 entry semantics; §2.2 list credential; §2.3 status-list entry; §3 processing; §7 encoding | A status list is a VC; `revocation` means cancelled validity, `suspension` temporarily prevents acceptance and is reversible; a set status bit represents the status; list credentials are signed; `statusListIndex` links an entry to a list position; invalid indices/encoding must not be trusted. The status-list credential issuer may differ from the credential issuer. | Does not require every credential to have a status field; does not define project Trust Registry, caching freshness, local publication binding, or universal fail-closed policy. Those are profile/hardening controls. |
| S-07 | [W3C Bitstring Status List version history](https://www.w3.org/TR/vc-bitstring-status-list/all/) | v1.0 Recommendation dated 15 May 2025; v1.1 First Public Working Draft dated 24 September 2026 | Confirms v1.0 remains the stable baseline and v1.1 is draft as of this audit date. | Does not authorize silent v1.1 adoption. |
| S-08 | [OpenID for Verifiable Credential Issuance 1.0 Final](https://openid.net/specs/openid-4-verifiable-credential-issuance-1_0-final.html) — Final, 16 September 2025 | §6.1 pre-authorized code grant; §7 Nonce Endpoint; credential request proof sections; Appendix F proof types | Supports the token/nonce/credential-endpoint structure and the Nonce Endpoint requirement when issuer proof requires a nonce. | The project’s choice of pre-authorized code only and `jwt` proof is a strict project profile, not the entire OID4VCI feature set. The plan must list unsupported grants/features. |
| S-09 | [OpenID for Verifiable Presentations 1.0 Final](https://openid.net/specs/openid-4-verifiable-presentations-1_0-final.html) — Final, 9 July 2025 | §5.1 request parameters; §5.2 nonce; §5.5 scope alias; §6 DCQL; §8 response modes | Either `dcql_query` or `scope` representing a well-defined DCQL query is required, but not both. The verifier supplies a fresh nonce; wallets process DCQL. `direct_post`/`direct_post.jwt` are final response-mode choices. | “The literal `dcql_query` parameter is the only standards-compliant option” is inaccurate; explicit `dcql_query` and unconditional `state` are this project’s stricter profile. The specification does not establish this repository’s DCQL interoperability. |
| S-10 | [W3C DID Core 1.0](https://www.w3.org/TR/did-core/) — Recommendation, 19 July 2022 | Core data model and verification relationships | Defines DID document concepts and verification relationships used by DID methods. | Does not define `did:web` or `did:key` method semantics as a W3C Recommendation and does not establish issuer trust. The project’s method allowlist is an ADR/profile decision. |
| S-11 | [IETF Token Status List current Datatracker entry](https://datatracker.ietf.org/doc/draft-ietf-oauth-status-list/) — draft-ietf-oauth-status-list-21, 21 June 2026 | Document status: Active Internet-Draft, intended Proposed Standard; IESG state RFC Editor Queue; §4–8 data and processing; expiration 23 December 2026 | Confirms TSL is a current draft under publication processing, not a published RFC on the audit date. TSL represents status for JOSE/COSE tokens and defines JWT/CWT list tokens. | Not interchangeable with W3C VC Bitstring Status List. Its advanced publication status does not silently change the project’s frozen profile. If later selected, require a new ADR, profile/interoperability analysis and migration plan. |
| S-12 | [IETF SD-JWT VC current Datatracker history](https://datatracker.ietf.org/doc/draft-ietf-oauth-sd-jwt-vc/history/) — draft-ietf-oauth-sd-jwt-vc-19, latest revision 31 August 2026; IETF Last Call/state information through September 2026 | Version history / review state | Confirms SD-JWT VC remained an Internet-Draft in the reviewed source and was undergoing standards-process review. | It is not the project’s W3C VC Data Integrity profile and cannot be treated as an already adopted final format. A project may choose a draft only through an explicit decision; this audit recommends retaining the existing frozen profile. |

## 2. Local repository evidence

| ID | Source inspected | What it establishes | Limitations / status |
|---|---|---|---|
| L-01 | `reports/independent-review-2026-10-05/SECURE_SSI_PLATFORM_MASTER_IMPLEMENTATION_PLAN_REVISED.md` | Explicitly supersedes V2.1 for engineering control; frozen product definition, standards, architecture, L0–L4, evidence, G0–G16 gates, WP08/P0 rules. | Plan statement, not proof implementation is complete. Consolidated as the new control plan. |
| L-02 | V2.1 PDF in Downloads | Role model, frozen VC/DI/OID profiles, explicit Trust Registry, Bitstring Status List, evidence model, G0–G16 gate concepts and release checklist. | Historical. No Git metadata/history; PDF cover/metadata must not override later revised Master. |
| L-03 | V2.0 Claude PDF in Downloads | Candidate SD-JWT VC/TSL/browser-key scope, recovery and UI catalogue, status policy, milestone sequencing, risks, and six approval questions. | Candidate only; PDF metadata says created 11 Oct while cover says 4 Oct; not tracked in Git. It contains contradictory Bitstring/TSL statements and self-reported source validation. |
| L-04 | `docs/adr/0001-did-methods-for-the-prototype.md`, `docs/adr/0002-vc-data-model-and-proof-format.md`, `docs/adr/README.md` | Accepted local choices are synthetic issuer `did:web`, synthetic holder `did:key`, VC DM 2.0 and DI `eddsa-jcs-2022`. ADR README says a decision change must be captured in a new ADR rather than silently rewriting an accepted decision. | These two ADRs do not by themselves lock every OID profile, status profile, custody/security constraint, or release gate; the final plan captures the broader baseline. |
| L-05 | `docs/standards-baseline.md` | Documents current stable baselines and labels drafts as monitor-only; states VC 2.0, DI, EdDSA/JCS, Bitstring, DID method choices. | Last reviewed 23 July 2026; requires refresh at next standards gate. |
| L-06 | `docs/architecture.md`, `docs/implementation-status.md`, `services/identity-service/README.md` | Documents actual Identity/Recovery boundaries, local proofs, Mongo-backed status list lifecycle, wallet/managed key and recovery behavior, synthetic/local key limitations, missing network resolver/selective disclosure/external certification, and service pytest command. | Documentation may drift. `implementation-status.md` contains older sprint rows and should be reconciled in G12/G16. |
| L-07 | Current WP-08 addendum in `reports/V2_1_WP08_FINAL_ACCEPTANCE.md` (modified working-tree file) | Reports 37 targeted cases collected, API execution blocked at Windows TestClient startup, 94 focused lower-level pass, 7 frontend cases pass, lint/build pass, Docker daemon permission blocked; labels WP08 partial/L3 fail/L4 unclaimed. | This is user-owned, uncommitted evidence. The audit did not rerun it; pass counts are **reported**, not independently verified by this audit. |
| L-08 | `services/identity-service/app/application/services/oid4vp_service.py`, `credential_proof_service.py`, status schema/domain/generator, and new untracked `test_wp08_remediation_status_security.py` | Current diff implements R1–R3 behavior described in the reconciliation report; the new file contains 28 API test cases across R1/R2/R3. | Source presence does not establish execution or correctness. API assertions were reported blocked. This audit did not modify or execute the test file. |
| L-09 | `pytest.ini`, `services/identity-service/README.md`, `.github/workflows/ci.yml`, `docker-compose.yml`, `apps/web/package.json` | Identity README documents `python -m pytest -q`; root pytest configuration uses `testpaths=services`; package scripts include frontend lint/build; CI currently tests Fraud, API Gateway, contracts and builds frontend but omits Identity Service; Compose has health checks for services/Mongo/Redis. | Compose healthcheck definitions do not prove running service health; no Docker command ran in this audit. |
| L-10 | Git read-only outputs | `main`, HEAD and `origin/main` at `59e8933f6e47922ba5a82cb7c9d76632e7edefe1`, with 22 modified tracked files and one untracked integration test. | No fetch; `origin/main` is the local ref, not independently confirmed remote freshness. |

### Current test claims: precise scope

The current WP-08 report states that its focused lower-level command yielded **94 passed, 0 failed, 0 skipped**, including proof/status unit and service tests and two issuance interoperability cases. It states the new API integration file and policy cases collected (37 tests total) but execution stalled before the first test completed. It also states seven frontend fail-closed cases and lint/build passed. These are report records, not this audit’s executed results; the full suite is not rerun and 616/14 remains historical.

No test, lint, build, Docker, or server command was executed for this audit. The proposed exact test/runtime commands are in the final plan §8.

## 3. Reference implementation source review

### R-01 — walt.id Identity

- Repository: [walt-id/waltid-identity](https://github.com/walt-id/waltid-identity), mutable `main` branch; no commit SHA was exposed by the rendered source page, so pin one before reuse.
- Inspected: repository README; `waltid-libraries/credentials` directory and `waltid-dcql` README/tree.
- The repo README describes OID4VCI 1.0 and OID4VP 1.0 services and support for W3C VC, SD-JWT VC and mdoc. The DCQL README describes parsing, credential matching, constraints, multiple credential formats/sets and test sources under `src/commonTest`.
- Limits: GitHub rendered source and test-file pages could not be retrieved by the research browser. Therefore this register does **not** claim that `DcqlParser.kt`, matcher source, or unit tests were directly inspected or passed. README descriptions do not prove complete conformance or suitability for this profile.
- Project lesson: DCQL can be separated as a matching engine with format adapters; this is an architectural pattern only. Do not adopt extra formats because the reference supports them.

### R-02 — OpenWallet Foundation Multipaz

- Repository: [openwallet-foundation/multipaz](https://github.com/openwallet-foundation/multipaz), mutable `main`; no immutable commit SHA was recorded.
- Inspected: `multipaz/src/commonMain/kotlin/org/multipaz/openid/OpenID4VP.kt`, `TESTING.md`, README and changelog.
- Source shows a DCQL query execution path feeding credential matching/presentment, and request/response code with `dcql_query`, `nonce`, `direct_post`/`direct_post.jwt`, response generation and consent cancellation. The source includes older draft-version branches, so it is not used as proof that the inspected code path conforms to this project’s OID4VP Final profile.
- `TESTING.md` says to run `./gradlew check` for server unit tests and `./gradlew connectedCheck` for connected-device tests, and documents manual test-app plus live OID4VP flows.
- Limits: the specific DCQL test directory/file could not be fetched from the research browser. The test instructions and changelog are not test results. This SDK is multiplatform/mobile-oriented and supports mdoc/SD-JWT/ZKP capabilities beyond this project’s profile.
- Project lesson: preserve separations among DCQL parsing/matching, consent, protocol response, and platform-specific credential operations; do not copy its full architecture or infer L4.

### R-03 — EUDI status-list service

- Repository: [eu-digital-identity-wallet/eudi-srv-statuslist-py](https://github.com/eu-digital-identity-wallet/eudi-srv-statuslist-py), mutable `main`; no immutable commit SHA recorded.
- Inspected: repository README and `app/status_list_endpoints.py` source page.
- README identifies ASL using an older IETF OAuth status-list draft and ISO ARL, not W3C Bitstring Status List 1.0; it labels the software an early development release. The endpoint source logs all request headers and form fields on its take endpoint before checking the API key. Its `/get` route has a commented-out API-key check.
- Limits: no test directory/test source was accessible through the research browser; the repository provides no evidence here of production readiness or W3C Bitstring conformance. A public read path may be intentional for status distribution, but authenticated mutation and sensitive request logging still need review.
- Project lesson: never log secrets/authorization headers; explicitly distinguish public status retrieval from protected list mutation; validate the correct status profile. Do not reuse this service as evidence of project conformance.

## 4. Source-access limits and confidence

| Area | Status | Reason and action |
|---|---|---|
| Normative VC/Data Integrity/EdDSA/Bitstring/OID sources | **CONFIRMED** for cited points | Official primary pages were opened; retain versions/sections and recheck before a future profile gate. |
| IETF TSL / SD-JWT VC process state | **CONFIRMED** as source state on audit date | Datatracker identifies active drafts and queue/review status; this can change, so recheck before future adoption. |
| Current repo branch/HEAD/worktree | **CONFIRMED locally** | Read-only Git commands; remote branch freshness not fetched. |
| WP-08 R1–R3 code intent | **PARTIALLY CONFIRMED** | Diff/source inspected; focused report records API execution blocked. Run targeted tests on authorized working runtime before acceptance. |
| 94 focused passing tests / frontend results | **REPORTED, NOT RERUN** | Read from the modified WP-08 report; this audit did not execute tests/build. |
| walt DCQL source and individual tests | **PARTIALLY CONFIRMED** | README/tree accessible; source/test pages failed in research browser. Pin and inspect before relying on a particular algorithm/test. |
| Multipaz specific DCQL test cases | **UNVERIFIED** | Source file and general testing instructions accessible, but specific test directory/file not retrievable. |
| EUDI service test coverage | **UNVERIFIED** | Endpoint source and README accessible; test tree/source tests not retrievable. |
| Public interoperability / L4 | **NOT DEMONSTRATED** | No independent protocol run was performed for this project. |

## 5. Citation and update notes

All external statements in this register are tied to the primary URL listed in the row. GitHub branch pages are snapshots rather than immutable evidence. At the next Interop or standards gate, record repository commit SHAs, tests inspected, exact invocation/environment, output, and unsupported profile differences. An external project’s popularity or own conformance language is not a substitute for evidence from this project’s flow.

## 6. Continuation research and current evidence — 13 October 2026

This dated addendum supersedes the older WP-08 evidence status in L-07 through L-10 and the “Current test claims” paragraph above. The earlier entries remain as a point-in-time record of the initial audit; use the current plan update, WP-08 acceptance addendum, and `reports/PROJECT_WIDE_AUDIT_PROGRESS_2026-10-13.md` for current execution status.

### Official standards and guidance checked

| ID | Primary source checked | Finding used in this continuation | Project boundary |
|---|---|---|---|
| S-13 | [OpenID4VCI 1.0 latest errata-corrected specification](https://openid.net/specs/openid-4-verifiable-credential-issuance-1_0.html) and [approved Final text](https://openid.net/specs/openid-4-verifiable-credential-issuance-1_0-final.html) | The OpenID Foundation labels 1.0 Final and recommends the latest revision URL for text incorporating errata. | The plan’s pre-authorized-code and `jwt` proof profile remains a subset/profile choice; this source does not prove repository conformance. |
| S-14 | [OpenID4VP 1.0 latest errata-corrected specification](https://openid.net/specs/openid-4-verifiable-presentations-1_0.html) and [approved Final text](https://openid.net/specs/openid-4-verifiable-presentations-1_0-final.html) | The Final specification recommends referencing the latest errata-corrected URL. The protocol defines DCQL request semantics, while the project’s explicit DCQL parameter and server-bound state are local profile choices. | The app is not a general OID4VP wallet; interoperability is not established by matching the protocol name. |
| S-15 | [W3C VC Data Model 2.0](https://www.w3.org/TR/vc-data-model-2.0/), [Data Integrity 1.0](https://www.w3.org/TR/vc-data-integrity/), [EdDSA Cryptosuites 1.0](https://www.w3.org/TR/vc-di-eddsa/), and [Bitstring Status List 1.0](https://www.w3.org/TR/vc-bitstring-status-list/) | These are the published W3C Recommendations used by the frozen profile. | Retain `eddsa-jcs-2022` and Bitstring Status List 1.0; no draft/status migration was made. |
| S-16 | [EUDI Wallet Reference Implementation feature map](https://docs.eudi.dev/latest/reference-implementation/feature-map/) | The official reference implementation describes issuance and remote presentation as aligned with OpenID4VCI/OpenID4VP and also lists other formats and flows. | `latest` is mutable and the implementation has a broader/different scope; use it only as a comparison source, not as certification or project conformance evidence. |
| S-17 | [OWASP ASVS](https://owasp.org/projects/asvs) and [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/) | ASVS provides web security verification requirements; WCAG 2.2 is the W3C accessibility recommendation suitable as an audit baseline. | No ASVS assessment, accessibility audit, or WCAG conformance claim was completed in this continuation. |

### Current local execution evidence

| ID | Command / inspection | Result | Limit |
|---|---|---|---|
| L-11 | Recovery Service `python -m pytest -q` (existing root Python 3.11 venv; working directory `services/recovery-service`) | 46 passed, 0 failed, 0 skipped; one Starlette/httpx deprecation warning. | In-process service tests; no live Mongo restart/failover or independent Guardian DID signature verification. |
| L-12 | Identity targeted OID4VCI/OID4VP Golden Path command listed in the progress report | 55 passed, 0 failed, 0 skipped; two deprecation warnings. | In-process integration tests; no independent wallet interoperability. |
| L-13 | Web build/lint and standalone OID4VP wallet, Recovery API, and presentation fail-closed contract checks listed in the progress report | Build and lint exit 0; 9 + 8 + 8 focused assertions passed. | No browser accessibility audit or captured UI screenshot. |
| L-14 | Current Git inspection | `main`, HEAD remains `59e8933f6e47922ba5a82cb7c9d76632e7edefe1`; existing working-tree changes remain uncommitted. | No fetch; local `origin/main` freshness is unknown. |

External TestClient commands were first attempted under the sandbox and hung before emitting results; the same scoped commands completed when rerun with local test-process permissions and fresh GUID-named temporary pytest directories. No package installation or dependency change was made. Docker, Hardhat, external peer, GitHub Actions, load test, security scanner, and browser accessibility evidence remain separate open checks; absence of evidence is not a pass.

## 7. Current execution and source recheck — 13 October 2026

This later same-day addendum supersedes the older execution limitations above where they conflict. The repository's authoritative frozen profile and gate order did not change.

### Official-source findings and implementation comparison

| Source | Current observation | Comparison / limit |
|---|---|---|
| [W3C VC Data Model 2.0](https://www.w3.org/TR/vc-data-model-2.0/) and [publication history](https://www.w3.org/standards/history/vc-data-model-2.0/) | W3C Recommendation dated 15 May 2025; errata are published. | The model defines credential/presentation structure; issuer trust remains an ecosystem decision. Local profile tests do not establish general conformance. |
| [W3C Data Integrity 1.0](https://www.w3.org/TR/vc-data-integrity/) and [EdDSA Cryptosuites 1.0](https://www.w3.org/TR/vc-di-eddsa/) | `eddsa-jcs-2022` canonicalizes with RFC 8785 JCS and uses EdDSA. | This confirms the selected algorithm description; broader proof conformance still needs vectors/independent implementation evidence. |
| [W3C Bitstring Status List 1.0](https://www.w3.org/TR/vc-bitstring-status-list/) | The specification distinguishes reversible `suspension` from irreversible `revocation`, requires purpose matching, proof verification, list-size and index checks. | The current project enforces tested status rejection; suspension restoration is still not implemented or claimed. |
| [OpenID4VCI 1.0 latest revision](https://openid.net/specs/openid-4-verifiable-credential-issuance-1_0.html) | OpenID Foundation labels the document Final and recommends this errata-updated URL. The specification lists the nonce endpoint as optional generally. | The project's stricter nonce/proof choices remain local profile decisions; tests here are not an independent interoperability result. |
| [OpenID4VP 1.0 latest revision](https://openid.net/specs/openid-4-verifiable-presentations-1_0.html) | The Final text has an errata-updated latest URL and defines DCQL authorization-request semantics. | Local server-bound presentation decisions are profile-specific; no external wallet/verifier was run. |
| [RFC 9700](https://www.rfc-editor.org/rfc/rfc9700.html) | IETF OAuth 2.0 Security BCP 240, January 2025. | Security review baseline; this audit did not complete a full OAuth/ASVS assessment. |
| [OWASP ASVS stable releases](https://github.com/OWASP/ASVS/releases) | Latest stable release observed: 5.0.0; bleeding-edge builds are explicitly not stable. | No ASVS checklist/scanner execution is claimed. The release page is the OWASP project's official repository. |
| [WCAG 2.2](https://www.w3.org/TR/WCAG22/) | W3C Recommendation; W3C reports ISO/IEC 40500:2025 adoption. | Accessibility requirements remain open; build/lint are not accessibility evidence. |
| [EUDI RI feature map](https://docs.eudi.dev/latest/reference-implementation/feature-map/) and [official repository map](https://docs.eudi.dev/latest/reference-implementation/repositories-list/) | Current documentation lists issuance/presentation as completed and Wallet Backup/Restore as planned; its repositories separate native Android/iOS wallet, issuer, verifier, and reusable core components. It documents different/broader credential formats and flows. | Useful comparison: this project is a custodial/server-mediated web prototype and explicitly does not implement local backup/restore. EUDI `latest` is mutable; none of these descriptions proves Secure SSI conformance. |

### Current local verification

| Check | Result | Acceptance boundary |
|---|---|---|
| Identity Service full suite | 676 passed, 0 failed, 12 skipped; 3 deprecation warnings; 219.78 seconds. | Seven real-Mongo cases skipped because `IDENTITY_TEST_MONGODB_URI` was not set; five live Hardhat cases skipped because localhost:8545 was unavailable. No test package was installed. |
| Recovery API browser-client contract | 21 assertions passed. | Includes server-policy parsing, wallet binding, quorum readiness, duplicate-request prevention, and no synthesized fallback policy. |
| Presentation fail-closed frontend contract | 8 checks passed. | Does not replace browser E2E or accessibility verification. |
| OID4VP wallet API contract | 9 assertions passed. | Mocked fetch contract only; not peer interoperability. |
| Frontend lint | Exit 0, no diagnostics. | Does not establish accessibility or full workflow correctness. |
| Frontend build | Exit 0; TypeScript passed and Vite transformed 1,826 modules. | Build evidence only. |
| Security scanner availability | `bandit`, `pip-audit`, `safety`, `semgrep`, `trivy`, and `osv-scanner` were not installed/available. | No dependency or security scan was run; no tools were installed. |

The documented repository-wide `run_tests.py` command is still running at the time of this entry; its final exit code and per-service counts must be appended after completion. The local Docker acceptance in the WP-08 report predates the Recovery UI edits made in this audit continuation, so it is not current-source deployment evidence for the final worktree. No Git commit or push was made.

## Current local verification — 14 October 2026

This continuation entry records current-source evidence after the latest test and authentication audit. The official standards findings S-13 through S-17 above remain the applicable primary-source research record; no standard-profile change was made.

| ID | Command / evidence | Result | Limit |
|---|---|---|---|
| L-15 | Root `.venv\Scripts\python.exe run_tests.py`, with Mongo unset and Gateway services locally available | 788 passed, 12 skipped, 0 failed, 155 subtests; per-service: Identity 678/12 skipped, Recovery 46, Fraud 23, Gateway 16, shared 7 + 19 subtests, root 18 + 136 subtests. | Seven skips are real Mongo tests requiring `IDENTITY_TEST_MONGODB_URI`; five live-chain checks were skipped at this instant and then rerun live under L-17. |
| L-16 | From `services/identity-service`, exact WP-08 three-file acceptance command from plan §8 | 48 passed, 0 skipped, 0 failed; two deprecation warnings. | In-process/FakeMongo evidence; Docker and real Mongo behavior remain separate. R1–R3 are accepted only within this tested scope. |
| L-17 | `blockchain` `npm test`; then `services/identity-service/tests/integration/test_blockchain_anchoring.py` against disposable Hardhat localhost:8545 | 19 contract tests and 7 live local-chain integration tests passed. | No public chain, deployment metadata, or production signer. The live tests use the repository’s fake persistence adapter. |
| L-18 | Targeted backend auth test plus frontend authentication/recovery/OID4VP/fail-closed contract scripts | Backend auth 36 passed; frontend scripts 11, 21, 9, and 8 checks passed. Frontend lint/build exit 0 (1,826 modules). | No browser, accessibility, MFA, external IdP, production wallet, or visual acceptance evidence. |
| L-19 | Root live Gateway/security integration command and Identity blockchain API unit command | 10/10 root tests and 3/3 blockchain API tests passed. The two prior 503 failures were diagnosed: blockchain health endpoints unnecessarily required Mongo; audit endpoints correctly fail with `PERSISTENCE_UNAVAILABLE` when authoritative Mongo is unavailable. | The test expectation for audit was corrected to assert the explicit unavailable response; the product did not return a false success or partial audit. |
| L-20 | `git diff --check`, final local process check | Exit 0; no listeners remained on 8000–8003 or 8545. | Existing CRLF and protected temp-directory access warnings remain; files were not changed by the check. |

Current WP/gate status remains scoped: WP-08 R1–R3 tests pass, but full G6 runtime closure, G8 restart/Guardian-signature evidence, G11 browser-backed Golden Path, G12 redesign/visual accessibility, G13–G16, and L4 are not established. No file content from the protected temp tree was inspected or removed.

## Current-source completion evidence — 14 October 2026

This entry supersedes current-status wording above only where it conflicts; earlier entries remain historical records.

| ID | Evidence | Current result and limit |
|---|---|---|
| L-21 | Current targeted Python G7/auth/consent command from the audit evidence register | `BLOCKED` before collection by repository `.venv` launcher: Windows `os error 5`; 0 collected, 0 executed. No product result. |
| L-22 | Current Web lint/build and four contract scripts | Lint/build exit 0; auth/OID4VP/fail-closed/recovery scripts: 15/9/8/21 checks passed. Client contracts are not backend or browser proof. |
| L-23 | Bundled Python AST parse | Three current schema/test files parse; syntax only. Bundled Python 3.12.14 lacks pytest, FastAPI, and PyMongo. |
| L-24 | Docker and WSL runtime probes | Docker command and standard Desktop paths absent; WSL command is present but distro/status enumeration returns `E_ACCESSDENIED`. |
| L-25 | Current G7 source migration/hardening | Legacy wallet-consent test migrated to canonical wallet-bound APIs; schema rejects caller-supplied server session context. Current backend execution is blocked; exact hashes and command are in `docs/implementation/SECURE_SSI_PLATFORM_TEST_EVIDENCE.md`. |
| L-26 | Official W3C status-list series page | v1.1 is First Public Working Draft dated 24 September 2026; selected v1.0 remains the Recommendation and frozen project profile. Monitor only; no ADR/profile migration. |

## G8 execution evidence — 15 October 2026

| Evidence | Result | Acceptance boundary |
|---|---|---|
| Recovery Service unit/API suite, `tests/unit tests/integration` | 45 passed, 1 skipped because `RECOVERY_TEST_MONGODB_URI` was unset; same suite passed with local asyncio socket permission. | Covers state/quorum/abuse and DID-bound proof verification; separately invoked live Mongo case below. |
| Live Mongo restart/rotation test `test_live_mongo_recovery_decision_and_rotation_survive_repository_restart` | 1 passed; initial sandbox connection received `WinError 10013`; permitted rerun passed. | Random isolated DB dropped after test; three client connections prove persisted approvals/time lock and successor-DID recovery with a local test gateway. No deployed Identity+Recovery cross-service Mongo flow. |
| Identity WP05 proof-signing integration file | 19 passed. | Authenticated Guardian managed-`did:key` proof signing, signature/claim checks and foreign-wallet denial; not independent device custody. |
| Identity recovery internal API + grant/key-rotation tests | 6 passed. | Local test adapters verify ownership, request-bound grant and idempotent key rotation; not deployed service-to-service E2E. |
| Web Recovery API contract + production build | 22 assertions passed; TypeScript and Vite build passed (1,826 modules). | Client wiring/build only; no browser E2E or accessibility evidence. |
| Recovery Ruff | Not run: existing authorized venv reports `No module named ruff`. | No software was installed. |

**G8 remains PARTIAL.** Required cryptographic proof is verified for Ed25519 `did:key`, but Identity's signer is server-managed, independent Guardian-device signing/MFA and share custody are absent, and `did:web` proofs fail closed. Refer to [the current test evidence](../docs/implementation/SECURE_SSI_PLATFORM_TEST_EVIDENCE.md) for exact commands and environment details. The tally remains G0/G6/G7 PASS; 12 PARTIAL; G11/G14 BLOCKED.

## G9 execution evidence — 15 October 2026

| Command / working directory | Result | Acceptance boundary |
|---|---|---|
| Fraud focused files from `services/fraud-service` | 21 passed, 2 deprecation warnings. | Deterministic synthetic heuristic disclosure, side-effect-free scoring, no auto-quarantine on event ingestion, explicit prototype quarantine behavior, and legacy endpoint. |
| `tests/integration/test_oid4vp_ai_policy_matrix.py` from `services/identity-service` | 8 passed, 2 deprecation warnings. | Low-risk crypto/expiry/nonce rejection, server-owned risk provenance, input override rejection, and high-risk policy behavior. |
| `tests/unit/test_verification_policy.py` from `services/identity-service` | 48 passed, 1 SQLite deprecation warning. | Every failed gate, including issuer trust and revocation/status, remains rejected at AI score zero. |
| Current Web production build recorded under G8 continuation | TypeScript passed; Vite transformed 1,826 modules. | Existing AI monitor labels compile; not a browser or accessibility audit. |

G9 is **PASS at L3 for the declared heuristic/synthetic scope**. There is no trained model, independent representative labeled evaluation, or real-world performance evidence; none is claimed. The Fraud evaluator does not mutate quarantine state. Identity's explicit policy applies risk only after protocol/security gates pass. The updated matrix tally is **4 PASS, 11 PARTIAL, 2 BLOCKED**; G11/G14 remain blocked.

The authoritative current checkpoint now has [G0–G16 acceptance](../docs/implementation/SECURE_SSI_PLATFORM_GATE_ACCEPTANCE.md), [completion audit](../docs/implementation/SECURE_SSI_PLATFORM_COMPLETION_AUDIT.md), [test evidence](../docs/implementation/SECURE_SSI_PLATFORM_TEST_EVIDENCE.md), [security review](../docs/implementation/SECURE_SSI_PLATFORM_SECURITY_REVIEW.md), [interoperability report](../docs/implementation/SECURE_SSI_PLATFORM_INTEROPERABILITY_REPORT.md), and [performance report](../docs/implementation/SECURE_SSI_PLATFORM_PERFORMANCE_REPORT.md). No report claims a backend test pass for the current Python-blocked source checkpoint.

## Current-source delta — 14 October 2026

This addendum records changes after L-20. Earlier test results remain historical and do not cover the changes below.

| Gate | Current source delta | Executable evidence / status |
|---|---|---|
| G7 consent and minimization | Anonymous legacy OID4VP reject/consent/signer routes now return 410; supported mutation and signing paths are wallet-bound and authenticated. Demo credentials are populated only for explicitly enabled Vite development auth. | New regression and migrated integration tests are present, but pytest could not start: the repository venv launcher returned Windows `os error 5`; bundled Python 3.12.14 lacks pytest/FastAPI. G7 remains open. One pre-existing WP-07 integration file still targets the retired routes and requires migration. |
| Authentication/session | Added a backend token-revocation test; frontend auth contract now includes logout revocation and confirms demo credentials are absent in the default non-demo environment. | Frontend auth contract: 15 assertions passed. Backend revocation test unexecuted. This does not prove distributed/persistent revocation, MFA, production IdP, or registration. |
| G12 frontend build baseline | Production bundle regenerated after demo-credential gating. | `npm run build -- --configLoader runner` passed (TypeScript + Vite 6.4.3, 1,826 modules); lint passed. Default Vite config bundling hit a sandbox read denial above the workspace. No visual/browser/accessibility acceptance. |

The active host has no `docker` command or standard Docker Desktop executable. The authorized bundled Python runtime is 3.12.14 and lacks pytest/FastAPI; no packages, images, or runtimes were installed. Current WP-08/repository pytest evidence remains the earlier 788/12-skip checkpoint, not a result for the current source.

## G10 execution evidence — 15 October 2026

| Evidence | Result | Acceptance boundary |
|---|---|---|
| `npm test` from `blockchain` | 19 Hardhat contract tests passed. | Repository-installed contracts, in-process Hardhat chain. |
| Current Identity anchor/API/settings/directory/live integration selection | 25 passed after the 5 no-chain skips were rerun on a temporary loopback Hardhat node. | Receipts and digest-only chain call data verified; integration anchor storage uses FakeMongo. |
| OID4VCI Golden Path + OID4 protocol suites | 8 passed; valid credential remains `ACCEPTED` with `blockchainAnchored == false`. | In-process API tests, not a real browser or production chain. |

G10 is **PASS at L3 for the optional local-chain scope**. Local chain ID was 1337, only bound to `127.0.0.1`, and stopped after the tests. No public-chain, production deployment, live Mongo anchor persistence or automated retry-worker claim is made. Current project tally: **5 PASS, 10 PARTIAL, 2 BLOCKED**; G11/G14 remain blocked.

## G11/G12 continuation evidence — 15 October 2026

| Evidence | Result | Acceptance boundary |
|---|---|---|
| Local browser OID4VP flow | Inline request parsed; server session/DCQL matched; consent and wallet presentation returned 200; Direct Post UI failed with `Failed to fetch`. Gateway recorded final `OPTIONS` as 200 and no final `POST`. | No verified browser result; no claim that the presentation was received. |
| Gateway CORS preflight and health | From the project Gateway container, preflight to `/api/v1/oid4vp/response` returned 200 with matching origin and allowed POST/content-type for both configured local origins. Browser GET to Gateway health returned healthy. | Confirms standard preflight configuration and basic reachability, not the cause of the missing POST. |
| Backend focused wallet flow | `test_wallet_bound_golden_path_uses_complete_signed_credential`: **1 passed** in the validation Identity container. | In-process test; not a browser or durable Mongo restart trace. |
| G12 network-error helper | `node --experimental-strip-types apps/web/tests/oid4vpSubmissionError_contract.test.ts`: **7 assertions passed**; changed-file ESLint passed; TypeScript/Vite build passed with 1,828 modules. | The revised retry button was not observed in-browser after build. |

G11 is now **PARTIAL**, not BLOCKED: runtime and browser steps executed, but final browser POST, accepted verifier result, and Mongo-backed audit/restart evidence are absent. G12 remains **PARTIAL**: error recovery copy, same-prepared-presentation retry state and accessible live-announcement roles are implemented and compile, while revised-browser, responsive, visual, keyboard/screen-reader and contrast reviews remain open. Current tally is **5 PASS, 11 PARTIAL, 1 BLOCKED, 0 FAIL**; G14 is the remaining blocked gate. The temporary static nginx test server's 404 on direct `/wallet/consent` reload is not treated as a product web-server result; the actual Compose app loaded `/login`. Refer to [current test evidence](../docs/implementation/SECURE_SSI_PLATFORM_TEST_EVIDENCE.md) for exact commands and outputs.

## G12 keyboard focus continuation — 15 October 2026

The web stylesheet now supplies a 3 px amber `:focus-visible` outline with 3 px offset, including controls with inline `outline: none`. `npm run lint --prefix apps/web` passed, and `npm run build --prefix apps/web -- --configLoader runner` passed TypeScript and Vite (1,828 modules). The outline has not been visually or assistively verified in a browser; G12 remains PARTIAL. Normal-sandbox Docker calls were denied, but authorized read-only checks confirmed Docker 29.8.1, 7/7 healthy services in the isolated project, and five HTTP endpoints returning 200. No container was started, stopped, or recreated. The gate tally remains 5 PASS, 11 PARTIAL, 1 BLOCKED, 0 FAIL.

## G13 security hardening continuation — 15 October 2026

Default Compose ports are loopback-only. The Gateway rate limiter now caps its LRU client map at 10,000 entries and uses the socket peer, not forwarded headers, as the client identity. Current tests passed: Gateway security 9/9, Identity auth/credential/revocation 104/104, and Recovery API/proof/secret-redaction 14/14. Compose config validation passed and all seven resolved bindings were checked. Offline npm audit reported 0 vulnerabilities for the frontend lockfile; Ruff and a Python dependency scanner are unavailable. Authorized read-only checks confirmed the existing project runtime is 7/7 healthy and five HTTP endpoints return 200. No SAST, secret scan, independent penetration review, or formal critical/high triage ran. G13 remains PARTIAL; rate limiting and token revocation are process-local, and Identity/Recovery do not have standalone limiters. Current tally: 5 PASS, 11 PARTIAL, 1 BLOCKED, 0 FAIL.

## G11/G12 isolated Web URL correction — 15 October 2026

The static Web image in the isolated stack had the default localhost:8000 Gateway URL while this test project published Gateway on 18000. Docker build-argument support was added with the same default for normal Compose runs; the isolated Web image was rebuilt with 127.0.0.1:18000 and only the Web container was replaced. Its root, JavaScript and CSS assets returned 200; the bundle contains the correct API URL and keyboard-focus CSS. Compose returned to 7/7 healthy. The first web restart attempt merged base/test ports and conflicted on 3000; using ports replacement brought Web back without restarting dependencies. This fixes the isolated Compose login configuration, not the previously observed Vite Direct Post failure. G11/G12 remain PARTIAL pending browser authentication and UI review.


## G15 component benchmark continuation — 15 October 2026

Existing Identity, Fraud and Recovery performance tests passed 3/3, 1/1 and 1/1 tests. Identity Ed25519 signing and Fraud deterministic heuristic tests emit P50/P95/P99 and throughput JSON; Recovery emits mean/P95/max for 25 in-memory workflows with a fake key gateway. Exact results, commands and scope are recorded in the performance report and test evidence. No API load, concurrency, Mongo pool or reliability experiment ran; G15 remains PARTIAL.


## G16 documentation consistency checkpoint — 15 October 2026

Current README/architecture/profile/API and implementation inventory claims were reconciled with current code and gate evidence. Historical benchmark/demo and WP-03–WP-07 reports now identify their scope and date. Static local Markdown link check: 80 files, 201 relative targets, 0 missing; anchors, external links, clean setup/demo, and rendered UI were not checked. No thesis file is in the repository. G16 remains PARTIAL until thesis comparison and clean-environment demo reproduction are possible.
