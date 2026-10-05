# V2.1 WP-04 — OID4VP 1.0 + DCQL ENGINE REPORT
**Secure SSI Platform — Controlled Remediation**  
**Package:** WP-04 — OID4VP 1.0 Authorization Request & DCQL Query Engine  
**Normative Baseline:** OpenID for Verifiable Presentations 1.0 Final (OpenID Foundation)  
**Verification Level:** L3 VERIFIED  
**Date:** 2026-10-05  

---

## 1. Executive Summary

Work Package 04 (WP-04) replaces the legacy DIF Presentation Exchange v2 (`presentation_definition` / `input_descriptors`) query mechanism with the normative **OpenID4VP 1.0 Final** protocol profile utilizing **DCQL (Digital Credentials Query Language)**.

Prior to WP-04, the verifier generated draft-era Presentation Exchange structures that lacked typed credential queries, failed to enforce query matching against stored credentials, and allowed wallet presentations to proceed with uncontrolled credential substitution. In addition, the Verifier Portal UI falsely advertised "EUDI Wallet Uyumlu" despite using legacy Presentation Exchange and mock URIs.

Under WP-04:
1. **Canonical Protocol:** Verifier authorization requests generate typed OID4VP 1.0 requests containing `client_id`, `response_uri`, `response_type=vp_token`, `response_mode=direct_post`, `nonce`, `state`, and `dcql_query`.
2. **Typed DCQL Engine:** Introduced domain dataclasses (`DcqlQuery`, `DcqlCredentialQuery`, `DcqlClaimQuery`, `DcqlCredentialSet`) and an evaluation engine (`DcqlEngine`) with fail-closed matching against candidate credentials.
3. **Wallet Matching:** The Wallet evaluates DCQL queries deterministically against actual stored credentials and exposes query satisfaction, claim paths, and unmatched reasons via `POST /api/v1/oid4vp/requests/{session_id}/evaluate-dcql`.
4. **Verifier Response Processing:** In `process_direct_post`, DCQL satisfaction is evaluated against the presentation's verifiable credentials. DCQL failure fails closed and invalidates `crypto_valid`, precluding acceptance.
5. **Fail-Closed Security Hierarchy:** WP-01 (tampering, expired timestamps, replayed nonces), WP-02 (cryptographic holder binding, audience/domain verification), and WP-03 (authoritative Trust Registry issuer checks) remain 100% active and uncompromised.
6. **Legacy Isolation:** `presentation_definition` is demoted to a secondary backwards-compatibility artifact, isolated from the canonical evaluation path.
7. **UI Truthfulness:** Verifier Portal replaced misleading Presentation Exchange URIs with canonical DCQL query objects and truthful OID4VP 1.0 / DCQL terminology.

All 19 targeted WP-04 tests, all 232 integration tests, and all 227 unit tests pass with zero failures. Static analysis with Pyright yields 0 errors, 0 warnings, and 0 informations across all modified files.

---

## 2. Specification Classification Matrix

In accordance with Section 13 of the WP-04 directive, protocol elements and architectural layers are strictly classified as follows:

| Component / Layer | Classification | Rationale |
| :--- | :--- | :--- |
| **OpenID4VP 1.0 Final** | **NORMATIVE** | The governing international standard for verifiable presentation exchange. |
| **DCQL (Digital Credentials Query Language)** | **NORMATIVE** | The normative query syntax in the selected OID4VP 1.0 profile replacing DIF Presentation Exchange. |
| **Project Profile DCQL Subset** | **PROJECT PROFILE** | Selected features (`format`, `meta.type_values`, `claims[].path`, `claims[].values`, `credential_sets.options`) strictly necessary for W3C VC 2.0 with Data Integrity proofs. |
| **MongoDB / In-Memory Session Storage** | **IMPLEMENTATION CHOICE** | Persistence mechanism for OID4VP verification sessions and transaction state. |
| **Advanced Cryptographic Selective Disclosure (SD-JWT / BBS+)** | **OPTIONAL / FUTURE** | Not implemented in WP-04. The current baseline operates on W3C VC 2.0 Data Integrity (Ed25519) credentials. Claim minimization is handled via presentation metadata, not ZKP or BBS+. |

---

## 3. Existing Presentation Exchange Problem

