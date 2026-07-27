# Issuance Lifecycle

## Scope

The Identity Service completes local credential issuance by binding a W3C
Bitstring Status List entry before proof creation and atomically storing the
secured credential. This is a synthetic academic implementation. It does not
provide production issuer governance, KMS/HSM custody, external conformance
certification, selective disclosure, Redis, blockchain, frontend behavior,
AI, or recovery. When the subject DID belongs to an active managed holder
wallet, issuance also persists the wallet and authenticated owner binding.

## Issuance workflow

```text
POST /api/v1/credentials/sign
        |
        v
Bearer authentication + credentials:sign
        |
        v
CredentialIssuanceService
        |
        +-- validate unsigned VC Data Model 2.0 profile
        +-- reject client proof and client credentialStatus
        +-- select deterministic active list and free index
        +-- build CredentialStatusEntry
        +-- inject credentialStatus
        +-- sign through IssuerCredentialSigningService
        +-- validate secured credential
        +-- hash canonical secured JSON
        +-- resolve an active managed wallet for the subject DID
        |
        v
MongoCredentialIssuanceRepository
        |
        +-- one `credentials` insert:
            signed JSON + status mapping + optional walletId/ownerUserId
```

A successful response is therefore already persisted. A credential with an
existing proof is rejected. A repeated credential ID is rejected with
`CREDENTIAL_ALREADY_ISSUED`.

## Automatic persistence and consistency

New issuance does not insert a separate `credential_status_entries` document.
The immutable entry ID and list mapping are embedded in the credential
document. The signed JSON contains the matching public `credentialStatus`
object. These values are validated against one another immediately before the
insert.

MongoDB single-document insertion is the transaction boundary. If validation,
status selection, proof creation, canonicalization, or insertion fails, no new
credential document exists. The initial optimistic `version` is `1`.

Wallet ownership is derived from the server-side wallet repository, never
from credential JSON supplied by the client. If no active local wallet owns
the subject DID, issuance remains valid but the record is not exposed through
any holder wallet inventory. A managed credential can therefore be listed
only by the authenticated owner captured at issuance.

The partial unique index on `(statusListId, statusListIndex)` prevents two new
credentials from committing the same slot. A concurrent conflict causes the
service to probe the next deterministic slot and sign again because the status
object is part of the proof.

Legacy status assignments remain readable from
`credential_status_entries`. Repository reads merge legacy and embedded
entries. The legacy revocation path checks embedded issuance slots before
reserving a separate entry.

## credentialStatus binding

The injected object has exactly:

```json
{
  "id": "urn:uuid:<deterministic-entry-urn>",
  "type": "BitstringStatusListEntry",
  "statusPurpose": "revocation",
  "statusListIndex": "<decimal-index>",
  "statusListCredential": "https://issuer.example/api/v1/status-lists/<id>"
}
```

The entry URN is deterministic from the credential ID. The list ID is
deterministic from issuer DID, purpose, and rollover sequence. The initial
candidate index is a SHA-256-derived value modulo logical capacity; bounded
linear probing resolves collisions.

Because injection happens before Data Integrity signing, changing any status
field invalidates the credential proof.

## Status List lifecycle

`IDENTITY_STATUS_LIST_LENGTH` controls the published bitstring length and
cannot be below the W3C minimum of 131,072 entries.
`IDENTITY_STATUS_LIST_CAPACITY` controls how many assignments are accepted
before rollover and may be smaller for controlled deployments or tests.

The first list ID remains:

```text
revocation-<24 lowercase hex characters>
```

Later lists use:

```text
revocation-<24 lowercase hex characters>-000002
```

The highest assigned sequence is the active list. Full lists remain
publishable and readable. Rollover does not move existing credentials.

## Publication history

`status_lists` stores the current publication and an append-only array of
complete snapshots. A material assignment or revocation change advances the
optimistic version and appends one snapshot. An unchanged read reuses the
same version, proof, timestamp, and ETag.

Public lifecycle routes are:

- `GET /api/v1/status-lists/{statusListId}`
- `GET /api/v1/status-lists/{statusListId}/metadata`
- `GET /api/v1/status-lists/{statusListId}/history`
- `GET /api/v1/status-lists/{statusListId}/versions/{version}`

Historical version responses use an immutable one-year cache policy.
Metadata reports logical capacity, utilization, and whether the list is
currently active.

## Issuer abstractions

Business logic depends on:

- `IssuerCredentialSigningService` for credential proof creation;
- `IssuerStatusListPublisher` for signed status publication;
- `KeyProvider` for issuer and verification-key access.

The current adapters retain the deterministic synthetic Ed25519 key and local
publication generator. A future Cloud KMS, HSM, or hardware-token adapter can
implement these ports without changing issuance selection, validation,
persistence, rollover, or history rules. No real KMS/HSM integration is
included.

## Interoperability

Fixtures and tests cover:

- W3C Verifiable Credentials Data Model 2.0 context and credential shape;
- `BitstringStatusListEntry` and `BitstringStatusListCredential`;
- `DataIntegrityProof` with local `eddsa-jcs-2022`;
- synthetic `did:web` issuer resolution;
- synthetic `did:key` holder resolution;
- minimum-length GZIP/base64url multibase bitstring decoding;
- signature validation for both issued credential and status publication.

These tests demonstrate compatibility with the bounded local profile, not an
external W3C conformance certification.

## Internal monitoring

Process-local, non-HTTP metrics track:

- successful and failed issuance;
- rollover count;
- publication count and last publication timestamp;
- per-list utilization;
- audit worker cycles, delivered/retried records, and outbox lag;
- last issuance and worker timestamps.

No dashboard, metrics endpoint, or external telemetry backend is added.

## Security considerations

- The client cannot select its status list or index.
- The status object is covered by the credential proof.
- Duplicate credential IDs and duplicate list slots are unique-index
  violations mapped to controlled domain behavior.
- Status publication URLs come only from typed configuration.
- Raw credentials, proof values, keys, hashes, and tokens are prohibited from
  audit metadata.
- The client cannot submit or override `walletId` or `ownerUserId`.
- Wallet inventory reads require both RBAC and exact object ownership.
- The synthetic private seed is public test material and unsuitable for any
  real issuer.

## Known limitations

- Only the `revocation` status purpose is assigned.
- Publication is generated on read rather than proactively pushed to a CDN.
- Embedded history has no compaction, archive, or retention worker.
- Process-local metrics reset on restart and are not exported.
- Legacy separate-entry concurrency cannot gain the same cross-collection
  uniqueness guarantee as the new single-document issuance path.
- There is no production key lifecycle, workload identity, rate limiting,
  external DID resolution, or external interoperability certification.
