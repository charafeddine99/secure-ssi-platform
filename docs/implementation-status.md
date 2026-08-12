# Implementation Status

| Component | Status | Implemented | Mocked | Tested | Notes |
| --- | --- | --- | --- | --- | --- |
| Web status page | Scaffolded | Layout and setup cards | Static state | Build and lint | No live polling |
| API Gateway | Scaffolded | Health endpoint | No | Health test | Planned paths are documentation only |
| Identity service | Prototype | Health; credential/status-list/wallet/challenge/VP/managed-key APIs; synthetic login/current-user; RBAC plus object authorization; local DID/proof core; Mongo lifecycle; provider-aware holder signing; reconciliation; durable audit | Local users, `did:web`, `did:key`, wallets, challenges, credentials, presentations, and a deterministic key provider | Unit, API integration, auth/RBAC, repository, ownership, challenge, key lifecycle, reconciliation, VP, revocation/status-list, outbox, resolver, profile, and security tests | Local academic use only; no vendor KMS/HSM deployment |
| SSI, DID, and VC | Partial | DID resolution, local VC/VP proofs, lifecycle status, Status Lists, wallet-bound full-disclosure presentations, and server challenges | Synthetic fixtures only | Positive, tamper, holder, wallet, domain/audience, replay, reconciliation, revocation, publication, status, and transition tests | No production trust, external wallet, selective disclosure, or conformance certification |
| Fraud service | Scaffolded | Health endpoint | No | Health test | Boundary only |
| AI fraud detection | Planned | No | No | No | No model, features, or thresholds |
| Blockchain | Planned | Workspace metadata | No | No | No contracts or deployment |
| Recovery service | Prototype | Health; Guardian/policy/request/decision/cancel/reconcile APIs; Mongo repositories; encrypted Shamir authorization shares; time-lock worker; audit; metrics; Identity managed-key orchestration | Synthetic users, DIDs, clocks, Mongo adapter, and managed-key provider | Domain, cryptography, repository, concurrency, service, API, Identity integration, reconciliation, security, performance, and regression tests | Academic only; no Guardian DID signature, independent share delivery, or production operations |
| Guardian recovery | Implemented with prototype limits | Generic M-of-N with 3-of-5 default, immutable snapshots, parallel idempotent decisions, persisted time lock, bounded retries, `did:key` successor rotation | Guardian identities and managed-key provider are synthetic in tests | Sufficient/insufficient quorum, concurrency, time lock, tamper/replay, cancellation/expiry, crash/retry, audit, metrics, and benchmark tests | Not cryptographic multisignature; optional proof is not independently verified |
| Authentication/JWT | Implemented | Argon2id login, short-lived HS256 JWT, Bearer dependency, current-user resolution, wallet/challenge/presentation permissions, opt-in Mongo user provider | Five synthetic local accounts | Domain, adapter, JWT attack, API, OpenAPI, RBAC, ownership, and provider tests | No production identity provider or token lifecycle |
| MongoDB | Implemented for current flows | Typed config, pooled lifecycle, separate Identity/Recovery Compose users and databases, wallet/challenge/credential/presentation/managed-key/recovery repositories, indexes, atomic issuance/challenge/VP/key lifecycle state | No | Unit, fake-Mongo integration, plus opt-in real-Mongo Identity tests | No migration runner or production operations |
| User repository | Implemented | Add/read/update/soft-delete, unique normalized username, optimistic version | No | Mapper, repository, duplicate, version, and provider tests | No registration or seed workflow |
| Credential repository | Implemented | Add/read/update/query/soft-delete, wallet/owner inventory, lifecycle status, irreversible revocation metadata, and optional raw JSON | Synthetic credentials in tests | Mapper, ownership, repository, duplicate, transition, query, version, and revocation tests | Legacy credentials may remain wallet-unbound |
| Holder wallet repository | Implemented | Add/read/owner query, active DID lookup, key rebinding, status update, soft-delete, optimistic version | Synthetic development wallets | Domain, mapper, duplicate, ownership, state, version, API, and opt-in real-Mongo tests | Opaque provider references only |
| Managed-key repository | Implemented | Public/provider metadata, purpose/version, lifecycle state, rotation lineage, idempotency, CAS updates, reconciliation leases, inventory queries | Deterministic development provider | Mapper, private-material rejection, indexes, repository, lifecycle, concurrency, API, and opt-in real-Mongo tests | Records retained after provider destruction |
| Managed-key lifecycle | Implemented for holder VP signing | Provision, rotate, suspend/resume, compromise, revoke, delayed destroy/cancel, reconcile, provider-aware sign | Development provider plus generic HTTPS contract | Domain, provider, service, API, RBAC, audit, metrics, recovery, and regression tests | Issuer/JWT/Status List signing remain local prototype paths |
| Presentation challenge repository | Implemented | Add/read, atomic one-time consumption, expiration/cancellation state, optimistic version | Synthetic random challenges | Domain, mapper, expiry, replay, binding, race, API, and opt-in real-Mongo tests | Consumed evidence retained; no TTL deletion |
| Revocation repository | Implemented | Atomic versioned revoke, status-list mapping, embedded audit outbox, and expiry transitions | Synthetic persisted credentials | Unit, fake-Mongo, HTTP integration, and opt-in real-Mongo tests | No suspension endpoint |
| Status List repositories | Implemented | Stable entry assignment, configurable rollover, optimistic latest state, and immutable embedded publication history | Synthetic status entries/publications | Domain, mapper, collision, rollover, history, service, API, and opt-in real-Mongo tests | No external conformance certification |
| Presentation repository | Implemented | Add/get, wallet/challenge metadata, atomic verification claim, stale-processing query/reconciliation claim, terminal result, reason codes, and optimistic version | Synthetic signed VPs | Domain, mapper, fake-Mongo, API, replay, reconciliation, and opt-in real-Mongo tests | No retention worker |
| Presentation reconciliation | Implemented | Configurable stale policy, lifecycle worker, admin endpoint, fail-closed evidence policy, idempotent completion | Synthetic crash windows | Stale claim, success, missing evidence, role, repeat, audit, and metrics tests | No distributed scheduler or dashboard |
| Audit outbox | Implemented | Standalone and credential-embedded records, leases, retry, background delivery, and idempotent publishing | Synthetic failure/crash windows | Repository, retry, duplicate prevention, embedded record, API, and regression tests | No dead-letter queue or operational dashboard |
| Audit event repository | Implemented | Append/get/list for closed event types and idempotent outbox destination | Synthetic events in tests | Metadata safety, append-only, index, repository, retry, wallet/challenge/ownership/key-lifecycle/reconciliation, credential/status, and VP tests | Not an independently tamper-evident compliance log |
| Redis | Provisioned | Compose service and healthcheck | No | Static config | Not integrated |
| Threat model | Updated baseline | Assets, boundaries, Guardian/share/grant/quorum/audit threats, and 30 invariants | No | Recovery abuse/control tests plus document review pending | Not an independent security review |
| API contracts | Partial | Credential routes, four Status List routes, wallet/challenge routes, four VP routes, eleven managed-key routes, fourteen Recovery methods, hidden Identity recovery integration, plus planned paths and conventions | No | OpenAPI, RBAC, object-authorization, lifecycle, concurrency, and API integration tests | Presentation Exchange and gateway facade remain planned |
| Shared schema catalog | Prototype | Nine versioned JSON Schemas and one bundled JSON-LD context | Synthetic examples | Structural and profile-specific catalog tests | Endpoint integration is planned |
| Security baseline | Drafted | Development and phase gates | No | Document review pending | Not a certification |
| DID standards decision | Accepted | ADR 0001 and standards baseline | No | Document consistency checks | `did:web` issuer; synthetic short-lived `did:key` holder |
| Credential proof decision | Accepted | ADR 0002 and standards baseline | No | Document consistency checks | VC DM 2.0 with `eddsa-jcs-2022` |
| DID resolver | Prototype | Ed25519 `did:key`, local `did:web`, validator, explicit errors | Network-free issuer fixture | 23 resolver/security tests | Network resolution and DID lifecycle planned |
| VC profile | Prototype | Credential/proof validation and structured result model | Synthetic affiliation fixtures | Positive and deterministic rejection tests | Full disclosure; bounded HTTP API |
| JCS canonicalization | Implemented | RFC 8785 adapter; proof/document SHA-256 hashing | Local profile | Determinism, whitespace, nesting, arrays, Unicode, invalid-number tests | No JSON-LD RDF canonicalization |
| Local Ed25519 credential signing | Implemented | Opaque signing handle and cryptography adapter | Deterministic public test seed | Determinism, timestamp binding, unknown issuer, re-sign rejection | Local academic use only |
| Local Ed25519 credential verification | Implemented | DID/key authorization, signature, validity, trust-key comparison | Local issuer allowlist | Valid, tampered, wrong-key, malformed-signature tests | Signature is not claim truth |
| DataIntegrityProof local profile | Implemented | `eddsa-jcs-2022`, `assertionMethod`, base58-btc proofValue | Synthetic fixture | Proof metadata and tamper tests | No complete interoperability claim |
| Tampered credential fixtures | Implemented | 15 named attack variants | Deterministic builders | All variants rejected with reason codes | Test data only |
| HTTP credential API | Implemented | Validate, sign/persist/status-bind, verify, status, revoke, capabilities, Status Lists, wallets, challenges, and create/verify/get/reconcile VP routes | Synthetic issuer/holder, wallets, challenges, credentials, and presentations | Schema, integration, ownership, RBAC, issuance, lifecycle, VP, replay, reconciliation, transport, interoperability, status-list, and safe-error tests | No rate limit or production issuer/holder custody |
| Holder key abstraction | Implemented | Opaque key references, managed lifecycle, provider registry, provider-aware holder signer, deterministic development adapter, generic HTTPS adapter | Public local derivation and mock gateway transport | Provider, signer, raw-key exclusion, wallet/VP, failure, and recovery tests | Development adapter is not secure custody |
| Persistent key storage | Implemented for non-secret metadata | Managed public metadata, opaque provider reference, lifecycle, lineage, idempotency digest, and reconciliation metadata | Deterministic development adapter | BSON/API/audit/repr/private-material exclusion tests | Raw private keys and provider credentials are prohibited |
| Production wallet/HSM | Provider-neutral boundary implemented | HTTPS gateway contract, auth abstraction, TLS/mTLS references, timeout/retry/circuit breaker, lifecycle policy | No real provider | Boundary, failure, configuration, and redaction tests | Vendor KMS/HSM/mobile/external-wallet integration and certification required |
| JSON-LD RDF canonicalization | Not implemented | No | No | JCS tests only | Explicitly outside this profile |
| Blockchain anchoring | Planned | No | No | No | No contract or credential data on-chain |

