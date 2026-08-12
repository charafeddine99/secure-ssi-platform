# Guardian-Based Account Recovery

## Scope and assurance statement

This sprint implements the Recovery Service application boundary for
Guardian-based recovery of a holder wallet whose access, device, or managed
presentation-signing key is lost or compromised. It is an academic prototype,
not a production account-recovery guarantee.

The implementation provides a generic M-of-N policy with a 3-of-5 default,
parallel and idempotent Guardian decisions, a persisted time lock, encrypted
Shamir authorization shares, restart-safe reconciliation, auditable state
changes, and idempotent orchestration of the existing Identity Service
`ManagedKeyService`.

The Shamir secret is a random 128-bit recovery authorization capability. It is
never a holder, issuer, JWT, KMS, HSM, DID, or credential private key. No KMS
private key is exported to the Recovery Service or MongoDB.

## Architecture

```text
Holder/Guardian Bearer token
          |
          v
Recovery HTTP API -- RBAC + object ownership
          |
          v
RecoveryService -- policy, quorum, time lock, state machine
     |            |                 |
     |            |                 +--> process-local metrics
     |            +--> Shamir + authenticated encrypted envelopes
     +--> RecoveryRepository --> secure_recovery MongoDB
          |
          +--> background reconciliation worker
                    |
                    v
          short-lived service grant
                    |
                    v
          Identity internal recovery API
                    |
                    v
          existing ManagedKeyService --> ExternalKeyProvider
```

Domain and application layers do not depend on FastAPI or PyMongo. Repository,
secret-sharing, identity/key, clock, and metrics boundaries are injected. The
default local runtime uses an in-memory repository when
`RECOVERY_MONGO_ENABLED=false`; Compose enables the dedicated Mongo adapter.

## Guardian and policy model

A Guardian is a wallet-scoped assignment between an owner and another existing
Identity user. The assignment records an opaque user ID, Guardian DID,
verification-method identifier, display label, lifecycle status, timestamps,
and an optimistic version. `ACTIVE`, `SUSPENDED`, `REVOKED`, and `REMOVED` are
explicit states. Removed assignments are retained as evidence.

Guardian is a resource assignment, not a new global Identity role. Existing
`holder` identities may be owners or assigned Guardians. Authorization first
checks a bounded recovery permission and then verifies ownership or exact
assignment. Foreign resources return not-found to reduce enumeration.

Policies are wallet-scoped and versioned. They contain:

- minimum approvals M and maximum Guardians N;
- approval-window, time-lock, expiration, cooldown, and retry durations;
- maximum execution attempts and cancellation policy;
- an explicit self-Guardian option, disabled by default.

The implementation accepts any valid `1 <= M <= N <= 32`. Defaults are M=3 and
N=5. A request persists the full policy version and sorted active-Guardian
snapshot, so later policy changes cannot alter an active recovery. Guardian or
policy mutation is blocked while that wallet has an active request.

## Secret sharing and cryptographic boundary

`PyCryptodomeSecretSharingProvider` uses PyCryptodome Shamir Secret Sharing to
split a freshly generated 16-byte authorization secret into N shares with an
M-share threshold. For each request:

1. A unique request ID, policy version, share version, challenge, and nonce are
   generated.
2. HKDF-SHA-256 derives separate encryption and integrity keys from the
   configured 32-byte envelope master key and policy context.
3. Each raw share and an HMAC-SHA-256 integrity value are encrypted with
   AES-256-GCM using unique 96-bit nonces and canonical metadata as associated
   data.
4. Request, policy, version, Guardian, index, threshold, and total-count
   bindings are persisted with the ciphertext.
5. A request-bound HMAC commitment verifies the recombined authorization
   secret before key orchestration.
6. Reconstructed mutable byte buffers are overwritten immediately after use.

Duplicate share IDs, Guardian IDs, or Shamir indexes; insufficient shares;
wrong request/policy/version bindings; malformed envelopes; altered metadata;
GCM authentication failure; HMAC failure; and commitment mismatch all fail
closed. Ciphertext and digest fields are excluded from dataclass `repr` output
and never returned by an API schema.

The current prototype stores encrypted share envelopes centrally in the
Recovery database. It does not independently deliver one share to each
Guardian device. Therefore it demonstrates real threshold reconstruction and
tamper detection, but not production share-custody separation.

## Recovery workflow and state machine

