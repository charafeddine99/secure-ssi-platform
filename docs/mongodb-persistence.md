# MongoDB Persistence Foundation

## Scope

The Identity Service has an optional MongoDB persistence foundation for users,
credentials, Verifiable Presentations, status-list assignments/publications,
holder wallets, server presentation challenges, durable audit delivery, and
security audit events. The managed-key lifecycle extension also persists
public key metadata, provider references, lifecycle state, rotation lineage,
and reconciliation leases in `managed_keys`. It provides typed configuration,
connection-pool lifecycle, repository ports, PyMongo adapters, BSON mappers,
idempotent index creation, optimistic version checks, and soft deletion where
the domain permits it.

The credential lifecycle and Bitstring Status List sprints add revocation,
stable status entries, shared publication, and an outbox worker on top of this
foundation. They still do not add registration, password reset, refresh
tokens, token blacklists, blockchain, Redis behavior, or frontend behavior.
Successful credential signing now persists the secured response and its
issuer-assigned status metadata atomically.

## Architecture

```text
FastAPI dependency composition / application lifespan
                       |
                       v
             Application repository ports
              /           |            \
             v            v             v
 UserRepo | WalletRepo | ChallengeRepo | CredentialRepo | PresentationRepo | StatusListRepos | OutboxRepo
              \           |          |          /
                       v
             Mongo repository adapters
                       |
                       v
       BSON mappers -> PyMongo MongoClient pool
                       |
                       v
 users | credentials | credential_status_entries | status_lists
 holder_wallets | managed_keys | presentation_challenges | presentations
                 audit_outbox | audit_events
```

Domain and application modules do not import PyMongo, BSON, FastAPI, or
MongoDB collection types. Infrastructure adapters own ObjectId conversion,
field-name mapping, driver exceptions, queries, and indexes.

## Connection lifecycle

`MongoConnectionManager` owns one process-wide `MongoClient`. PyMongo manages
the connection pool beneath that client. When persistence is enabled, FastAPI
startup:

1. creates the client with bounded selection, connection, and socket timeouts;
2. enables timezone-aware BSON datetimes, retryable reads, and retryable
   writes;
3. executes `ping`;
4. creates all declared indexes idempotently;
5. starts the enabled audit-outbox background worker;
6. starts the enabled stale-presentation reconciliation worker;
7. starts the enabled managed-key reconciliation worker; and
8. fails startup if the connection or index contract cannot be established.

Shutdown closes the client and its pool. The URI is excluded from object
representations and controlled errors.

## Configuration

| Variable | Host-development default | Purpose |
| --- | --- | --- |
| `IDENTITY_MONGO_ENABLED` | `false` | Enables startup connection and indexes |
| `IDENTITY_MONGO_URI` | `mongodb://localhost:27017/secure_identity` | Mongo connection URI; treated as secret |
| `IDENTITY_MONGO_DATABASE` | `secure_identity` | Database name |
| `IDENTITY_MONGO_SERVER_SELECTION_TIMEOUT_MS` | `3000` | Server selection bound |
| `IDENTITY_MONGO_CONNECT_TIMEOUT_MS` | `3000` | Socket connection bound |
| `IDENTITY_MONGO_SOCKET_TIMEOUT_MS` | `5000` | Operation socket bound |
| `IDENTITY_MONGO_MAX_POOL_SIZE` | `50` | Maximum pooled connections |
| `IDENTITY_MONGO_MIN_POOL_SIZE` | `0` | Minimum pooled connections |
| `IDENTITY_MONGO_RETRY_READS` | `true` | Retry supported reads |
| `IDENTITY_MONGO_RETRY_WRITES` | `true` | Retry supported writes |
| `IDENTITY_MONGO_APP_NAME` | `secure-ssi-identity-service` | Driver identification |
| `IDENTITY_AUTH_USER_PROVIDER` | `synthetic` | `synthetic` or `mongodb` |
| `IDENTITY_PRESENTATION_CHALLENGE_LIFETIME_SECONDS` | `300` | Default server challenge lifetime |
| `IDENTITY_PRESENTATION_RECONCILIATION_ENABLED` | `true` | Starts stale-claim recovery |
| `IDENTITY_PRESENTATION_RECONCILIATION_STALE_SECONDS` | `60` | Age before `PROCESSING` is recoverable |
| `IDENTITY_PRESENTATION_RECONCILIATION_POLL_INTERVAL_MS` | `1000` | Worker poll interval |
| `IDENTITY_PRESENTATION_RECONCILIATION_BATCH_SIZE` | `100` | Maximum records per cycle |