## Credential HTTP API sprint status

| Capability | Status |
| --- | --- |
| Credential validation HTTP API | Implemented |
| Credential signing HTTP API | Implemented |
| Credential verification HTTP API | Implemented |
| Credential capabilities API | Implemented |
| Credential persistence | Implemented automatically for successful signing |
| Authentication | Implemented for local synthetic users |
| Authorization/RBAC | Implemented for current-user and credential signing |
| Rate limiting | Not implemented |
| Credential revocation/status | Implemented for existing Mongo credential documents |
| Production KMS/HSM | Holder provider-neutral boundary implemented; issuer/JWT/Status List production custody remains planned |
| External DID resolution | Not implemented |
| Blockchain anchoring | Planned |

## Local authentication and RBAC sprint status

| Capability | Status |
| --- | --- |
| Local synthetic user authentication | Implemented |
| Password hashing with Argon2id | Implemented |
| JWT access tokens | Implemented |
| Bearer authentication dependency | Implemented |
| Role-based authorization | Implemented |
| Credential sign authorization | Implemented |
| Credential revoke authorization | Implemented for `admin` and `issuer`; denied to `verifier` |
| Admin role | Implemented |
| Issuer role | Implemented |
| Verifier role | Implemented |
| Holder role | Implemented with wallet create/read/inventory, challenge read, and owned presentation create/read permissions |
| Presentation verification authorization | Implemented for `verifier`; `holder` denied |
| Persistent user storage | Mongo repository and auth adapter implemented; opt-in |
| User registration | Not implemented |
| Refresh token rotation | Not implemented |
| Token blacklist/revocation | Not implemented |
| MFA | Not implemented |
| Rate limiting | Not implemented |
| External identity provider | Not implemented |
| Production JWT key management | Planned |
| MongoDB user repository | Implemented |
| Redis token/session support | Planned |

