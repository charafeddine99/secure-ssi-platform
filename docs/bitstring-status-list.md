# W3C Bitstring Status List and Durable Audit Delivery

## Scope

The Identity Service publishes issuer-scoped revocation lists following the
data shape and bitstring encoding defined by the W3C Bitstring Status List
v1.0 Recommendation:

- <https://www.w3.org/TR/vc-bitstring-status-list/>
- <https://www.w3.org/TR/vc-data-model-2.0/#status>
- <https://www.w3.org/TR/vc-data-integrity/>

The current lifecycle also binds status during atomic issuance and retains
immutable publication versions. It does not add presentation exchange,
selective disclosure, Redis, blockchain, frontend behavior, issuer enrollment,
or production key management.

## Status List architecture

```text
CredentialRevocationService
        |
        +--> CredentialStatusEntryRepository
        |       `credential_status_entries`
        |       unique credentialId
        |       unique (statusListId, statusListIndex)
        |
        +--> MongoRevocationRepository
                one credential update:
                REVOKED metadata + list mapping + embedded audit outbox

GET /api/v1/status-lists/{statusListId}
        |
        v
StatusListService
        |
        +--> read assigned entries and revoked credentials
        +--> generate GZIP + base64url multibase bitstring
        +--> sign DataIntegrityProof with the local issuer key
        +--> publish/version in `status_lists`

POST /api/v1/credentials/sign
        |
        v
CredentialIssuanceService
        |
        +--> deterministic list/index selection and rollover
        +--> credentialStatus injection before proof creation
        +--> one atomic `credentials` insert
```

The first deterministic list identifier is derived from the issuer DID and
`revocation` purpose; rollover lists add a six-digit sequence suffix. A
credential receives a hash-derived candidate index.
The repository reserves that index under a unique compound index and probes
forward on collision. The persisted assignment is returned on repeated calls,
so a credential never moves between indexes.

`CredentialStatusEntry.to_credential_status()` produces the fields required
for a `BitstringStatusListEntry`: `type`, `statusPurpose`,
`statusListIndex`, and `statusListCredential`. The signing endpoint injects
this object before proof creation and stores the signed JSON, entry ID, list
ID, and index together.

## Status publication

The configured default list has 131,072 entries (16 KiB before compression).
The logical assignment capacity is separately configurable; reaching it rolls
issuance to the next deterministic list without shortening the bitstring.
Index zero is the most-significant bit of the first byte. Revoked entries are
set to one; all other entries are zero. The bytes are deterministically
GZIP-compressed, base64url encoded without padding, and prefixed with the
multibase `u` identifier.

The published credential contains:

- VC Data Model 2.0 context;
- `VerifiableCredential` and `BitstringStatusListCredential` types;
- the issuer DID and `validFrom`;
- a `BitstringStatusList` credential subject;
- `statusPurpose: revocation`, `encodedList`, and TTL in milliseconds;
- a local `eddsa-jcs-2022` Data Integrity proof.

The public URL comes only from
`IDENTITY_STATUS_LIST_PUBLIC_BASE_URL`; an untrusted request `Host` header is
never used to construct credential identifiers.

## Versioning and caching

`status_lists` stores current publication state, an optimistic `version`, and
an append-only array of complete historical snapshots. A fingerprint covers
the encoded list and the number of assigned entries. Repeated publication
with unchanged state returns the same document, version, proof, ETag, and
timestamp. Material changes append the next version without rewriting prior
snapshots.

The document response includes:

- `ETag: "<fingerprint>-v<version>"`;
- `Cache-Control: public, max-age=<ttl>, must-revalidate`;
- `Vary: Accept-Encoding`;
- `304 Not Modified` when `If-None-Match` matches.

`GET /api/v1/status-lists/{statusListId}/metadata` exposes version, ETag,
issuer, purpose, configured capacity, utilization, active-list state,
assigned count, revoked count, TTL, and publication timestamp without
returning the compressed list.

`GET /api/v1/status-lists/{statusListId}/history` returns immutable version
metadata. `GET /api/v1/status-lists/{statusListId}/versions/{version}` returns
the exact historical signed document with immutable caching.

## Durable audit pipeline

```text
business commit
     |
     +-- revocation: outbox embedded in credential document
     |               (same atomic Mongo update)
     |
     +-- status check: record in `audit_outbox`
                    |
                    v
          background delivery worker
                    |
            lease / publish / ack
                    |
                    v
              `audit_events`
```

