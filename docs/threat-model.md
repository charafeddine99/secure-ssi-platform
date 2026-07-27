# Threat Model

## Purpose and scope

This document defines the security assumptions for the academic prototype before identity, fraud, blockchain, or recovery logic is implemented. It covers the planned web client, API Gateway, internal services, data stores, blockchain workspace, and guardian interactions.

This is an initial design artifact, not a security certification. It must be reviewed whenever an API, trust relationship, stored data category, or cryptographic operation changes.

## Protected assets

| Asset | Security objective |
| --- | --- |
| Holder identifiers and credential claims | Confidentiality, integrity, data minimization |
| Issuer signing keys | Confidentiality, integrity, availability |
| Holder private keys | Holder control; never transmitted to platform services |
| Holder wallets and ownership bindings | Integrity, confidentiality, object-level authorization |
| Holder key references | Integrity, least privilege, resistance to substitution |
| Presentation challenges | Unpredictability, domain/audience binding, expiry, non-replay |
| Verification results | Integrity, freshness, auditability |
| Fraud signals and risk results | Confidentiality, integrity, explainability |
| Guardian approvals | Authenticity, integrity, non-replay |
| Recovery state | Integrity, availability, resistance to coercion |
| Blockchain anchors | Integrity and unlinkability where possible |
| Audit events | Integrity, ordering, retention control |
| Service credentials and configuration | Confidentiality and least privilege |

## Actors

- **Holder:** Controls their identifier and presents credentials or proofs.
- **Issuer:** Issues credentials under an explicit governance policy.
- **Verifier:** Requests the minimum data necessary for a declared purpose.
- **Guardian:** Participates in a threshold recovery policy and cannot recover an identity alone.
- **Platform operator:** Maintains infrastructure without receiving holder private keys.
- **External attacker:** Has no legitimate platform access.
- **Malicious or compromised insider:** Has some authorized platform or guardian access.

## Trust zones and boundaries

| Zone | Components | Boundary rule |
| --- | --- | --- |
| Untrusted client zone | Browser, holder wallet, external verifier | All input is untrusted; never place secrets in browser-delivered configuration |
| Public edge | API Gateway | The only planned production public boundary; production authentication, rate limits, request limits, and correlation IDs belong here |
| Internal application zone | Identity, Fraud, Recovery services | Not publicly exposed in production; use authenticated service identities and explicit authorization |
| Data zone | MongoDB, Redis | No direct client access; separate credentials and minimum retention |
| Key-management zone | Opaque holder-key ports with synthetic local adapter; planned KMS/HSM or external wallet | The public test derivation is non-secret and prohibited outside local tests; production keys must not be stored in source, MongoDB, Redis, or logs |
| Blockchain network | Smart contracts and public ledger | Treat all written data as public and permanent; only non-identifying digests may be considered |
| Guardian zone | Independent guardian devices/services | A single guardian is not trusted to complete recovery |

## Entry points

- Public HTTP requests to the API Gateway.
- Local development requests to the Identity Service login, current-user, and
  credential APIs; synthetic authentication does not make this a public edge.
- Credential presentations originating from holder-controlled software.
- Issuer administration operations.
- Fraud signals supplied by internal services.
- Guardian approval messages.
- Blockchain RPC responses and events.
- Environment configuration, deployment pipelines, and dependency updates.

## Key threats and required controls

