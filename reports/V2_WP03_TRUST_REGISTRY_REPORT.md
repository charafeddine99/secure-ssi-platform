# V2.1 WP-03: Authoritative Trust Registry & Trust Policy Integration Report

**Execution Mode**: Controlled Remediation Work Package (V2.1 Remediation Plan)  
**Work Package**: WP-03  
**Status**: COMPLETE / L3 VERIFIED  
**Date**: October 5, 2026  
**Target Branch**: `main`  

> **Historical, package-scoped report.** `L3 VERIFIED` here describes this
> WP-03 snapshot only; it is not project-wide G0–G16 acceptance or current
> source-state proof. See the current
> [gate matrix](../docs/implementation/SECURE_SSI_PLATFORM_GATE_ACCEPTANCE.md)
> and [test evidence](../docs/implementation/SECURE_SSI_PLATFORM_TEST_EVIDENCE.md).

---

## 1. Executive Summary

Work Package 03 (WP-03) has definitively eliminated the legacy heuristic shortcut in the verification pipeline:
```python
# PREVIOUS HEURISTIC SHORTCUT (REMOVED):
issuer_trusted = issuer_did.startswith(("did:web:", "did:key:"))
```
and replaced it with an authoritative, persistent, auditable, and fail-closed **Trust Registry domain**.

Under WP-03:
1. **Identifier $\neq$ Trust**: Having a syntactically valid `did:web:` or `did:key:` identifier no longer establishes trust. Issuer trust is now an explicit data-backed decision backed by authoritative MongoDB persistence.
2. **Explicit Verification Context**: The Trust Registry answers: *"Is this issuer identity trusted for this verification context (credential types), under the project's local trust policy, at this point in time (validity window and operational status)?"*
3. **Fail-Closed Semantics**: Unknown issuers, suspended issuers, revoked issuers, expired issuers, not-yet-valid records, out-of-scope credential requests, malformed DIDs, and registry lookup failures all evaluate strictly to `is_trusted = False`.
4. **Authorized Administrative Mutations**: Trust record creation, status updates, suspension, and revocation are restricted strictly to administrators (`Role.ADMIN` with `Permission.TRUST_REGISTRY_WRITE`). Regular holders and verifiers are forbidden from mutating trust records (403 Forbidden).
5. **Full Audit Traceability**: Privileged mutations append immutable audit events (`TRUST_RECORD_CREATED`, `TRUST_RECORD_UPDATED`, `TRUST_RECORD_DEACTIVATED`, `TRUST_RECORD_REVOKED`) with actor attribution, reasons, and timestamps.
6. **Preservation of Prior Guarantees**: Cryptographic signature validation (WP-01) and holder binding proof-of-possession (WP-02) remain untouched and independently enforced in the 9-point verification hierarchy.

---

## 2. Standards & Classification Baseline

| Concept | Classification | Context / Profile |
| :--- | :--- | :--- |
| **Local Trust Registry** | **PROJECT PROFILE** | Selected project profile for prototype deployment. Authoritative persistence in local MongoDB. |
| **Trust Record Persistence** | **IMPLEMENTATION CHOICE** | Implemented via MongoTrustRegistryRepository with optimistic concurrency control and unique indexing. |
| **DID Identity Itself** | **NOT SUFFICIENT FOR TRUST** | W3C DID Core 1.0 compliant: DIDs identify subjects and verification methods, but identifier format alone establishes zero ecosystem trust. |
| **OpenID Federation 1.0** | **REFERENCE / STANDARDS CONTEXT** | Conceptual reference for trust anchors, entity identifiers, and trust scopes. Not claimed as full federation implementation. |
| **EUDI Trusted List Service** | **REFERENCE / STANDARDS CONTEXT** | Architecture benchmark for status separation (active/suspended/revoked) and authority publication. Not claimed as government accreditation. |

---

## 3. Current Problem & Architectural Defect (Prior to WP-03)

Prior to WP-03, `Oid4vpService.process_direct_post` contained a known heuristic shortcut:
```python
issuer_trusted = (
    issuer_did.startswith("did:web:")
    or issuer_did.startswith("did:key:")
    or issuer_did == "did:web:issuer.example"
)
```
This heuristic had critical vulnerabilities:
- **Rogue Issuer Acceptance**: Any entity with an arbitrary `did:web:` or `did:key:` string was deemed "trusted".
- **No Revocation / Suspension**: There was no mechanism to suspend or revoke trust in an untrusted or compromised issuer.
- **No Temporal Bounds**: Trust had no expiration date or validity window.
- **No Scoping**: Any issuer was implicitly trusted for all credential types without domain restriction.
- **Zero Auditability**: No audit records tracked who established or modified trust decisions.

