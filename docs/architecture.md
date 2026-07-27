# Planned Architecture

## Conceptual lifecycle

```text
User / Web Client
        |
        v
API Gateway
        |
        v
Identity Service
        |
        v
Fraud Detection Service
        |
        v
Blockchain
        |
        v
Recovery Service
```

This sequence describes the project areas in the academic concept; it is not an implemented synchronous call chain. The planned runtime architecture uses the API Gateway as the public boundary. Identity operations may request advisory fraud analysis and may submit a non-identifying digest to a future blockchain adapter. Recovery is a separate, constrained state machine rather than the final step of every identity request.

## Actors

- **Holder:** Controls an identity wallet and presents credentials or proofs. Holder private keys remain holder-controlled.
- **Issuer:** Creates and signs credentials after applying an explicit assurance and governance policy.
- **Verifier:** Requests and validates only the information required for a declared transaction purpose.
- **Guardian:** Participates in a threshold recovery policy. A single guardian cannot complete recovery.

## Component responsibilities

| Component | Planned responsibility | Must not do |
| --- | --- | --- |
| Web Client | User interaction and wallet hand-off | Store platform or holder private keys |
| API Gateway | Public request boundary, correlation, limits, authentication and authorization enforcement | Implement credential cryptography |
| Identity Service | Local DID resolution, synthetic VC/VP proofs, wallet/credential object ownership, opaque holder-key references, server challenges, challenge/domain/audience-bound presentations, stale-processing reconciliation, synthetic authentication/RBAC, MongoDB repositories, irreversible revocation, Status Lists, and durable audit delivery | Expose secrets, let roles bypass object ownership, persist raw private keys, trust client challenge bindings, bypass versions, reuse challenges, reverse revocation, treat signatures as claim truth, or accept arbitrary resolver/context input |
| Fraud Service | Produce versioned advisory risk results and reason codes | Receive raw credentials or autonomously recover identities |
| Blockchain Adapter/Contracts | Anchor narrowly selected non-identifying digests | Store DIDs, claims, credentials, guardian data, or personal data |
| Recovery Service | Expiring, idempotent, threshold guardian workflow | Permit one guardian to finalize recovery |
| MongoDB | User, holder-wallet, challenge, credential, and presentation lifecycle; status-list assignments/publications; durable outbox; and append-only audit persistence | Store raw private keys, bypass data minimization, erase revocation/outbox/replay evidence, reuse a VP challenge, or treat soft deletion as credential revocation |
| Redis | Planned short-lived challenges, idempotency, and rate-limit state | Become a system of record |

## Trust boundaries

```text
[Untrusted client zone]
          |
          | Public HTTPS boundary
          v
[API Gateway / public edge]
          |
          | Authenticated internal service boundary
          v
[Identity | Fraud | Recovery]
          |
          +---- Data boundary ----> [MongoDB | Redis]
          |
          +---- Public ledger boundary ----> [Blockchain]
          |
          +---- Independent approval boundary ----> [Guardians]
```

Detailed assets, threats, controls, and security invariants are defined in [threat-model.md](threat-model.md).

## Accepted prototype standards decisions

The accepted standards baseline is documented in [standards-baseline.md](standards-baseline.md):

- DID Core v1.0 is the stable DID data-model baseline.
- `did:web` represents the synthetic institutional issuer.
- `did:key` is allowed only for short-lived, synthetic holder fixtures.
- VC Data Model v2.0 defines credential structure.
- VC Data Model v2.0 defines the local full-disclosure Verifiable Presentation
  structure and holder proof relationship.
- Data Integrity `eddsa-jcs-2022` with Ed25519 and Multikey defines the first proof format.
- W3C Bitstring Status List v1.0 concepts define shared revocation-list encoding and publication.
- Draft next versions are monitored but not implemented.
- Blockchain is not used as the DID registry in the first prototype.

The rationale, limitations, and review triggers are in [ADR 0001](adr/0001-did-methods-for-the-prototype.md) and [ADR 0002](adr/0002-vc-data-model-and-proof-format.md).

## Planned request principles

- Only the gateway is publicly reachable in a production design.
- Internal calls require authenticated workload identity and action-level authorization.
- Mutating requests use idempotency keys and correlation identifiers.
- Credentials and proofs are minimized and are never written to logs or a public ledger.
- Fraud results are advisory and versioned.
- Recovery uses expiry, threshold approval, cooling-off, notification, and audit controls.
- Blockchain writes are optional until their necessity and privacy impact are justified.

## Current implementation boundary

All FastAPI services expose `GET /health`. The Identity Service additionally
exposes local routes under `/api/v1/credentials` for profile validation,
synthetic signing, verification, Mongo-backed revocation/status, and
capability discovery, plus public routes under `/api/v1/status-lists` for
signed publication, metadata, immutable history, and historical versions.
Authenticated wallet, presentation-challenge, and presentation routes create
wallet-bound short-lived presentations and reconcile stale verification work.
These routes are a
direct development boundary only; the planned production architecture still
places authenticated, authorized, rate-limited access behind the API Gateway.

The Identity Service also exposes public synthetic login at
`POST /api/v1/auth/token` and protected current-user resolution at
`GET /api/v1/auth/me`. Credential signing and revocation require local Bearer
authentication and the `credentials:sign` or `credentials:revoke` permission.
The `admin` and `issuer` roles can revoke; `verifier` cannot. The local holder
can create/read its wallets and presentations. A verifier can issue/read its
challenges and verify/read related presentations. Application services apply
object ownership after RBAC and hide foreign objects. Only the admin role can
reconcile. Validation, credential verification, capabilities, and credential
status lookup remain public.

