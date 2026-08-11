# Holder Wallet and Key Custody

## Scope

The Identity Service now has a production-oriented application boundary for
holder wallets, object ownership, holder signing, server-issued presentation
challenges, and recovery of stale presentation verification work. The current
managed-key extension adds a provider-neutral lifecycle and signing boundary,
a deterministic local adapter, and a generic HTTPS KMS gateway contract. It
does not claim a configured vendor KMS, HSM, mobile wallet, hardware token,
secure enclave, or hardware-backed key ceremony.

This sprint does not add Redis, Presentation Exchange, selective disclosure,
blockchain, recovery, frontend work, OAuth/OIDC, refresh tokens, or rate
limiting.

## Architecture

```text
authenticated holder
        |
        v
HolderWalletService --------------------+
        | ownerUserId                   |
        | holderDid                     | opaque keyReference
        v                               v
holder_wallets ----> managed_keys ----> ExternalKeyProvider
        |                               |
        | walletId/ownerUserId          v
        +----> credentials       ProviderAwareHolderSigner
        |
        v
HolderPresentationService
        |-- application-layer wallet ownership
        |-- credential wallet/owner/holder binding
        |-- atomic server challenge consumption
        |-- signing through HolderSigner
        v
presentations

authenticated verifier
        |
        v
PresentationChallengeService
        |
        v
presentation_challenges

lifecycle worker / admin
        |
        v
PresentationReconciliationService
        |
        +--> stale PROCESSING claim + deterministic revalidation
        +--> VERIFIED or controlled REJECTED completion
```

Domain and application modules do not import PyMongo, BSON, FastAPI, private
key types, filesystem key files, Cloud KMS SDKs, or HSM SDKs. Infrastructure
adapters own BSON mapping, provider HTTP/TLS, and local development
cryptography.

## Holder wallet model

`HolderWallet` contains:

| Field | Meaning |
| --- | --- |
| `walletId` | Opaque public wallet identifier |
| `ownerUserId` | Exactly one authenticated platform user |
| `holderDid` | Holder DID controlled by the wallet key |
| `status` | `ACTIVE`, `LOCKED`, or `DISABLED` |
| `keyReference` | Opaque infrastructure reference; never private key bytes |
| `createdAt` / `updatedAt` | UTC lifecycle timestamps |
| `version` | Optimistic concurrency version |
| `deletedAt` | Soft-deletion timestamp |

Only an active, non-deleted wallet may sign. Locking and disabling are
application operations and emit durable audit intents. Soft deletion forces
the persisted status to `DISABLED` and normal repository reads exclude the
record.

One active wallet may control a given holder DID. A user may not read another
user's wallet even when their role otherwise contains the route permission.
The application service returns the same not-found result for absent and
foreign wallets.

## Credential ownership

Credential documents retain their existing `holderDid` and may additionally
contain `walletId` and `ownerUserId`. During issuance, an existing managed
wallet for the credential subject DID is detected and both ownership fields
are written with the credential. Legacy or externally managed subjects remain
unbound until an explicit migration or external-wallet adapter exists.

Wallet inventory queries require both `walletId` and `ownerUserId`.
Presentation creation checks all of the following in the application layer:

1. the authenticated user owns the wallet;
2. the wallet is active and not soft-deleted;
3. the wallet controls the presentation holder DID;
4. every credential has the same holder DID;
5. every credential has the wallet's `walletId`;
6. every credential has the authenticated `ownerUserId`;
7. every credential remains active, valid, correctly signed, hash-consistent,
   and correctly mapped to its status entry.

An administrator does not bypass these holder, wallet, or credential bindings.
The manual administrative capability is limited to stale presentation
reconciliation.

## Key-provider and signing boundary

The application exposes three distinct ports:

- `HolderKeyProvider` provisions or locates a key through an opaque reference;
- `HolderKeyMetadataProvider` returns holder DID, verification method, and
  algorithm metadata;
- `HolderSigner` signs bytes using the opaque reference.

Wallet and presentation records never contain raw private key bytes. The
presentation builder receives only the wallet's key reference and signs
through `HolderSigner`.

`LocalHolderKeyProvider` and `LocalDevelopmentHolderSigner` are development
adapters. They deterministically derive Ed25519 fixture keys from opaque local
references and retain compatibility with the previous synthetic holder
fixture. Their deterministic material is public test behavior and provides no
production protection.

