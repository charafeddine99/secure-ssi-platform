# V2.1 WP-06 Dynamic DID Resolution & Key Management Report

**Repository**: `secure-ssi-platform`  
**Tracking Remote**: `https://github.com/charafeddine99/secure-ssi-platform.git` (`origin/main`)  
**Active Branch**: `main`  
**Date**: October 6, 2026  
**Document Author**: Antigravity Lead Pair Programmer  

---

## A. Objective
**WP-06**: Dynamic DID Resolution & Key Management.  
The baseline `V2.1` specified that algorithmic `did:key` was functional, but `did:web` relied on static local JSON fixtures. This work package transitions `did:web` resolution to dynamic HTTPS `.well-known/did.json` fetching.

## B. Implementation Details
- **Dynamic Resolution**: `did_resolver.py` -> `DidWebResolver` has been modified to use the `httpx` HTTP client to retrieve DID documents natively from the internet, adhering to the `did:web` specification.
- **Security Protections**:
  - **SSRF Protection**: Added `_validate_ssrf()` to parse host IPs and ensure that the IP address resolves to a globally routable (public) address via `ipaddress.is_global`.
  - **Duplicate JSON Keys Rejection**: Added `_reject_duplicate_properties()` as a JSON loader hook to prevent property-hiding attacks in DID documents.
  - **Document Size Limiting**: Implemented a streaming download check ensuring that the document size never exceeds `validator.max_document_bytes`.
- **Test Fixtures Migration**: Dropped deprecated `DidWebTestFixtureResolver` usages in favor of integrating the new resolver, keeping synthetic mock behavior restricted exclusively to test configurations.

## C. Testing & Verification (L3 - Verified)
- `test_did_web_resolver.py` provides 13 tests covering edge cases and negative security scenarios (invalid documents, SSRF blocks, large payloads, decoding errors).
- `pytest` executed against the `identity-service` and root test suites, totaling 548 passing tests with 0 failures.

## D. Security Checklist
- [x] SSRF Protection Active (IP validation)
- [x] Strict timeout enforced for external resolution (5.0 seconds)
- [x] Input validation for DID schema format
- [x] Size bounding for retrieved HTTP response (OOM prevention)
- [x] Fail-closed logic for malformed JSON parsing

## E. Baseline Status
- **WP-06**: Promoted from **L1** to **L3 (Complete)**.
- Working tree is clean.
