# SSI Plan Traceability and Decision Matrix

**Date:** 5 October 2026  
**How to read:** each row is classified as exactly one of NORMATIVE | PROJECT PROFILE | IMPLEMENTATION CHOICE | OPTIONAL/FUTURE for the *decision itself*. Evidence columns describe how the team should accept the row.

| ID | Decision / Requirement | Source | Normative status | Classification | Rationale | Affected work package / gate | Acceptance evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| D-VC20 | Use VC Data Model 2.0 | W3C TR vc-data-model-2.0 Rec 15 May 2025; V2.1; ADR 0002 | Recommendation | NORMATIVE (selected spec) | 2.1 is WD 30 Sep 2026 | G2, G4, G5 | Issued JSON-LD uses v2 context; fixture tests |
| D-DI10 | Use Data Integrity 1.0 proofs | W3C TR vc-data-integrity Rec 15 May 2025 | Recommendation | NORMATIVE (selected spec) | Embedded proofs for this profile | G2, G4, G6 | Fail-closed verify; negative tamper tests |
| D-EDDSA-JCS | Cryptosuite `eddsa-jcs-2022` | W3C TR vc-di-eddsa Rec 15 May 2025 | Recommendation defines two suites | PROJECT PROFILE | JCS chosen over RDFC for implementation simplicity; RFC 8785 is Informational but required by this suite | G2, G4 | Test vectors; RFC 8785 canonical bytes |
| D-CID | Align verification methods with CID 1.0 | W3C TR cid-1.0 Rec 15 May 2025 | Recommendation | PROJECT PROFILE | DID Core + Data Integrity implementations use CID method types (`Multikey`) | G2, G6 | DID document fixtures |
| D-DIDCORE | DID Core 1.0 as DID architecture | W3C TR did-core Rec 19 Jul 2022 | Recommendation | NORMATIVE (selected spec) | Does not include methods | G2, G3 | Resolver tests per method |
| D-DIDWEB | Issuer `did:web` | w3c-ccg did-method-web (community draft); ADR 0001 | Not a W3C Rec | PROJECT PROFILE | Institutional domain fit; HTTPS inspectable | G2, G4, G6 | Resolution of `.well-known/did.json` or labeled fixture + port test |
| D-DIDKEY | Holder `did:key` fixtures only | w3c-ccg did-key (community draft); ADR 0001 | Not a W3C Rec | PROJECT PROFILE | Offline demos; no update/deactivate — forbidden for long-lived users | G2, G3, G8 | Rotation creates new DID; tests forbid treating did:key as updatable |
| D-NO-CUSTOM-DID | No custom DID method | DID Core; review | — | PROJECT PROFILE | Avoids non-interoperable identifiers | G2 | Allowlist in resolver |
| D-NO-LEDGER-DID | No Indy/ledger DID | V2.1; ADR 0001; review | — | PROJECT PROFILE | Ledger not required by DID Core; thesis Indy stack rejected | G2, G10 | Architecture docs |
| D-VCI10 | OpenID4VCI 1.0 Final | OIDF 16 Sep 2025 | Final Specification | NORMATIVE (selected spec) | Draft 13 token-c_nonce model obsolete | G2, G4 | Metadata + traces |
| D-PAC | Pre-authorized code as demo grant | OpenID4VCI 1.0 (grant defined); V2.1 | Spec defines; selection is profile | PROJECT PROFILE | Simpler controlled demo than auth code | G4 | Single-use/expiry tests |
| D-TOKEN | Token Endpoint exchange of PAC | OpenID4VCI 1.0 | NORMATIVE for that grant | NORMATIVE | PAC is an OAuth grant | G4 | `/token` traces |
| D-NONCE-EP | Nonce Endpoint for `c_nonce` | OpenID4VCI 1.0 Final §7 | NORMATIVE if proofs require c_nonce | NORMATIVE | Token-response c_nonce is draft hangover | G2, G4 | `/nonce` returns c_nonce; proof includes it |
| D-VCI-JWT-PROOF | Issuance PoP type `jwt` | OpenID4VCI 1.0 Appendix F (`jwt`,`di_vp`,`attestation`) | Spec offers types | PROJECT PROFILE | Easier negative tests; issued VC remains DI | G4 | Invalid/missing/replayed proof rejected |
| D-VCI-ATTEST | Wallet attestation proofs | OpenID4VCI; Multipaz | Optional in spec | OPTIONAL/FUTURE | No attestation infra | G14 unsupported list | Listed unsupported |
| D-AUTHCODE | Authorization code + PKCE | OpenID4VCI | Defined | OPTIONAL/FUTURE (deferred) | Demo uses PAC | G14 | Listed unsupported |
| D-VP10 | OpenID4VP 1.0 Final | OIDF Final | Final Specification | NORMATIVE (selected spec) | | G5 | Request/response traces |
| D-DCQL | `dcql_query`; wallet evaluates | OID4VP 1.0 §6 | NORMATIVE for 1.0 primary query | NORMATIVE | DIF PE is not the 1.0 primary language | G5, G7 | DCQL match/unsatisfied tests |
| D-STATE | `state` always required | OID4VP (conditionally required); V2.1 | Tightening | PROJECT PROFILE | Session correlation | G5 | Missing state rejected |
| D-NONCE-VP | Fresh nonce, single use | OID4VP | NORMATIVE (replay) | NORMATIVE | | G5, G13 | Replay rejected |
| D-DP | `response_mode=direct_post` | OID4VP | Defined | PROJECT PROFILE | Fits web verifier | G5 | POST response tests |
| D-XDEVICE | QR cross-device + same-browser link | walt.id flow types (reference); V2.1 | Not a W3C MUST | PROJECT PROFILE | Web prototype | G5, G12 | Both transports in E2E |
| D-DCAPI | Digital Credentials API | OID4VP Appendix A; EUDI | Optional path | OPTIONAL/FUTURE | Native/browser OS wallets | G14 | Listed unsupported |
| D-BSL | Bitstring Status List 1.0 | W3C Rec 15 May 2025 | Recommendation | NORMATIVE (selected spec) | 1.1 is FPWD | G6 | Revoke→reject; corrupt list fail-closed |
| D-TRUST-REG | Explicit trust registry | V2.1; EUDI trusted lists as analog only | Not W3C VC MUST | PROJECT PROFILE | Prefix matching is not trust | G6 | Unregistered issuer rejected |
| D-NO-EUDI-CLAIM | No EUDI/gov compliance claim | EUDI ARF v3.0.0 informative; V2.1 non-goal | — | PROJECT PROFILE | Avoid overclaim | G12, G16 | Copy/screenshot review |
| D-CONSENT | Consent bound to VP payload | V2.1; privacy principles | Not a substitute for SD | PROJECT PROFILE | UX correctness | G7 | Deny path; payload check |
| D-NO-ZKP | No ZKP/BBS+/crypto SD | V2.1 non-goal; cryptosuite reality | — | PROJECT PROFILE | eddsa-jcs-2022 is not SD | G7, G12 | UI strings |
| D-CLAIM-UX | Prefer full-VC present + honest UI, or issuer subset VC | Data Integrity semantics; review | — | PROJECT PROFILE | Omitting signed fields breaks proof | G5, G7 | Tests that stripped VC fails |
| D-AI-BOUND | AI never overrides crypto | V2.1 | — | PROJECT PROFILE | Safety | G9, G6 | Invalid sig + low risk = reject |
| D-AI-LABEL | Heuristic unless artifacts exist | G0 evidence | — | PROJECT PROFILE | Academic honesty | G9, G16 | Model card or heuristic README |
| D-CHAIN | Optional SHA-256 EVM anchor | V2.1 | — | PROJECT PROFILE | Integrity ≠ validity | G10 | Failure visible; no PII |
| D-NO-4337 | Do not use EIP-4337 as identity | Thesis vs V2.1 | — | PROJECT PROFILE | Wrong abstraction | G10, G16 | Absent from architecture |
| D-NO-INDY | No Indy/Aries/DIDComm in V2 | V2.1 non-goal; OpenID 1.0 | — | PROJECT PROFILE | Protocol family choice | All | Code/docs scan |
| D-RECOVERY | M-of-N + timelock + rotate | Thesis intent; V2.1 G8 | Not SSI-standard | PROJECT PROFILE | Accessibility of keys | G8 | Abuse negatives |
| D-WEB-WALLET | Custodial web wallet prototype | Review vs Multipaz | — | PROJECT PROFILE | Scope honesty | G3, G12 | Docs + UI |
| D-NO-HSM | No HSM/SecureArea claim | V2.1 non-goal | — | PROJECT PROFILE | | G3 | KeyCustody port only |
| D-MONGO | Mongo durable, Redis ephemeral | V2.1 | — | IMPLEMENTATION CHOICE | Prototype persistence | G1 | Schema ownership |
| D-GATEWAY | API Gateway public boundary | V2.1 | — | IMPLEMENTATION CHOICE | Could be BFF; still one boundary | G1 | Network rules |
| D-LADDER | L0–L4; COMPLETE only L3/L4 | V2.1 | — | PROJECT PROFILE (process) | Prevents file-exists completion | All | Reports |
| D-G0 | G0 already run 4 Oct 2026 | G0 reports | — | IMPLEMENTATION CHOICE (process) | Don’t block on duplicate G0 | G0 | Delta only |
| D-INTEROP-A | Own-stack Golden Path | V2.1 G14 | — | PROJECT PROFILE | Minimum interop | G11, G14 | E2E evidence |
| D-INTEROP-B | walt.id only if format shared | walt.id docs Aug 2026 | Reference impl | OPTIONAL/FUTURE | jwt_vc_json vs DI mismatch | G14 | Explicit format ADR |
| D-FORMAT-EXTRA | SD-JWT, mDL | walt.id/Multipaz/EUDI | Other specs | OPTIONAL/FUTURE | Feature-count risk | — | Out of core |
| D-NATIVE | Native mobile | Multipaz; thesis future work | — | OPTIONAL/FUTURE | Explicit non-goal | — | Future work list |
| D-KVKK | Privacy principles / minimization | Thesis; KVKK 6698 | Legal, not protocol | PROJECT PROFILE | Principles, not a certification | G7, G16 | Consent + retention notes |
| D-THESIS | Thesis must follow this profile | Review D1–D7 | — | PROJECT PROFILE (academic) | Two-stack contradiction | G16 | Rewritten standards chapter |

