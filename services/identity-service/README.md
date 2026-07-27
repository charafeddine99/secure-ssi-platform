# Identity Service

FastAPI service exposing `GET /health` and a bounded local credential API:

- `POST /api/v1/auth/token` (public)
- `GET /api/v1/auth/me` (Bearer)
- `POST /api/v1/credentials/validate`
- `POST /api/v1/credentials/sign` (`admin`/`issuer`)
- `POST /api/v1/credentials/verify`
- `POST /api/v1/credentials/{credentialId}/revoke` (`admin`/`issuer`)
- `GET /api/v1/credentials/{credentialId}/status`
- `GET /api/v1/credentials/capabilities`
- `GET /api/v1/status-lists/{statusListId}`
- `GET /api/v1/status-lists/{statusListId}/metadata`
- `GET /api/v1/status-lists/{statusListId}/history`
- `GET /api/v1/status-lists/{statusListId}/versions/{version}`
- `POST /api/v1/wallets` (`wallets:create`)
- `GET /api/v1/wallets/{walletId}` (`wallets:read`)
- `GET /api/v1/wallets/{walletId}/credentials`
- `POST /api/v1/presentation-challenges` (`presentation-challenges:create`)
- `GET /api/v1/presentation-challenges/{challengeId}`
- `POST /api/v1/presentations/create` (`presentations:create`)
- `POST /api/v1/presentations/verify` (`presentations:verify`)
- `GET /api/v1/presentations/{presentationId}` (`presentations:read`)
- `POST /api/v1/presentations/{presentationId}/reconcile` (`admin`)

Implemented internally:

- explicit DID resolution result and error types;
- allowlisted `did:key` and `did:web` resolver dispatch;
- deterministic Ed25519 `did:key` expansion;
- network-free local `did:web` fixture resolution;
- DID document validation and security rejection tests;
- a strict synthetic VC Data Model 2.0 profile validator;
- versioned credential, proof, and verification-result contracts;
- RFC 8785/JCS canonicalization with SHA-256 proof/document hashing;
- local Ed25519 signing and library-backed verification;
- an opaque, deterministic, test-only issuer signing capability;
- unsigned, signed, and 15 tampered credential fixture variants;
- explicit verification checks and machine-readable reason codes.
- strict request envelopes, request/credential size limits, JSON depth limits,
  duplicate-property rejection, non-finite-number rejection, and UTF-8 checks;
- centralized sanitized API errors and lightweight request IDs;
- OpenAPI request, response, limitation, and error documentation.
- Argon2id verification against immutable synthetic user fixtures;
- 15-minute HS256 JWT access tokens with required claim validation;
- Bearer authentication and closed enum-based roles/permissions;
- current-user provider re-resolution and sign permission enforcement.
- typed MongoDB configuration and one lifecycle-managed PyMongo connection
  pool;
- user, credential, and append-only audit event repository ports and adapters;
- BSON/ObjectId mappers, idempotent indexes, optimistic versions, and user/
  credential soft deletion;
- an opt-in Mongo-backed authentication provider.
- a closed credential lifecycle model with `ACTIVE`, `REVOKED`, `SUSPENDED`,
  and `EXPIRED`;
- an atomic optimistic-lock revocation repository and application policy;
- permanent `revokedAt`, `revokedBy`, and `revocationReason` metadata;
- append-only `CREDENTIAL_REVOKED` and `STATUS_CHECKED` audit events;
- strict revocation/status OpenAPI contracts and RBAC enforcement.
- issuance-time status assignment, proof creation, and atomic credential
  persistence;
- W3C-oriented Bitstring Status List generation, rollover, caching, immutable
  history, and historical retrieval;
- durable standalone/embedded audit outbox delivery with leases, retry, and
  idempotent publication;
- a strict W3C VC Data Model 2.0 Verifiable Presentation profile;
- one-to-eight credential holder presentations with short-lived
  server challenge/domain/audience-bound `authentication` proofs;
- current credential proof/hash/status/holder re-validation and atomic
  one-time presentation nonce consumption;
