# External KMS/HSM Adapter and Managed-Key Lifecycle

## Scope and assurance statement

This milestone adds a provider-neutral managed-key architecture to the
Identity Service. Holder Verifiable Presentation signing can now be routed to
an external key provider without returning private key material to the
application. The implementation includes a non-production development
provider and a generic HTTPS KMS gateway adapter.

No vendor KMS, HSM, PKCS#11 device, cloud account, mobile secure enclave, or
production key ceremony was configured or tested. The generic adapter is a
contract boundary, not evidence that a real HSM deployment exists.

Issuer credential signing and Status List signing retain their stable local
prototype paths. This sprint integrates managed keys into holder VP signing
and does not falsely broaden the custody assurance of unrelated signing paths.

## Architecture

```text
Authenticated holder/admin
        |
        v
Managed-key API + RBAC + object ownership
        |
        v
ManagedKeyService
   |         |                  |
   |         |                  +--> durable audit outbox
   |         +--> holder_wallets key binding (CAS)
   +--> managed_keys repository (CAS and unique indexes)
        |
        v
ExternalKeyProvider registry
   |                              |
   +--> Development provider      +--> Generic HTTPS KMS gateway
        (non-production)               (configurable contract)

VP canonical payload
        |
        v
ProviderAwareHolderSigner
        |
        +--> active ManagedKey lookup and policy enforcement
        +--> provider metadata validation
        +--> provider sign operation
        +--> signature bytes only
```

The domain and application layers depend only on ports. PyMongo, HTTP, TLS,
and local cryptography remain infrastructure details. Provider references are
opaque routing identifiers. They are persisted but are never returned by the
managed-key HTTP models or written to audit metadata.

## ManagedKey domain model

Each `managed_keys` record contains:

- internal `keyId`, `walletId`, `ownerUserId`, and `holderDid`;
- provider name and opaque `providerKeyReference`;
- `algorithm`, `purpose`, and monotonic `keyVersion`;
- lifecycle `state`;
- public multibase material, fingerprint, and verification method;
- creation, activation, rotation, suspension, revocation, destruction,
  expiry, and provider-sync timestamps where applicable;
- predecessor and successor links;
- bounded compromise/failure metadata;
- a one-way idempotency-key digest;
- reconciliation lease/attempt metadata; and
- optimistic metadata `version`.

Raw private keys, private JWK parameters, PEM private keys, seeds, mnemonics,
unencrypted key blobs, provider credentials, and Authorization values are not
domain fields and are rejected by the Mongo mapper if injected into a
document.

## Algorithms and purposes

The implemented algorithm allowlist is Ed25519, used by the existing
`eddsa-jcs-2022` profile. ECDSA, RSA, BBS+, and other algorithms are not
implemented.

Purposes are explicit:

- `HOLDER_AUTHENTICATION`
- `HOLDER_ASSERTION`
- `CREDENTIAL_SIGNING`
- `PRESENTATION_SIGNING`
- `ISSUER_ASSERTION`
- `STATUS_LIST_SIGNING`

A purpose enum value does not imply that every path uses managed custody.
Current provider-aware signing is `PRESENTATION_SIGNING` only. Algorithm,
purpose, state, provider enablement, and current public metadata are checked
before every managed holder signature.

## Lifecycle states and transitions

| From | Allowed next states |
| --- | --- |
| `PENDING` | `ACTIVE`, `FAILED` |
| `ACTIVE` | `ROTATING`, `SUSPENDED`, `COMPROMISED`, `REVOKED`, `FAILED` |
| `ROTATING` | `ACTIVE`, `SUSPENDED`, `COMPROMISED`, `REVOKED`, `FAILED` |
| `SUSPENDED` | `ACTIVE`, `COMPROMISED`, `REVOKED`, `FAILED` |
| `COMPROMISED` | `REVOKED`, `FAILED` |
| `REVOKED` | `DESTROY_PENDING`, `FAILED` |
| `DESTROY_PENDING` | `REVOKED`, `DESTROYED`, `FAILED` |
| `DESTROYED` | none |
| `FAILED` | none; manual investigation/dead-letter state |