## MongoDB persistence foundation sprint status

| Capability | Status |
| --- | --- |
| Typed MongoDB configuration | Implemented |
| Connection manager and pooled client lifecycle | Implemented |
| Startup ping and fail-closed initialization | Implemented |
| Idempotent index management | Implemented |
| User repository | Implemented |
| Credential repository | Implemented |
| Audit event repository | Implemented |
| Presentation repository | Implemented in the Verifiable Presentation sprint |
| BSON/ObjectId mappers | Implemented |
| `createdAt` / `updatedAt` metadata | Implemented |
| Optimistic `version` checks | Implemented |
| User and credential soft delete | Implemented |
| Append-only audit events | Implemented |
| Repository dependency injection | Implemented |
| Mongo-backed authentication provider | Implemented; opt-in |
| Automatic credential persistence from HTTP routes | Implemented for signing |
| Automatic audit emission from revocation/status flows | Implemented |
| Real Mongo integration suite | Implemented; requires `IDENTITY_TEST_MONGODB_URI` |
| Redis changes | Not part of this sprint |
| Credential lifecycle and revocation repository | Implemented in the following sprint |
| W3C Bitstring Status List | Implemented in the following sprint |

## Credential Revocation & Status Management sprint status

| Capability | Status |
| --- | --- |
| `CredentialStatus` lifecycle model | Implemented: `ACTIVE`, `REVOKED`, `SUSPENDED`, `EXPIRED` |
| Revocation policy | Implemented; `REVOKED` is terminal |
| Revocation repository port and Mongo adapter | Implemented |
| Mongo revocation metadata | Implemented: `revokedAt`, `revokedBy`, `revocationReason` |
| Optimistic transition checks | Implemented with atomic state/version predicate |
| Revocation application service | Implemented |
| Revocation dependency injection | Implemented |
| `POST /api/v1/credentials/{credentialId}/revoke` | Implemented |
| `GET /api/v1/credentials/{credentialId}/status` | Implemented |
| Admin/issuer revocation permission | Implemented |
| Verifier revocation denial | Implemented |
| `CREDENTIAL_REVOKED` audit event | Implemented |
| `STATUS_CHECKED` audit event | Implemented |
| Expiration transition on status lookup | Implemented |
| Legacy `stored`/`verified` BSON read compatibility | Implemented as `ACTIVE` |
| Automatic persistence from credential signing | Implemented in the issuance lifecycle sprint |
| Suspension/resume endpoint | Not implemented |
| W3C Bitstring Status List | Implemented in the following sprint |
| Durable audit coupling | Implemented in the following sprint with embedded revocation outbox |

