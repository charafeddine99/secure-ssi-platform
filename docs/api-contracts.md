# Versioned API Contracts

## Contract status

`GET /health`, two Identity Service authentication operations, and six
credential operations documented below are implemented. Every other `/api/v1`
and `/internal/v1` operation remains **planned**. Authentication and RBAC use
non-persistent synthetic fixtures and do not represent a production identity
system.

The JSON Schemas referenced below live in `packages/shared/schemas/v1`.

## Cross-cutting conventions

- Media type: `application/json`.
- Public base path: `/api/v1`.
- Internal base path: `/internal/v1`.
- Date/time values: UTC RFC 3339 strings.
- Identifiers: opaque strings; clients must not infer meaning from them.
- Planned gateway mutations require `Idempotency-Key`; the local sign prototype
  does not claim idempotency because its timestamp may change.
- Credential API callers may send a bounded `X-Request-ID`; otherwise the
  Identity Service creates one and returns it in the response header and error
  body. The planned gateway correlation contract remains separate.
- Implemented credential errors use the central runtime shape below. The
  shared `api-error.schema.json` remains a draft for planned gateway contracts.
- Unknown fields are rejected for security-sensitive request bodies.
- Local authentication and authorization protect `/auth/me`, credential
  signing, and credential revocation. Production-grade identity, broader policy enforcement,
  MFA, rate limiting, and token lifecycle remain planned.

## Implemented health contract

All FastAPI services implement:

```http
GET /health
```

```json
{
  "service": "identity-service",
  "status": "healthy",
  "version": "0.1.0"
}
```

Health responses describe process availability only. They do not assert readiness of SSI, AI, blockchain, recovery, database, or external dependencies.

## Implemented Identity Service authentication API

| Method and path | Policy | Result |
| --- | --- | --- |
| `POST /api/v1/auth/token` | Public strict JSON login for enabled synthetic fixtures | `200` short-lived Bearer access token |
| `GET /api/v1/auth/me` | Valid Bearer token and `auth:self:read` | `200` current public user and permissions |

Authentication uses Argon2id and a pinned HS256 JWT profile with mandatory
issuer, subject, audience, issue, not-before, expiration, JTI, role, and
token-use claims. Details are in
[authentication-and-rbac.md](authentication-and-rbac.md).

## Implemented Identity Service credential API

