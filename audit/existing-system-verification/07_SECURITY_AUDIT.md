# 07 – Security Audit

Scope: the existing system on the isolated `audit-20261121` stack, synthetic accounts only. No external system was attacked. No security control was weakened to make a test pass.

## Results by area

| Area | How it was tested | Result |
|---|---|---|
| Authentication bypass | E2E/gaps: missing, expired, forged and revoked tokens; wrong passwords; disabled accounts | No bypass found |
| Broken access control / IDOR | E2E and onboarding: holder reading another holder's wallet, credential or request; non-admin on admin routes; issuer on another issuer's data; anonymous request reads | All refused (401/403/404) |
| Session and token handling | Gateway tests: HttpOnly, SameSite=Strict, `__Host-` prefix when Secure, CSRF check on cookie requests, server-side revocation; step-up tokens bound to action and resource, client-invented values refused | Pass |
| CSRF / XSS | Gateway CSRF tests; React rendering; CSP and security headers on every response; pages stage reports no console errors | Pass |
| NoSQL injection | Request validation (Pydantic), size and depth limits at the gateway (1 MB, depth 16) | No finding |
| CORS | Gateway allows only configured origins with credentials; fraud service without credentials | Pass |
| Secret exposure | Error handlers never echo internal exceptions or hostnames; harness checks responses for tokens; reports contain no secrets | Pass. F-01 leaked the internal hostname in QR links (fixed) |
| Sensitive data in logs | Audit and security events carry pseudonymised subjects; no passwords, tokens or keys seen in service logs during the audit | No finding |
| Credential signature verification | 15 tamper variants rejected; wrong key, key substitution via DID, non-Ed25519 keys rejected; risk score cannot override a failed check | Pass |
| QR / request_uri manipulation | `wp32_oid4vp_security` 16/16: replay, nonce reuse, wrong audience, expired request, tampered request object, foreign `request_uri` origins refused (SSRF-safe fetch) | Pass. FIX-1: forged `X-Forwarded-Host` cannot reach the link |
| Replay protection | Replayed presentation refused; second consent on the same QR refused | Pass |
| Unauthorised recovery | Single guardian cannot complete; time lock cannot be skipped; self-guardian refused; policy floors enforced; owner can cancel; step-up required | Pass (after F-02, which caused false 403s, not a bypass) |
| Key management | Development provider only; private keys never leave the service; dual control on restore | No vulnerability found; external KMS/HSM not available |
| Backup file security | Wallet backups encrypted client-side (Argon2id + AES-GCM), wrong password refused; platform archives encrypted and integrity-verified, corrupted archive refused | Pass |
| Audit integrity | Tampered audit event detected by the chain check; ledger principal cannot delete or drop | Pass |
| Accessibility (not security, recorded here) | axe on 62 page/viewport combinations | 0 violations |

## Risks by severity

| Severity | Open items |
|---|---|
| Critical | None found |
| High | None open (F-01 fixed) |
| Medium | F-02 fixed. F-14 (operational, not a vulnerability: routine key re-syncs wrote ~2,880 audit events per key per day, which could bury real security events) and F-15 (availability: one transient provider error could fail an ACTIVE key) fixed on 2026-11-23 in code and unit tests (FIX-4, FIX-6); live re-check pending. State changes, failures and administrative reconciliations are still audited |
| Low | F-03 fixed. Remaining low risks: default dev secrets must be replaced in any real deployment (documented in `.env.example`) |
| Info | F-04 step-up/dual control off in development mode by default; F-05 ledger optional; F-09/F-10 external dependencies not available; no independent penetration test |

## What this audit does not prove

Green tests do not make the system production-secure. Not covered: a real phone on a public HTTPS address, a real KMS/HSM, a live blockchain, official OpenID conformance suites, load and resilience testing beyond the drill, an independent penetration test, and a legal (KVKK) review.
