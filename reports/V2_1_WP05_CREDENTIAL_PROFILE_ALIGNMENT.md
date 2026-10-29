# V2.1 WP-05 — Credential Profile Alignment Follow-up

**Checkpoint:** 24 October 2026
**Branch:** `besna-dev`
**Source before this follow-up:** `5c283791e8440ca582b990383f129e9e09dd7574`
**Decision:** **PARTIAL** — metadata, offer allowlisting, and code-level context/type pairing are aligned for the two configured profiles; focused unit tests pass, while HTTP issuance and full Identity regression remain blocked on this Windows host.

## Confirmed mismatch

The issuer metadata advertised four configurations: University Affiliation, QEAA, National ID, and Driver License. The validator accepted only University Affiliation and QEAA, and issuance stamped every type with the University context. This meant metadata claimed configurations for which no code-level profile existed, and QEAA issuance used a context that did not match its type.

The revised V2.1 profile says demo credential types must remain allowlisted and verifier logic must not assume only one credential type when DCQL constrains it. The implementation now shares an explicit type-to-context map between validation and issuance. Metadata advertises only those two configured types; unsupported National ID and Driver License identifiers are rejected at offer creation rather than emitted under the wrong profile. This does not represent government credential issuance or integration.

## Standards basis and profile boundary

