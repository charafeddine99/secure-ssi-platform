# Secure SSI Platform — Interoperability and Standards Report

**Review date:** 15 October 2026 · **Profile authority:** [Final Implementation Plan](SECURE_SSI_PLATFORM_FINAL_IMPLEMENTATION_PLAN.md).

## Frozen project profile

- W3C DID Core 1.0; synthetic `did:web` issuer and short-lived `did:key` holder fixtures.
- W3C VC Data Model 2.0 and Data Integrity 1.0.
- `eddsa-jcs-2022`, Ed25519, and RFC 8785 JCS.
- W3C Bitstring Status List 1.0.
- OpenID4VCI 1.0 and OpenID4VP 1.0 using the documented project profiles (pre-authorized issuance, JWT proof, DCQL, wallet-bound server session).
- Complete signed credentials are presented; no claim-level cryptographic selective disclosure is implemented.

The profile was not migrated during this review.

## Official-source recheck

| Standard | Current official source observation | Project decision |
|---|---|---|
| Bitstring Status List | The [W3C specification series](https://www.w3.org/TR/vc-bitstring-status-list/all/) lists v1.0 as a Recommendation and v1.1 as a First Public Working Draft dated 24 September 2026. | Keep required v1.0; v1.1 is monitor-only until an ADR and project-owner approval. |
| EdDSA Cryptosuites | The [W3C EdDSA Recommendation](https://www.w3.org/TR/vc-di-eddsa/) includes both `eddsa-jcs-2022` and `eddsa-rdfc-2022`; its JCS section specifies RFC 8785 canonicalization. | The selected JCS suite exists in the Recommendation; no suite change is needed. This does not itself prove the local implementation interoperates. |
| VC Data Model | [VC Data Model 2.0](https://www.w3.org/TR/vc-data-model-2.0/) is the frozen Recommendation; v2.1 remains draft/monitor context in the baseline. | Retain v2.0. |
| OpenID4VCI / OpenID4VP | The OpenID Foundation's current [VCI](https://openid.net/specs/openid-4-verifiable-credential-issuance-1_0.html) and [VP](https://openid.net/specs/openid-4-verifiable-presentations-1_0.html) URLs are the errata-corrected Final documents. | Use the plan's explicit subset/profile; protocol naming is not conformance evidence. |

## Local evidence and boundaries

The current source checkpoint has focused G6/WP-08 evidence (48 passed), current Identity regression evidence (686 passed, 5 Hardhat-dependent skips), current wallet-consent/auth/privacy evidence (80 passed), and a passing Web wallet API contract check (9 assertions). These are own-component checks; they do not establish an independently implemented wallet/verifier run or general standards conformance.

No independently implemented wallet, issuer, verifier, or pinned conformance suite was executed. No external repository was pinned to a commit and used as a peer. No L4 or certification claim is made. The local Python/Docker environment is now usable; G14 remains `BLOCKED` because no independent peer or approved pinned vector set supporting the frozen `eddsa-jcs-2022` profile is available in the current project setup.

## Reproducible next evidence

1. Record peer implementation, release/commit SHA, configuration, and supported formats.
2. Exchange fixed positive and negative issuance/presentation vectors using the frozen profile.
3. Record exact proof, DID resolution, status, DCQL, nonce/state, trust, and error outcomes.
4. Preserve inputs and redacted outputs; do not label self-tests as external certification.
5. Propose a profile ADR before adopting any draft, alternate cryptosuite, or credential format.
