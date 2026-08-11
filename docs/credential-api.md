# Credential HTTP API

## Scope

The Identity Service exposes a versioned HTTP boundary for the existing local
credential profile:

| Method | Path | Result |
| --- | --- | --- |
| `POST` | `/api/v1/credentials/validate` | Profile validation result |
| `POST` | `/api/v1/credentials/sign` | Credential with a local proof (`201`) |
| `POST` | `/api/v1/credentials/verify` | Cryptographic verification result |
| `POST` | `/api/v1/credentials/{credentialId}/revoke` | Permanent lifecycle revocation |
| `GET` | `/api/v1/credentials/{credentialId}/status` | Current persisted lifecycle status |
| `GET` | `/api/v1/credentials/capabilities` | Supported operations and limitations |
| `GET` | `/api/v1/status-lists/{statusListId}` | Signed shared revocation list |
| `GET` | `/api/v1/status-lists/{statusListId}/metadata` | Publication/cache metadata |
| `GET` | `/api/v1/status-lists/{statusListId}/history` | Immutable publication history |
| `GET` | `/api/v1/status-lists/{statusListId}/versions/{version}` | Exact historical publication |
| `POST` | `/api/v1/presentations/create` | Short-lived signed multi-credential VP (`201`) |
| `POST` | `/api/v1/presentations/verify` | One-time VP validation result |
| `GET` | `/api/v1/presentations/{presentationId}` | Persisted VP and lifecycle metadata |

These routes are a local academic prototype. Signing requires the local Bearer
authentication and RBAC foundation. Revocation additionally requires
`credentials:revoke`; only `admin` and `issuer` have it. Validation,
verification, status, and capabilities remain public. They must not be exposed
to the public internet or used with real credentials. They do not add rate
limiting, external DID resolution, externally certified status-list
interoperability, Presentation Exchange, selective disclosure, or production
identity/key management.

Interactive OpenAPI documentation is available at `/docs` while the service is
running. The API description also repeats the prototype limitations.

## Request envelope

All three `POST` operations require `application/json` and the same envelope:

```json
{
  "credential": {
    "@context": [
      "https://www.w3.org/ns/credentials/v2",
      "https://secure-ssi.example/contexts/university-affiliation/v1"
    ],
    "id": "urn:uuid:00000000-0000-4000-8000-000000000001",
    "type": [
      "VerifiableCredential",
      "UniversityAffiliationCredential"
    ],
    "issuer": "did:web:issuer.example",
    "validFrom": "2026-01-01T00:00:00Z",
    "validUntil": "2026-12-31T23:59:59Z",
    "credentialSubject": {
      "id": "did:key:z6Mkf5rGMoatrSj1f4CyvuHBeXJELe9RPdzo2PKGNCKVtZxP",
      "affiliation": "student",
      "programCode": "SYN-CS-001",
      "degree": "Bachelor of Science",
      "graduationYear": 2026
    }
  }
}
```

Unknown envelope fields are rejected. Credential claims are checked by the
existing strict profile validator. The HTTP boundary rejects requests larger
than 36,864 bytes, credentials larger than 32,768 bytes, excessive JSON
nesting, duplicate properties, non-finite numbers, invalid UTF-8, and malformed
JSON. Request bodies and proof values are not logged.

## Validation

`POST /api/v1/credentials/validate` accepts unsigned or signed credentials and
returns `200` with profile checks:

```json
{
  "valid": true,
  "checks": {
    "jsonValid": true,
    "profileValid": true,
    "contextValid": true,
    "typeValid": true,
    "issuerValid": true,
    "subjectValid": true,
    "proofValid": true
  },
  "errors": [],
  "cryptographicVerificationPerformed": false
}
```

Validation checks structure and the pinned local profile only. It does not
verify the signature and never adds a proof. Profile failures return `200`
with `valid=false` and a domain reason code; malformed envelopes and transport
errors use `4xx`.

## Signing

`POST /api/v1/credentials/sign` validates an unsigned credential, assigns a
deterministic `CredentialStatusEntry`, injects `credentialStatus`, signs
through the issuer signing port, validates the secured result, and atomically
persists it. It requires a valid Bearer token whose current local user has
`credentials:sign`; `admin` and `issuer` are allowed and `verifier` is denied.
Success returns `201`:

```json
{
  "credential": {
    "...": "...",
    "proof": {
      "@context": ["..."],
      "type": "DataIntegrityProof",
      "cryptosuite": "eddsa-jcs-2022",
      "created": "2026-06-01T00:00:00Z",
      "verificationMethod": "did:web:issuer.example#key-1",
      "proofPurpose": "assertionMethod",
      "proofValue": "z..."
    }
  }
}
```

Time is supplied by an injectable UTC clock. The client cannot provide
`created` or `credentialStatus`. Re-signing a credential with an existing
proof returns `409`; repeating an issued credential ID returns
`CREDENTIAL_ALREADY_ISSUED`. The returned signed JSON, SHA-256 digest,
status-entry ID, list ID, and index are committed in one credential document
at optimistic version `1`.