```text
PENDING_APPROVALS
   | M approvals                 | quorum impossible
   v                             v
QUORUM_REACHED                REJECTED
   |
   v
WAITING_TIMELOCK -- due --> READY_FOR_EXECUTION
                                  |
                                  v
                              EXECUTING
                                /   \
                               v     v
                         COMPLETED  RECONCILIATION_REQUIRED
                                         |
                                         +--> READY_FOR_EXECUTION (bounded retry)
                                         +--> FAILED
```

`CANCELLED` and `EXPIRED` are terminal outcomes available only from explicitly
allowed states. `FAILED`, `REJECTED`, and `COMPLETED` are also terminal. Every
transition is validated in the domain model.

### Request and decisions

The owner first creates a policy and Guardian assignments, then creates one
active request for a wallet. Supported reasons are account compromise, lost
access, device loss, and key loss. A recovery request always targets
`MANAGED_KEY_ROTATION`.

An assigned active Guardian must authenticate with the existing short-lived
Identity JWT and submit its own assignment ID plus the exact request challenge.
One deterministic approval ID is allowed per request and Guardian. Repeating
the same decision is idempotent; changing an existing decision conflicts.
Optional proof material is digested and bound to idempotency but is not yet
validated as an independent DID signature.

Parallel decisions use unique Mongo indexes and optimistic compare-and-set
updates. Quorum is recalculated from persisted, still-active, wallet-bound
assignments. The service persists `QUORUM_REACHED` before
`WAITING_TIMELOCK` and emits deterministic audit IDs, preventing duplicate
quorum events. If remaining Guardians cannot satisfy M, the request becomes
`REJECTED`.

### Time lock and execution

No key operation runs when quorum is merely reached. The persisted
`executableAfter` timestamp must pass first. The owner may cancel during the
time lock when policy permits. The worker atomically acquires an expiring
lease and transitions `READY_FOR_EXECUTION -> EXECUTING` before combining the
approved shares.

Stale executions become `RECONCILIATION_REQUIRED`; bounded retries use the
same recovery request ID. Retry exhaustion is terminal `FAILED`. Process
restart does not erase the request, approval, time lock, attempt, lease,
result, or failure evidence when MongoDB is enabled.

## Managed-key and DID recovery

The Recovery Service never writes Identity managed-key records directly. It
creates a short-lived HS256 service grant bound to scope, wallet, owner, and
recovery request and calls two non-public Identity routes:

- `GET /internal/v1/recovery/wallets/{walletId}/owners/{ownerUserId}` verifies
  exact wallet ownership.
- `POST /internal/v1/recovery/key-rotation` uses
  `Idempotency-Key: recovery:{requestId}` and a request-bound service grant.

The Identity Service verifies issuer, audience, time, scope, wallet, owner,
request, and idempotency bindings. `ManagedKeyService.recover_wallet` reuses
the normal provider-neutral rotation path. Repeated execution returns the
same successor by idempotency digest. For `ACCOUNT_COMPROMISE`, the predecessor
is marked compromised and provider suspension is attempted. Old public
metadata remains available for verifying historical signatures; the old key
cannot sign new material.

For `did:key`, rotation creates and persists a new successor DID because the
method is immutable. An unchanged successor fails closed. Holder `did:web`
recovery remains blocked because this repository has no controlled mutable
DID publication process.

## Public HTTP API

All routes below require a Bearer token. Strict Pydantic envelopes reject
unknown fields and constrain identifiers, strings, counts, and durations.
Responses expose state and bounded metadata, never plaintext or encrypted
shares, envelope keys, service grants, or private-key material.

| Method and path | Authorization and behavior |
| --- | --- |
| `POST /api/v1/guardians` | Holder owner; verifies wallet ownership and creates assignment |
| `GET /api/v1/guardians` | Owner/assigned Guardian projection; optional `walletId` filter |
| `GET /api/v1/guardians/{guardianId}` | Exact owner or assignee |
| `PATCH /api/v1/guardians/{guardianId}` | Owner; no active wallet recovery |
| `DELETE /api/v1/guardians/{guardianId}` | Owner; retained `REMOVED` state |
| `GET /api/v1/recovery/policy?walletId=...` | Exact wallet owner |
| `PUT /api/v1/recovery/policy` | Exact wallet owner; optimistic versioned replacement |
| `POST /api/v1/recovery/requests` | Exact wallet owner; one active request per wallet |
| `GET /api/v1/recovery/requests` | Owner and assigned-Guardian projections |
| `GET /api/v1/recovery/requests/{requestId}` | Exact owner or assigned Guardian |
| `POST /api/v1/recovery/requests/{requestId}/approve` | Exact active assignee and challenge |
| `POST /api/v1/recovery/requests/{requestId}/reject` | Exact active assignee and challenge |
| `POST /api/v1/recovery/requests/{requestId}/cancel` | Owner when policy/state permit |
| `POST /api/v1/recovery/requests/{requestId}/reconcile` | Admin only; deterministic worker path |