Invalid schemes, database names, booleans, integers, timeout bounds, or pool
bounds fail configuration. A Mongo auth provider also requires Mongo
persistence to be enabled.

## Collections and documents

### `users`

| BSON field | Domain meaning |
| --- | --- |
| `_id` | ObjectId mapped to domain `id` as a 24-character string |
| `username` | Trimmed, case-folded login identifier |
| `displayName` | Public display name |
| `roles` | Closed `admin`, `issuer`, `verifier`, or `holder` values |
| `enabled` | Current account state |
| `passwordHash` | Argon2 hash; never returned by public models |
| `createdAt` | Immutable timezone-aware creation time |
| `updatedAt` | Last repository mutation time |
| `version` | Positive optimistic-lock version |
| `deletedAt` | `null` or soft-deletion time |

The username remains globally unique after soft deletion. This prevents an old
login identifier from being silently rebound to a different account.

### `credentials`

| BSON field | Domain meaning |
| --- | --- |
| `_id` | Internal ObjectId |
| `credentialId` | Unique external credential identifier |
| `issuerDid` | Issuer DID |
| `holderDid` | Holder/subject DID |
| `credentialType` | Ordered credential type strings |
| `issuanceDate` | Timezone-aware issuance time |
| `expirationDate` | Optional timezone-aware expiration time |
| `credentialHash` | Lowercase SHA-256 hex digest |
| `status` | Lifecycle status: `ACTIVE`, `REVOKED`, `SUSPENDED`, or `EXPIRED` |
| `revokedAt` | Permanent revocation timestamp, otherwise `null` |
| `revokedBy` | Acting principal ID for a revocation, otherwise `null` |
| `revocationReason` | Bounded non-empty reason for a revocation, otherwise `null` |
| `statusListId` | Deterministic issuer/purpose list assignment |
| `statusListIndex` | Stable reserved bit position |
| `statusEntryId` | ObjectId of the immutable issuance-time assignment |
| `walletId` | Optional server-derived managed wallet binding |
| `ownerUserId` | Optional authenticated owner captured from that wallet |
| `auditOutbox` | Embedded durable revocation event and delivery state |
| `rawCredential` | Optional defensive copy of the raw JSON document |
| `createdAt` | Immutable creation time |
| `updatedAt` | Last repository mutation time |
| `version` | Optimistic-lock version |
| `deletedAt` | `null` or storage soft-deletion time |

Legacy BSON values `stored` and `verified` are read as `ACTIVE`; all new writes
use the uppercase lifecycle vocabulary. `REVOKED` is terminal. Soft deletion
only hides a document from normal repository reads and cannot replace
revocation. The status assignment is consumed by the W3C-oriented shared
publication described in [bitstring-status-list.md](bitstring-status-list.md).
Raw credential storage is optional and requires data-minimization, encryption,
access, and retention review before production use.

### `holder_wallets`

Wallet documents store a unique `walletId`, authenticated `ownerUserId`,
derived `holderDid`, opaque `keyReference`, public verification-method
metadata, `ACTIVE|LOCKED|DISABLED` status, timestamps, optimistic `version`,
and optional `deletedAt`. The API never returns the key reference. Raw private
keys, seeds, and signing handles are not BSON fields.

### `managed_keys`

Managed-key documents store public and operational metadata only:
`keyId`, `walletId`, `ownerUserId`, `holderDid`, provider name, opaque
`providerKeyReference`, algorithm, purpose, monotonic `keyVersion`, lifecycle
state, public multibase key, fingerprint, verification method, activation and
lifecycle timestamps, predecessor/successor links, a one-way idempotency
digest, reconciliation lease/attempt fields, and optimistic `version`.

The mapper rejects private-key, seed, mnemonic, secret, token, authorization,
and credential-shaped fields. Provider references are required to route
operations but are never returned by the managed-key API or copied into audit
metadata. Lifecycle records are retained as evidence; key destruction does
not delete the Mongo document. See
[external-kms-key-lifecycle.md](external-kms-key-lifecycle.md).

### `presentation_challenges`

Challenge documents store unique `challengeId` and random `challenge`,
normalized `domain` and `audience`, optional requested holder DID, issuing
verifier, issued/expiry/consumption timestamps, lifecycle status, optimistic
version, and optional cancellation timestamp. Atomic state/version predicates
make consumption one-time. Consumed records are retained as replay evidence;
no TTL index deletes them.