Repeated no-op requests may return the current state. All other invalid
transitions raise a deterministic controlled error. Only `ACTIVE` keys can
sign. `ROTATING`, `SUSPENDED`, `COMPROMISED`, `REVOKED`,
`DESTROY_PENDING`, `DESTROYED`, and `FAILED` keys cannot sign.

## Provider abstraction

`ExternalKeyProvider` supports:

- idempotent key creation;
- bounded public metadata retrieval;
- signing without private-key export;
- enable, suspend, and revoke operations;
- scheduled deletion, cancellation, and confirmed destruction;
- provider availability checks; and
- stable timeout, unavailable, permission, not-found, and metadata errors.

The application sends the canonical Ed25519 proof payload and receives only a
signature. It does not receive a signing handle with export methods.

### DevelopmentExternalKeyProvider

The development adapter provides deterministic Ed25519 behavior for local
tests. Private material is derived and used inside the adapter boundary and is
never persisted in MongoDB. It supports failure injection, lifecycle
operations, restart-stable public derivation from its development reference,
and a redacted representation.

It is explicitly `production_ready = false`. Production-like environments
fail configuration when development-only custody is the default or sole
provider.

### GenericRemoteKmsAdapter

The generic adapter defines a JSON/HTTPS gateway contract under `/v1/keys`.
It supports:

- configurable provider name and HTTPS base URL;
- authentication headers through a separate abstraction;
- bearer-secret lookup by environment-variable name at request time;
- request timeout;
- bounded exponential retry;
- a process-local circuit breaker;
- TLS verification; and
- optional client certificate/key path references.

The adapter maps provider HTTP failures to controlled application errors. It
does not log request bodies, provider bodies, Authorization values, canonical
signing payloads, or provider credentials.

The current standard-library HTTP transport applies one request timeout to the
connection/read operation; the separately validated connection-timeout value
is retained for a future transport with distinct phases.

## Key provisioning

1. Authenticate and authorize the caller.
2. Verify wallet ownership and active wallet state.
3. Validate provider, algorithm, and purpose policy.
4. Hash the `Idempotency-Key`; do not persist the plaintext header.
5. insert a `PENDING` record with a unique wallet/purpose/key version.
6. create the provider key idempotently.
7. validate provider identity, reference, algorithm, multibase encoding,
   fingerprint, DID, and verification method.
8. atomically update the record to `ACTIVE`.
9. for presentation signing, atomically bind the wallet to the new provider
   reference and holder DID.
10. publish safe durable audit events and metrics.

A provider success followed by local persistence failure leaves a recoverable
`PENDING` record. Reconciliation repeats provider creation with the same
stored idempotency identity, retrieves the same provider key, validates it,
activates it, and repairs the wallet binding.

## Rotation and DID semantics

Rotation uses an atomic source-key `ACTIVE -> ROTATING` claim. A concurrent
claim with the old optimistic version fails. The service creates and
validates a `PENDING` successor, activates it, links predecessor/successor,
updates the wallet binding, and retires the predecessor.

Only one `ACTIVE` key for a wallet/purpose is permitted by a partial unique
Mongo index. `keyVersion` is also unique per wallet/purpose.

The default rotation grace is zero: the predecessor provider key is suspended
immediately after wallet binding. With a non-zero configured grace, the
predecessor remains provider-enabled but locally `ROTATING`; it still cannot
sign because the signer requires `ACTIVE` and the wallet points to the
successor. Reconciliation suspends it after the grace window.

### `did:key`

`did:key` is immutable. Rotation generates a new provider public key and
therefore a new `did:key`. The wallet is rebound to the successor DID. The
application stores predecessor/successor relationships and never pretends to
mutate the old DID document.

Old proof signatures remain cryptographically verifiable because the old
`did:key` contains its public key and public managed-key metadata is retained.
Existing credentials are not reissued automatically. Credentials bound to an
old holder DID are not automatically treated as belonging to the successor
DID.

### `did:web`

