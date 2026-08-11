# Credential Revocation and Status Management

## Scope

The Identity Service implements an application-specific credential lifecycle
for credentials persisted during issuance or provisioned through repository
adapters. It provides:

- the closed `ACTIVE`, `REVOKED`, `SUSPENDED`, and `EXPIRED` domain vocabulary;
- a one-time, irreversible revocation transition;
- a public local status lookup;
- `admin`/`issuer` revocation authorization;
- permanent revocation metadata in the credential document;
- durable, idempotently delivered `CREDENTIAL_REVOKED` and `STATUS_CHECKED`
  audit events;
- stable Bitstring Status List assignment and shared revocation publication;
- optimistic concurrency and legacy BSON compatibility.

Signing now persists and status-binds the credential automatically. This
lifecycle does not add suspend/resume endpoints,
presentation exchange, blockchain, Redis behavior, rate limiting, refresh
tokens, or frontend behavior.

## Standards boundary

W3C Verifiable Credentials Data Model v2.0 defines `credentialStatus` as the
place where a credential identifies the status mechanism used to discover
whether it is suspended or revoked. The exact format and protocol come from a
specific status type:

- <https://www.w3.org/TR/vc-data-model-2.0/#status>

W3C Bitstring Status List v1.0 is a separate privacy-preserving publication
mechanism for grouped revocation and suspension state:

- <https://www.w3.org/TR/vc-bitstring-status-list/>

The current domain maps a stable assignment to
`BitstringStatusListEntry`, and the API publishes a signed
`BitstringStatusListCredential`. New issuance injects the entry before proof
creation. External conformance certification remains absent, so full
interoperability is not claimed. The credential-specific lookup can reveal
verifier interest to the service and remains a documented privacy limitation.

## Architecture

```text
POST revoke                      GET status
     |                               |
     v                               v
Bearer auth + credentials:revoke   public local lookup
     |                               |
     +------------+------------------+
                  v
      CredentialRevocationService
          | policy + UTC clock
          |
          +--> StatusListService / entry repository
          |
          +--> RevocationRepository
          |      |
          |      v
          |   credentials + embedded revocation outbox
          |
          +--> AuditOutboxDeliveryService
                 |
                 v
          audit_outbox --> audit_events
```

Domain/application code depends on repository protocols and has no PyMongo,
BSON, or FastAPI dependency. Infrastructure owns the atomic MongoDB query,
BSON mapping, and driver-error translation. FastAPI dependency composition
binds the repositories, status-list service, audit delivery pipeline, and
injectable clock.

## Lifecycle model

| Current state | Allowed result in this sprint | Notes |
| --- | --- | --- |
| `ACTIVE` | `REVOKED`, `EXPIRED` | `SUSPENDED` is domain-ready but has no endpoint |
| `SUSPENDED` | `REVOKED`, `EXPIRED` | No suspend/resume API is exposed |
| `EXPIRED` | `REVOKED` | Expiry does not prevent administrative revocation |
| `REVOKED` | None | Terminal and irreversible |

Status lookup computes expiration from `expirationDate`. If an active or
suspended credential is at or past that instant, the repository atomically
writes `EXPIRED` and increments `version`. Revocation always wins over expiry.

The old persistence-only values `stored` and `verified` are accepted while
reading existing BSON documents and normalized to `ACTIVE`. New writes use
only the uppercase lifecycle values.

## MongoDB document

The `credentials` collection retains its existing unique `credentialId` and
query indexes. Lifecycle fields are:

| BSON field | Rule |
| --- | --- |
| `status` | `ACTIVE`, `REVOKED`, `SUSPENDED`, or `EXPIRED` |
| `revokedAt` | UTC revocation time; required only for `REVOKED` |
| `revokedBy` | Current authenticated principal ID; required only for `REVOKED` |
| `revocationReason` | Trimmed 1–500 character reason; required only for `REVOKED` |
| `updatedAt` | Transition time |
| `version` | Incremented by each lifecycle mutation |
| `deletedAt` | Separate soft-delete state; normal reads require `null` |
| `statusListId` | Deterministic issuer/purpose list identifier |
| `statusListIndex` | Stable reserved revocation bit |
| `statusEntryId` | Immutable ObjectId for an issuance-time assignment |
| `auditOutbox` | Durable embedded `CREDENTIAL_REVOKED` delivery record |

The revocation update matches `credentialId`, expected `version`,
`deletedAt=null`, and a non-revoked current status in one `update_one`.
Concurrent or stale mutations return a controlled `409`. The generic
credential update repository rejects direct `REVOKED` writes and cannot
reactivate a revoked document. The transition also writes the stable
`statusListId`, `statusListIndex`, and embedded revocation outbox in the same
atomic update.