New wallets provision a managed presentation-signing key through
`ManagedKeyService`. `ProviderAwareHolderSigner` requires an `ACTIVE` managed
key, validates provider/public metadata, and asks the provider to sign without
exporting private material. The generic HTTPS adapter implements the
provider-neutral contract; a future vendor KMS/HSM, hardware-token,
mobile-wallet, or external-agent integration can replace that provider
without changing wallet, ownership, challenge, or presentation business
rules. Full lifecycle details are in
[external-kms-key-lifecycle.md](external-kms-key-lifecycle.md).

## Secure challenge lifecycle

`POST /api/v1/presentation-challenges` creates a challenge using
`secrets.token_urlsafe(32)`. A record contains:

- opaque `challengeId`;
- random challenge value;
- normalized verifier DNS `domain`;
- bounded `audience`;
- optional `requestedHolderDid`;
- `issuedBy`, `issuedAt`, and `expiresAt`;
- optional `consumedAt`;
- `ISSUED`, `CONSUMED`, `EXPIRED`, or `CANCELLED` status;
- optimistic `version`.

The value and ID each have unique indexes. Consumption atomically matches the
ID, `ISSUED` state, optimistic version, unexpired timestamp, domain, audience,
and optional holder restriction before writing `CONSUMED` and `consumedAt`.
The same challenge cannot create a second presentation.

The wallet-bound presentation proof covers the server record's challenge,
domain, audience, holder, credentials, and lifetime. Optional legacy request
hints are never authoritative; conflicting challenge, domain, or audience
values consume and reject the challenge. Verification obtains authoritative
bindings from the persisted challenge record rather than trusting caller
expectations.

Challenge reads are permitted only to the issuing actor or the owner of the
explicitly requested holder DID. All other lookups return not found.
Challenge values, credentials, proof values, tokens, and key references are
excluded from audit metadata.

Consumed records are retained for replay evidence. The `expiresAt` index is a
normal query index, not a TTL index.

## Presentation reconciliation

The repository stores `processingStartedAt` when it atomically claims
`PENDING -> PROCESSING`. It also stores `reconciliationAttempts` and
`lastReconciledAt`.

Records older than
`IDENTITY_PRESENTATION_RECONCILIATION_STALE_SECONDS` are stale. The
reconciliation service:

1. atomically matches `PROCESSING`, the stale timestamp, and `version`;
2. increments the attempt and writes `lastReconciledAt`;
3. restores the wallet key metadata through its opaque key reference;
4. loads the consumed server challenge;
5. re-runs VP proof, challenge/domain/audience, document, credential proof,
   credential hash, holder, ownership, validity, and status checks;
6. atomically completes `PROCESSING -> VERIFIED|REJECTED`;
7. emits the normal terminal presentation event and one reconciliation event.

Missing wallet, key, or challenge evidence fails closed as `REJECTED` with
`RECONCILIATION_EVIDENCE_INCOMPLETE`. A completed record is returned
unchanged on repeated reconciliation, so the workflow is idempotent and does
not consume the challenge again.

The enabled application lifecycle runs a background reconciliation worker.
`POST /api/v1/presentations/{presentationId}/reconcile` exposes the same
operation only to the `admin` role. The all-capability legacy issuer role is
explicitly denied at this route.

## MongoDB schema and indexes

New collections:

| Collection | Important indexes |
| --- | --- |
| `holder_wallets` | unique `walletId`; unique `keyReference`; unique active `holderDid`; `ownerUserId + status + createdAt` |
| `presentation_challenges` | unique `challengeId`; unique challenge value; `expiresAt`; `status + expiresAt`; `issuedBy + issuedAt` |

Extended collections:

- `credentials`: optional `walletId` and `ownerUserId`, plus a wallet/owner
  inventory index;
- `presentations`: optional compatibility fields plus `walletId`,
  `ownerUserId`, `challengeId`, `audience`, `processingStartedAt`,
  `reconciliationAttempts`, and `lastReconciledAt`;
- `presentations`: new wallet/owner and stale-processing indexes.

Index creation remains named and idempotent. Existing legacy documents remain
readable. New default application presentation creation requires wallet and
server challenge state.

## RBAC and object authorization

New permissions are:

- `wallets:create`;
- `wallets:read`;
- `wallets:credentials:read`;
- `presentation-challenges:create`;
- `presentation-challenges:read`;
- `presentations:reconcile`.

