# SSI Plan Change Log (V2.1 → Revised)

**Date:** 5 October 2026  
**From:** Secure SSI Platform V2.1 Source-Validated Master Implementation Plan  
**To:** `SECURE_SSI_PLATFORM_MASTER_IMPLEMENTATION_PLAN_REVISED.md` + design report revision  

Only evidence-backed changes. Product direction preserved.

| ID | Old decision (V2.1 or thesis) | New decision | Reason | Supporting source | Impact |
| --- | --- | --- | --- | --- | --- |
| C1 | OID4VCI: Wallet gets `c_nonce` from Token Endpoint after PAC exchange | PAC still exchanged at Token Endpoint; **`c_nonce` from Nonce Endpoint** when proofs require it | Final spec moved freshness to §7 Nonce Endpoint; token `c_nonce` is draft-era | OpenID4VCI 1.0 Final 16 Sep 2025; OpenID4VCI issue #677 | G4 implementation, G0 remediation text, baseline freeze docs, tests |
| C2 | DID methods: “explicitly selected, must precede implementation” without names in the master plan | Freeze **`did:web` issuer** + **`did:key` holder fixtures only** | Plan required freeze; ADR 0001 already decided; leaving it open causes rework | DID Core 1.0; ADR 0001; did-method-web / did-key community drafts | G2, G3, G6, G8 |
| C3 | OID4VCI proof type: “declare jwt / di_vp / attestation later” | Freeze issuance PoP as **`jwt` (`openid4vci-proof+jwt`, EdDSA)**; issued credential remains Data Integrity | Avoids undefined PoP; attestation needs absent infra; jwt is widely used in OpenID4VCI | OpenID4VCI 1.0 Appendix F; ADR 0002 (credential proof unchanged) | G4 metadata + negative tests |
| C4 | Wallet described as “real wallet” without custody class | Label **custodial/server-mediated web wallet prototype** | Prevents HSM/EUDI-wallet overclaim; Multipaz SecureArea is out of scope | V2.1 non-goals; Multipaz SecureArea docs (reference only) | G3 docs/UI |
| C5 | QR/link mentioned; flow types not frozen | Freeze **cross-device QR + same-browser link**; DC API/native deep link out of scope | Matches web prototype; walt.id treats flow_type as first-class (reference) | OID4VP 1.0 transports; walt.id Verifier2 docs | G5, G12 |
| C6 | G0 is the first execution step with no feature work | **G0 already executed (4 Oct 2026)**; next step is G2 freeze + P0 gaps | Duplicate G0 blocks DCQL/VCI; artifacts exist | `reports/V2_G0_PRODUCT_REALITY_AUDIT.md` | Sequencing |
| C7 | Trust gate after full VP (G6 after G5) without calling out parallelism | Keep G6 after protocol exists, but treat **trust registry as P0 parallel** with G4/G5 | Prefix-matching trust makes Golden Path false | G0 GAP trust prefix; V2.1 trust rules | WP order |
| C8 | G15 performance in the same control list without dependency | **G15 only after G11 L3** | Thesis-style TPS/accuracy without a valid verifier is not evidence | ISO quality vs academic overclaim in thesis §3.6 | G15 |
| C9 | Interop B “reference/external where feasible” | Interop B only if peer supports **VC + `eddsa-jcs-2022`**, or a new ADR for another format | walt.id tutorials often `jwt_vc_json`; silent interop would fail or force format explosion | walt.id Wallet/Verifier2 docs (Aug 2026) | G14 |
| C10 | Claim minimization described; UI still at risk of SD language | Design report: **do not strip signed fields and keep issuer proof**; honest full-VC presentation or issuer-subset credentials | Data Integrity signs the canonical document | W3C Data Integrity 1.0; vc-di-eddsa | G7, G12, consent implementation |
| C11 | Thesis Indy+Aries+DIDComm+EIP-4337 as system design | **Rejected as implementation architecture**; V2.1/revised OpenID+local registry+optional EVM hash only | Incompatible protocol family and overclaim | V2.1 non-goals; OpenID 1.0 Final; ADR 0001 | Thesis G16 rewrite |
| C12 | Thesis ZKP/zk-SNARK | Remain **non-goal**; truthful wording mandatory | Cryptosuite is not ZKP | V2.1; VC 2.0 does not imply SNARKs | UI, thesis |
| C13 | Thesis “full eIDAS/EUDI/NIST/KVKK” | **Architectural/privacy principles only**; ARF v3.0.0 informative | No FCAF/trusted-list evidence | EUDI ARF v3.0.0 (Jul 2026) README: ARF not legally binding | G12, G16 |
| C14 | Thesis VC 2.0 cited as Rec Mar 2023 | Cite **Rec 15 May 2025** | Publication history | w3.org/standards/history/vc-data-model-2.0 | Bibliography |
| C15 | Thesis performance/OWASP scores as results | **Do not import into the plan as acceptance metrics** | Unreproducible in supplied PDF; conflicts with G0 | Thesis §3.6–3.8 vs G0 | G15, G16 |
| C16 | Authority: V2.1 vs thesis unspecified in V2.1 PDF | **Revised plan > V2.1 PDF > G0 evidence for code > thesis for motivation only** | Resolve D1–D7 | This review | All agents |
| C17 | Demo hosts not constrained | **Ban europa.eu / eudi / national eID / e-Devlet identifiers** | G0/reconciliation UI overclaim | G0 GAP-13; ScanQr demo URI | G12 |
| C18 | CID 1.0 not in V2.1 table | Add **Controlled Identifiers 1.0** to baseline table | Rec 15 May 2025; used by DI verification methods | W3C TR cid-1.0 | G2 docs |
| C19 | Bitstring 1.0 correctly Rec in V2.1; 1.1 draft warning | **Keep**; confirm Rec 15 May 2025 and 1.1 FPWD 24 Sep 2026 | Independent verification of TR pages on 5 Oct 2026 | w3.org/TR/vc-bitstring-status-list/ | None (keep) |
| C20 | Product roles, L0–L4, evidence E1–E12, AI/chain bounds, DCQL VP, fail-closed, non-goals (mobile/HSM/ZKP/EUDI cert/Indy) | **Keep as-is** | Already sound | V2.1; this review §KEEP | None |

---

## Changes considered and rejected

| Idea | Why rejected |
| --- | --- |
| Add native mobile / Multipaz SecureArea now | Explicit non-goal; scope explosion |
| Add BBS+ / SD-JWT / mDL to match EUDI/walt.id | Feature-count; no evidence of need for Golden Path |
| Restore Hyperledger Indy as “more decentralized” | Conflicts with OpenID 1.0 profile already chosen |
| Use EIP-4337 for recovery | Not a DID/VC control; extra chain complexity |
| Claim EUDI conformance via ARF reading | ARF is informative; FCAF not in scope |
| Hardware HSM requirement | Not available; would block the prototype |
| Silent switch to VC 2.1 | Still a Working Draft |
| Silent switch to Bitstring 1.1 | FPWD |
| Declare current code COMPLETE because V2.1 is detailed | G0 shows otherwise; plan ≠ implementation |