### `audit_events`

| BSON field | Domain meaning |
| --- | --- |
| `_id` | Event ObjectId |
| `eventType` | Closed audit event type |
| `subjectId` | Optional affected subject identifier |
| `actorId` | Optional acting principal identifier |
| `correlationId` | Optional bounded request correlation value |
| `metadata` | Bounded string map with sensitive-key rejection |
| `createdAt` | Event creation time |
| `updatedAt` | Equal to `createdAt` |
| `version` | Always `1` |

Allowed event types are `LOGIN_SUCCESS`, `LOGIN_FAILURE`, `VC_SIGNED`,
`VC_VERIFIED`, `TOKEN_ISSUED`, `TOKEN_REJECTED`, `CREDENTIAL_REVOKED`,
`STATUS_CHECKED`, `PRESENTATION_CREATED`, `PRESENTATION_VERIFIED`, and
`PRESENTATION_REJECTED`, plus wallet, challenge, ownership, and reconciliation
events documented in
[holder-wallet-and-key-custody.md](holder-wallet-and-key-custody.md), and the
managed-key events documented in
[external-kms-key-lifecycle.md](external-kms-key-lifecycle.md). Audit events are
append-only: the repository intentionally exposes no update or delete method.
Passwords, tokens, authorization values, credentials, proofs, secrets, and
hashes are rejected as metadata keys.

### `credential_status_entries`

Legacy documents map one unique `credentialId` to one issuer-scoped
`statusListId` and stable `statusListIndex`. It also stores `issuerDid`,
`statusPurpose`, `createdAt`, `updatedAt`, and optimistic `version`. A unique
compound index prevents two credentials from reserving the same bit.
New issuance keeps the canonical entry ID/list/index in the credential
document so the credential and assignment commit in one insert. Repository
reads merge both representations for backward compatibility.

### `status_lists`

The current signed publication stores `statusListId`, `issuerDid`,
`statusPurpose`, `encodedList`, publication `document`, `contentHash`, counts,
logical capacity, TTL, ETag, timestamps, optimistic `version`, and an
append-only `history` array of complete publication snapshots. Repeated unchanged
publication returns the existing record; changed state replaces it only when
the expected version still matches and appends the new snapshot.

### `audit_outbox`

Standalone outbox documents contain the immutable embedded audit event,
aggregate identity, source, delivery status, attempt count, availability time,
lease, safe error code, delivery time, timestamps, and optimistic `version`.
Revocation outbox records use the same schema but are embedded in the
credential so terminal state and delivery intent commit atomically.

### `presentations`

| BSON field | Domain meaning |
| --- | --- |
| `_id` | Internal ObjectId |
| `presentationId` | Unique UUIDv4 URN |
| `holderDid` | Holder DID covered by the VP proof |
| `walletId` / `ownerUserId` | Server-derived wallet and object owner |
| `challengeId` | Persisted server challenge reference |
| `challenge` | Bounded signed verifier nonce |
| `domain` | Normalized signed verifier DNS domain |
| `audience` | Normalized verifier audience covered by the proof |
| `credentialIds` | Ordered one-to-eight credential identifiers |
| `document` | Defensive copy of the exact signed VP |
| `verificationResult` | `PENDING`, `PROCESSING`, `VERIFIED`, or `REJECTED` |
| `createdAt` | VP creation time |
| `expiresAt` | Maximum accepted verification time |
| `updatedAt` | Last state transition time |
| `verifiedAt` | Terminal verification/rejection time, otherwise `null` |
| `processingStartedAt` | Start of the current atomic verification claim |
| `reconciliationAttempts` | Number of bounded recovery claims |
| `lastReconciledAt` | Last recovery claim time |
| `rejectionCodes` | Bounded machine-readable terminal reasons |
| `version` | Optimistic state-machine version |

Verification atomically transitions `PENDING -> PROCESSING` before any
content validation and only then completes as `VERIFIED` or `REJECTED`.
Repeated claims fail, so both successful and rejected verification attempts
consume the nonce. The worker can atomically claim only records that remain
`PROCESSING` beyond the configured stale threshold and completes them
deterministically from persisted evidence.

## Indexes