## W3C Bitstring Status List & Durable Audit Delivery sprint status

| Capability | Status |
| --- | --- |
| `CredentialStatusEntry` domain object | Implemented |
| Deterministic issuer status-list identifier | Implemented |
| Stable hash-derived index with collision-safe reservation | Implemented |
| W3C-oriented GZIP/base64url multibase bitstring | Implemented |
| 131,072-entry default/minimum | Implemented |
| Signed `BitstringStatusListCredential` generator | Implemented with synthetic `eddsa-jcs-2022` issuer key |
| Status List repository and optimistic versioning | Implemented |
| ETag, TTL, cache headers, and `304` | Implemented |
| `GET /api/v1/status-lists/{statusListId}` | Implemented |
| `GET /api/v1/status-lists/{statusListId}/metadata` | Implemented |
| Embedded revocation audit outbox | Implemented in the same credential update |
| Standalone audit outbox | Implemented |
| Lease recovery and capped exponential retry | Implemented |
| Idempotent audit publication | Implemented with immutable event ID/evidence validation |
| Background delivery service | Implemented in application lifespan |
| Mongo indexes and typed settings | Implemented |
| Unit, repository, service, generation, API, and regression tests | Implemented |
| Automatic status entry injection during credential signing | Implemented in the issuance lifecycle sprint |
| Publication history and list rollover | Implemented in the issuance lifecycle sprint |
| External W3C conformance certification | Not performed |

## Issuance-Time Status Binding & Status List Lifecycle sprint status

| Capability | Status |
| --- | --- |
| Automatic persistence after signing | Implemented as one credential insert |
| Issuance-time `CredentialStatusEntry` | Implemented and embedded by reference in the credential document |
| `credentialStatus` injection before proof | Implemented |
| Atomic issuance consistency | Implemented with no separate new-entry write |
| Deterministic index and collision handling | Implemented |
| Unique credential list/index constraint | Implemented as a partial compound index |
| Configurable logical capacity | Implemented with `IDENTITY_STATUS_LIST_CAPACITY` |
| Deterministic list rollover | Implemented with six-digit sequence suffixes |
| Immutable publication history | Implemented as append-only snapshots |
| Historical publication retrieval | Implemented |
| `GET /api/v1/status-lists/{statusListId}/history` | Implemented |
| `GET /api/v1/status-lists/{statusListId}/versions/{version}` | Implemented |
| Issuer signing/publication abstractions | Implemented |
| Future KMS/HSM key-provider boundary | Provider-neutral holder adapter implemented; issuer signing still local |
| Internal issuance/publication/utilization metrics | Implemented |
| Internal outbox lag/worker metrics | Implemented |
| VC v2, Bitstring, Data Integrity, `did:key`, `did:web` fixtures | Implemented |
| Domain, repository, service, API, interoperability, regression tests | Implemented |