- **W3C Verifiable Credentials Data Model 2.0**, W3C Recommendation of 15 May 2025: sections 4.3 and 4.5 require a credential context and type information; the base VC v2 context is first, and the subtype is used to identify the intended credential profile. The project pins exact type/context pairs in its validator. [Official Recommendation](https://www.w3.org/TR/vc-data-model-2.0/)
- **OpenID for Verifiable Credential Issuance 1.0**, Final, published 16 September 2025: section 12.2.4 and Appendix A.1.2.2 specify `credential_definition` for `ldp_vc` issuer metadata, including `@context` and `type`. Metadata now emits those fields from the same type/context allowlist used by the validator. [Official Final specification](https://openid.net/specs/openid-4-verifiable-credential-issuance-1_0.html)

The contexts use the repository's prototype `secure-ssi.example` identifiers. This run did not establish that these contexts are publicly hosted or that an independent wallet can resolve and process them. The validator's QEAA branch accepts scalar subject claims; this is not an externally interoperable, accredited QEAA schema. The supported types are a project-local demo profile, not national identity or qualified-attestation integration.

## Changes

- `services/identity-service/app/services/credential_validator.py` now validates the exact type/context pair for the code-level University and QEAA profiles. University claim restrictions remain; QEAA subject claims remain scalar-only.
- `services/identity-service/app/application/services/oid4vci_service.py` derives the issued context from the profile map, advertises only configured types, emits OID4VCI `ldp_vc` `credential_definition` context/type metadata, and fails closed if an unconfigured type appears in an offer or persisted issuance path.
- `services/identity-service/app/api/v1/oid4vci.py` returns HTTP 422 for an unsupported credential profile in an offer.
- Added unit coverage for profile contexts, metadata/profile agreement, supported QEAA subject shape, and rejection of unsupported types. Added HTTP integration regression cases for metadata, unsupported offers, and QEAA issuance.

No dependency, cryptographic suite, trust-registry rule, storage schema, or OpenID protocol contract was changed.

## Verification

| Command / observation | Result | Boundary |
|---|---|---|
| From repository root: `python -m py_compile services/identity-service/app/services/credential_validator.py services/identity-service/app/application/services/oid4vci_service.py services/identity-service/app/api/v1/oid4vci.py services/identity-service/tests/test_credential_validator.py services/identity-service/tests/unit/test_oid4vci_credential_profiles.py services/identity-service/tests/integration/test_wp05_oid4vci_token_and_proof.py` | Exit 0 | Python syntax check only. |
| CWD `services/identity-service`: `..\..\.venv\Scripts\python.exe -m pytest -q tests/test_credential_validator.py tests/unit/test_oid4vci_credential_profiles.py` | **30 passed, 0 failed, 0 skipped; 1 SQLite deprecation warning; exit 0.** | Current-source profile, metadata, and validator unit tests. |
| From `services/identity-service`: `..\..\.venv\Scripts\python.exe -m pytest -q tests/integration/test_issuance_interoperability.py tests/integration/test_credential_proof_service.py` | **29 passed, 2 errors; exit 1.** Both errors occurred during `tmp_path` setup because the sandbox denied creating a pytest temp directory under its AppData Temp path. | The tests did not reach application assertions in those two cases. |
| CWD `services/identity-service`; resolved `$repo = (Resolve-Path ..\..).Path`; `..\..\.venv\Scripts\python.exe -m pytest -q --basetemp=$tempPath tests/integration/test_credential_proof_service.py -k 'test_key_substitution_via_did_document_is_rejected or test_non_ed25519_did_verification_method_is_rejected'`, where `$tempPath = Join-Path $repo '.codex-pytest-wp05-temp'` | **2 passed, 0 failed, 27 deselected; 1 warning; exit 0.** | The temporary directory was created under the repository, resolved/checked inside it, then removed. Filtered retry of the two setup errors above. |
| CWD `services/identity-service`: `..\..\.venv\Scripts\python.exe -m pytest -q tests/integration/test_wp05_oid4vci_token_and_proof.py -k 'metadata_advertises_token_and_nonce_endpoints or offer_rejects_unconfigured_credential_profiles or qeaa_issuance_uses_the_validator_pinned_context'` | Interrupted after 10 seconds with no pytest summary; no pass/fail/skip count; exit 1 after Ctrl+C. | TestClient stalled in the Windows async/loopback startup path. The metadata HTTP and issuance integration assertions are **BLOCKED**, not PASS. |
| `docker version --format 'Client={{.Client.Version}} Server={{.Server.Version}}'` | Client 29.8.1; server unavailable; Docker API returned named-pipe `permission denied`. | No current-source image rebuild or container regression was run. |

## Acceptance boundary

The code-level profile/metadata inconsistency is corrected and the new OID4VCI metadata fields are covered by service unit assertions. The complete WP-05 token/proof/credential HTTP regression set was not rerun to a valid summary after this change. WP-05 therefore remains **PARTIAL for final source** until the targeted HTTP issuance regression, current full Identity suite, and current-source Docker verification can run. Independent issuer interoperability, government integration, an externally hosted custom context, and certification are not claimed.

## 25 October 2026 — current-source verification addendum

This update supersedes the 24 October statement that WP-05 HTTP issuance and current Docker verification remained blocked. No application code or dependency version changed during this verification; the existing test changes align fixtures and assertions with current validation/error-envelope behavior.

- Host targeted command from `services/identity-service`: `python -m pytest -q tests/integration/test_wp05_oid4vci_token_and_proof.py` — **22 passed, 0 failed, 0 skipped, 4 warnings**, exit 0.
- Eight-file current Identity security/protocol regression — **125 passed, 0 failed, 0 skipped, 4 warnings**, exit 0. Full Identity suite — **719 passed, 0 failed, 12 environment-gated skips, 7 warnings**, exit 0.
- In the rebuilt current-source Identity container, the focused WP-05/WP-08/OID4VP command passed **74 tests, 0 failed, 0 skipped, 2 warnings**, exit 0. The same container's unauthenticated protected OID4VP session request returned HTTP 401.
- Five application images were rebuilt with `--no-cache` from the current working tree and only those five services were recreated. The seven-service Compose project reported all services healthy; MongoDB/Redis containers and volumes were preserved.
- The complete authorized root Python runner also completed: **834 passed, 13 environment-gated skipped, 266 passing subtests, 0 failed**, exit 0. This is separate from and not added to the Identity/Docker test counts.

WP-05's code-level profile and HTTP integration behavior has current-source test evidence, so the former Windows TestClient blocker is no longer applicable to this execution. The configured University and QEAA types remain prototype profiles; public context resolution, independent issuer/wallet interoperability, accredited QEAA semantics, external conformance and production use remain unverified. Accordingly WP-05 remains **PARTIAL** for the broader package/interoperability scope, rather than being represented as fully interoperable.

The rebuilt Docker Web bundle and the host Node 24 production bundle have different filenames, sizes and SHA-256 values; byte-for-byte equivalence is **not established**. The Dockerfile uses Node 20 Alpine while the host used Node 24.19.0; that difference is a hypothesis, not a demonstrated cause. OCI revision/source labels are absent on all five images. No packages or lockfiles were changed. One authorized online npm audit found React Router 6.30.6 (through react-router-dom 6.30.6) with two moderate advisories and a major upgrade path to react-router-dom 7.18.4, plus Vite 6.4.3 with moderate/high advisories and a fix available but no exact fixed version in the audit output. Remediation remains separate and open.