| Collection | Name | Keys | Unique |
| --- | --- | --- | --- |
| users | `uq_users_username` | `username ASC` | Yes |
| users | `ix_users_created_at` | `createdAt DESC` | No |
| credentials | `uq_credentials_credential_id` | `credentialId ASC` | Yes |
| credentials | `ix_credentials_issuer_did` | `issuerDid ASC` | No |
| credentials | `ix_credentials_holder_did` | `holderDid ASC` | No |
| credentials | `ix_credentials_status` | `status ASC` | No |
| credentials | `ix_credentials_created_at` | `createdAt DESC` | No |
| credentials | `ix_credentials_status_list_status` | `statusListId ASC, status ASC` | No |
| credentials | `uq_credentials_status_list_index` | `statusListId ASC, statusListIndex ASC` | Yes, partial |
| credentials | `ix_credentials_wallet_owner_created_at` | `walletId ASC, ownerUserId ASC, createdAt DESC` | No |
| audit_events | `ix_audit_events_created_at` | `createdAt DESC` | No |
| audit_events | `ix_audit_events_type_created_at` | `eventType ASC, createdAt DESC` | No |
| credential_status_entries | `uq_status_entries_credential_id` | `credentialId ASC` | Yes |
| credential_status_entries | `uq_status_entries_list_index` | `statusListId ASC, statusListIndex ASC` | Yes |
| credential_status_entries | `ix_status_entries_issuer_purpose` | `issuerDid ASC, statusPurpose ASC` | No |
| status_lists | `uq_status_lists_status_list_id` | `statusListId ASC` | Yes |
| status_lists | `ix_status_lists_issuer_purpose` | `issuerDid ASC, statusPurpose ASC` | No |
| status_lists | `ix_status_lists_updated_at` | `updatedAt DESC` | No |
| audit_outbox | `ix_audit_outbox_delivery` | `status ASC, availableAt ASC` | No |
| audit_outbox | `ix_audit_outbox_aggregate` | `aggregateType ASC, aggregateId ASC` | No |
| presentations | `uq_presentations_presentation_id` | `presentationId ASC` | Yes |
| presentations | `uq_presentations_challenge_domain` | `challenge ASC, domain ASC` | Yes |
| presentations | `ix_presentations_holder_created_at` | `holderDid ASC, createdAt DESC` | No |
| presentations | `ix_presentations_verification_result` | `verificationResult ASC` | No |
| presentations | `ix_presentations_expires_at` | `expiresAt ASC` | No |
| presentations | `ix_presentations_wallet_owner` | `walletId ASC, ownerUserId ASC` | No |
| presentations | `ix_presentations_stale_processing` | `verificationResult ASC, processingStartedAt ASC` | No |
| holder_wallets | `uq_holder_wallets_wallet_id` | `walletId ASC` | Yes |
| holder_wallets | `uq_holder_wallets_key_reference` | `keyReference ASC` | Yes |
| holder_wallets | `uq_holder_wallets_active_holder_did` | `holderDid ASC` | Yes, partial active/non-deleted |
| holder_wallets | `ix_holder_wallets_owner_status` | `ownerUserId ASC, status ASC, createdAt DESC` | No |
| managed_keys | `uq_managed_keys_key_id` | `keyId ASC` | Yes |
| managed_keys | `uq_managed_keys_provider_reference` | `provider ASC, providerKeyReference ASC` | Yes, partial |
| managed_keys | `uq_managed_keys_wallet_purpose_version` | `walletId ASC, purpose ASC, keyVersion ASC` | Yes |
| managed_keys | `ix_managed_keys_wallet_purpose_state` | `walletId ASC, purpose ASC, state ASC` | No |
| managed_keys | `uq_managed_keys_active_wallet_purpose` | `walletId ASC, purpose ASC, state ASC` | Yes, partial `ACTIVE` |
| managed_keys | `ix_managed_keys_holder_purpose_state` | `holderDid ASC, purpose ASC, state ASC` | No |
| managed_keys | `ix_managed_keys_owner_created` | `ownerUserId ASC, createdAt DESC` | No |
| managed_keys | `ix_managed_keys_predecessor` | `predecessorKeyId ASC` | No |
| managed_keys | `ix_managed_keys_successor` | `successorKeyId ASC` | No |
| managed_keys | `ix_managed_keys_state_updated` | `state ASC, updatedAt ASC` | No |
| managed_keys | `ix_managed_keys_stale_rotation` | `state ASC, rotatedAt ASC` | No |
| managed_keys | `ix_managed_keys_destruction_due` | `state ASC, destructionScheduledAt ASC` | No |
| managed_keys | `uq_managed_keys_idempotency` | `walletId ASC, purpose ASC, idempotencyKeyHash ASC` | Yes, partial |
| managed_keys | `uq_managed_keys_verification_method` | `verificationMethod ASC` | Yes, partial |
| presentation_challenges | `uq_presentation_challenges_challenge_id` | `challengeId ASC` | Yes |
| presentation_challenges | `uq_presentation_challenges_challenge` | `challenge ASC` | Yes |
| presentation_challenges | `ix_presentation_challenges_expires_at` | `expiresAt ASC` | No |
| presentation_challenges | `ix_presentation_challenges_status_expires` | `status ASC, expiresAt ASC` | No |
| presentation_challenges | `ix_presentation_challenges_issuer_created_at` | `issuedBy ASC, issuedAt DESC` | No |