This repository does not control a mutable holder `did:web` publication
pipeline. A `did:web` rotation request therefore fails closed before provider
mutation. It does not fabricate a DID document update. A future implementation
requires controlled publishing, HTTPS/DNS operations, versioning, and an
independent security review.

## Suspension, compromise, revocation, and destruction

- A holder may suspend, resume, or revoke a key belonging to their own wallet.
- Resume is valid only from `SUSPENDED`.
- Compromise, destruction, and administrative reconciliation require
  elevated admin permissions and explicit routes.
- Compromise is persisted locally before a best-effort provider suspension so
  provider failure cannot leave local signing enabled.
- Revocation is irreversible.
- Destruction requires a bounded reason, exact key-ID confirmation, admin
  permission, and a policy delay.
- `DESTROY_PENDING` is distinct from confirmed `DESTROYED`.
- Cancellation returns a pending key to `REVOKED`, never `ACTIVE`.
- Physical deletion may be asynchronous. The worker confirms or safely maps
  provider not-found to destroyed only after the scheduled time.

The later Guardian recovery sprint integrates at this application-service
boundary. It invokes `ManagedKeyService.recover_wallet` through a hidden,
request-bound internal route; it does not call a provider or mutate key
documents directly. See [account-recovery.md](account-recovery.md).

## Reconciliation

The lifecycle worker polls a bounded batch and uses an optimistic lease. It
handles:

- stale `PENDING` provisioning;
- stale or partial `ROTATING` operations;
- active provider metadata synchronization;
- missing provider keys;
- disabled provider keys;
- inconsistent wallet bindings;
- due `DESTROY_PENDING` records; and
- retry exhaustion into terminal `FAILED`.

The worker is idempotent, restart-safe, concurrency-safe, and shuts down with
the application lifespan. It never destroys a provider key merely because a
wallet or metadata inconsistency exists. An orphan active provider key is
suspended before its local record is failed.

## REST endpoints

| Method and path | Authorization |
| --- | --- |
| `POST /api/v1/wallets/{walletId}/keys` | holder create permission + owner |
| `GET /api/v1/wallets/{walletId}/keys` | holder read permission + owner |
| `GET /api/v1/wallets/{walletId}/keys/{keyId}` | holder read permission + owner |
| `POST .../{keyId}/rotate` | holder rotate permission + owner |
| `POST .../{keyId}/suspend` | holder suspend permission + owner |
| `POST .../{keyId}/resume` | holder resume permission + owner |
| `POST .../{keyId}/compromise` | admin elevated permission |
| `POST .../{keyId}/revoke` | holder revoke permission + owner |
| `POST .../{keyId}/schedule-destruction` | admin elevated permission |
| `POST .../{keyId}/cancel-destruction` | admin elevated permission |
| `POST .../{keyId}/reconcile` | admin reconciliation permission |

Creation and rotation require `Idempotency-Key`. Lists use a bounded
`limit` and optional `afterKeyId` cursor. Request schemas reject extra fields.
Reason-bearing actions require bounded reasons; destruction also requires
exact key-ID confirmation.

Normal admin read permission does not bypass object ownership. Issuer and
verifier roles have no managed-holder-key permissions. Foreign and missing
resources share the same `404` response shape.

HTTP responses expose only public key and lifecycle metadata. They omit the
provider key reference, idempotency digest, compromise details, provider
credentials, and all private material.

## MongoDB

The `managed_keys` collection uses named idempotent indexes for:

- unique `keyId`;
- unique provider plus provider reference when present;
- unique wallet/purpose/key version;
- unique active wallet/purpose/state;
- wallet/purpose/state and holder/purpose/state queries;
- owner lookup;
- predecessor and successor lookup;
- state/update and stale rotation lookup;
- due destruction lookup;
- unique idempotency identity; and
- unique verification method.

Lifecycle updates use compare-and-set predicates containing the current
metadata version and, where required, current state.

## Audit

Durable outbox events cover request, provider creation, activation, failure,
rotation, successor creation, completion/failure, suspension, resume,
compromise, revocation, destruction, provider mismatch, reconciliation,
unauthorized object access, and lifecycle signing rejection.