The persistence boundary consists of application repository protocols and
infrastructure-only PyMongo adapters. Domain records use strings and
timezone-aware datetimes; BSON mappers convert domain IDs to ObjectId and map
camelCase document fields. A lifecycle-managed connection pool performs a
startup ping, ensures stable named indexes, and starts the audit outbox
worker plus the presentation reconciliation worker. User, wallet, challenge,
credential, presentation, status-entry, status-publication, and outbox records
use optimistic versions where mutable. Audit events are append-only.

The revocation application service composes revocation, status-list, and
durable audit-delivery ports. A status transition uses an atomic
`credentialId` + `version` + current-state predicate. The same credential
update stores terminal revocation metadata, its stable list assignment, and
the embedded `CREDENTIAL_REVOKED` outbox record. `REVOKED` is terminal; the
generic credential repository cannot write it or reactivate it. Status lookup
persists `EXPIRED` when the validity window has elapsed and first persists a
standalone `STATUS_CHECKED` outbox record.

The Status List application service reads stable assignments and current
revocation state, generates a 131,072-entry GZIP/base64url multibase
bitstring, signs a `BitstringStatusListCredential`, and optimistically stores
the latest publication with append-only embedded history. Unchanged state
returns the same version and ETag; changed assignment or revocation state
advances the version without changing earlier snapshots. Configurable logical
capacity rolls issuance into a deterministic suffixed list identifier.
Publication URLs come from typed configuration, never the request host.

The audit worker claims either standalone or credential-embedded outbox
records using a lease and version predicate. Temporary failure reschedules
the record with capped exponential delay. The immutable audit event ID is the
idempotency key, so a crash after destination insertion but before
acknowledgement cannot create a second event.

The issuance application service validates the unsigned VC, chooses a
deterministic free status slot, injects `credentialStatus`, signs through an
issuer abstraction, validates the secured result, and inserts one credential
document containing both the signed JSON and assignment. The unique partial
`statusListId + statusListIndex` index resolves concurrent slot races. No
separate status-entry write occurs for new issuance, so a partial credential
cannot be committed. A managed subject wallet adds `walletId` and
`ownerUserId` to the same credential document. Mongo-backed user
authentication remains opt-in.

The holder wallet service binds one owner user, holder DID, status, and opaque
key reference. Presentation creation requires an owned active wallet and
rejects cross-user, cross-wallet, or cross-holder credentials before signing.
The challenge service generates random expiring server records bound to
domain, audience, optional holder DID, and issuing verifier. An atomic
state/version/expiry predicate consumes each challenge once.

The holder presentation service loads one to eight owned credential IDs,
re-runs proof/hash/status checks, and signs through `HolderSigner`. Its
`authentication` proof covers the server challenge, normalized domain,
audience, validity window, holder, and embedded credentials. MongoDB stores
the exact document in `PENDING`; unique identifiers prevent reuse.

The verifier presentation service atomically claims `PENDING -> PROCESSING`
using the optimistic version before checking content. It validates the holder
`did:key`, VP proof, server challenge/domain/audience, expiry, persisted
document, credential set, current issuer proofs, persistence hashes, holder
binding, lifecycle state, and issuance-time status mapping. Completion is an
atomic `PROCESSING -> VERIFIED|REJECTED` update. Both results consume the nonce.
Presentation audit intents use deterministic IDs and the existing durable
standalone outbox. The claim stores `processingStartedAt`.

The reconciliation worker atomically claims stale `PROCESSING` records,
restores wallet/key/challenge evidence, and repeats verification. Complete
evidence finishes `VERIFIED` or `REJECTED`; missing evidence fails closed with
a controlled rejection. Attempts and the last reconciliation time are
persisted. The same service powers the admin-only manual endpoint and is
idempotent.

The HTTP router calls a credential application service. Dependency composition
connects the existing validator, canonicalizer, signer, key provider, DID
resolver, proof service, and injectable UTC clock. Infrastructure adapters
provide `rfc8785`, `cryptography`, the deterministic public test key, and
network-free fixtures. Domain and application code remain independent of
FastAPI.

The module has no network resolver, DID management route, registration,
refresh token, MFA, rate
limiting, external identity provider, production authentication/key store,
external conformance certification, CDN publication, or blockchain anchoring.
Issuer/holder signing, holder metadata, key provisioning, and publication are
ports suitable for future KMS/HSM or wallet adapters, but only local synthetic
adapters exist. The public credential-specific status endpoint is
not privacy
preserving, and the W3C-oriented shared publication must not be presented as
fully certified interoperability. Its boundaries are documented in
[authentication-and-rbac.md](authentication-and-rbac.md),
[mongodb-persistence.md](mongodb-persistence.md),
[credential-revocation.md](credential-revocation.md),
[bitstring-status-list.md](bitstring-status-list.md),
[issuance-lifecycle.md](issuance-lifecycle.md),
[verifiable-presentation.md](verifiable-presentation.md),
[holder-wallet-and-key-custody.md](holder-wallet-and-key-custody.md),
[credential-api.md](credential-api.md), [vc-profile.md](vc-profile.md), and
[vc-signing.md](vc-signing.md). The web UI remains static. MongoDB is
integrated at the repository foundation; Redis remains provisioned but unused
by application code. The blockchain directory
contains workspace metadata but no contract. Planned paths are documented in
[api-contracts.md](api-contracts.md), resolver controls in
[did-resolver.md](did-resolver.md), and shared contracts in
`packages/shared/schemas/v1`.
