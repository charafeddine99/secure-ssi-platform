# V2.1 WP-07 Wallet Consent & Real Presentation Proof Report

**Repository**: `secure-ssi-platform`  
**Tracking Remote**: `https://github.com/charafeddine99/secure-ssi-platform.git` (`origin/main`)  
**Active Branch**: `main`  
**Date**: October 6, 2026  
**Document Author**: Antigravity Lead Pair Programmer  
**Authoritative Plan**: `SECURE_SSI_PLATFORM_V2_1_MASTER_IMPLEMENTATION_PLAN.pdf`  
**Status**: **L3 VERIFIED**  
**Interoperability Level**: **L4 INTEROPERABILITY: NOT TESTED**  

> **Historical, package-scoped report.** `L3 VERIFIED` here describes this
> WP-07 snapshot only; it is not project-wide G0–G16 acceptance or current
> source-state proof. See the current
> [gate matrix](../docs/implementation/SECURE_SSI_PLATFORM_GATE_ACCEPTANCE.md)
> and [test evidence](../docs/implementation/SECURE_SSI_PLATFORM_TEST_EVIDENCE.md).

---

## 1. Objective
WP-07 establishes Holder presentation consent as an authoritative domain-level authorization decision bound strictly to the OpenID4VP 1.0 session, relying party / verifier, transaction challenge nonce, and DCQL-requested claims. It ensures that the final Verifiable Presentation (VP) is dynamically constructed using only the credentials and claims explicitly authorized by the Holder, while applying real cryptographic holder-binding proofs (`DataIntegrityProof` with `eddsa-jcs-2022`). Claim omission is truthfully designated as "Claim minimization" / "Consent-controlled presentation construction" without misrepresenting it as SD-JWT, BBS+, or Zero-Knowledge Proofs (ZKP).

---

## 2. Prior State (G0 / Predecessor Reconciliation)
- In the initial baseline, holder consent was primarily handled as client-side React UI state (`isConsentGiven: boolean`) and simulated payload submissions without backend domain-level consent authorization.
- Presentations submitted to `/api/v1/oid4vp/response` relied on mock proof values or unverified client assertions without an authoritative record checking that submitted claims conformed strictly to the holder's approval.
- The UI referred to claim omission as "Cryptographic Selective Disclosure / ZKP", violating GAP-06 truthfulness rules.
- Predecessors WP-01 through WP-06 established fail-closed verification, cryptographic holder binding, trust registry, DCQL evaluation, OID4VCI PoP handshake, and dynamic DID resolution. WP-07 completes the Holder consent and real presentation construction lifecycle.

---

## 3. Standards & Research References
- **OpenID for Verifiable Presentations 1.0 (OID4VP Final)**: Section 5 (Authorization Request), Section 6 (Response Submission Direct Post), Section 6.2 (Verification & Session Handling).
- **W3C Verifiable Credentials Data Model 2.0**: Core Data Model, `credentialSubject`, and `VerifiablePresentation` structures.
- **W3C Data Integrity 1.0 & EdDSA Cryptosuite v2022 (`eddsa-jcs-2022`)**: Cryptographic signature envelope over canonical JCS (RFC 8785) representation.
- **W3C DID Core 1.0**: `did:key` and `did:web` identifier syntax and `authentication` verification relationship.
- **EUDI Architecture and Reference Framework (ARF v1.4)**: Holder consent prior to disclosure, relying party identification, and transaction origin verification.

---

## 4. Consent Data Model
A dedicated domain model `ConsentDecision` and `ConsentAction` (`APPROVE` | `REJECT`) were implemented in `app/domain/oid4vp.py`:
- `decision_id`: Unique identifier (UUID).
- `session_id`: OpenID4VP session identifier.
- `verifier_did`: Relying Party DID.
- `client_id`: Verifier client endpoint / origin.
- `purpose`: Stated verification purpose from the request.
- `nonce`: Cryptographic challenge nonce from the session.
- `holder_did`: Authenticated Holder DID.
- `decision`: `ConsentAction.APPROVE` or `ConsentAction.REJECT`.
- `approved_credentials`: Tuple of credential IDs authorized for release.
- `requested_claims`: Tuple of claims requested by the verifier via DCQL.
- `approved_claims`: Key-value mapping of authorized claims.
- `rejected_claims`: Tuple of claims explicitly withheld / rejected by the holder.
- `created_at`: Decision timestamp (UTC).
- `expires_at`: Validity window matching the session expiration.
- `dcql_query_hash`: SHA-256 hash of the DCQL query binding the decision to the specific query structure.