`GET /internal/metrics` is deliberately absent from public OpenAPI and requires
the admin permission.

## MongoDB persistence

Compose provisions a separate `secure_recovery` database and least-privilege
`recovery_app` user. The init script still applies only to a fresh Mongo
volume.

| Collection | Primary contents |
| --- | --- |
| `guardians` | Wallet assignment, owner/assignee, DID, status, timestamps, version |
| `recovery_policies` | M/N and timing/retry policy, timestamps, version |
| `recovery_requests` | Immutable snapshot, challenge/nonce digests, state, quorum, lease, result/failure, version |
| `recovery_approvals` | One immutable decision per request and Guardian |
| `recovery_secret_shares` | Authenticated encrypted Shamir envelopes and safe metadata |
| `recovery_audit_events` | Append-only typed recovery events with deterministic event IDs |

Named indexes enforce unique domain IDs; one active Guardian assignment per
wallet/user; one policy per wallet; one active request per wallet; one
decision and share per request/Guardian; one share per policy/share version
and index; and one audit event ID. Query indexes cover owner/assignee lists,
wallet creation order, state/expiry, time-lock due work, stale execution,
decision counts, and audit timelines. Mutable documents use optimistic
versions and compare-and-set writes.

## Audit and metrics

Typed events cover Guardian add/update/suspend/resume/remove, policy update,
request, approve/reject, quorum, time-lock, readiness, execution, new key, DID
change, completion, cancellation, expiration, failure, reconciliation,
unauthorized attempts, and share-validation failure. Event IDs are
deterministic over event type, aggregate, discriminator, and timestamp context
where required, so retrying a publication does not duplicate the record.

Recovery audit writes are append-only Mongo inserts but are not in a Mongo
transaction/outbox with every state mutation. A crash between state and audit
writes can leave an audit gap; the collection is also not independently
tamper-evident or compliance certified.

Process-local metrics include active Guardians, request/decision/quorum/
cancel/expire/success/failure counts, reconciliation counts, share-validation
failures, and accumulated timings for request creation, approval, quorum,
time-lock, key rotation, and execution. They use no user, wallet, request, DID,
or key labels.

## Security controls and threat analysis

- Short-lived Identity JWT validation pins HS256, issuer, audience, subject,
  roles, time, and bounded clock skew.
- Wallet ownership is confirmed at the Identity boundary before owner
  mutations; exact assignment is checked for every Guardian decision.
- Foreign resources use not-found behavior; response and log models redact
  secret material.
- Random request IDs, challenges, nonces, authorization secrets, GCM nonces,
  and opaque grants prevent predictable replay material.
- Approval windows, overall expiration, cooldown, time lock, maximum attempts,
  and cancellation limit the recovery window.
- Immutable policy snapshots prevent active-request threshold downgrades.
- Unique indexes, deterministic IDs, optimistic versions, and execution leases
  handle duplicate/concurrent requests and worker crashes.
- Shares are request/policy/version/Guardian/index-bound, authenticated,
  encrypted at the application layer, and commitment-checked after combine.
- Key rotation remains inside the existing provider-neutral KMS boundary; the
  Recovery Service never receives private key material.
- Production mode refuses development fallback secrets.

Important residual threats are Guardian social compromise, owner-token theft,
central envelope-key compromise, malicious database administrators, lack of
independent Guardian signature verification, denial of service, and missing
production notification/incident operations. Rate limiting, MFA, device
attestation, independent share custody, production KMS attestation, and token
revocation remain required external controls.

## Configuration

The sample environment files document Mongo connection/database/timeout;
JWT issuer/audience/secret/skew; Identity endpoint and service-grant
issuer/audience/secret/timeout; base64 envelope master key; M/N and timing
defaults; and worker poll/batch/lease/stale settings. Production/staging must
explicitly set independent JWT, service-grant, and 32-byte base64 envelope
secrets. Development defaults must never be promoted.

## Tests and measured performance

The suite covers domain validation and state transitions; Guardian lifecycle;
generic 2-of-3, 3-of-5, and 4-of-7 policies; sufficient and insufficient
quorum; concurrent approvals; replay/idempotency; cancellation; expiration;
time lock; Shamir tamper, duplicate, wrong-request, and insufficient-share
failure; optimistic repository behavior and indexes; API RBAC and ownership;
Identity service grants; ManagedKey rotation/idempotency; crash/retry
reconciliation; and Mongo adapter behavior with a deterministic fake database.