Index creation is idempotent and occurs during enabled application startup.
The reviewed rollover migration removes only the obsolete
`uq_status_lists_issuer_purpose` index before creating its non-unique
replacement. Other index changes require an explicit migration review.

## Optimistic concurrency and soft deletion

New records start at version `1`. Updates match both identity and the caller's
expected version, set `updatedAt`, and write version `N+1`. A stale, missing,
or already deleted record raises a controlled optimistic-lock failure.

User and credential soft deletion matches the expected version, sets
`deletedAt` and `updatedAt`, and increments the version atomically. User
deletion also sets `enabled=false`. Normal reads and lists always add
`deletedAt=null`.

Revocation uses a dedicated repository update that matches `credentialId`,
`version`, `deletedAt=null`, and a non-revoked current status in one MongoDB
operation. It writes `REVOKED` plus all revocation metadata and increments the
version. The same update writes the status-list mapping and embedded audit
outbox. The generic credential update path rejects direct `REVOKED` writes and
cannot reactivate an already revoked document.

Wallets and challenges start at version `1`. Wallet state changes and
challenge consumption match the expected version and advance exactly once.
Presentation creation starts at version `1`. A verification claim matches
`presentationId`, `PENDING`, and the expected version in one update, then
increments to version `2`. Completion matches `PROCESSING` and version `2`,
stores the terminal result/reasons/time, and increments to version `3`.
There is intentionally no reset-to-pending path. Reconciliation instead
matches the stale processing timestamp and current version, records an
attempt, increments the version, and then performs the same terminal
completion path.

Managed-key provisioning, rotation, wallet rebinding, provider reconciliation,
and lifecycle changes use optimistic compare-and-set predicates. Rotation
claims the source only from `ACTIVE`; reconciliation uses a bounded lease;
only one `ACTIVE` key per wallet/purpose is allowed. Destruction changes
lifecycle metadata to `DESTROYED` but retains the record and public lineage.

## Authentication adapter

`MongoUserProvider` adapts `UserRepository` to the existing authentication
port. Set `IDENTITY_AUTH_USER_PROVIDER=mongodb`, disable fixture users, and
enable Mongo only after provisioning users with valid Argon2 password hashes.
The Authentication Service still re-resolves users on each protected request,
checks enabled state, compares current roles with token roles, and derives
permissions from current roles.

No default Mongo users are seeded. The synthetic provider remains the local
default so existing development and test behavior is unchanged.

## Docker Compose

Compose enables Mongo persistence for the Identity Service, waits for a healthy
MongoDB service, and initializes a database-scoped `readWrite` application
user. Root credentials are used only by Mongo initialization. All supplied
credentials are public local-development placeholders and must be replaced.

The init script runs only when the Mongo data volume is empty. After changing
initialization credentials in development, recreate the local volume
deliberately; never delete an unknown or production volume.

## Recovery persistence extension

The Guardian recovery sprint adds a separate `secure_recovery` database and
`recovery_app` Compose user. Recovery configuration, connection lifecycle,
domain mappers, repository protocol, in-memory adapter, PyMongo adapter, and
named-index creation remain isolated in the Recovery Service. Identity and
Recovery do not share application database credentials.

Recovery collections are:

- `guardians`: assignment lifecycle, owner/assignee, DID metadata, timestamps,
  and optimistic version;
- `recovery_policies`: one M-of-N and timing/retry policy per wallet;
- `recovery_requests`: immutable policy snapshot, digested challenge/nonce,
  state, quorum, timing, lease, result/failure, and version;
- `recovery_approvals`: one immutable decision per request/Guardian;
- `recovery_secret_shares`: request-bound authenticated encrypted Shamir
  envelopes and non-secret metadata;
- `recovery_audit_events`: typed append-only deterministic recovery events.