Audit metadata contains bounded identifiers and state/reason codes. It omits
provider references, request bodies, signing payloads, private material,
Authorization values, tokens, proofs, credentials, and hashes.

## Metrics

Process-local counters track:

- creation attempts/success/failure;
- provider requests, latency, timeouts, and errors;
- signing attempts/success/failure/lifecycle rejection;
- rotation attempts/success/failure and stale rotations;
- compromise and revocation;
- scheduled/completed/failed destruction;
- reconciliation attempts/success/failure; and
- bounded provider/purpose and lifecycle-state inventories.

No metric label uses a key ID, wallet ID, user ID, DID, or provider reference.
Metrics reset on process restart because no durable monitoring backend exists.

## Configuration and deployment

All settings are documented in `.env.example` and passed through Compose.
The default is the development provider for local use. To configure the
generic gateway, enable its configured provider name, set it as default,
provide an HTTPS base URL, and inject any authentication secret through the
named runtime environment variable. Never commit the secret value.

Production-like environments reject development-only default custody and
reject a remote provider with TLS verification disabled.

Client certificate and private key paths are references only. Certificate
material must be mounted through deployment secret management; it is not
included in this repository.

## Operational runbook

1. Confirm MongoDB and the configured provider are healthy.
2. Inspect reconciliation counts and provider timeout/error counters.
3. For a stale key, use the admin reconciliation endpoint only after checking
   provider state and the durable audit trail.
4. Never manually set a key back to `ACTIVE` in MongoDB.
5. For suspected compromise, mark the key compromised first, then investigate
   provider suspension evidence and rotate/revoke under incident policy.
6. Schedule destruction only after retention/legal requirements are met.
7. Do not shorten the destruction timestamp directly in the database.
8. If retry limits produce `FAILED`, preserve the record and provider key,
   investigate, and use an explicitly reviewed repair process.
9. Do not delete orphan provider keys automatically based only on local
   inconsistency.

## Threat considerations

Controls address provider substitution, algorithm/purpose confusion,
concurrent rotation, crash windows, provider outage, lifecycle bypass,
foreign-object access, audit duplication, private-key leakage, request
ambiguity, and premature destruction. Residual risks include provider/gateway
compromise, development derivation predictability, process-local metrics,
operator access to provider references, absent hardware attestation, and the
lack of a controlled mutable holder DID method.

## Verification

Tests cover domain transitions, invalid transitions, provider operations and
errors, metadata validation, non-export, mapper rejection, repository
compare-and-set, idempotency, activation/binding, rotation/races/partial
failure, prior-signature verification, lifecycle signing rejection,
destruction, reconciliation/retry limits, worker shutdown, RBAC,
non-enumeration, OpenAPI, and opt-in real MongoDB behavior.

## Current limitations

- The development provider is not secure custody.
- The generic HTTPS adapter has no deployed provider behind it in this
  repository.
- No HSM attestation, quorum administration, vendor-specific IAM, or hardware
  deletion evidence exists.
- Issuer credential and Status List signing remain on stable local prototype
  paths.
- Holder `did:web` mutation is not implemented.
- There is no automated time-based rotation scheduler; rotation is requested
  explicitly and the configured interval is policy metadata for operations.
- The outbox is durable in MongoDB, but metrics and the provider circuit
  breaker are process-local.
- Managed-key state and its standalone outbox intent are separate MongoDB
  writes. A database outage or process crash between them can leave an audit
  gap; production requires a transaction, embedded intent, or audited
  backfill/reconciliation design.
- Guardian recovery now reuses this boundary, but no Guardian DID signature,
  independent share delivery, blockchain, AI, DIDComm, Presentation Exchange,
  selective disclosure, mobile wallet, or frontend is part of this KMS sprint.

## Future extensions

Future, separately reviewed work may add vendor-specific adapters, PKCS#11,
attestation validation, provider-native deletion evidence, a mutable holder
DID publication workflow, a rotation scheduler, and production hardening of
the implemented recovery integration. None of those capabilities is claimed
here.