---

## 4. Trust Domain & Data Model

### Domain Models (`app.domain.trust_registry`)

1. **`TrustStatus`**: Explicit lifecycle state:
   - `ACTIVE`: Fully trusted within validity window and permitted scopes.
   - `SUSPENDED`: Temporarily deactivated pending investigation/audit.
   - `REVOKED`: Permanently untrusted due to compromise or decommission.
2. **`TrustRole`**:
   - `ISSUER`: Authorized to issue verifiable credentials.
   - `VERIFIER`: Authorized to accept presentations.
3. **`TrustRecord`**: Authoritative domain entity:
   - `id`: Unique record identifier (MongoDB ObjectId string).
   - `issuer_did`: Canonical issuer DID (unique constraint index).
   - `organization_name`: Human-readable synthetic organization name.
   - `trust_status`: `TrustStatus` enum.
   - `roles`: Tuple of `TrustRole` values.
   - `permitted_credential_types`: Permitted VC schemas/types (supports scoped evaluation).
   - `valid_from`: UTC timestamp when trust becomes effective.
   - `valid_until`: Optional UTC timestamp when trust expires.
   - `trust_source`: Source of trust authority (e.g., `LOCAL_TRUST_REGISTRY`, `DEMO_ACCREDITATION_BOARD`).
   - `trust_anchor`: Optional trust anchor reference (e.g., `urn:trust-anchor:demo-academic-consortium`).
   - `created_at`, `updated_at`: UTC audit timestamps.
   - `created_by`: Identity of administrative actor.
   - `audit_metadata`: Arbitrary key-value metadata for audit tracing.
   - `version`: Optimistic concurrency lock counter.

### Database Persistence & Schema

- **Collection**: `trust_registry`
- **Indexes**:
  - `issuerDid`: Unique ascending index (`unique=True`).
  - `trustStatus`: Ascending index.
  - `validUntil`: Ascending index.
  - `createdAt`: Descending index.
- **Optimistic Concurrency**: Atomic conditional updates (`version == expected_version`), incrementing version on write.
- **Fallback In-Memory Store**: `InMemoryTrustRegistryRepository` implemented for unit testing isolation without external database dependencies.

---

## 5. API & Service Architecture

### Service Operations (`TrustRegistryService`)

- `register_trusted_issuer`: Registers new trusted entity with unique DID enforcement. Emits `TRUST_RECORD_CREATED`.
- `update_trust_record`: Updates entity metadata, permitted credential types, validity dates, or status with optimistic locking. Emits `TRUST_RECORD_UPDATED`.
- `suspend_issuer`: Temporarily suspends issuer trust. Emits `TRUST_RECORD_DEACTIVATED`.
- `revoke_issuer`: Permanently revokes issuer trust. Emits `TRUST_RECORD_REVOKED`.
- `evaluate_issuer_trust`: Pure authoritative evaluation of trust against status, temporal window, and credential type scope.
- `seed_default_demo_issuers`: Idempotent seeding of synthetic academic demo institutions (`Demo Technical University`, `Demo Metropolitan Municipality`, `Demo Synthetic Ed25519 Issuer`).

### API Endpoints (`/api/v1/trust-registry`)