The legacy system had critical deficiencies:
- **Loose Semantic Typing:** Verifier requests contained a JSON-encoded DIF Presentation Exchange v2 `presentation_definition` with `input_descriptors` and JSONPath strings (`$.credentialSubject.degree`).
- **No Protocol-Level Enforcement:** The verifier service did not evaluate whether the submitted credentials in the `vpToken` matched the requested input descriptors; it merely validated signatures and trusted any valid credential.
- **UI-Only Filtering:** Credential selection was deferred to wallet client UI logic rather than enforced deterministically by the verifier's policy engine.
- **False Claims:** The user interface labeled DIF PE queries as "EUDI Wallet Uyumlu" and claimed selective disclosure compliance without standards-aligned query structures.

---

## 4. Official OpenID4VP 1.0 Baseline & Project Profile

### 4.1 Normative Authorization Request Model
In the V2.1 project profile, authorization requests conform to OpenID4VP 1.0 Final:
- `client_id`: Verifier entity identifier or origin (`https://verifier.platform.eudi/auth`).
- `response_uri`: Verifier direct post endpoint (`/api/v1/oid4vp/response`).
- `response_type`: `vp_token`.
- `response_mode`: `direct_post`.
- `nonce`: Cryptographically random 128-bit hex string, bound to the single-use session.
- `state`: Verification session identifier (`session_{ObjectId}`).
- `dcql_query`: Standardized JSON object representing the credentials and claims requested.

### 4.2 DCQL Project Profile
To prevent over-engineering while satisfying all Golden Path scenarios, the DCQL implementation supports:
- **`credentials` list:**
  - `id`: Non-empty string identifying the query item (e.g., `query_1`).
  - `format`: Must be `w3c_vc` or `ldp_vc` (W3C Verifiable Credentials with Data Integrity proofs). Unsupported formats fail closed.
  - `meta.type_values`: Sequence of required credential type URIs/strings (e.g. `["UniversityAffiliationCredential"]`).
  - `claims`: Sequence of claim queries with `id`, `path` tuple (e.g., `("credentialSubject", "degree")`), and optional `values` constraint tuple.
- **`credential_sets` list:**
  - `options`: Tuple of tuples of query IDs defining satisfying combinations or alternatives (e.g., `(("query_1",), ("query_2",))`).
  - `required`: Boolean flag indicating whether satisfaction of the set is mandatory.
  - `purpose`: Human-readable description for holder consent.

Features intentionally **DEFERRED / UNSUPPORTED** in WP-04:
- Multiple nested JSONPath filter predicates beyond exact path tuples.
- Range, regex, or mathematical claim value filters (only exact set inclusion via `values` is supported).
- BBS+ / SD-JWT selective disclosure cryptographic proof handling (planned for future work packages).

---

## 5. Architectural Implementation

### 5.1 Domain Models (`app/domain/dcql.py` & `app/domain/oid4vp.py`)
- `DcqlClaimQuery`: Represents requested claim path and optional allowed values.
- `DcqlCredentialQuery`: Strongly typed query definition including query ID, format, type values, and claims.
- `DcqlCredentialSet`: Combinatorial grouping of query IDs allowing alternatives or multi-credential sets.
- `DcqlQuery`: Root query container with strict JSON deserialization and structural validation in `from_dict()`.
- `DcqlEvaluationResult`: Immutable evaluation outcome detailing satisfaction status, matched credentials, matched claim mappings, and explicit unsatisfied reasons.
- `VerificationSession`: Updated with `dcql_query: Mapping[str, Any]` and `to_authorization_request_uri()` generating standards-aligned `openid4vp://` URIs with query parameters.

### 5.2 DCQL Engine (`app/application/services/dcql_engine.py`)
- `extract_value_at_path(candidate, path)`: Safely traverses dictionary structures without code execution or unsafe eval.
- `evaluate_credential_query(query, candidate)`: Validates format, matches required `type_values`, extracts all requested claim paths, and verifies optional value constraints. Returns `(matched: bool, claims: dict, reason: str | None)`.
- `evaluate(query, candidate_credentials)`: Evaluates all candidates across all credential queries and evaluates `credential_sets` options. Fails closed if any required set or query cannot be satisfied.
- `build_dcql_query_from_types_and_fields(requested_types, requested_fields)`: Constructs canonical DCQL query objects with alternative options in `credential_sets` when multiple types are requested.
- `convert_legacy_presentation_definition_to_dcql(pe)`: Explicit legacy adapter translating DIF PE `input_descriptors` to DCQL.