| Method and path | Responsibility | Result |
| --- | --- | --- |
| `POST /api/v1/credentials/validate` | Validate the pinned local VC profile; no cryptographic verification | `200` profile result |
| `POST /api/v1/credentials/sign` | Validate and sign with the synthetic local issuer; Bearer `credentials:sign` required | `201` secured credential |
| `POST /api/v1/credentials/verify` | Run local profile, DID/key, validity, and signature checks | `200` verification result, including expected failures |
| `POST /api/v1/credentials/{credentialId}/revoke` | Permanently revoke an existing Mongo credential; Bearer `credentials:revoke` required | `200` lifecycle projection |
| `GET /api/v1/credentials/{credentialId}/status` | Read current lifecycle state and audit the lookup | `200` lifecycle projection |
| `GET /api/v1/credentials/capabilities` | Report supported operations and explicit limitations | `200` capability document |
| `POST /api/v1/wallets` | Create a wallet owned by the authenticated holder | `201` wallet metadata |
| `GET /api/v1/wallets/{walletId}` | Read an owned wallet | `200` wallet metadata |
| `GET /api/v1/wallets/{walletId}/credentials` | List credentials bound to the owned wallet | `200` minimized inventory |
| `POST /api/v1/wallets/{walletId}/keys` | Provision an owned purpose-bound managed key; requires `Idempotency-Key` | `201` public key/lifecycle metadata |
| `GET /api/v1/wallets/{walletId}/keys` | List owned managed keys with bounded cursor pagination | `200` public metadata inventory |
| `GET /api/v1/wallets/{walletId}/keys/{keyId}` | Read one owned managed key | `200` public metadata or non-enumerating `404` |
| `POST /api/v1/wallets/{walletId}/keys/{keyId}/rotate` | Claim and rotate an active owned key; requires `Idempotency-Key` | `200` active successor metadata |
| `POST /api/v1/wallets/{walletId}/keys/{keyId}/suspend` | Suspend an owned key | `200` suspended metadata |
| `POST /api/v1/wallets/{walletId}/keys/{keyId}/resume` | Resume an owned suspended key | `200` active metadata |
| `POST /api/v1/wallets/{walletId}/keys/{keyId}/compromise` | Administratively mark a key compromised with a reason | `200` compromised metadata |
| `POST /api/v1/wallets/{walletId}/keys/{keyId}/revoke` | Irreversibly revoke an owned key with a reason | `200` revoked metadata |
| `POST /api/v1/wallets/{walletId}/keys/{keyId}/schedule-destruction` | Admin reason, exact confirmation, and delayed provider deletion | `200` destruction-pending metadata |
| `POST /api/v1/wallets/{walletId}/keys/{keyId}/cancel-destruction` | Administratively cancel pending deletion | `200` revoked metadata |
| `POST /api/v1/wallets/{walletId}/keys/{keyId}/reconcile` | Administratively reconcile local/provider state | `200` current metadata |
| `POST /api/v1/presentation-challenges` | Issue a random, expiring verifier challenge | `201` challenge metadata |
| `GET /api/v1/presentation-challenges/{challengeId}` | Read challenge state as its issuer or requested holder | `200` challenge metadata |
| `POST /api/v1/presentations/create` | Build/persist a wallet-bound, server-challenge/domain/audience-bound VP; Bearer `presentations:create` | `201` VP and metadata |
| `POST /api/v1/presentations/verify` | Atomically consume and validate a persisted VP; Bearer `presentations:verify` | `200` bounded verification result |
| `GET /api/v1/presentations/{presentationId}` | Read persisted VP lifecycle; Bearer `presentations:read` | `200` VP and metadata |
| `POST /api/v1/presentations/{presentationId}/reconcile` | Admin-only deterministic recovery of a stale verification claim | `200` terminal VP metadata |

The validate, sign, and verify routes accept `{"credential": {...}}` and
reject unknown credential envelope fields; revocation instead accepts the strict
`{"reason":"..."}` body. Request safety covers size, nesting, duplicate properties,
non-finite numbers, invalid UTF-8, and malformed JSON. Full request, response,
status, and limitation details are in
[credential-api.md](credential-api.md).

## API Gateway public contracts

| Method and path | Responsibility | Request schema | Result |
| --- | --- | --- | --- |
| `POST /api/v1/credentials/issuance-requests` | Start a governed issuance request | `credential-issuance-request.schema.json` | `202` with opaque operation ID |
| `POST /api/v1/presentations/verification-requests` | Verify a presentation against a declared policy and fresh challenge | To be defined after credential-format decision | `200` verification result |
| `POST /api/v1/recovery/requests` | Start an expiring recovery workflow | `recovery-request.schema.json` | `202` with recovery request ID |
| `GET /api/v1/recovery/requests/{requestId}` | Read recovery status without exposing guardian identities | None | `200` status projection |

The gateway validates shape, size, idempotency, correlation, and caller policy before delegating. It does not hold private keys or implement credential cryptography.

## Identity Service internal contracts

| Method and path | Responsibility | Notes |
| --- | --- | --- |
| `POST /internal/v1/issuance-requests` | Validate issuer policy and prepare an issuance operation | Planned; request uses the shared issuance schema |
| `POST /internal/v1/presentations/verify` | Verify format, signature, status, challenge, audience, and expiry | Planned; must return reason codes without leaking claims |
| `POST /internal/v1/anchors` | Request anchoring of a non-identifying digest | Planned; uses `anchor-request.schema.json` |