## API

### Revoke

```http
POST /api/v1/credentials/{credentialId}/revoke
Authorization: Bearer <token>
Content-Type: application/json

{"reason":"Affiliation ended"}
```

Only `admin` and `issuer` have `credentials:revoke`. `verifier` receives
`403`; an anonymous request receives `401`.

Success returns `200`:

```json
{
  "credentialId": "urn:uuid:credential-1",
  "status": "REVOKED",
  "revoked": true,
  "revocationReason": "Affiliation ended",
  "revokedAt": "2026-07-24T12:00:00Z",
  "revokedBy": "usr_local_issuer"
}
```

### Status

```http
GET /api/v1/credentials/{credentialId}/status
```

The local status route is public for prototype verifier use. It returns the
same six fields. Non-revoked records return null revocation metadata.

## Errors

| Status | Code | Meaning |
| --- | --- | --- |
| `400` | `INVALID_JSON`, `DUPLICATE_JSON_PROPERTY`, or related transport code | Unsafe JSON was rejected |
| `401` | `AUTHENTICATION_REQUIRED` or access-token code | Revocation is unauthenticated |
| `403` | `PERMISSION_DENIED` | Current principal cannot revoke |
| `404` | `CREDENTIAL_NOT_FOUND` | No active MongoDB credential exists |
| `409` | `CREDENTIAL_ALREADY_REVOKED` | Revocation was already completed |
| `409` | `PERSISTENCE_VERSION_CONFLICT` | Lifecycle state changed concurrently |
| `413` | `REQUEST_TOO_LARGE` | Revocation body exceeds 4,096 bytes |
| `422` | `REQUEST_VALIDATION_FAILED` | Reason or request shape is invalid |
| `500` | safe central error | Unexpected or mapping failure |
| `503` | `PERSISTENCE_UNAVAILABLE` | MongoDB operation failed |

Errors use the central response envelope and include the request ID without
returning repository details, credentials, hashes, proofs, tokens, or secrets.

## Audit

Successful revocation appends:

```text
eventType: CREDENTIAL_REVOKED
subjectId: <credentialId>
actorId: <authenticated principal id>
correlationId: <request id>
metadata.status: REVOKED
```

Successful status lookup appends:

```text
eventType: STATUS_CHECKED
subjectId: <credentialId>
actorId: null
correlationId: <request id>
metadata.status: <effective lifecycle status>
```

The destination repository is append-only and rejects sensitive audit
metadata keys. `CREDENTIAL_REVOKED` uses a deterministic event ObjectId
derived from the credential ID. Its delivery intent is embedded in the same
credential commit. `STATUS_CHECKED` is inserted into `audit_outbox` before
publication. Immediate delivery is best-effort; a background worker uses
leases, optimistic versions, and capped exponential retry.

Before appending, the worker checks the immutable event ID. An identical
existing event closes the crash window idempotently; conflicting evidence is
an integrity error. Publication failure preserves the pending event and does
not roll back a committed revocation. See
[bitstring-status-list.md](bitstring-status-list.md) for the complete pipeline.

## Testing

The automated suite covers:

- exact enum values and transition policy;
- bounded reason validation and immutable revocation metadata;
- service audit emission and expiry behavior;
- durable failure preservation, lease recovery, retry, and duplicate
  prevention;
- deterministic entry assignment, list encoding, publication, versioning,
  ETag, and `304`;
- atomic versioned MongoDB updates and irreversible state;
- BSON round trips plus legacy `stored`/`verified` reads;
- admin/issuer success, verifier `403`, anonymous `401`;
- first revocation success and repeated-revocation `409`;
- public status lookup, `404`, strict JSON safety, and request size;
- OpenAPI security, response models, and documented errors;
- opt-in real MongoDB revocation behavior.

Run the real MongoDB integration suite only with a disposable test database:

```powershell
$env:IDENTITY_TEST_MONGODB_URI = "mongodb://identity_app:change-me-app@localhost:27017/?authSource=secure_identity"
python -m pytest tests/integration/test_mongo_repositories.py -q
```

## Known limitations

- No suspend/resume operation exists.
- Issuance supports only the `revocation` status purpose.
- Historical publication retention has no compaction or archival policy.
- The public per-credential lookup has correlation and enumeration risk.
- The status endpoint depends on Identity Service and MongoDB availability.
- Audit delivery is asynchronous and needs production lag/retry monitoring.
- Audit events are not an independently tamper-evident compliance log.
- There is no rate limiting, production workload identity, issuer KMS/HSM
  deployment, or production issuer governance. Holder VP signing has a
  separate provider-neutral managed-key boundary.