Revocation uses a deterministic `CREDENTIAL_REVOKED` event ID. The event is
embedded as `auditOutbox` in the credential document and committed in the
same single-document update as terminal revocation metadata and the status
list assignment. A successful revocation therefore cannot exist without its
durable audit delivery intent.

Other audit events, including `STATUS_CHECKED`, are first inserted into the
standalone `audit_outbox` collection. The request may attempt immediate
delivery, but temporary destination failure does not discard the committed
record.

## Retry and idempotency behavior

The background worker claims ready records with an optimistic version and a
time-bounded processing lease. A crashed worker's expired lease can be
reclaimed. Failed publication returns the record to `PENDING` with a capped
exponential delay. Attempts continue indefinitely; there is no dead-letter
drop in this prototype.

Delivery is at-least-once, while the effect in `audit_events` is idempotent:

1. the worker looks up the immutable event ID;
2. an absent event is appended;
3. an existing byte-equivalent domain event is accepted;
4. the outbox is marked delivered;
5. an existing event with different evidence is treated as an integrity
   conflict.

If the process stops after inserting `audit_events` but before acknowledging
the outbox, the next attempt recognizes the existing identical event and
only completes the acknowledgement. Audit events are never intentionally
duplicated.

## MongoDB collections and indexes

| Collection | Purpose | Important indexes |
| --- | --- | --- |
| `credential_status_entries` | Stable credential-to-index assignments | unique `credentialId`; unique `statusListId + statusListIndex`; `issuerDid + statusPurpose` |
| `status_lists` | Current signed publication plus immutable history | unique `statusListId`; `issuerDid + statusPurpose`; `updatedAt` |
| `audit_outbox` | Non-revocation durable delivery intents | `status + availableAt`; `aggregateType + aggregateId` |
| `credentials` | Issuance assignment, revocation, embedded outbox | unique partial `statusListId + statusListIndex`; `statusListId + status` |
| `audit_events` | Idempotent append-only delivery target | ObjectId event ID plus existing time/type indexes |

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `IDENTITY_STATUS_LIST_PUBLIC_BASE_URL` | `http://localhost:8001/api/v1/status-lists` | Stable public publication base |
| `IDENTITY_STATUS_LIST_LENGTH` | `131072` | Published bitstring length |
| `IDENTITY_STATUS_LIST_CAPACITY` | `131072` | Assignments before rollover |
| `IDENTITY_STATUS_LIST_TTL_SECONDS` | `300` | HTTP and subject TTL |
| `IDENTITY_AUDIT_OUTBOX_ENABLED` | `true` | Start background delivery |
| `IDENTITY_AUDIT_OUTBOX_POLL_INTERVAL_MS` | `1000` | Worker poll interval |
| `IDENTITY_AUDIT_OUTBOX_BATCH_SIZE` | `100` | Maximum records per cycle |
| `IDENTITY_AUDIT_OUTBOX_BASE_RETRY_SECONDS` | `1` | Initial retry delay |
| `IDENTITY_AUDIT_OUTBOX_MAX_RETRY_SECONDS` | `300` | Retry delay cap |
| `IDENTITY_AUDIT_OUTBOX_LEASE_SECONDS` | `30` | Claim recovery window |

## Security and privacy considerations

- Status List endpoints are intentionally public and must not require a
  bearer token.
- The large shared bitstring avoids one URL request per credential, but
  verifier access patterns and issuer-scoped list URLs can still be observed
  by network and service operators.
- The hash-derived index is stable and non-sequential, but it is not a
  substitute for a cryptographically random issuance-time assignment when
  credential identifiers are predictable.
- The public base URL must be HTTPS outside local development.
- The current Ed25519 seed is public synthetic fixture material. It provides
  reproducibility, not production issuer authenticity.
- Outbox records contain bounded audit metadata only. Raw credentials,
  proofs, hashes, tokens, passwords, and authorization values remain
  prohibited.
- MongoDB durability, backup, replication, monitoring, and retention remain
  deployment responsibilities.

## Interoperability and limitations

The publication shape, encoding, purpose, entry mapping, and minimum list
size follow W3C Bitstring Status List concepts. Synthetic fixtures exercise VC
Data Model 2.0, Bitstring Status List, Data Integrity, `did:key`, and
`did:web`. Full interoperability is not claimed because this prototype has no
external conformance-suite result, production issuer trust framework, or
KMS/HSM.

Publication is generated on read rather than proactively pushed to a CDN.
History has no compaction or archival policy. Real deployments must add
availability monitoring, retention policy, CDN behavior, issuer key
lifecycle, and external interoperability testing.