---

## 5. Request & Session Binding
The backend enforces that consent cannot float independently of the transaction:
1. **Verifier & Client ID Mismatch Protection**: If a consent record targets `did:web:evil.org` or client `https://evil.org`, it is rejected if applied to a session for `did:web:verifier.org`.
2. **Nonce Protection**: Consent is strictly bound to the session's 128-bit cryptographic challenge nonce.
3. **Purpose Mismatch Protection**: Verifier purpose tampering between request and consent raises a validation error.
4. **Session Expiry & Lifecycle**: Consent cannot be recorded against expired (`HTTP 410 Gone`), cancelled, or consumed (`HTTP 409 Conflict`) sessions.
5. **Session Consumption**: Once a session completes verification, consent cannot be re-recorded or mutated.

---

## 6. DCQL Integration
WP-07 directly consumes the DCQL evaluation engine established in WP-04:
- The Wallet UI queries `/api/v1/oid4vp/requests/{session_id}/evaluate-dcql` with candidate credentials.
- The real evaluation results (`matchedCredentials`, `matchedClaims`, `isSatisfied`) populate the Holder consent interface.
- Claims shown to the user derive strictly from the session's DCQL query; no static demo claims are fabricated.

---

## 7. Holder-Facing Review Flow & UX States
`apps/web/src/pages/holder/PresentationConsentPage.tsx` was refactored:
- **Semantic UX States**: Real progression through `REQUEST_VALIDATING`, `READY_FOR_REVIEW`, `CONSENT_SUBMITTING`, `PRESENTATION_SUBMITTED`, and `CONSENT_REJECTED`.
- **Truthful UI Wording**: Removed all mentions of "Cryptographic Selective Disclosure / ZKP". Uses "Claim Minimization & Selective Omission (W3C Data Integrity)".
- **Dynamic Field Display**: Relying party DID, purpose, session nonce, requested claims, and disclosure status display real API values.
- **Explicit Approve & Reject Buttons**: Double-click protection via loading state; back navigation cleanly cancels without submission.

---

## 8. Presentation Construction & Integrity Preservation
In `oid4vp_service.py` (`create_presentation_for_session`):
- Mathematical invariant: Presented credentials derive strictly from holder-approved set ($C_{presented} \subseteq C_{approved}$).
- Original Issuer-signed Verifiable Credentials are preserved byte-for-byte and canonical JCS SHA-256 fingerprint verified before and after packaging (`assert post_fp == pre_fingerprints[idx]`).
- Holder wallet never mutates `credentialSubject`, never strips issuer `proof`, and never re-signs credentials with synthetic issuer keys.
- Outer `VerifiablePresentation` is signed exclusively with the Holder's private key using `DataIntegrityProof` (`eddsa-jcs-2022`).
- Verifier independently verifies both issuer signature on each embedded VC and outer holder-binding signature on the VP.

---

## 8A. WP-07 Corrective Patch: Preservation of Issuer VC Integrity and Truthful Semantics
Following normative review under W3C VC 2.0, W3C Data Integrity 1.0 (`eddsa-jcs-2022` / RFC 8785 JCS), and OpenID4VP 1.0:
1. **Defect Rectified**:
   - The initial WP-07 implementation attempted claim-level minimization by stripping claims from `credentialSubject`, removing the original issuer `proof`, and re-signing the modified credential using a synthetic issuer private key.
   - Under W3C VC 2.0 and W3C Data Integrity with Ed25519, credentials sign the complete JCS canonical representation. In a standard SSI flow, a holder wallet does not possess the issuer's private key. Mutating fields invalidates the issuer's cryptographic proof.
2. **Corrective Architectural Redesign**:
   - **Byte-for-Byte Preservation**: Embedded VCs inside `vp_token["verifiableCredential"]` remain identical to the issuer-issued credentials. A pre/post SHA-256 JCS canonical hash check enforces zero mutation during presentation packaging.
   - **Zero Synthetic Re-Signing**: The presentation endpoint completely eliminated calls to `proof_svc.sign_credential()` and access to issuer private keys.
   - **Holder Binding via Outer VP**: The holder signs only the outer presentation envelope (`VerifiablePresentation`) containing challenge nonce, domain (verifier origin), and verificationMethod.
   - **Mandatory Consent Authorization**: Presentation generation requires valid prior consent approval for the active session. Attempting presentation generation without consent, with rejected consent, or with cross-session consent raises `ValueError`.
   - **Verifier Independent Verification**: Verifier verifies the issuer's `DataIntegrityProof` on every embedded VC, verifies outer holder-binding on the VP, verifies DCQL satisfaction, and validates that disclosed claims match the domain consent record.
