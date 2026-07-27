# ADR 0001: DID Methods for the Synthetic Prototype

- **Status:** Accepted
- **Date:** 2026-07-23
- **Scope:** First synthetic issuance and verification prototype
- **Decision owners:** Project team

## Context

The project needs resolvable verification material for a university-like issuer and a holder-controlled identifier for a local, synthetic demonstration. It also has future emergency-recovery goals. No single evaluated DID method satisfies the immediate simplicity goal and the long-term recovery goal without additional infrastructure or governance.

[DID Core v1.0](https://www.w3.org/TR/did-core/) is the stable W3C Recommendation baseline. DID Core defines the common data model and operations but does not select a DID method. DID Core v1.1 is a 2026 Candidate Recommendation and is not the compatibility baseline for this milestone.

The evaluated `did:web` and `did:key` method specifications are community drafts, not W3C Recommendations. Their status and limitations must remain visible in code, documentation, and demonstrations.

## Decision

### Standards baseline

- Implement DID documents against W3C DID Core v1.0.
- Track DID Core v1.1 separately and reassess after it becomes a Recommendation.
- Use an explicit method allowlist. A verifier must not resolve arbitrary DID methods supplied by untrusted input.

### Institutional issuer

Use `did:web` for the synthetic university issuer.

- The issuer is naturally associated with an institutional domain.
- Its DID document can be inspected with ordinary HTTPS tooling.
- Key rotation and deactivation can be represented by controlled DID document updates.
- The prototype will use a local fixture/resolver abstraction; it will not require a real public domain.

This decision does not make DNS or HTTPS decentralized. Domain, DNS, certificate, hosting, and deployment control are part of the issuer trust model.

### Synthetic holder

Use `did:key` only for short-lived, generated holder fixtures in local tests and demonstrations.

- It provides deterministic, offline DID document expansion from public key material.
- It avoids a ledger or external resolver in the first cryptographic spike.
- It keeps synthetic holder private keys outside services.

`did:key` is explicitly prohibited for real users, long-lived credentials, and the recovery implementation because its method specification does not support update or deactivation. A compromised key cannot be rotated within the identifier.

### Blockchain role

Do not use a ledger-based DID method in the first prototype. Blockchain remains a separately justified anchoring boundary for non-identifying digests. No DID, DID document, credential, claim, holder reference, or guardian identity may be written to the ledger.

### Unresolved production decision

The production-capable holder DID method remains undecided. It must support secure update/deactivation or an equivalent recovery mechanism, privacy-preserving identifiers, method governance, resolver availability, and a documented migration path.

## Decision matrix

| Option | Prototype simplicity | Update/deactivate | Privacy | Infrastructure | Decision |
| --- | --- | --- | --- | --- | --- |
| `did:web` for institutional issuer | High | Through controlled web publication | Resolution is observable by DNS/web host | Domain, DNS, TLS, hosting | Selected for issuer |
| `did:key` for synthetic holder | High | No | Reuse is correlatable | None for resolution | Selected only for short-lived fixtures |
| `did:web` for holder | Medium | Yes, through website control | Poor fit for users without domains | Per-holder hosting/domain control | Rejected |
| Ledger-based DID for all actors | Low | Method-specific | Public activity can be correlatable | Nodes/RPC, fees, governance | Deferred |
| Custom DID method | Low | Custom | Unknown | Full method/resolver ecosystem | Rejected |

## Consequences

### Positive

- The first prototype can be deterministic and local.
- Issuer control is easy to explain and inspect.
- Holder keys remain holder-side fixtures.
- Blockchain complexity is not falsely presented as necessary for DID resolution.

### Negative and risks

- Two resolver implementations are required behind one resolver interface.
- `did:web` inherits DNS, certificate, web-hosting, availability, and resolution-tracking risks.
- `did:key` is unsuitable for recovery and long-term identity.
- A synthetic prototype cannot demonstrate production holder lifecycle or method governance.

## Required safeguards

1. Resolver code accepts only `did:web` and `did:key` during the prototype.
2. Network resolution is disabled by default in tests.
3. `did:web` responses require HTTPS outside local development, size/time limits, exact identifier matching, and no redirect to a different host.
4. DID documents are validated before use.
5. Verification methods must be authorized for `assertionMethod`.
6. Private keys never appear in DID documents, API bodies, logs, MongoDB, Redis, or blockchain payloads.
7. Fixtures are labelled synthetic and are never reused as production keys.

## Acceptance criteria for the next implementation milestone

- A resolver interface with explicit result/error types.
- Deterministic `did:key` fixture resolution tests.
- Local `did:web` issuer fixture resolution tests without external network access.
- Rejection tests for unsupported methods, mismatched DID document IDs, missing assertion methods, oversized documents, and private key material.
- No issuance endpoint before resolver validation tests pass.

## Review triggers

Review or supersede this ADR before:

- external user testing;
- implementing holder recovery;
- using long-lived credentials;
- connecting a public DID resolver;
- choosing a blockchain network;
- DID Core v1.1 becoming a Recommendation;
- a selected method specification changing incompatibly.

## References

- [W3C DID Core v1.0](https://www.w3.org/TR/did-core/)
- [W3C DID Core specification series](https://www.w3.org/TR/did-core/all/)
- [W3C DID Resolution v0.3 Working Draft](https://www.w3.org/TR/did-resolution/)
- [`did:web` method draft](https://w3c-ccg.github.io/did-method-web/)
- [`did:key` method v0.9 draft](https://w3c-ccg.github.io/did-key-spec/)