Unique indexes cover every domain identifier, active wallet/Guardian
assignment, policy wallet, active recovery wallet, request/session, one
request/Guardian decision, one request/Guardian share, one policy/share
version/Guardian share, and audit event ID. Query indexes cover wallet and
owner timelines, assignee/status, state/expiry, due time lock, stale execution,
decisions, and audit timelines. Mutating Guardian, policy, and recovery request
writes use exact prior-version predicates.

The active-wallet uniqueness constraint is a partial index over the explicit
nonterminal states. This makes concurrent duplicate request creation fail at
the database boundary. Worker leases and state/version predicates prevent two
workers from owning the same execution. The Identity managed-key database
remains authoritative for keys; Recovery stores only outcome IDs/public DID
metadata and never private material.

Recovery state and its audit event are currently separate Mongo writes. This
is a documented crash-gap limitation; production requires a transaction,
embedded outbox intent, or deterministic audited reconciliation. Encrypted
share envelopes are application-protected but centrally stored, so production
also requires independent Guardian custody or equivalent separation.

Full collection fields, indexes, workflow, and limitations are in
[account-recovery.md](account-recovery.md).

## Testing

Unit tests cover configuration, connection lifecycle, URI redaction, domain
invariants, BSON/ObjectId round trips, index declarations, duplicate handling,
queries, optimistic locking, soft deletion, append-only audit behavior,
repository dependency injection, revocation irreversibility, status-entry
collision handling, publication versioning, outbox leasing/retry/idempotency,
expiry transitions, legacy-status compatibility, and the Mongo authentication
adapter. Presentation tests cover ObjectId/BSON round trips, unique
challenge/domain enforcement, state/version claims, terminal completion,
dependency injection, and the opt-in real-Mongo adapter. Wallet and challenge
tests cover mapping, indexes, ownership filtering, unique conflicts, atomic
challenge consumption/expiry, stale-processing queries, reconciliation
claims, and real-Mongo round trips. Managed-key tests cover mapper
private-material rejection, indexes, repository queries and compare-and-set
behavior, provisioning idempotency, rotation lineage, lifecycle transitions,
destruction delay, provider mismatch handling, signing, reconciliation, and
opt-in real-Mongo round trips.
Recovery tests cover mapper round trips, named indexes, duplicate assignments,
one active request, immutable decisions/shares, optimistic races, due/stale
queries, deterministic fake-Mongo integration, and service/API behavior. A
real Recovery Mongo URI is not required for the default suite; Compose remains
the local integration deployment.

Real MongoDB integration tests are opt-in:

```powershell
$env:IDENTITY_TEST_MONGODB_URI = "mongodb://identity_app:change-me-app@localhost:27017/?authSource=secure_identity"
python -m pytest tests/integration/test_mongo_repositories.py -q
```

The integration fixture uses a unique `secure_identity_test_*` database and
drops only that verified test database after execution.

## Production limitations

- Issuance is single-document atomic on the configured standalone MongoDB.
  Multi-document transaction orchestration is intentionally not introduced.
- The credential mutation and central audit-event append are intentionally
  decoupled by a durable outbox. Revocation delivery intent is in the same
  credential update; other event intents are inserted before publication.
  Production still requires outbox-lag/retry monitoring and tested recovery.
- Presentation audit intents use the standalone outbox. Presentation state and
  the outbox insert are separate writes, so a crash between them requires
  production reconciliation or transactional orchestration.
- There is no schema migration runner, backup/restore automation, Mongo
  storage-encryption key manager, retention worker, change stream, or external
  observability pipeline.
- Reconciliation is polling-based and process-local. It does not coordinate a
  distributed scheduler; optimistic Mongo predicates provide the duplicate
  work guard.
- Consumed challenge evidence and presentations have no retention/archival
  worker.
- Holder key custody has a provider-neutral lifecycle boundary, a
  deterministic development adapter, and a generic HTTPS gateway adapter.
  No vendor KMS/HSM, hardware attestation, secure enclave, or external-wallet
  deployment has been integrated or certified.
- Publication history is embedded and grows with material versions; there is
  no history compaction, archival policy, or external CDN replication.
- Compose credentials and non-TLS localhost networking are development-only.
- Production requires managed secrets, TLS, least privilege, replica-set or
  managed deployment design, tested backups, monitoring, capacity planning,
  retention policy, and privacy review.
- Audit persistence is an application audit foundation, not an independently
  tamper-evident or compliance-certified log.
- Recovery state/audit writes are not transactionally coupled, and encrypted
  Shamir envelopes remain centrally stored under one service-controlled
  envelope key. Both require redesign or compensating controls for production.
