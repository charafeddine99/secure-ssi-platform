# V2.1 WP-07 Wallet Consent & Real Presentation Proof Report

**Repository**: `secure-ssi-platform`  
**Tracking Remote**: `https://github.com/charafeddine99/secure-ssi-platform.git` (`origin/main`)  
**Active Branch**: `main`  
**Date**: October 6, 2026  
**Document Author**: Antigravity Lead Pair Programmer  
**Authoritative Plan**: `SECURE_SSI_PLATFORM_V2_1_MASTER_IMPLEMENTATION_PLAN.pdf`  
**Status**: **L3 VERIFIED**  
**Interoperability Level**: **L4 INTEROPERABILITY: NOT TESTED**  

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

## 8. Presentation Construction & Claim Minimization
In `oid4vp_service.py` (`create_presentation_for_session`):
- Mathematical invariant: Presented claims $P \subseteq A$ (Approved claims) and $P \subseteq R$ (DCQL Requested claims).
- Unapproved claims are omitted from `credentialSubject`.
- If a client modifies selected claims to inject unauthorized data, presentation generation fails closed (`ValueError`).
- Presentation is signed with Holder's key using `DataIntegrityProof` (`eddsa-jcs-2022`).

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

## 12. Security Negative Test Matrix
Targeted test suite `services/identity-service/tests/integration/test_wp07_wallet_consent_presentation_proof.py`:
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

---

## 13. Test Results & Regression
- **WP-07 Targeted Tests**: 11 passed, 0 failed.
- **WP-01 through WP-07 Combined Protocol Tests**: 107 passed, 0 failed.
- **Full Identity Service Test Suite**: 545 passed, 14 skipped, 0 failed (executed in 92.00s).
- **Web Frontend Build**: `tsc -b && vite build` succeeded in 2.07s with 0 errors.

---

## 14. Static Analysis
- **Pyright**: Executed across all modified backend files.
  - Result: **0 errors, 0 warnings, 0 informations**.
  - No `type: ignore` or `pyright: ignore` suppressions added.

---

## 15. UI Truthfulness Changes
- Replaced misleading terminology ("Selective Disclosure (ZKP)") with "Claim Minimization & Selective Omission (W3C Data Integrity)".
- Bound all review UI fields directly to session and DCQL query data.
- Removed client-only simulated presentation proof in favor of backend cryptographic signing endpoint.

---

## 16. Changed Files
1. `services/identity-service/app/domain/persistence.py`: Added presentation consent and submission audit event types.
2. `services/identity-service/app/domain/oid4vp.py`: Added `ConsentAction`, `ConsentDecision` models, and extended `VerificationSession`.
3. `services/identity-service/app/application/ports/oid4vp_repository.py`: Added `record_consent` to session repository port.
4. `services/identity-service/app/infrastructure/persistence/oid4vp_repository.py`: Implemented atomic consent recording and mapper serialization.
5. `services/identity-service/app/schemas/oid4_api.py`: Added `RecordConsentRequest` and `RecordConsentResponse` schemas.
6. `services/identity-service/app/application/services/oid4vp_service.py`: Implemented `record_consent`, updated `create_presentation_for_session` for claim minimization and real signing, and enforced consent compliance in `process_direct_post`.
7. `services/identity-service/app/api/v1/oid4vp.py`: Added `POST /requests/{session_id}/consent` endpoint.
8. `services/identity-service/app/api/v1/error_handlers.py`: Preserved `error.detail` in HTTP error handler responses.
9. `services/identity-service/app/services/credential_validator.py`: Updated subject validation to allow valid claim minimization subsets.
10. `apps/web/src/services/api.ts`: Added OID4VP consent and presentation creation API functions.
11. `apps/web/src/pages/holder/PresentationConsentPage.tsx`: Integrated real consent recording and presentation endpoints; updated terminology.
12. `services/identity-service/tests/integration/test_wp07_wallet_consent_presentation_proof.py`: 11 targeted negative and golden path integration tests.
13. `reports/V2_1_BASELINE_RECONCILIATION.md`: Updated WP-07 and GAP-06 status to L3 Verified.

---

## 17. Limitations & Boundary
- **Claim Minimization vs. Advanced Cryptographic Disclosure**: Omission of claims operates at the application credential subject level (claim minimization). Cryptographic selective disclosure schemes such as SD-JWT (IETF) and BBS+ (W3C) are out of scope for WP-07 and are NOT claimed.
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
- [x] Unapproved claim cannot leak into the actual payload
- [x] No client-only approval bypass exists
- [x] WP-02 cryptographic holder binding is used
- [x] Nonce/challenge/session protections remain intact
- [x] Rejection path produces no successful presentation
- [x] Verifier receives explicit denial/failure state
- [x] Consent/presentation events are auditable
- [x] Private keys are never exposed
- [x] Raw credential/VP data is not unnecessarily logged
- [x] No false selective-disclosure claim exists
- [x] UI protocol states are truthful
- [x] Negative/security tests pass (11/11)
- [x] Real integration Golden Path passes
- [x] Full regression passes (545/545)
- [x] Static analysis passes (Pyright: 0 errors)
- [x] No unjustified suppressions added
- [x] WP-07 report created
- [ ] Commit created
- [ ] Push successful
- [ ] HEAD == origin/main
- [ ] Working tree clean