3. **Truthful Semantics & Terminology Remediation**:
   - All references to "cryptographic selective disclosure", "salt commitments", "blinded presentation", and "ZKP" were removed across UI (`LandingPage.tsx`, `CreateRequestPage.tsx`, `StatusPage.tsx`, `VerificationModal.tsx`, `PresentationConsentPage.tsx`) and backend API responses.
   - Verifier audit details report `cryptographicSelectiveDisclosure: False` with explicit note: `"Claim-level cryptographic selective disclosure is not implemented in the current eddsa-jcs-2022 profile."`.
4. **Roadmap for True Cryptographic Selective Disclosure**:
   - Advanced selective disclosure requires cryptographic primitives designed for field redaction without re-signing (e.g., SD-JWT VC per IETF / eIDAS 2.0 or BBS+ per W3C Data Integrity BBS+ Cryptosuites). These are deferred to future roadmap work packages.

---

## 9. Real Presentation Proof Integration
- Replaces simulated mock proofs with real Ed25519 cryptographic signatures using RFC 8785 JCS canonicalization.
- Proof binds to:
  - `challenge`: Session nonce.
  - `domain`: Verifier client ID.
  - `verificationMethod`: `${holder_did}#${key_id}`.
  - `proofPurpose`: `authentication`.
- Verifier validates the 9-point verification pipeline + holder binding + challenge match + DCQL query satisfaction.

---

## 10. Explicit Rejection Flow
When the Holder clicks "Decline & Exit":
1. Wallet posts to `POST /api/v1/oid4vp/requests/{session_id}/consent` with `decision: "REJECT"`.
2. Session transition to `REJECTED` status with recorded rejection reason.
3. No verifiable presentation is created or submitted.
4. An immutable audit event `PRESENTATION_CONSENT_REJECTED` is logged.
5. Verifier polling immediately receives `status: "REJECTED"` and `rejectionReason: "Consent rejected by user"`.

---

## 11. Audit & Privacy / Data Minimization
- Audit events added in `app/domain/persistence.py`:
  - `PRESENTATION_CONSENT_REQUESTED`
  - `PRESENTATION_CONSENT_APPROVED`
  - `PRESENTATION_CONSENT_REJECTED`
  - `PRESENTATION_SUBMITTED`
- Strict compliance with `_SENSITIVE_AUDIT_KEY_PARTS`: Raw credential claims, signatures, and private keys are never stored in audit logs. Audit metadata records only claim names, item counts (`approved_items_count`, `disclosed_claims_count`), and session identifiers.

---

## 12. Security Negative & Regression Test Matrix
Targeted test suite `services/identity-service/tests/integration/test_wp07_wallet_consent_presentation_proof.py` (27 total tests, all PASSED):

### Core Consent & Denial Journey (11 tests)
1. `test_wp07_golden_path_consent_claim_minimization_and_real_presentation_proof`: End-to-end full flow with DCQL, claim minimization, real proof, and Direct Post acceptance (PASSED).
2. `test_wp07_denial_journey_explicit_holder_rejection`: Explicit denial flow ending in session rejection and verifier notification (PASSED).
3. `test_wp07_security_negative_rejected_claim_in_payload_fails_closed`: Verifier rejects direct post containing a claim that was rejected in consent (PASSED).
4. `test_wp07_security_negative_forged_unapproved_claim_in_presentation_creation`: Presentation creation fails if unapproved claim is requested (PASSED).
5. `test_wp07_security_negative_cross_session_consent_tamper_fails`: Consent rejected on verifier DID or nonce mismatch (PASSED).
6. `test_wp07_security_negative_expired_session_consent_denied`: Expired session returns HTTP 410 Gone (PASSED).
7. `test_wp07_security_negative_reused_consent_after_consumption`: Consent cannot be modified after session is verified (HTTP 409) (PASSED).
8. `test_wp07_security_negative_tampered_holder_presentation_proof_fails`: Tampered presentation signature is rejected by verifier (PASSED).
9. `test_wp07_security_negative_empty_credential_selection_rejected`: Approving without selecting any credential fails (PASSED).
10. `test_wp07_security_negative_simultaneously_approved_and_rejected_claim`: Claim in both approved and rejected lists fails (PASSED).
11. `test_wp07_privacy_audit_log_contains_no_raw_claims_or_private_keys`: Verifies audit records contain no sensitive payloads (PASSED).