| Method | Endpoint | Authorization | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/trust-registry/issuers` | Authenticated | List all registered trust records with status filtering. |
| `GET` | `/api/v1/trust-registry/issuers/{issuer_did}` | Authenticated | Get trust record details for an issuer DID. |
| `POST` | `/api/v1/trust-registry/issuers` | `Role.ADMIN` (`TRUST_REGISTRY_WRITE`) | Register new trusted issuer. |
| `PUT` | `/api/v1/trust-registry/issuers/{record_id}` | `Role.ADMIN` (`TRUST_REGISTRY_WRITE`) | Update existing trust record. |
| `POST` | `/api/v1/trust-registry/issuers/{record_id}/suspend` | `Role.ADMIN` (`TRUST_REGISTRY_WRITE`) | Suspend issuer trust. |
| `POST` | `/api/v1/trust-registry/issuers/{record_id}/revoke` | `Role.ADMIN` (`TRUST_REGISTRY_WRITE`) | Revoke issuer trust. |
| `POST` | `/api/v1/trust-registry/evaluate` | Public / Verifier | Evaluate trust for an issuer DID and requested types. |

---

## 6. Verifier Integration (OID4VP Direct Post)

In `Oid4vpService.process_direct_post`:
1. The prefix-based heuristics (`startswith("did:web:")` and `startswith("did:key:")`) have been **completely eliminated**.
2. The verifier queries `self._trust_registry.evaluate_issuer_trust(...)` using:
   - Canonical `issuer_did` from the Target VC.
   - VC `type` array from the Target VC.
   - Evaluation timestamp `now` (UTC).
3. The structured trust result is integrated into `NinePointVerificationResult`:
   - `issuer_trusted`: Boolean strictly reflecting registry evaluation.
   - `details["trust"]`: Contains `trusted`, `status`, `reason`, `source`, `recordId`, and `matchedTypes`.
   - `details["evaluations"]["issuer"]`: Explicit reason string (e.g. `Trusted in local registry: did:web:issuer.example` or `Issuer untrusted: ISSUER_NOT_IN_TRUST_REGISTRY`).
4. If `issuer_trusted` is `False`, `final_policy_result` fails closed to `REJECTED`, even if cryptographic signatures, nonces, and holder bindings are valid.

---

## 7. Negative & Security Test Suite

The automated suite in `tests/integration/test_wp03_trust_registry.py` verifies all 16 required test cases:

| Test Case | Scenario Tested | Outcome | Result |
| :--- | :--- | :--- | :--- |
| `test_exact_registered_issuer_is_trusted` | Exact registered issuer DID lookup | `isTrusted=True, status=active` | **PASSED** |
| `test_unknown_issuer_is_untrusted_fail_closed` | Unregistered DID presented | `isTrusted=False, reason=ISSUER_NOT_IN_TRUST_REGISTRY` | **PASSED** |
| `test_similar_did_with_wrong_suffix_is_untrusted` | Substring, path, and suffix injection | All rejected with `isTrusted=False` | **PASSED** |
| `test_malformed_did_fails_closed` | Empty string, non-DID, URL | `isTrusted=False, reason=MALFORMED_ISSUER_DID` | **PASSED** |
| `test_suspended_trust_record_is_untrusted` | Admin suspended issuer record | `isTrusted=False, reason=ISSUER_TRUST_SUSPENDED` | **PASSED** |
| `test_revoked_trust_record_is_untrusted` | Admin revoked issuer record | `isTrusted=False, reason=ISSUER_TRUST_REVOKED` | **PASSED** |
| `test_expired_trust_record_is_untrusted` | Past validity window (`validUntil < now`) | `isTrusted=False, reason=ISSUER_TRUST_EXPIRED` | **PASSED** |
| `test_not_yet_valid_trust_record_is_untrusted` | Future validity window (`validFrom > now`) | `isTrusted=False, reason=ISSUER_TRUST_NOT_YET_VALID` | **PASSED** |
| `test_scoped_trust_credential_types` | Trusted issuer outside permitted type scope | Permitted type: Trusted; Disallowed type: Untrusted | **PASSED** |
| `test_holder_cannot_mutate_trust_registry` | Holder role attempts to register issuer | `403 Forbidden` | **PASSED** |
| `test_verifier_cannot_mutate_trust_registry` | Verifier role attempts to register issuer | `403 Forbidden` | **PASSED** |
| `test_unauthenticated_cannot_mutate_trust_registry` | Anonymous request to register issuer | `401 / 403 Forbidden` | **PASSED** |
| `test_duplicate_issuer_record_rejected` | Duplicate issuer registration attempt | `409 Conflict` | **PASSED** |
| `test_verifier_rejects_untrusted_issuer_presentation` | Verifier direct_post with unregistered DID | `finalPolicyResult=REJECTED, issuerTrusted=False` | **PASSED** |
| `test_verifier_accepts_registered_trusted_issuer_presentation` | Verifier direct_post with seeded demo issuer | `finalPolicyResult=ACCEPTED, issuerTrusted=True` | **PASSED** |
| `test_suspending_issuer_causes_subsequent_verification_rejection` | Dynamic suspension of previously trusted issuer | Immediate fail-closed rejection on direct_post | **PASSED** |

---

## 8. Regression Suite Verification

To verify that WP-03 changes introduced zero regressions to earlier completed work packages:
- **WP-01 Test Suite** (`test_wp01_fail_closed_verification.py`): 14/14 tests **PASSED** (challenge/nonce, tampering, fail-closed signature verification).
- **WP-02 Test Suite** (`test_wp02_holder_binding_verification.py`): 16/16 tests **PASSED** (ephemeral keypair, proof-of-possession, holder DID binding).
- **Identity Service Unit Suite**: 270/270 tests **PASSED**.
- **Total Integrated Pass Count**: 46 integration tests + 270 unit tests = **316 tests PASSED**.

---

## 9. Static Analysis & Type Checking

Static analysis executed with Pyright across all changed production and test files:
```bash
cmd.exe /c "npx pyright \
  services/identity-service/app/domain/trust_registry.py \
  services/identity-service/app/domain/permissions.py \
  services/identity-service/app/domain/persistence.py \
  services/identity-service/app/application/ports/trust_registry.py \
  services/identity-service/app/infrastructure/persistence/indexes.py \
  services/identity-service/app/infrastructure/persistence/trust_registry_repository.py \
  services/identity-service/app/application/services/trust_registry_service.py \
  services/identity-service/app/schemas/trust_registry_api.py \
  services/identity-service/app/api/v1/trust_registry.py \
  services/identity-service/app/application/services/oid4vp_service.py \
  services/identity-service/app/api/v1/dependencies.py \
  services/identity-service/tests/integration/test_wp03_trust_registry.py"
