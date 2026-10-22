# Secure SSI Platform — Security Review

**Review date:** 15 October 2026 · **Scope:** current source review focused on OID4VP status/consent/authentication, scoped G6/G7 evidence, and documented remaining controls. This is not a complete ASVS assessment, penetration test, or production security certification.

## Current findings

| ID | Severity / status | Finding and evidence | Action / acceptance condition |
|---|---|---|---|
| SEC-01 | High impact; remediation verified in scoped suite | Legacy OID4VP reject/consent/presentation routes that accepted caller-asserted holder context or fixture signing return HTTP 410. The current G7/Identity regression passed the retired-route and canonical wallet-auth cases. | Keep route contract covered in current regression; no device-bound wallet or external peer claim follows from this. |
| SEC-02 | High impact; remediation verified in scoped suite | `WalletOid4vpConsentRequest` explicitly allows only consent fields and forbids client override of stored nonce/client/verifier/purpose. Current G7 tests passed the 422 rejection and unchanged pending-session cases. | Retain current API negative tests; durable cross-layer consent evidence remains G11 work. |
| SEC-03 | Open limitation | Logout token revocation is process-local/in-memory according to current authentication documentation. Multi-worker propagation and restart persistence are not established. | Before production/multi-instance use, use a shared durable revocation/session mechanism or short-lived token strategy with equivalent revocation guarantees; add multi-worker/restart tests. |
| SEC-04 | Partial; G8 remains open | Recovery now requires and verifies challenge-bound EdDSA JWT proofs for registered Ed25519 `did:key` Guardians. The signing key is managed by the server-side Identity provider; Guardian-device possession/MFA, `did:web` proofs, and independent share delivery are not established; encrypted share envelopes remain centrally stored. | Preserve proof-verification regression tests; establish independent Guardian-device assurance, decide supported DID methods, and evidence share custody/delivery and cross-service recovery in the target runtime. |
| SEC-05 | Open product/privacy limitation | The wallet flow presents the complete selected signed credential. Claim-level cryptographic selective disclosure, predicate proofs, and ZK proofs are absent. | Keep UI/docs explicit; a selective-disclosure feature requires an approved credential-format/proof profile and independent testing. |
| SEC-06 | Open architecture limitation | Holder signing uses server-mediated managed-key operations and development/local paths; vendor KMS/HSM and hardware key ceremony are not evidenced. | Do not claim device self-custody or HSM-backed production custody; complete provider and operational security evaluation before deployment. |
| SEC-07 | Partial operational control | Current G13 evidence covers the Gateway's bounded process-local limiter, loopback-only Compose host ports, focused Gateway/Identity/Recovery tests, and an offline frontend lockfile audit. No Python dependency scanner, SAST, secret scan, independent penetration review, or formal critical/high triage was performed; Identity/Recovery have no independent limiter. | Complete the remaining G13 control inventory and record scanner versions, output, reviewed findings, owners, and retest evidence. |
| SEC-08 | Resolved for current local validation | The installed Python 3.11 venv and Docker Desktop were usable with elevated test-process permission. Normal sandboxed local socket operations remain denied; WSL access remains denied. | Keep using the authorized runtimes; do not change Windows policy. This is not a blocker for the current G6/G7 runs. |
| SEC-09 | Regression gap closed for the identified scenario | A dedicated case now creates a valid holder proof around an issuer-tampered credential; current full Identity and dedicated G7 suites passed, with the verifier rejecting the credential. | Preserve this regression. Other historical tests were not claimed to be copied one-for-one. |

## Controls evidenced in current code/doc inventory

- OID4VP canonical writes/signing are designed around authenticated, wallet-bound APIs; retired routes fail closed with HTTP 410.
- The consent payload schema does not allow client-supplied server session context.
- Frontend sends the authenticated wallet context and reports authoritative backend outcomes; 15 authentication, 9 wallet API, 8 fail-closed and 21 recovery API checks passed.
- Demo authentication is explicitly development-gated; product text states full-credential disclosure and server-mediated key custody.
- Threat-model continuation records legacy route, caller-supplied consent context, and process-local token revocation risks.

Current backend evidence: WP-08 focus 48/48, Identity regression 686 passed/5 Hardhat-only skipped, real Mongo repository tests 7/7, and G7 wallet-consent/auth/privacy suite 80/80. Frontend fail-closed passed 8/8. These are scoped executable checks, not a complete security assessment or browser E2E.

## Threat boundaries and remaining test cases

| Boundary | Remaining coverage / evidence |
|---|---|
| Identity/token | Current auth/logout/role paths passed. Multi-worker and restart-persistent revocation remain unverified. |
| Wallet/session/consent | Current G7 covers wallet/session binding, context override, denial, replay, privacy and legacy routes. Browser presentation and durable cross-layer trace remain G11. |
| Issuer/status/trust | Current G6 covers focused tampering, issuer/trust, malformed/missing status, purpose/index and fail-closed errors. Independent peer evidence remains G14. |
| Recovery | Current tests cover challenge-bound `did:key` signature validation and recovery API/state behavior. Independent device possession/MFA, `did:web`, separate share custody, and a deployed Identity+Recovery persistence/restart trace remain open at G8. |
| Operations | Rate limiting, dependency/secret scanning, CORS/cookie/CSRF as applicable, exhaustive PII log review and SSRF review remain G13 work. |

## Security conclusion

No production-readiness conclusion is supported. Scoped G6/G7 checks pass, but no ASVS checklist, Python dependency/secret scan, full PII review, or external penetration test was run. G8 remains PARTIAL: the submitted `did:key` proof verification is covered, while independent Guardian-device assurance and the other residuals above remain open. Keep distributed token revocation, external conformance, deployment hardening and production readiness explicitly open.