## Verifiable Presentation Framework sprint status

| Capability | Status |
| --- | --- |
| W3C VC Data Model 2.0 VP domain model | Implemented as a strict local profile |
| Presentation builder and validator | Implemented |
| Holder and verifier application services | Implemented |
| Holder `did:key` signing and verification | Implemented through an opaque holder signer port and deterministic development adapter |
| One-to-eight credential support | Implemented |
| Credential existence and extraction | Implemented |
| Current credential proof/hash/status validation | Implemented |
| Revoked, suspended, expired, and not-yet-valid rejection | Implemented |
| Issuance-time `credentialStatus` mapping validation | Implemented |
| Holder binding | Implemented across VP, persisted holder, and every credential subject |
| Server challenge issuance, validation, and proof binding | Implemented |
| DNS domain and audience normalization/proof binding | Implemented |
| 30-to-600-second presentation lifetime | Implemented |
| Replay protection | Implemented with persisted server challenge evidence and atomic state/version claims |
| Presentation Mongo repository and BSON mapper | Implemented |
| Presentation Mongo indexes | Implemented |
| `POST /api/v1/presentations/create` | Implemented; Bearer `presentations:create` |
| `POST /api/v1/presentations/verify` | Implemented; Bearer `presentations:verify` |
| `GET /api/v1/presentations/{presentationId}` | Implemented; Bearer `presentations:read` |
| `PRESENTATION_CREATED` audit event | Implemented through durable outbox |
| `PRESENTATION_VERIFIED` audit event | Implemented through durable outbox |
| `PRESENTATION_REJECTED` audit event | Implemented through durable outbox |
| Domain, proof, repository, service, API, audit, and regression tests | Implemented |
| Presentation Exchange | Not implemented |
| Selective disclosure | Not implemented |
| Production wallet/KMS/HSM | Generic holder gateway boundary implemented; no vendor deployment or certification |
| Redis, blockchain, AI, recovery, frontend | Not part of this sprint |

## Production Holder Wallet & Key Custody sprint status

| Capability | Status |
| --- | --- |
| Holder wallet domain and status model | Implemented |
| Wallet-to-user and wallet-to-holder DID binding | Implemented |
| Credential wallet/owner persistence and inventory | Implemented |
| Application-layer object ownership | Implemented with enumeration-resistant not-found behavior |
| Holder key provider/metadata/signer ports | Implemented |
| Local development key adapter | Implemented; deterministic and explicitly non-production |
| Raw private-key persistence | Prohibited and tested |
| Server challenge issuance | Implemented with cryptographic randomness |
| Challenge domain/audience/holder binding | Implemented |
| Atomic one-time challenge consumption | Implemented |
| Challenge expiry/replay/cancellation states | Implemented |
| Wallet/challenge Mongo repositories and BSON mappers | Implemented |
| Wallet/challenge/ownership/reconciliation audit events | Implemented through durable outbox |
| Wallet/challenge/reconciliation process-local metrics | Implemented |
| Stale `PROCESSING` reconciliation service | Implemented |
| Background reconciliation worker | Implemented through application lifespan |
| Admin manual reconciliation endpoint | Implemented |
| Controlled incomplete-evidence rejection | Implemented |
| Wallet/challenge/reconciliation API and OpenAPI | Implemented |
| Domain, mapper, repository, service, security, API, and regression tests | Implemented |
| Real KMS/HSM/mobile/external wallet integration | Generic HTTPS provider contract implemented; no concrete vendor/mobile deployment |
| Redis, blockchain, AI, recovery, frontend | Not part of this sprint |

## External KMS/HSM Adapter, Key Rotation, and Lifecycle sprint status

