# ADR 0002: Verifiable Credential Data Model and Proof Format

- **Status:** Accepted
- **Date:** 2026-07-23
- **Scope:** First synthetic issuance and verification prototype
- **Decision owners:** Project team

## Context

The project requires a stable credential data model and one narrowly defined proof format before implementing issuance or verification. Supporting multiple formats in the first spike would multiply canonicalization, key representation, verification, and negative-test paths.

W3C Verifiable Credentials Data Model v2.0, Verifiable Credential Data Integrity v1.0, and Data Integrity EdDSA Cryptosuites v1.0 became W3C Recommendations on 15 May 2025. VC Data Model v2.1 and EdDSA Cryptosuites v1.1 are 2026 drafts and are not the baseline for this milestone.

## Decision

### Credential data model

Use [W3C Verifiable Credentials Data Model v2.0](https://www.w3.org/TR/vc-data-model-2.0/) with:

- `https://www.w3.org/ns/credentials/v2` as the first JSON-LD context;
- `VerifiableCredential` as the base type;
- an opaque `urn:uuid` credential identifier;
- issuer and credential-subject identifiers that follow ADR 0001;
- `validFrom` and, when policy requires it, `validUntil`;
- synthetic, allowlisted claims only.

Version 2.1 draft features are not used until separately reviewed.

### Securing mechanism

Use [Verifiable Credential Data Integrity v1.0](https://www.w3.org/TR/vc-data-integrity/) with:

- proof `type`: `DataIntegrityProof`;
- cryptosuite: `eddsa-jcs-2022`;
- signature algorithm: Ed25519;
- verification-method representation: `Multikey` with `publicKeyMultibase`;
- proof purpose: `assertionMethod`;
- `created` timestamp in UTC;
- `verificationMethod` as an absolute DID URL.

`eddsa-jcs-2022` is selected over `eddsa-rdfc-2022` for the first spike because it uses the JSON Canonicalization Scheme and avoids implementing the RDF Dataset Canonicalization path. This is an implementation-scope decision, not a claim that JCS is universally superior.

### Disclosure and status

- The first spike is full-disclosure and synthetic only.
- Selective disclosure is required before any real personal-claim pilot.
- BBS, SD-JWT, JOSE/COSE, and other securing mechanisms are deferred, not rejected.
- An application-local MongoDB lifecycle and revocation API is now implemented.
  An interoperable credential-embedded status format and privacy-preserving
  publication mechanism remain deferred until issuer policy and privacy
  requirements are written.
- Long-lived credential issuance is blocked until status and key-rotation behavior are defined.

### Verification result

Verification returns structured checks rather than one unexplained boolean:

- document structure valid;
- supported context and type;
- issuer DID resolved;
- verification method authorized for `assertionMethod`;
- proof cryptosuite supported;
- signature valid;
- validity window accepted;
- status accepted when status support is added;
- machine-readable reason codes.

A successful signature alone does not establish that an issuer is trusted or that claims are true.

## Alternatives considered

| Option | Advantages | Drawbacks | Decision |
| --- | --- | --- | --- |
| VC Data Model 2.0 + Data Integrity EdDSA/JCS | W3C Recommendations, JSON-oriented canonicalization, clear Ed25519 test vectors | JSON-LD context handling and canonicalization still require care | Selected |
| VC Data Model 2.0 + Data Integrity EdDSA/RDFC | Strong linked-data semantics | Adds RDF dataset canonicalization complexity to first spike | Deferred |
| VC Data Model 2.0 + JOSE/JWT | Broad JOSE tooling | Different envelope and claim-mapping paths; easy to confuse signature with trust | Deferred |
| SD-JWT-based selective disclosure | Better disclosure minimization | Additional holder-binding and disclosure verification complexity | Required evaluation before real-data pilot |
| Custom JSON credential/signature | Superficially simple | Poor interoperability and unsafe protocol design risk | Rejected |

## Consequences

### Positive

- One stable standards baseline.
- One signature algorithm and canonicalization path.
- Small, auditable verification surface for the first spike.
- Official test vectors exist for later conformance testing.

### Negative and risks

- JSON-LD context handling can involve remote-resource and context-integrity risks.
- JCS requires strict I-JSON-compatible input and deterministic processing.
- Ed25519 private-key protection remains an operational responsibility.
- Full disclosure is unsuitable for real identity claims.
- Status and selective-disclosure interoperability remain unresolved.

## Required safeguards

1. Pin or bundle approved contexts; verification must not fetch arbitrary contexts from credential input.
2. Reject duplicate JSON properties, unsupported contexts, unknown proof suites, and malformed timestamps.
3. Enforce a maximum credential size and claim allowlist.
4. Resolve only method-allowlisted issuer DIDs.
5. Confirm `verificationMethod` belongs to the resolved issuer and is authorized under `assertionMethod`.
6. Use maintained cryptographic libraries; do not implement Ed25519 primitives manually.
7. Never log credentials, claims, proof values, or private keys.
8. Use synthetic fixtures and deterministic negative tests.

## Acceptance criteria for the next implementation milestone

- Versioned credential and proof JSON Schemas.
- Unsigned synthetic credential fixture.
- Signed valid fixture using official-compatible `eddsa-jcs-2022` processing.
- Negative fixtures for claim tampering, proof tampering, wrong issuer, wrong proof purpose, expired credential, unsupported context, and unsupported cryptosuite.
- Verification result with explicit check outcomes and reason codes.
- No real personal data and no public issuance endpoint.

## Review triggers

Review or supersede this ADR before:

- adding selective disclosure;
- adding credential status/revocation;
- supporting another securing mechanism;
- external interoperability testing;
- VC Data Model v2.1 or EdDSA Cryptosuites v1.1 becoming Recommendations;
- changing the issuer or holder DID method.

## References

- [W3C Verifiable Credentials Data Model v2.0](https://www.w3.org/TR/vc-data-model-2.0/)
- [W3C VC Data Model specification series](https://www.w3.org/TR/vc-data-model/all/)
- [W3C Verifiable Credential Data Integrity v1.0](https://www.w3.org/TR/vc-data-integrity/)
- [W3C Data Integrity EdDSA Cryptosuites v1.0](https://www.w3.org/TR/vc-di-eddsa/)
- [W3C Securing Verifiable Credentials using JOSE and COSE](https://www.w3.org/TR/vc-jose-cose/)
- [RFC 8032: Ed25519 and Ed448](https://www.rfc-editor.org/rfc/rfc8032)
- [RFC 8785: JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785)
