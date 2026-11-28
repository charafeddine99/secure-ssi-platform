# 06 – Module Verification Matrix

"Before" = status at the start of the audit (from code and the initial run). "After" = after the fixes and the regression run. Evidence names refer to `evidence/`.

| Module | Before | After | Test evidence | Open gap |
|---|---|---|---|---|
| Authentication | VERIFIED | VERIFIED | identity 1086; `final_e2e`; `final_gaps` 38/38 | Password reset does not exist (NOT IMPLEMENTED) |
| Authorization / RBAC / IDOR | VERIFIED | VERIFIED | `final_e2e`; `final_onboarding` 40/40 | – |
| Onboarding and invitations | VERIFIED | VERIFIED | `final_onboarding` 40/40; `final_wp32_ui` | – |
| MFA (TOTP) and step-up | VERIFIED (with matching secrets) | VERIFIED | `final_e2e` MFA/guardian sections run with `RECOVERY_STEP_UP_SECRET` unset (FIX-2 fallback in use) | – |
| WebAuthn | PARTIALLY VERIFIED | PARTIALLY VERIFIED | identity WebAuthn tests; `final_browser` (virtual authenticator) | Real device / security key (external) |
| Dual control | VERIFIED | VERIFIED | `final_dr` (two-person restore, single-use token) | Off in development mode by default |
| Issuer: VC 2.0 issuance and signing | VERIFIED | VERIFIED | identity crypto tests; `final_e2e` | – |
| OpenID4VCI | VERIFIED (platform) | VERIFIED (platform) | `test_wp05_*`, `test_oid4_protocols.py`; `final_e2e`; `final_gaps` | Official conformance suite (external) |
| Status list / revocation / suspension | VERIFIED | VERIFIED | identity tests; `final_e2e` | – |
| Revocation ledger | VERIFIED when configured | VERIFIED when configured | `final_e2e` ledger section | Optional; off by default |
| Holder wallet and green card UI | VERIFIED | VERIFIED | `final_wp32_card` | – |
| OpenID4VP + DCQL + JAR | VERIFIED (platform) | VERIFIED (platform) | `final_oid4vp_security` 16/16; `test_wp32_request_uri.py` | Official conformance suite (external) |
| QR / request_uri | **PRESENT BUT BROKEN in the default setup** (internal hostname in the link, F-01) | VERIFIED (simulated devices) | `regression_fix1_origin` 7/7 (default setup); `final_wp32_scan` 11/11; `final_wp32_cross`; FIX-1 unit tests | Physical phone + public HTTPS (external) |
| Wallet backup and restore | VERIFIED | VERIFIED | `final_e2e` wallet section; `final_browser`; web crypto tests | – |
| Guardian recovery | **PRESENT BUT BROKEN when secrets differ** (F-02, all guardian actions 403) | VERIFIED | recovery 131; `final_e2e` guardian section with the fallback secret | Recovery only from a signed-in account (documented) |
| Platform backup and DR | VERIFIED (isolated drill) | VERIFIED (isolated drill), with a false-alarm check | `initial_dr` 32/32; `final_dr` 30/32 (restore verified; the 2 failures are the F-12 count check) | F-12 / F-14 fixed 2026-11-23 (FIX-4, FIX-5), drill not yet re-run; RPO not measured |
| KMS / key management | PARTIALLY VERIFIED | PARTIALLY VERIFIED | identity KMS tests (development provider) | External KMS/HSM. F-14 (audit volume) and F-15 (retry counter) fixed 2026-11-23, unit-tested |
| DID and issuer trust | VERIFIED | VERIFIED | identity tests; `final_wp32_card` (suspended issuer) | – |
| Audit log and hash chain | VERIFIED | VERIFIED | `final_gaps` (tamper detected) | – |
| Fraud / risk (rule-based) | VERIFIED as rule-based | VERIFIED as rule-based | fraud 90; `final_e2e` (risk cannot override) | No ML model (by design) |
| Security intelligence | VERIFIED | VERIFIED | fraud intel tests; `final_scenarios`; `final_ui` | – |
| Blockchain anchoring | PRESENT BUT UNTESTED (live) | PRESENT BUT UNTESTED (live) | unit tests with fakes; 5 live tests skipped | Chain node (external) |
| Admin and other pages | VERIFIED | VERIFIED | `final_pages` (62 combinations); `final_browser` 40/40 | – |
| API gateway | VERIFIED | VERIFIED | gateway 50 (incl. FIX-1 header tests) | – |
| Deployment configuration | **PRESENT BUT BROKEN when DB passwords change** (F-03) | VERIFIED | stack started with URIs derived from the password variables; `docker compose config` checks | – |
| Selective disclosure | NOT IMPLEMENTED | NOT IMPLEMENTED | – | Needs a different proof suite |
| Password reset | NOT IMPLEMENTED | NOT IMPLEMENTED | – | Planned only in the TÜBİTAK work |