The holder role receives wallet creation/read/inventory, challenge read, and
its prior presentation creation/read permissions. The verifier role receives
challenge creation/read and its prior presentation verification/read
permissions. Role permission is only the first gate: wallet, challenge,
credential, and presentation services apply object ownership after RBAC.

## Audit events

New closed audit event types are:

- `WALLET_CREATED`;
- `WALLET_LOCKED`;
- `WALLET_DISABLED`;
- `CHALLENGE_ISSUED`;
- `CHALLENGE_CONSUMED`;
- `CHALLENGE_REJECTED`;
- `PRESENTATION_RECONCILED`;
- `PRESENTATION_RECONCILIATION_FAILED`;
- `HOLDER_OWNERSHIP_REJECTED`.

Events use the existing durable outbox and idempotent `audit_events`
destination. IDs are deterministic for one logical state change. Metadata is
bounded to safe identifiers, state, domain/audience, and reason codes.

Wallet/challenge/presentation state and standalone outbox insertion are not a
single multi-document transaction. A process failure in that narrow gap is a
known operational limitation; the outbox remains durable after insertion.

## Internal metrics

Process-local metrics now include:

- active and locked wallet counts;
- challenge issuance, rejection, replay, and expiry counts;
- current stale-processing observation;
- reconciliation attempts, successes, and failures;
- holder ownership rejection count.

They are runtime signals, not durable accounting. Counts begin when the
process starts and are not reconstructed from MongoDB. No dashboard is
implemented.

## Security considerations

- Foreign wallet and challenge lookups are enumeration resistant.
- A role never substitutes for wallet ownership or holder cryptographic
  control.
- Challenge domain and audience are server state and signature-covered.
- Consumed challenges remain evidence and are not prematurely deleted.
- Raw private keys are excluded from domain records, BSON documents, HTTP
  models, OpenAPI, audit metadata, logs, and object representations.
- Key references are operationally sensitive identifiers even though they are
  not private keys; production access must be least privilege and audited.
- Optimistic state/version predicates protect wallet, challenge,
  presentation verification, and reconciliation races.

## Testing

Domain, repository, service, API, authorization, replay, expiry, ownership,
audit, metrics, and reconciliation behavior is covered by the Holder Wallet
test suite. The focused suite runs with:

```powershell
python -m pytest -q `
  tests/unit/test_holder_wallet_domain.py `
  tests/unit/test_holder_wallet_repositories.py `
  tests/unit/test_holder_wallet_services.py `
  tests/unit/test_holder_wallet_settings.py `
  tests/unit/test_presentation_repository.py `
  tests/integration/test_holder_wallet_api.py
```

Real MongoDB index, mapping, uniqueness, and atomic-transition coverage is
explicitly opt-in:

```powershell
$env:IDENTITY_TEST_MONGODB_URI = "mongodb://identity_app:change-me-app@localhost:27017/?authSource=secure_identity"
python -m pytest tests/integration/test_mongo_repositories.py -q
```

The integration fixture creates and drops only its uniquely named test
database. The URI shown above is a local-development placeholder.

## Operational limitations

- The authentication users and holder adapter are synthetic local fixtures.
- The local deterministic key derivation is not secure custody.
- Managed-key rotation, suspension, compromise, revocation, delayed
  destruction, and reconciliation are implemented for holder presentation
  signing. There is no vendor KMS/HSM deployment, hardware attestation,
  recovery, or external-wallet protocol.
- No migration runner backfills legacy credentials or presentations with
  wallet ownership.
- Process-local metrics are not a monitoring platform.
- Consumed challenges and presentation documents have no retention or
  archival worker.
- Standalone audit outbox creation is not transactionally coupled to every
  wallet, challenge, or presentation state change.
- MongoDB production TLS, backup, replica-set, encryption, secret management,
  retention, and disaster-recovery controls remain deployment work.

## External KMS/HSM boundary

The implemented generic provider contract may replace local derivation only
when a concrete deployment:

1. accepts the stored opaque key reference;
2. returns bounded holder/key metadata without private material;
3. performs signing internally;
4. enforces key state, purpose, tenant, rotation, and authorization;
5. returns controlled errors without provider secrets;
6. preserves the existing ownership, challenge, audit, and reconciliation
   behavior.

Provider authentication, tenant isolation, key status, rotation, destruction,
failure handling, audit, and operational signals are represented in the
current generic boundary. A production adoption still requires a concrete
vendor adapter or gateway, deployment-specific access policy, hardware
attestation where applicable, key ceremonies, monitoring integration, and an
independent security review.