| Capability | Status |
| --- | --- |
| `ManagedKey` domain model and explicit lifecycle state machine | Implemented |
| Algorithm and key-purpose policy | Implemented; Ed25519 allowlist |
| `ExternalKeyProvider` port and provider registry | Implemented |
| Deterministic development provider | Implemented; explicitly non-production |
| Generic remote KMS gateway adapter | Implemented with HTTPS, auth abstraction, TLS verification, optional mTLS references, bounded retry, timeout, and circuit breaker |
| Private-key non-export and persistence prohibition | Implemented and tested |
| Managed-key Mongo mapper/repository/indexes | Implemented |
| Optimistic provisioning and idempotency | Implemented |
| Holder VP provider-aware signing | Implemented |
| Rotation lineage and wallet rebinding | Implemented |
| `did:key` rotation semantics | Implemented as successor DID; old public metadata retained |
| `did:web` mutation | Rejected until a controlled publication pipeline exists |
| Suspend/resume/compromise/revoke lifecycle | Implemented |
| Delayed destruction and cancellation | Implemented; administrative confirmation required |
| Restart-safe reconciliation worker and manual endpoint | Implemented |
| RBAC and object ownership | Implemented; elevated actions are explicit admin routes |
| Durable key lifecycle audit events | Implemented through the outbox |
| Process-local key/provider metrics | Implemented without high-cardinality identifiers |
| Managed-key REST/OpenAPI contracts | Implemented for eleven routes |
| Domain, mapper, provider, repository, service, API, RBAC, audit, recovery, and regression tests | Implemented |
| Vendor KMS/HSM/cloud account integration | Not performed |
| Hardware attestation and production key ceremonies | Not implemented |
| Issuer credential, Status List, and JWT signing migration | Not part of this sprint; current local prototype paths preserved |

## Guardian-Based Account Recovery sprint status

| Capability | Status |
| --- | --- |
| Guardian domain, lifecycle, owner/assignee authorization, API | Implemented |
| Generic M-of-N policy | Implemented; any valid threshold up to 32 shares |
| Default 3-of-5 recovery | Implemented and tested |
| Immutable active-request policy and Guardian snapshot | Implemented |
| One active recovery per wallet | Implemented with a partial unique Mongo index |
| Recovery challenge, nonce, session, quorum, result, failure, lease | Implemented |
| Explicit recovery state machine | Implemented with validated terminal/transient transitions |
| Parallel Guardian decisions | Implemented with unique indexes and optimistic CAS |
| Duplicate decision/publication idempotency | Implemented with deterministic IDs and exact repeat semantics |
| Independent Guardian DID signature verification | Not implemented; optional proof is only digested/bound |
| Shamir Secret Sharing | Implemented for a dedicated random 128-bit authorization secret |
| KMS/private-key sharing or export | Prohibited; never performed |
| Share confidentiality/integrity | AES-256-GCM envelopes, HKDF-derived keys, HMAC, commitment, and context binding implemented |
| Independent per-Guardian share delivery/custody | Not implemented; encrypted envelopes are centrally persisted |
| Persisted time lock, cancellation, expiry, cooldown | Implemented |
| Restart-safe worker lease and bounded reconciliation | Implemented |
| Managed-key integration | Implemented through short-lived request-bound service grant and existing `ManagedKeyService` |
| Key rotation idempotency and lineage | Implemented with `recovery:{requestId}` digest |
| `did:key` recovery semantics | New successor DID; unchanged successor rejected |
| Holder `did:web` mutation | Fails closed pending a controlled publisher |
| Account-compromise predecessor handling | Marked compromised and provider suspension attempted |
| Mongo recovery repositories, mappers, and indexes | Implemented in dedicated `secure_recovery` database |
| Typed recovery audit events | Implemented as append-only deterministic records |
| Transactional recovery state/audit coupling | Not implemented; documented crash-gap limitation |
| Process-local recovery metrics | Implemented without high-cardinality identity labels |
| Recovery REST/OpenAPI contracts | Implemented for fourteen public methods; metrics/internal Identity routes hidden |
| Domain, Shamir, repository, service, API, concurrency, integration, security, and regression tests | Implemented |
| Performance budget | In-memory 25-run workflow mean 2.335 ms, p95 2.711 ms; component means documented; production SLA unproven |
| Redis, blockchain, AI, DIDComm, frontend, VP/selective disclosure | Not implemented in this sprint |

Requirement-level implemented/partial/not-implemented mapping is maintained in
[account-recovery.md](account-recovery.md). The recommended next feature sprint
is explainable advisory AI fraud detection; it must not receive autonomous
credential, key, or recovery authority.