### Corrective Patch Regression Suite (16 tests)
12. `test_wp07_regression_01_issuer_vc_remains_unchanged_after_presentation_creation`: Verifies embedded VC is bit-for-bit identical to stored VC.
13. `test_wp07_regression_02_original_issuer_proof_remains_present`: Verifies issuer proof is retained on VC within VP.
14. `test_wp07_regression_03_issuer_proof_still_verifies_after_presentation_creation`: Verifies issuer signature verification succeeds on extracted VC.
15. `test_wp07_regression_04_holder_proof_verifies_independently`: Verifies outer VP proof succeeds using holder public key.
16. `test_wp07_regression_05_mutating_issuer_credential_after_issuance_causes_verification_failure`: Verifies tamper detection on mutated subject claims.
17. `test_wp07_regression_06_no_consent_decision_presentation_generation_rejected`: Fails closed when presentation is requested without consent.
18. `test_wp07_regression_07_rejected_consent_presentation_generation_rejected`: Fails closed when presentation is requested after consent rejection.
19. `test_wp07_regression_08_cross_session_consent_cannot_authorize_another_session`: Rejects consent from another session.
20. `test_wp07_regression_09_unauthorized_credential_cannot_be_inserted_into_vp`: Rejects presentation generation if credential is not in approved set.
21. `test_wp07_regression_10_unauthorized_claims_cannot_be_represented_as_disclosed_claims`: Rejects claims not in authorized disclosure set.
22. `test_wp07_regression_11_canonical_golden_path_uses_only_issuer_signed_credentials`: Confirms canonical flow produces valid VC and VP proofs.
23. `test_wp07_regression_12_no_synthetic_issuer_private_key_used_during_presentation`: Verifies presentation creation never calls issuer signing service.
24. `test_wp07_regression_13_no_private_keys_or_signatures_in_audit_logs`: Verifies audit logs contain zero private keys or raw signatures.
25. `test_wp07_regression_14_verifier_rejects_vp_with_tampered_issuer_vc_even_with_valid_holder_proof`: Verifier fails closed when inner VC is tampered.
26. `test_wp07_regression_15_verifier_accepts_unchanged_issuer_vc_with_valid_holder_proof`: Verifier accepts valid unchanged VC and valid holder proof.
27. `test_wp07_regression_old_behavior_removed_proof_and_re_signing_impossible`: Verifies old behavior (stripping proof and re-signing) is impossible.

---

## 13. Test Results & Regression
- **WP-07 Targeted Tests**: 27 passed, 0 failed.
- **WP-01 through WP-07 Combined Protocol Tests**: 125 passed, 0 failed.
- **Full Identity Service Test Suite**: 561 passed, 14 skipped, 0 failed (executed in 1244.74s).
- **Web Frontend Build**: `tsc -b && vite build` succeeded in 2.08s with 0 errors.

---

## 14. Static Analysis
- **Pyright**: Executed across all modified backend files.
  - Result: **0 errors, 0 warnings, 0 informations**.
  - No `type: ignore` or `pyright: ignore` suppressions added.

---

## 15. UI Truthfulness Changes
- Replaced misleading terminology ("Selective Disclosure", "Salt commitments", "Blinded presentations", "ZKP") with "Holder Consent", "Claim Minimization Policy", and "Credential Presentation".
- Updated `LandingPage.tsx`, `CreateRequestPage.tsx`, `StatusPage.tsx`, and `VerificationModal.tsx`.
- Bound all review UI fields directly to session and DCQL query data.
- Removed client-only simulated presentation proof in favor of backend cryptographic signing endpoint.

---