```
**Result**: `0 errors, 0 warnings, 0 informations`. Zero `@ts-ignore`, `type: ignore`, or `pyright: ignore` shortcuts.

---

## 10. UI Truthfulness Alignment

The verification UI (`apps/web/src/components/verification/NinePointVerificationMatrix.tsx`) was reviewed and updated to ensure complete truthfulness:
- **Previous**: *"Resolves issuer DID and validates trust anchor accreditation."*
- **Truthful WP-03 Baseline**: *"Evaluates issuer DID against local authoritative Trust Registry."*
- **Default Evaluation Label**: *"Verified trusted issuer in local Trust Registry"*.
- **Demonstration Scenarios**: Demo issuers are labeled with explicit synthetic names (`Demo Technical University`, `Demo Metropolitan Municipality`). No claims of Turkish government, EUDI, or official legal accreditation exist.

---

## 11. Known Limitations & Scope Boundaries

1. **Local Prototype Registry**: The Trust Registry is currently local to the platform instance (MongoDB-backed). Dynamic discovery of external OpenID Federation 1.0 entity configurations or multi-party trust chains is a future capability and not claimed in WP-03.
2. **DID Resolution Scope**: DID resolution remains composite fixture-based (`did:web:issuer.example`) and `did:key:`. Dynamic `did:web` HTTPS document fetching is strictly allocated to **WP-06**.
3. **DCQL Query Language**: Presentation definitions currently follow Presentation Exchange 2.0. Transition to OID4VP DCQL is strictly allocated to **WP-04**.

---

## 12. Production & Test Files Changed

### Production Files Created / Modified:
1. `services/identity-service/app/domain/trust_registry.py` (New domain model)
2. `services/identity-service/app/domain/permissions.py` (Added `TRUST_REGISTRY_READ`, `TRUST_REGISTRY_WRITE`)
3. `services/identity-service/app/domain/persistence.py` (Added `AuditEventType` trust values)
4. `services/identity-service/app/application/ports/trust_registry.py` (New repository port)
5. `services/identity-service/app/infrastructure/persistence/indexes.py` (Added `trust_registry` collection indexes)
6. `services/identity-service/app/infrastructure/persistence/trust_registry_repository.py` (Mongo & In-Memory repositories)
7. `services/identity-service/app/application/services/trust_registry_service.py` (Application service with seeding)
8. `services/identity-service/app/schemas/trust_registry_api.py` (Pydantic API request/response schemas)
9. `services/identity-service/app/api/v1/trust_registry.py` (FastAPI REST endpoints)
10. `services/identity-service/app/api/v1/router.py` (Router registration)
11. `services/identity-service/app/api/v1/dependencies.py` (Dependency injection wiring)
12. `services/identity-service/app/application/services/oid4vp_service.py` (Integrated authoritative trust evaluation)
13. `apps/web/src/components/verification/NinePointVerificationMatrix.tsx` (Truthful UI matrix labels)

### Test Files Created:
1. `services/identity-service/tests/integration/test_wp03_trust_registry.py` (16 negative, lifecycle, authorization, and direct_post integration tests)

---

## 13. Acceptance Decision

**WP-03 Completion Level**: **L3 VERIFIED**  
All functional, security, persistence, fail-closed, authorization, audit, and truthfulness requirements for WP-03 are fully satisfied. All automated tests pass without regressions, and static analysis reports 0 errors.