The opt-in benchmark runs 25 complete 3-of-5 service workflows after Guardian
setup: request creation, three approvals, simulated time passage,
reconciliation, Shamir combination, and fake managed-key rotation. On the
2026-08-12 development test run it measured workflow mean 2.335 ms, p95
2.711 ms, and maximum 4.099 ms.

| Measured component | Mean processing time |
| --- | ---: |
| Request creation | 0.654 ms |
| Approval processing per decision | 0.126 ms |
| Quorum calculation per decision | 0.035 ms |
| Time-lock due-transition overhead | 0.019 ms |
| Fake managed-key rotation call | 0.012 ms |
| Final execution, including share combine and fake rotation | 1.229 ms |

This is only an in-memory computational regression budget. It excludes human
approval time, HTTP/network transit, real MongoDB, process scheduling, real
KMS/HSM latency, failover, and production load. It therefore does not prove a
2.7-second production recovery target. The configured one-second test time lock
is advanced by the deterministic clock and is not counted as processing time.

## Requirement traceability

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| 5 | PARTIAL | Guardian M-of-N recovery exists; no alternate-device UI or cryptographic Guardian multisignature |
| 15 | PARTIAL | Guardian wallet assignment exists; no distinct global Identity role |
| 66 | PARTIAL | Device-loss reason and API exist; no mobile/backup-device experience |
| 67 | IMPLEMENTED | Key-loss request, threshold approval, and managed-key rotation |
| 68 | PARTIAL | Compromise marks old managed key unusable; existing JWT remains valid until expiry because no blacklist was added |
| 69 | IMPLEMENTED | Guardian domain, lifecycle, ownership, persistence, API, and tests |
| 70 | PARTIAL | Generic M-of-N decision quorum; optional proof is not independently verified as a Guardian DID signature |
| 71 | IMPLEMENTED | Configurable default 3-of-5 and explicit tests |
| 72 | IMPLEMENTED | Parallel idempotent decisions with unique indexes and optimistic CAS |
| 73 | IMPLEMENTED | Persisted, tested time lock blocks early execution |
| 74 | IMPLEMENTED | Existing ManagedKeyService provisions a new provider-managed successor |
| 75 | IMPLEMENTED | `did:key` successor DID; `did:web` fails closed pending publication workflow |
| 76 | PARTIAL | Old provider-managed key is suspended/compromised locally; no blockchain was implemented |
| 77 | IMPLEMENTED | Idempotent existing managed-key rotation path and lineage |
| 78 | NOT IMPLEMENTED | DIDComm result delivery is outside sprint scope |
| 79 | NOT IMPLEMENTED | Encrypted DIDComm notification is outside sprint scope |
| 80 | IMPLEMENTED | Typed append-only recovery audit collection; not transactional/tamper-evident |
| 81 | PARTIAL | Real Shamir authorization shares and encrypted envelopes; no independent Guardian-device distribution |
| 82 | PARTIAL | In-memory benchmark is below 2.7 seconds; production end-to-end latency is unproven |
| 143 | IMPLEMENTED | Sufficient/insufficient quorum and duplicate-decision tests |
| 145 | IMPLEMENTED | Early execution blocked and due execution tested |
| 168 | PARTIAL | Parallel assignment/share validation works; no cryptographic Guardian signature verification |

## Known limitations and next work

- Existing access tokens have no blacklist/refresh/logout mechanism and remain
  usable until their short expiry.
- A Guardian assignment uses an existing holder JWT; no dedicated enrollment,
  MFA, device attestation, or independent signature-validation ceremony exists.
- Encrypted shares and their master key are controlled by one service boundary;
  there is no per-Guardian secure delivery or hardware-backed custody.
- Recovery audit persistence is not transactionally coupled to every state
  update and is not a tamper-evident external log.
- No real Mongo replica/failover, vendor KMS/HSM, disaster-recovery exercise,
  alerting, notification, support runbook, or independent security review has
  been completed.
- There is no DIDComm, blockchain, AI, Redis integration, rate limiting,
  frontend, mobile wallet, selective disclosure, or Verifiable Presentation
  feature in this sprint.

The recommended next feature sprint is explainable AI fraud detection as an
advisory-only service. Separately, production readiness requires Guardian
signature verification, independently delivered shares, token/MFA controls,
transactional audit reconciliation, and a reviewed vendor KMS/HSM deployment.