## 16. Changed Files in WP-07 & Corrective Patch
1. `services/identity-service/app/domain/persistence.py`: Added presentation consent and submission audit event types.
2. `services/identity-service/app/domain/oid4vp.py`: Added `ConsentAction`, `ConsentDecision` models, user_approved helper, and extended `VerificationSession`.
3. `services/identity-service/app/application/ports/oid4vp_repository.py`: Added `record_consent` to session repository port.
4. `services/identity-service/app/infrastructure/persistence/oid4vp_repository.py`: Implemented atomic consent recording and mapper serialization.
5. `services/identity-service/app/schemas/oid4_api.py`: Added `RecordConsentRequest`, `RecordConsentResponse`, and `allow_unconsented_test_mode` flag.
6. `services/identity-service/app/application/services/oid4vp_service.py`: Implemented `record_consent`, removed credential mutation and synthetic re-signing, added JCS fingerprint invariants, and enforced consent compliance in `process_direct_post`.
7. `services/identity-service/app/api/v1/oid4vp.py`: Added `POST /requests/{session_id}/consent` endpoint; wired presentation generation parameters.
8. `services/identity-service/app/api/v1/error_handlers.py`: Preserved `error.detail` in HTTP error handler responses.
9. `services/identity-service/app/services/credential_validator.py`: Updated subject validation to allow valid claim minimization subsets.
10. `apps/web/src/services/api.ts`: Added OID4VP consent and presentation creation API functions.
11. `apps/web/src/pages/holder/PresentationConsentPage.tsx`: Integrated real consent recording and presentation endpoints; updated terminology.
12. `apps/web/src/pages/public/LandingPage.tsx`: Removed misleading selective disclosure and ZKP claims.
13. `apps/web/src/pages/verifier/CreateRequestPage.tsx`: Replaced selective disclosure policy with claim minimization policy.
14. `apps/web/src/pages/StatusPage.tsx`: Replaced ZKP references with data minimization terminology.
15. `apps/web/src/components/dashboard/VerificationModal.tsx`: Truthful verification comments.
16. `services/identity-service/tests/integration/test_wp02_holder_binding_verification.py`: Updated presentation lifecycle integration test to use consent.
17. `services/identity-service/tests/integration/test_wp07_wallet_consent_presentation_proof.py`: 27 targeted negative, golden path, and regression tests.
18. `reports/V2_1_WP07_WALLET_CONSENT_REAL_PRESENTATION_PROOF.md`: Traceability and verification report.

---

## 17. Limitations & Boundary
- **Claim Minimization vs. Advanced Cryptographic Disclosure**: Omission of claims operates at the application credential selection and claim disclosure metadata level. True cryptographic selective disclosure (redacting attributes from a single signed credential without breaking issuer signatures) requires SD-JWT VC or BBS+ signatures. These are out of scope for the current `eddsa-jcs-2022` profile and are NOT claimed.
- **Interoperability**: Automated internal integration tests confirm complete lifecycle compliance. Cross-ecosystem testing with external reference wallets (EUDI reference app, walt.id) is not part of this work package. Therefore, marked as **L4 INTEROPERABILITY: NOT TESTED**.

---

## 18. Definition of Done Checklist
- [x] Holder receives the real OID4VP request
- [x] Wallet uses actual WP-04 DCQL evaluation result
- [x] Requested verifier/purpose/claims are shown from real request state
- [x] Holder approval is explicit
- [x] Holder rejection is explicit
- [x] Consent is bound to verifier/session/request
- [x] Consent is bound to credentials/claims
- [x] Consent is timestamped
- [x] Stale/replayed/cross-session consent is rejected
- [x] Actual presentation is constructed from the approved set
- [x] Unapproved credential cannot leak into the presentation
- [x] Original issuer-signed VC is preserved byte-for-byte unchanged
- [x] Original issuer proof is preserved and verifies independently
- [x] No synthetic issuer private key is accessed or used during presentation
- [x] WP-02 cryptographic holder binding is applied to outer VP
- [x] Nonce/challenge/session protections remain intact
- [x] Rejection path produces no successful presentation
- [x] Verifier receives explicit denial/failure state
- [x] Consent/presentation events are auditable
- [x] Private keys are never exposed in audit logs
- [x] Raw credential/VP data is not unnecessarily logged
- [x] No false selective-disclosure or ZKP claims exist in code or UI
- [x] UI protocol states are truthful
- [x] All 27 WP-07 tests pass
- [x] WP-01 through WP-07 combined integration tests pass (125/125)
- [x] Full regression suite passes
- [x] Static analysis passes (Pyright: 0 errors)
- [x] Web frontend builds with 0 errors
- [x] No unjustified suppressions added
- [x] WP-07 report updated with corrective patch details
- [x] Commit created
- [x] Push successful
- [x] HEAD == origin/main
- [x] Working tree clean