The service must never accept or return holder private keys. The first synthetic implementation follows ADR 0001 and ADR 0002:

- resolve only allowlisted `did:web` and `did:key` identifiers;
- use `did:web` for the synthetic institutional issuer;
- allow `did:key` only for short-lived synthetic holder fixtures;
- produce VC Data Model v2.0 credentials;
- accept only `DataIntegrityProof` with `eddsa-jcs-2022` in the first verifier;
- require issuer verification methods authorized for `assertionMethod`;
- load only bundled or pinned JSON-LD contexts.

The ADR 0001 resolver profile is implemented as an internal Python interface with deterministic `did:key` expansion and registered local `did:web` fixtures. It is deliberately not exposed as an HTTP route and performs no network calls.

The ADR 0002 local profile is implemented internally. It validates the pinned
context/type sequence, identifier methods, claim allowlist, timestamps, proof
shape, size, duplicate properties, non-finite numbers, and private-key
exclusion. It also creates and verifies the local `eddsa-jcs-2022` proof using
RFC 8785, SHA-256, and Ed25519. The claim-free result uses
`credential-verification-result.schema.json`.

The local VP routes implement authenticated wallet ownership, opaque
provider key references, server-issued challenge/domain/audience binding,
holder/proof/status checks, one-time replay protection, and bounded stale
claim reconciliation. Presentation Exchange, selective disclosure, external
wallet protocols, deployed vendor KMS/HSM custody, production issuance policy, governed
issuance, and a gateway-mediated production verification contract remain
deferred. The local credential and presentation routes above are implemented;
no DID management endpoint is implemented.

## Fraud Service internal contracts

| Method and path | Responsibility | Request/response |
| --- | --- | --- |
| `POST /internal/v1/risk-assessments` | Evaluate approved, minimized signals | `risk-assessment-request.schema.json` / `risk-assessment-result.schema.json` |

Risk output is advisory. It includes a model version and reason codes. It cannot directly issue, revoke, reject, or recover an identity.

## Recovery Service internal contracts

| Method and path | Responsibility | Notes |
| --- | --- | --- |
| `POST /internal/v1/recovery-requests` | Create an expiring recovery state machine | Planned; shared recovery request schema |
| `POST /internal/v1/recovery-requests/{requestId}/approvals` | Record one authenticated guardian decision | Planned; approval schema deferred until signing method is chosen |
| `POST /internal/v1/recovery-requests/{requestId}/finalize` | Finalize only after policy, threshold, expiry, and cooling-off checks | Planned and idempotent |

Guardian identities and approvals are never returned through the public status projection.

## Blockchain boundary

Blockchain access will be isolated behind an adapter rather than called from the browser. The only currently reserved input is `anchor-request.schema.json`, which permits a digest and metadata category but no DID, credential, claim, or guardian data.

Contract methods, events, network, confirmations, and upgrade governance remain undecided.

## Error contract

The implemented credential routes return:

```json
{
  "error": {
    "code": "REQUEST_VALIDATION_FAILED",
    "message": "The request envelope is invalid.",
    "details": []
  },
  "requestId": "request-123"
}
```

Error messages must not reveal credential contents, guardian identities, model features, stack traces, secrets, or internal network details.

## Compatibility policy

- Breaking changes require a new path or schema version.
- Optional fields may be added only when consumers ignore unknown response fields.
- Security-sensitive request schemas continue to reject unknown fields.
- Schema `$id` values are stable once implemented.
- Deprecated versions require an announced migration period and usage telemetry that contains no identity data.

## Standards profile

The selected prototype profile is defined by [ADR 0001](adr/0001-did-methods-for-the-prototype.md), [ADR 0002](adr/0002-vc-data-model-and-proof-format.md), and [standards-baseline.md](standards-baseline.md). Supporting another DID method, VC version, proof suite, or canonicalization algorithm requires a new or superseding ADR and negative interoperability tests.