---

## Traceability skeleton (requirement → evidence)

Use the repository matrix `docs/requirements/V2_REQUIREMENTS_MATRIX.md` for live status. Snapshot for this review:

| Requirement | Design | Code area (indicative) | UI | Test | E2E | Interop | Status at review |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VC 2.0 + DI proof | ADR 0002; design §6 | identity-service credentials/proofs | credential detail | unit/fixtures | Golden Path | C optional | PARTIAL / CLAIMED |
| Fail-closed verify | design §6 | oid4vp_service | matrix | WP-01 claimed | not re-run here | — | NOT YET VERIFIED (this review) |
| Holder binding crypto | design §8 | oid4vp_service | matrix | WP-02 claimed | not re-run here | — | NOT YET VERIFIED |
| Trust registry | design §9 | missing / prefix | trust badges | missing | — | — | MISSING |
| DCQL | design §8 | PE v2 present | request builder | missing DCQL | — | — | MISSING / CONTRADICTED (PE vs DCQL) |
| OID4VCI nonce endpoint | design §7 | token/credential partial | issuer/wallet | missing Final nonce | — | — | MISSING / PARTIAL |
| Consent-bound VP | design §6/§8 | PresentationConsentPage | consent | partial | — | — | PARTIAL / MISREPRESENTED if ZKP labeled |
| Status list | design §10 | status_list_service | status UI | partial | revoke path | — | PARTIAL |
| Recovery | design §11 | recovery-service | guardian portal | unit exist | secondary GP | n/a | PARTIAL (project protocol) |
| AI bounded | design §12 | fraud-service | risk | policy tests | high-risk path | n/a | PARTIAL / MISREPRESENTED if “trained ML” |
| Integrity anchor | design §13 | blockchain + integrity domain | anchor status | hardhat | optional | n/a | PARTIAL |
| Interop A | plan G14 | all | all roles | e2e | required | A | MISSING until GP L3 |
| Interop B | plan G14 | format-dependent | n/a | external | optional | B | MISSING |