| ID | Threat | Impact | Required design controls | Planned verification |
| --- | --- | --- | --- | --- |
| T01 | Credential or proof replay | Unauthorized acceptance | Nonces, audience binding, expiry, one-time challenge storage | Replay integration tests |
| T02 | Forged issuer or credential | False identity claims | Trusted issuer policy, signature verification, status checking | Local signature, 15 tamper variants, and application status tests implemented; governance/interoperability planned |
| T03 | Correlation through identifiers or ledger data | Privacy loss | Pairwise identifiers, selective disclosure, data minimization, never put claims/DIDs on-chain | Privacy review and ledger inspection |
| T04 | Private-key disclosure | Identity takeover | Holder-side key custody, KMS/HSM for production issuer keys, rotation, no secret logging | Synthetic key redaction/output tests implemented; production secret scanning and rotation drills planned |
| T05 | Fraud model manipulation or evasion | Incorrect risk decision | Input validation, signed signal provenance, model/version tracking, human-review policy | Adversarial and drift tests |
| T06 | Biased or unexplained risk decisions | Unfair denial and compliance risk | Reason codes, evaluation datasets, appeal path, prohibit autonomous irreversible recovery denial | Fairness and explainability review |
| T07 | Guardian collusion or coercion | Account takeover | Threshold approvals, independent channels, cooling-off period, holder notification | Threshold and coercion scenario tests |
| T08 | Recovery request replay | Account takeover | Unique request IDs, expiry, state machine, idempotency, signed approvals | State-transition and replay tests |
| T09 | Internal service impersonation | Data alteration or disclosure | Workload identity, mutual authentication, least-privilege authorization | Unauthorized service-call tests |
| T10 | API denial of service | Loss of availability | Rate limits, request size limits, timeouts, queues, circuit breakers | Load and fault-injection tests |
| T11 | Log or database data leakage | Privacy loss | Redaction, field allowlists, encryption, retention limits, access audit | Log inspection and retention tests |
| T12 | Smart-contract defect or privileged upgrade | Permanent loss or takeover | Minimal contract scope, independent review, tests, explicit upgrade governance | Static analysis and testnet review |
| T13 | Compromised dependency or build | Code execution | Lockfiles, dependency review, reproducible builds, image scanning | CI supply-chain checks |
| T14 | Stale or spoofed blockchain/RPC data | Incorrect state | Network allowlist, confirmation policy, multiple-provider strategy where justified | Reorg and provider-failure tests |
| T15 | `did:web` DNS, TLS, or hosting compromise | Issuer impersonation | HTTPS, exact host/ID checks, controlled publishing, key rotation, monitoring | Local mismatch/size/private-material tests implemented; network tests planned |
| T16 | Long-lived or reused `did:key` | Irrecoverable compromise and correlation | Synthetic short-lived use only; prohibit real users and recovery | Method/key allowlist tests implemented; lifecycle policy test planned |
| T17 | Malicious JSON-LD context or unsupported proof suite | Verification bypass or resource exhaustion | Pinned contexts, suite allowlist, no arbitrary remote context loading, size/time limits | DID/VC context, size, duplicate-property, non-finite-number, and proof-suite rejection tests implemented |
| T18 | Canonicalization confusion, proof tampering, or key substitution | Signature bypass or verification under an attacker key | RFC 8785 library, signed proof configuration, exact Ed25519 Multikey/controller/authorization checks, trusted-key comparison | Deterministic JCS, proof tamper, wrong-length signature, alternate-key, and substituted DID-key tests implemented |
| T19 | Malformed, oversized, deeply nested, or ambiguous credential HTTP input | Resource exhaustion, parser disagreement, or unsafe error disclosure | Request/credential size limits, depth limit, strict UTF-8 JSON, duplicate/non-finite rejection, strict envelope, sanitized errors, request IDs, no body logging | API transport, error-contract, OpenAPI, tamper, and safe-500 tests implemented |
| T20 | Mongo credential or connection-string disclosure | Database takeover and privacy loss | URI redaction, secret placeholders, least-privilege application user, no URI logging | Configuration, connection failure, and representation redaction tests implemented |
| T21 | Lost update or stale concurrent write | Authorization/data state overwritten | Atomic identity-plus-version predicates and version increment | User and credential stale-version repository tests implemented |
| T22 | Soft-deleted record returned as active | Disabled identity reuse or retained data exposure | `deletedAt=null` on normal reads/lists; user deletion also disables account | User and credential soft-delete tests implemented |
| T23 | Duplicate username or credential identifier | Account confusion or credential ambiguity | Stable unique indexes and controlled duplicate errors | Index and duplicate repository tests implemented |
| T24 | Audit event mutation or sensitive metadata capture | Evidence loss or secret exposure | Append-only repository port, closed event enum, bounded metadata, sensitive-key rejection | Audit mapper, metadata, duplicate, ordering, and real-Mongo tests implemented |
| T25 | Unauthorized or repeated credential revocation | Denial of valid credential use or lifecycle ambiguity | Dedicated `credentials:revoke` permission, current-user resolution, terminal `REVOKED`, atomic state/version predicate | Admin/issuer, verifier-denial, repeated-revocation, and stale-version tests implemented |
| T26 | Per-credential status lookup correlation | Issuer learns verifier interest in a holder/credential | Public grouped Bitstring Status List, shared cache headers, and local-only warning on exact lookup | Shared publication, ETag, `304`, and status mapping tests implemented; CDN/privacy review still required |
| T27 | Revocation state and central audit divergence | Incomplete evidence after partial persistence failure | Embedded revocation outbox in the same credential update; standalone outbox for other events; background leases/retry | Failure preservation, lease recovery, crash-window, and duplicate-prevention tests implemented |
| T28 | Status-list assignment collision, tampering, or stale publication | Wrong credential reported revoked or current revocation omitted | Unique list/index reservation, optimistic publication version, signed document, deterministic encoding, bounded configured URL | Collision, bit orientation, signature, version, ETag, API, and opt-in real-Mongo tests implemented |
| T29 | Wallet takeover or broken object-level authorization | Foreign wallet/credential use | Application-layer owner checks after RBAC, enumeration-resistant 404, active/non-deleted state | Cross-user wallet, admin bypass, inventory, and API tests implemented |
| T30 | Holder DID or key substitution | Presentation signed under attacker control | Wallet-to-DID binding, opaque key reference, metadata/DID equality, exact credential holder binding | Cross-holder, key metadata, signer, and reconciliation tests implemented |
| T31 | Challenge theft or replay | Unauthorized/repeated presentation | Cryptographic randomness, expiry, optional holder restriction, atomic one-time status/version consumption | Entropy assumptions, expiry, replay, atomic repository, and API tests implemented |
| T32 | Cross-domain or cross-audience challenge use | Proof accepted for a different verifier context | Server-owned domain/audience, signature coverage, conflict rejection, verifier ownership | Domain/audience confusion and proof validation tests implemented |
| T33 | Credential ownership bypass | Another wallet's credential is presented | Persisted owner/wallet fields, inventory predicate, owner/wallet/holder checks in application service | Cross-wallet and cross-user tests implemented |
| T34 | Locked, disabled, or deleted wallet signing | Compromised or retired wallet remains usable | Closed wallet states, soft-delete exclusion, active-state requirement | Domain, service, repository, and API rejection tests implemented |
| T35 | Stale `PROCESSING` abuse or crash window | Permanent denial or ambiguous verification | Processing timestamp, configurable stale timeout, atomic reconciliation claim, controlled terminal policy | Crash-window, stale claim, success/failure, and idempotency tests implemented |
| T36 | Reconciliation race or audit duplication | Conflicting result or duplicate evidence | State/time/version predicate, deterministic event IDs, idempotent terminal reads | Repository claim, repeat reconciliation, and audit count tests implemented |
| T37 | Insider access to key references | Targeted key misuse | References are non-secret but sensitive; least privilege, no HTTP/audit exposure, provider-side authorization required | BSON/OpenAPI/repr and raw-key exclusion tests implemented; production access audit planned |
| T38 | Raw holder key persistence or logging | Holder identity takeover | HolderSigner port, opaque references only, redacted adapters, field allowlists | Mapper, Mongo document, API, audit, and representation tests implemented |