The issuer key is deterministic synthetic fixture material. The API never
serializes secret material or a signing capability. This is not production
issuer key custody; a production design requires KMS/HSM-backed operations,
authentication, authorization, audit, rotation, and incident procedures.

## Verification

`POST /api/v1/credentials/verify` runs the existing profile, local DID/key
authorization, validity-window, canonicalization, and Ed25519 verification
flow. A valid credential returns:

```json
{
  "valid": true,
  "verifiedAt": "2026-06-01T00:00:00Z",
  "checks": {
    "profileValid": true,
    "issuerResolved": true,
    "verificationMethodResolved": true,
    "cryptosuiteSupported": true,
    "proofPurposeValid": true,
    "timestampValid": true,
    "signatureValid": true,
    "contentIntegrityValid": true
  },
  "errors": []
}
```

Expected credential failures—including tampering, unknown suites, unknown
local DIDs, unauthorized methods, key substitution, and malformed signatures—
return `200`, `valid=false`, and domain reason codes. Transport or envelope
failures remain `4xx`. A successful verification proves only integrity against
the locally trusted fixture key; it does not prove claim truth, credential
status, holder control, audience binding, or non-replay.

## Revocation

`POST /api/v1/credentials/{credentialId}/revoke` requires a current enabled
`admin` or `issuer` Bearer principal and this strict JSON body:

```json
{
  "reason": "Affiliation ended"
}
```

The trimmed reason must contain 1 to 500 characters, cannot contain control
characters, and the full request is limited to 4,096 bytes. Unknown fields,
duplicate JSON properties, malformed JSON, invalid UTF-8, and non-finite
numbers are rejected before the application service runs.

The credential must already exist in MongoDB. Success atomically matches its
current optimistic version and non-revoked state, writes `REVOKED`,
`revokedAt`, `revokedBy`, `revocationReason`, its stable status-list mapping,
and an embedded durable `CREDENTIAL_REVOKED` outbox record, then increments
`version`:

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

Revocation is one-time and irreversible. A second request returns `409`
`CREDENTIAL_ALREADY_REVOKED`. The generic credential repository cannot write
`REVOKED` or transition a revoked record back to another state. `verifier`
receives `403` before the application service is invoked.

## Status lookup

`GET /api/v1/credentials/{credentialId}/status` is public in this local
prototype. It returns the same six-field response contract. Active credentials
return `ACTIVE` and null revocation metadata. A non-revoked record whose
expiration time has elapsed is atomically transitioned to `EXPIRED`.
`SUSPENDED` exists in the closed domain vocabulary, but this sprint exposes no
suspend/resume endpoint. Every successful lookup first persists a
`STATUS_CHECKED` outbox event and then attempts delivery.

The lifecycle values are exactly `ACTIVE`, `REVOKED`, `SUSPENDED`, and
`EXPIRED`. This credential-specific lookup is application status. The shared
Bitstring Status List endpoints are preferred for grouped revocation checks.
A verifier calling the exact-credential route can create correlation and
availability risks; that route must not be treated as a production privacy
design.

## Bitstring Status List publication

`GET /api/v1/status-lists/{statusListId}` is public and returns a signed
`BitstringStatusListCredential` as `application/vc+ld+json`. The document has
a minimum 131,072-entry GZIP/base64url multibase list, `revocation` purpose,
TTL, and local `eddsa-jcs-2022` Data Integrity proof. Every credential
revoked through the service has a stable reserved bit that is set in the
issuer list.

The response includes public cache headers and a strong ETag. A matching
`If-None-Match` returns `304` with no body. Repeated reads of unchanged state
return the same document, proof, version, timestamp, and ETag.

`GET /api/v1/status-lists/{statusListId}/metadata` returns issuer, purpose,
capacity, utilization, active-list state, assigned/revoked counts, version,
ETag, publication time, TTL, and cache policy without returning `encodedList`.

`GET /api/v1/status-lists/{statusListId}/history` returns append-only version
metadata. `GET /api/v1/status-lists/{statusListId}/versions/{version}` returns
the exact signed historical document with an immutable one-year cache policy.
All Status List endpoints return `404`
before any credential has been assigned to the requested deterministic list.

See [bitstring-status-list.md](bitstring-status-list.md) for encoding,
versioning, retry, security, and interoperability details.

## Verifiable Presentations

Wallet, challenge, and presentation routes require Bearer authentication.
RBAC is always followed by application-layer object authorization: a caller
cannot read another user's wallet, wallet credential inventory, or
presentation. Deliberate object-hiding failures return `404`.

The holder first creates a wallet:

```http
POST /api/v1/wallets
Content-Type: application/json

{}
```

The `201` response contains public wallet metadata, including a generated
`walletId` and holder DID. It does not expose `keyReference`, a private key,
seed, signing handle, or credential contents. The holder can read that wallet
with `GET /api/v1/wallets/{walletId}` and its minimized inventory with
`GET /api/v1/wallets/{walletId}/credentials`.

The verifier then requests server-generated evidence:

```json
{
  "domain": "verifier.example",
  "audience": "https://verifier.example/callback",
  "requestedHolderDid": "did:key:z...",
  "lifetimeSeconds": 300
}
```

`POST /api/v1/presentation-challenges` returns a cryptographically random
challenge, stable `challengeId`, normalized domain/audience, issuer, expiry,
status, and optimistic version. `GET
/api/v1/presentation-challenges/{challengeId}` is visible only to the issuing
verifier or requested holder. The evidence is persisted, expires, and is
atomically consumed once.

`POST /api/v1/presentations/create` accepts:

```json
{
  "credentialIds": [
    "urn:uuid:00000000-0000-4000-8000-000000000001"
  ],
  "walletId": "wallet_example_identifier_0001",
  "challengeId": "challenge_example_identifier_0001",
  "lifetimeSeconds": 300
}
```

The production composition requires both identifiers. It loads the challenge,
checks the requested holder, expiry, and wallet ownership, then consumes the
challenge atomically. All one-to-eight credentials must belong to that wallet
and owner and remain active. Issuer proofs, validity, persisted hashes,
holder subjects, and issuance-time status mappings are re-checked before
signing through the wallet's opaque key reference. Client challenge, domain,
or audience hints are accepted only for backward-compatible schemas and must
exactly match the server record when supplied.

`POST /api/v1/presentations/verify` accepts the exact presentation. Optional
expectation hints must match the persisted server challenge:

```json
{
  "presentation": {"id": "urn:uuid:...", "...": "..."},
  "expectedDomain": "verifier.example",
  "expectedAudience": "https://verifier.example/callback"
}
```

Only the verifier that issued the challenge can verify. The service atomically
claims `PENDING -> PROCESSING`, then checks the VP holder `authentication`
proof, server challenge/domain/audience, lifetime, original content,
credential set, current lifecycle state, issuer proofs, persistence hashes,
wallet/holder binding, and exact status mappings. Success and rejection are
terminal; a second attempt returns `409 PRESENTATION_REPLAY_DETECTED`.

`GET /api/v1/presentations/{presentationId}` returns the exact persisted VP
and its ownership, challenge, audience, reconciliation, and
`PENDING|PROCESSING|VERIFIED|REJECTED` metadata. Stale `PROCESSING` records are
claimed by a bounded background worker. An admin can invoke the same
idempotent recovery with `POST
/api/v1/presentations/{presentationId}/reconcile`; ordinary issuer, holder,
and verifier roles cannot. See
[verifiable-presentation.md](verifiable-presentation.md) for the document
profile, state machine, Mongo indexes, audit behavior, and limitations.

## Capabilities

`GET /api/v1/credentials/capabilities` returns `200` and declares the local VC
Data Model 2.0 profile, `DataIntegrityProof`, `eddsa-jcs-2022`, `did:web`
issuer fixtures, and `did:key` holder fixtures. It reports validation, signing,
verification, automatic signing persistence, revocation, and presentation as
supported. Its limitations include:

- local fixture DID resolution only;
- synthetic issuer key;
- no production issuer KMS or HSM; the holder VP path has a separate generic
  managed-key provider boundary;
- no external conformance certification;
- no JSON-LD RDF canonicalization.

The response contains no sensitive key or configuration values.

## Error contract and status codes

All controlled errors use the same shape. The request ID is also returned in
the `X-Request-ID` response header:

```json
{
  "error": {
    "code": "CREDENTIAL_ALREADY_SIGNED",
    "message": "Credential already contains a proof.",
    "details": []
  },
  "requestId": "request-123"
}
```

| Status | Meaning |
| --- | --- |
| `200` | Validation, verification, capabilities, status, revocation, wallet/challenge reads, VP verification/read/reconciliation |
| `201` | Credential issuance, wallet/challenge creation, or VP creation |
| `304` | Status List ETag is unchanged |
| `400` | Malformed JSON or semantically unusable input |
| `401` | Bearer token missing, expired, malformed, or otherwise invalid |
| `403` | Authenticated user lacks the required permission |
| `404` | The active object was absent or intentionally hidden by ownership policy |
| `409` | Credential, version, wallet, challenge, state, or replay conflict |
| `413` | Request, credential, or presentation size limit exceeded |
| `422` | Pydantic envelope validation failed |
| `500` | Sanitized unexpected server failure |
| `503` | MongoDB persistence or status-list capacity is unavailable |

Internal exception messages, exception class names, credential contents, and
stack traces are not included in responses. The lightweight request ID is for
correlation only; it is not an authentication or audit mechanism.

## Explicit limitations

Local synthetic authentication and sign RBAC are implemented as documented in
[authentication-and-rbac.md](authentication-and-rbac.md). There is no API key,
rate limiting, automatic user registration, refresh token,
MFA, production identity provider, Redis integration, external W3C
conformance validation, Presentation Exchange, selective disclosure,
external wallet protocols, external DID resolution, blockchain anchoring, or
real KMS/HSM custody. The implementation uses RFC 8785/JCS, not
JSON-LD RDF dataset canonicalization. Do not deploy these endpoints as a public
production service.