### 5.3 Verifier Session & Direct Post (`app/application/services/oid4vp_service.py`)
- `create_session`: Accepts optional caller-provided `dcql_query` (validated with `DcqlQuery.from_dict`) or synthesizes a canonical DCQL query from requested types and fields.
- `evaluate_wallet_credentials`: Exposes session query evaluation to wallets prior to submission, allowing holder consent screens to present exact matching credentials and disclosed claims.
- `process_direct_post`: Extracts VCs from `vpToken`, evaluates them against `session.dcql_query` using `DcqlEngine.evaluate()`. Incorporates `dcql_satisfied` directly into the cryptographic validity invariant:
  ```python
  crypto_valid = (
      cred_valid
      and sig_valid
      and holder_binding_valid
      and issuer_trusted
      and expiry_valid
      and revocation_status_clear
      and challenge_valid
      and dcql_satisfied
      and not is_already_quarantined
  )
  ```
  If DCQL is unsatisfied, `finalPolicyResult` is set to `REJECTED`, and the detailed failure reason is recorded in audit logs and verification details.

### 5.4 Protocol State Machine
The verifier and wallet interact through the following state transitions:
1. `REQUEST_CREATED`: Verifier initializes session with `nonce`, `client_id`, and `dcql_query`.
2. `REQUEST_VALID`: Session persisted, authorization URI formed (`openid4vp://...`).
3. `PRESENTATION_REQUESTED`: Wallet scans QR / fetches authorization request.
4. `REQUEST_RESOLVED`: Wallet parses OID4VP parameters and extracts `dcql_query`.
5. `DCQL_MATCHED`: `DcqlEngine` evaluates wallet credentials. If satisfied, matched credentials/claims are identified; if not, state transitions to `REJECTED (UNSATISFIED_QUERY)`.
6. `AWAITING_HOLDER_CONSENT`: Wallet displays requested claims and verifier identity for user authorization.
7. `PRESENTATION_CREATED`: Holder creates W3C VP 2.0 with WP-02 cryptographic proof (`holder_did`, `challenge=nonce`, `domain=client_id`).
8. `PRESENTATION_SUBMITTED`: Wallet posts payload to `response_uri` via `direct_post`.
9. `PRESENTATION_VALIDATING`: Verifier executes 9-point verification checklist (DCQL satisfaction, WP-01 signature, WP-02 holder binding, WP-03 trust registry, challenge, revocation, expiry, AI risk).
10. `ACCEPTED` / `REJECTED`: Final policy result determined and session marked consumed (single-use replay prevention).

---

## 6. Security Analysis & Invariant Preservation

### 6.1 Cryptographic Failure Hierarchy Preservation
WP-04 strictly reinforces the fail-closed hierarchy established in WP-01 and WP-02:
- An unsatisfied DCQL query immediately sets `dcql_satisfied = False` and `crypto_valid = False`.
- Zero AI risk (risk score = 0) **cannot** override an unsatisfied DCQL query.
- Valid cryptographic signatures **cannot** pass if the presented credential does not satisfy the DCQL query.
- Tampered credentials, invalid holder binding, or untrusted issuers continue to fail closed regardless of query satisfaction.

### 6.2 Anti-Replay & Session Fixation Protection
- Nonces remain 128-bit entropy single-use values bound to individual verification sessions.
- Direct post responses referencing consumed or expired sessions are rejected immediately (HTTP 404 or `challengeValid=False`).
- Replay attempts of previously accepted presentations fail closed.

### 6.3 Fail-Closed DCQL Evaluation
- Malformed DCQL queries raise `MalformedDcqlQueryError` during session creation (HTTP 400).
- Queries specifying unknown credential formats (e.g., `unknown_crypto_v99`) fail matching with `Unsupported credential format`.
- Queries specifying missing claim paths fail matching with `Claim path '...' not present in credential`.
- Value constraints with mismatched values fail matching with `Claim '...' value does not match allowed values`.
- Empty credential lists fail matching with `NO_CANDIDATE_CREDENTIALS_AVAILABLE`.
- No fallback to `match=True` exists anywhere in the codebase.

---

## 7. Required DCQL Scenarios Evidence

All scenarios mandated in Section 7 of the WP-04 directive are fully implemented and verified:

| Scenario | Description | Test Name | Result |
| :--- | :--- | :--- | :--- |
| **Scenario A** | Single credential, specific claims (`degree`, `university`). | `test_wp04_scenario_a_single_credential_specific_claims` | **PASS** |
| **Scenario B** | Unsatisfied query: Wallet has University credential, Verifier requests Residence credential. Verifier receives explicit unsatisfied outcome. | `test_wp04_scenario_b_unsatisfied_query_no_accidental_presentation` | **PASS** |
| **Scenario C** | Multiple acceptable credentials: `credential_sets` with alternatives. Deterministic satisfying selection. | `test_wp04_scenario_c_credential_set_alternatives` | **PASS** |
| **Scenario D** | Claim value matching: Exact allowed value matching and mismatch failure. | `test_wp04_scenario_d_claim_value_matching` | **PASS** |
| **Scenario E** | Unknown credential format: Unsupported format fails closed safely. | `test_wp04_scenario_e_unknown_credential_format_rejected` | **PASS** |
| **Scenario F** | Malformed DCQL: Syntax errors, missing IDs, or malformed dictionaries rejected safely without crashing. | `test_wp04_scenario_f_malformed_dcql_rejected_safely` | **PASS** |
| **Scenario G** | PE legacy request migration: DIF PE input descriptors converted to DCQL; canonical path remains DCQL. | `test_wp04_scenario_g_pe_legacy_migration_and_conversion` | **PASS** |

---

## 8. UI Truthfulness Modifications

In `apps/web/src/components/portals/VerifierPortal.tsx`:
1. **Replaced Legacy PE URI:**
   - *Previous:* `openid4vp://authorize?...presentation_definition={"id":"eudi_verify_req","input_descriptors":[...]}`
   - *Updated:* `openid4vp://authorize?...response_type=vp_token&response_mode=direct_post&nonce=...&dcql_query=${encodeURIComponent(JSON.stringify(dcqlQueryObj))}`
2. **Replaced Misleading Badges:**
   - *Previous:* "EUDI Wallet Uyumlu"
   - *Updated:* "OID4VP 1.0 / DCQL Uyumlu"
3. **Preserved UI Constraints:**
   - No global redesign, no landing page overhaul, no styling regressions.

---

## 9. Test Matrix & Verification Results

### 9.1 Targeted WP-04 Suite (`test_wp04_oid4vp_dcql.py`)
19 integration tests executed via pytest:
- `test_wp04_verifier_request_generates_canonical_dcql_query`: **PASSED**
- `test_wp04_verifier_request_with_explicit_dcql_query`: **PASSED**
- `test_wp04_verifier_request_with_malformed_dcql_query_fails_closed`: **PASSED**
- `test_wp04_scenario_a_single_credential_specific_claims`: **PASSED**
- `test_wp04_scenario_b_unsatisfied_query_no_accidental_presentation`: **PASSED**
- `test_wp04_scenario_c_credential_set_alternatives`: **PASSED**
- `test_wp04_scenario_d_claim_value_matching`: **PASSED**
- `test_wp04_scenario_e_unknown_credential_format_rejected`: **PASSED**
- `test_wp04_scenario_f_malformed_dcql_rejected_safely`: **PASSED**
- `test_wp04_scenario_g_pe_legacy_migration_and_conversion`: **PASSED**
- `test_wp04_wallet_evaluation_api_satisfied`: **PASSED**
- `test_wp04_wallet_evaluation_api_unsatisfied`: **PASSED**
- `test_wp04_direct_post_satisfying_dcql_accepted`: **PASSED**
- `test_wp04_direct_post_mismatched_credential_type_fails_closed`: **PASSED**
- `test_wp04_direct_post_missing_required_claim_fails_closed`: **PASSED**
- `test_wp04_security_regression_invalid_signature_fails_closed`: **PASSED**
- `test_wp04_security_regression_wrong_nonce_fails_closed`: **PASSED**
- `test_wp04_security_regression_wrong_holder_key_fails_closed`: **PASSED**
- `test_wp04_security_regression_untrusted_issuer_fails_closed`: **PASSED**

**WP-04 Result: 19 / 19 PASSED (100%)**

### 9.2 Full Regression Suite
- **Identity Service Integration Tests:** 232 passed, 12 skipped (Mongo integration requiring live cluster), 0 failed.
  - WP-01 Fail-Closed Verification: 11 / 11 passed.
  - WP-02 Cryptographic Holder Binding: 14 / 14 passed.
  - WP-03 Authoritative Trust Registry: 16 / 16 passed.
  - Golden Path, OID4VP AI Policy Matrix, Revocation, Holder Wallet: All passed.