## Local authentication risk analysis

| Risk | Current mitigation | Residual risk |
| --- | --- | --- |
| Credential stuffing | Generic login failures and Argon2id verification | No rate limiting, breached-password screening, or adaptive detection; public exposure remains unsafe |
| Brute-force login | Argon2id cost and bounded login body | Unlimited attempts are possible because rate limiting is intentionally absent |
| Password spraying | Same failure response for all fixture accounts | No attempt aggregation, lockout, CAPTCHA, or monitoring |
| User enumeration | Unknown users verify against a fallback hash; wrong user/password/disabled login share one `401` | Network and runtime variance may still permit statistical inference without edge controls |
| Stolen bearer token | 15-minute default lifetime, audience/issuer binding, current-user re-resolution | Tokens remain usable until expiry; no blacklist, device binding, sender constraint, or secure client storage |
| JWT tampering | PyJWT signature verification and required claim validation | Shared-secret compromise permits token forgery |
| Algorithm confusion | Header algorithm must equal configured HS256; decode allowlist contains only HS256; `none` rejected | Future algorithm expansion could reintroduce confusion if not separately reviewed |
| Weak JWT secret | Minimum 32-byte check; production-like mode requires explicit configuration | Development fallback is public and intentionally provides no production security |
| Access-token replay | Short lifetime, audience, JTI, and token-use checks | JTI is not persisted or consumed; replay within the validity window is possible |
| Excessive token lifetime | Config lifetime bounded to 60–3,600 seconds; signed token lifetime cannot exceed configured value | Even the maximum window may be too long for higher-risk deployments |
| Role escalation | Closed role enum, signed claims, provider role comparison, current permission derivation | Compromise of the shared JWT secret or local registry process remains authoritative |
| Stale authorization claims | Token roles must match current provider roles on every request | No distributed cache invalidation or durable user-version claim exists |
| Disabled-user token reuse | Enabled state is checked against the selected provider on every protected request | Synthetic state is process-local; Mongo availability and database integrity become authentication dependencies when selected |
| Secret leakage through logs | Application logs omit passwords, bodies, Authorization headers, full JWTs, hashes, and signing material | Infrastructure, proxy, crash dump, or third-party logging is outside this prototype |
| Absence of rate limiting | Explicitly documented; request sizes are bounded | Brute force and denial of service remain unmitigated |
| Absence of MFA | Explicitly documented; synthetic users only | One password compromise is sufficient to obtain a token |
| Absence of token revocation | Short-lived access tokens and current user-state checks | A stolen token cannot be individually revoked before expiry |