- Mongo presentation mapping, indexes, lifecycle states, RBAC, and
  `PRESENTATION_CREATED|VERIFIED|REJECTED` audit events;
- authenticated holder wallets with persisted owner, holder DID, opaque key
  reference, lifecycle status, optimistic version, and object authorization;
- wallet-bound credential inventory and issuance-time owner binding;
- cryptographically random, server-issued presentation challenges with
  domain, audience, requested-holder, expiry, one-time atomic consumption,
  and retained replay evidence;
- `HolderSigner` and holder-key metadata ports with a deterministic
  development adapter that never persists raw private keys;
- stale `PROCESSING` detection, optimistic reconciliation claims, bounded
  background recovery, admin-only manual recovery, audit, and metrics.

The credential API is a local academic prototype. Validation checks the pinned
profile but does not verify a signature; verification runs the cryptographic
flow. Signing uses only the deterministic synthetic issuer, assigns
`credentialStatus`, and returns `201` after atomically persisting the signed
credential and status assignment. Presentation creation requires a wallet
owned by the authenticated holder and a verifier-issued server challenge.
The development signer resolves the wallet's opaque key reference internally;
the wallet document and API never expose raw private key material.

The service performs no network resolution. Authentication and authorization
remain local foundations, not production identity controls. MongoDB user
storage can be selected explicitly, while synthetic fixtures remain the
development default. It does not implement registration, refresh tokens,
logout/blacklist, MFA, rate limiting, external identity providers, production
issuer governance, KMS/HSM integration, selective disclosure, Presentation
Exchange, external wallet protocols, or blockchain anchoring. The implemented
credential-specific status lookup and full-disclosure VP profile are not a
production privacy design. Do not expose them
as a public production service.

The validate, sign, and verify `POST` operations accept:

```json
{
  "credential": {
    "...": "..."
  }
}
```

Expected validation and verification failures return structured reason codes.
Transport/envelope failures return the centralized shape
`{"error":{"code":"...","message":"...","details":[]},"requestId":"..."}`.
See [../../docs/credential-api.md](../../docs/credential-api.md) for complete
examples and status codes.

## Cryptographic dependencies

- `cryptography==49.0.0` provides Ed25519 signing and library-backed
  verification under Apache-2.0 OR BSD-3-Clause. Project code does not
  implement Ed25519.
- `rfc8785==0.1.4` provides UTF-8 RFC 8785 canonical bytes. It is a small
  Apache-2.0, Beta-status package with no runtime dependency.
- `argon2-cffi==25.1.0` provides Argon2id hashing and verification under MIT.
- `PyJWT==2.13.0` provides the pinned HS256 JWT implementation under MIT.
- `pymongo==4.17.0` is the official MongoDB Python driver used for connection
  pooling, BSON/ObjectId conversion, indexes, and repository operations.

The `rfc8785` maintenance and maturity profile is a known risk. Re-review its
license, activity, conformance coverage, and pinned version before production
or external interoperability work.

```powershell
python -m pytest -q
```

Run locally from this directory:

```powershell
python -m uvicorn app.main:app --reload --port 8001
```

See [../../docs/did-resolver.md](../../docs/did-resolver.md),
[../../docs/authentication-and-rbac.md](../../docs/authentication-and-rbac.md),
[../../docs/mongodb-persistence.md](../../docs/mongodb-persistence.md),
[../../docs/credential-revocation.md](../../docs/credential-revocation.md),
[../../docs/bitstring-status-list.md](../../docs/bitstring-status-list.md),
[../../docs/issuance-lifecycle.md](../../docs/issuance-lifecycle.md),
[../../docs/verifiable-presentation.md](../../docs/verifiable-presentation.md),
[../../docs/holder-wallet-and-key-custody.md](../../docs/holder-wallet-and-key-custody.md),
[../../docs/vc-profile.md](../../docs/vc-profile.md),
[../../docs/vc-signing.md](../../docs/vc-signing.md), and the
[architecture decisions](../../docs/adr/README.md).