- **Identity Service Unit Tests:** 227 passed, 0 failed.
- **Total Test Count:** 459 passing tests.

### 9.3 Static Analysis & Type Checking
Executed command:
```bash
npx pyright \
  services/identity-service/app/domain/dcql.py \
  services/identity-service/app/application/services/dcql_engine.py \
  services/identity-service/app/domain/oid4vp.py \
  services/identity-service/app/schemas/oid4_api.py \
  services/identity-service/app/infrastructure/persistence/oid4vp_repository.py \
  services/identity-service/app/application/services/oid4vp_service.py \
  services/identity-service/app/api/v1/oid4vp.py \
  services/identity-service/tests/integration/test_wp04_oid4vp_dcql.py
```
**Result:** `0 errors, 0 warnings, 0 informations` across all modified production files and test suites. No `# type: ignore` or `# pyright: ignore` suppressions were introduced.

---

## 10. Files Changed

### Production Code:
1. `services/identity-service/app/domain/dcql.py`: Strongly typed DCQL domain models and exceptions.
2. `services/identity-service/app/application/services/dcql_engine.py`: DCQL query evaluation engine, path extraction, and legacy conversion utility.
3. `services/identity-service/app/domain/oid4vp.py`: Added `dcql_query` to `VerificationSession` and updated `to_authorization_request_uri()`.
4. `services/identity-service/app/schemas/oid4_api.py`: Added `dcql_query` to session requests/responses and introduced `EvaluateDcqlRequest`/`EvaluateDcqlResponse`.
5. `services/identity-service/app/infrastructure/persistence/oid4vp_repository.py`: Added MongoDB BSON persistence for `dcqlQuery` with backward compatibility decoding.
6. `services/identity-service/app/application/services/oid4vp_service.py`: Added DCQL query generation, wallet credential evaluation, and direct post DCQL enforcement.
7. `services/identity-service/app/api/v1/oid4vp.py`: Added `dcql_query` validation on session creation and new endpoint `POST /api/v1/oid4vp/requests/{session_id}/evaluate-dcql`.
8. `apps/web/src/components/portals/VerifierPortal.tsx`: Replaced legacy PE QR URI with canonical DCQL query and updated UI labeling.

### Test Code:
9. `services/identity-service/tests/integration/test_wp04_oid4vp_dcql.py`: 19 comprehensive automated integration tests for protocol, engine, API, scenarios A-G, and security regressions.

---

## 11. Known Limitations & Deferred Work

1. **Selective Disclosure Cryptography:** Advanced selective disclosure algorithms such as BBS+ (W3C BBS Cryptosuite v1.0) and SD-JWT (RFC draft) are deferred to future cryptographic work packages. DCQL in WP-04 selects and enforces credentials and claim paths, but does not construct cryptographic zero-knowledge proofs.
2. **External Interoperability Evidence (L4):** While the DCQL implementation conforms strictly to OpenID4VP 1.0 Final and walt.id Verifier2/Wallet2 models, external interop testing against third-party conformant wallets (e.g. EU Digital Identity Wallet reference apps) has not yet been executed in a live cross-domain environment. Per project rules, this package is certified **L3 VERIFIED** (comprehensive internal automated validation), not L4.
3. **Full Trust & Status Policy Matrix:** Deeper integration of status lists and dynamic accreditation rules into cross-domain policies remains scheduled for WP-08.

---

## 12. Final Acceptance Decision

**WP-04 STATUS: L3 VERIFIED**

All criteria specified in Section 12 ("Acceptance Gate — WP-04 = L3 VERIFIED") of the authoritative directive have been completely satisfied:
- Canonical verifier requests use OID4VP 1.0 semantics with `dcql_query`.
- Typed DCQL model is implemented and enforced.
- Wallet evaluates DCQL against stored credentials; satisfied/unsatisfied states are explicit.
- Fail-closed security and previous work packages (WP-01, WP-02, WP-03) remain fully intact.
- DIF Presentation Exchange is removed from the canonical path.
- UI truthfulness updates applied; no false EUDI/ZKP claims.
- 100% test pass rate across all suites; 0 Pyright errors/warnings/infos.
- Next permitted work package: WP-05.