## Security invariants

The implementation must preserve these rules:

1. Holder private keys never enter platform APIs, logs, MongoDB, Redis, or blockchain transactions.
2. No raw credential, personal claim, guardian identity, email, phone number, or DID is written to a public ledger.
3. A fraud score alone cannot issue, revoke, or recover an identity.
4. A single guardian cannot complete recovery.
5. Recovery transitions are explicit, expiring, idempotent, and auditable.
6. Internal service access is denied unless the caller identity and action are authorized.
7. Logs contain correlation identifiers, not credential contents or secret material.
8. Every externally accepted proof is bound to a verifier, purpose, nonce, and validity window.
9. `did:key` is never used for a real user, long-lived identity, or recovery target.
10. Verification never resolves a DID method or loads a JSON-LD context outside an explicit allowlist.
11. A proof is accepted only when the issuer DID document and local trust
    profile agree on the exact Ed25519 verification key.
12. A syntactically valid proof or successful signature does not establish
    claim truth, credential status, holder control, or production issuer trust.
13. `REVOKED` is terminal; no generic repository or API may reactivate it.
14. Only a current enabled `admin` or `issuer` can invoke revocation.
15. Revocation reasons, actors, and timestamps remain persisted with the
    credential; soft deletion is not a revocation substitute.
16. A role never substitutes for wallet ownership, holder DID control, or
    credential object ownership.
17. Holder signing uses only an opaque key reference; raw private keys never
    enter domain/application records, MongoDB, HTTP, OpenAPI, audit, or logs.
18. Presentation challenges are generated server-side, expire, bind domain
    and audience, and are consumed at most once.
19. Reconciliation never resets a challenge or presentation to a reusable
    state and never silently accepts incomplete evidence.

## Privacy and data-retention baseline

- Collect only fields required by the declared transaction purpose.
- Prefer derived results over storing raw presentations or fraud signals.
- Define retention periods before storing real or sensitive records.
- Raw credential storage remains optional and requires a documented purpose,
  field minimization, encryption, access policy, and deletion policy.
- Redis must not become a durable identity store.
- Development and test environments must use synthetic identities and credentials.
- Data export and deletion behavior must be specified before real user testing.

## Explicitly deferred decisions

- External/mobile wallet protocol and production-capable holder DID method.
- Privacy-preserving interoperable credential status and selective-disclosure mechanism.
- KMS/HSM provider and key-rotation process.
- Production issuer trust registry and credential status policy.
- Guardian threshold and cooling-off duration.
- Fraud-model family, features, and acceptance thresholds.
- Blockchain network, contract governance, and finality policy.

Prototype DID and credential-format decisions are recorded in ADR 0001 and ADR 0002. The remaining decisions require written rationale and threat-model updates before their implementation.
