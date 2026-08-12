# Secure Self-Sovereign Identity Platform

## Project overview

This university capstone repository is the runnable foundation for **Secure Self-Sovereign Identity with AI-Based Fraud Detection and Emergency Recovery on Blockchain**. The current milestone provides service boundaries, health endpoints, a local Identity Service credential and Verifiable Presentation HTTP API, synthetic authentication and RBAC, atomic MongoDB-backed credential issuance, lifecycle status and irreversible revocation, W3C-oriented Bitstring Status List rollover and immutable publication history, wallet-bound holder identity, server-issued challenge/domain/audience-bound presentations, stale-verification reconciliation, durable audit delivery, provider-neutral managed holder keys, controlled rotation and lifecycle reconciliation, and a Guardian-based M-of-N account-recovery state machine with encrypted Shamir authorization shares and time-locked managed-key rotation.

## Planned architecture

`User / Web Client → API Gateway → Identity Service → Fraud Detection Service → Blockchain → Recovery Service`

See [docs/architecture.md](docs/architecture.md), [docs/threat-model.md](docs/threat-model.md), [docs/api-contracts.md](docs/api-contracts.md), [local authentication and RBAC](docs/authentication-and-rbac.md), the [MongoDB persistence foundation](docs/mongodb-persistence.md), [credential revocation and status](docs/credential-revocation.md), [Bitstring Status List and durable audit delivery](docs/bitstring-status-list.md), the [issuance lifecycle](docs/issuance-lifecycle.md), the [Verifiable Presentation framework](docs/verifiable-presentation.md), [holder wallet and key custody](docs/holder-wallet-and-key-custody.md), the [external KMS and key lifecycle architecture](docs/external-kms-key-lifecycle.md), [Guardian-based account recovery](docs/account-recovery.md), the [credential HTTP API](docs/credential-api.md), the [DID resolver milestone](docs/did-resolver.md), the [synthetic VC profile](docs/vc-profile.md), [local VC signing](docs/vc-signing.md), the [Architecture Decision Records](docs/adr/README.md), and the permanent [contribution workflow](CONTRIBUTING.md).

## Service list

| Component | Purpose | Local address |
| --- | --- | --- |
| Web | React status UI | http://localhost:3000 |
| API Gateway | Planned public entry point | http://localhost:8000 |
| Identity Service | Local VC issuance/status, holder-wallet, secure-challenge, and VP creation/verification prototype | http://localhost:8001 |
| Fraud Service | Planned AI risk analysis | http://localhost:8002 |
| Recovery Service | Guardian policy, M-of-N approvals, time lock, reconciliation, and managed-key recovery orchestration | http://localhost:8003 |
| MongoDB | User, wallet, managed-key, challenge, credential, presentation, status-list, recovery, outbox, and audit persistence | localhost:27017 |
| Redis | Planned cache/state | localhost:6379 |

## Folder structure

```text
apps/web/
services/{api-gateway,identity-service,fraud-service,recovery-service}/
blockchain/
infrastructure/
packages/shared/             Versioned JSON Schemas and contract tests
docs/
scripts/
```

## Prerequisites

- Docker Desktop with Docker Compose
- For host development: Node.js 20+, npm 10+, Python 3.11+
- Optional: GNU Make

## Local development

Web:

```powershell
cd apps/web
npm install
npm run dev
```

One API service (change the directory and port for other services):

```powershell
cd services/api-gateway
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

## Docker startup instructions

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Make targets: `make up`, `make down`, `make logs`, `make test`, `make lint`.

Windows equivalents:

```powershell
docker compose up --build
docker compose down
docker compose logs -f
docker compose run --rm api-gateway pytest
docker compose run --rm identity-service pytest
docker compose run --rm fraud-service pytest
docker compose run --rm recovery-service pytest
python -m unittest discover packages/shared/tests -v
python -m unittest discover tests -v
docker compose build web
```

## Health endpoint list

- `GET http://localhost:8000/health`
- `GET http://localhost:8001/health`
- `GET http://localhost:8002/health`
- `GET http://localhost:8003/health`

## Identity credential endpoints

- `POST http://localhost:8001/api/v1/auth/token` (public synthetic login)
- `GET http://localhost:8001/api/v1/auth/me` (Bearer token required)
- `POST http://localhost:8001/api/v1/credentials/validate`
- `POST http://localhost:8001/api/v1/credentials/sign` (`admin`/`issuer` only)
- `POST http://localhost:8001/api/v1/credentials/verify`
- `POST http://localhost:8001/api/v1/credentials/{credentialId}/revoke` (`admin`/`issuer` only)
- `GET http://localhost:8001/api/v1/credentials/{credentialId}/status`
- `GET http://localhost:8001/api/v1/credentials/capabilities`
- `GET http://localhost:8001/api/v1/status-lists/{statusListId}`
- `GET http://localhost:8001/api/v1/status-lists/{statusListId}/metadata`
- `GET http://localhost:8001/api/v1/status-lists/{statusListId}/history`
- `GET http://localhost:8001/api/v1/status-lists/{statusListId}/versions/{version}`
- `POST http://localhost:8001/api/v1/wallets` (`holder` permission required)
- `GET http://localhost:8001/api/v1/wallets/{walletId}` (owner only)
- `GET http://localhost:8001/api/v1/wallets/{walletId}/credentials` (owner only)
- `POST http://localhost:8001/api/v1/wallets/{walletId}/keys` (owner; `Idempotency-Key`)
- `GET http://localhost:8001/api/v1/wallets/{walletId}/keys` (owner; cursor pagination)
- `GET http://localhost:8001/api/v1/wallets/{walletId}/keys/{keyId}` (owner)
- `POST http://localhost:8001/api/v1/wallets/{walletId}/keys/{keyId}/rotate` (owner; `Idempotency-Key`)
- `POST http://localhost:8001/api/v1/wallets/{walletId}/keys/{keyId}/suspend` (owner)
- `POST http://localhost:8001/api/v1/wallets/{walletId}/keys/{keyId}/resume` (owner)
- `POST http://localhost:8001/api/v1/wallets/{walletId}/keys/{keyId}/compromise` (admin)
- `POST http://localhost:8001/api/v1/wallets/{walletId}/keys/{keyId}/revoke` (owner)
- `POST http://localhost:8001/api/v1/wallets/{walletId}/keys/{keyId}/schedule-destruction` (admin)
- `POST http://localhost:8001/api/v1/wallets/{walletId}/keys/{keyId}/cancel-destruction` (admin)
- `POST http://localhost:8001/api/v1/wallets/{walletId}/keys/{keyId}/reconcile` (admin)
- `POST http://localhost:8001/api/v1/presentation-challenges` (`verifier` permission required)
- `GET http://localhost:8001/api/v1/presentation-challenges/{challengeId}` (object-authorized)
- `POST http://localhost:8001/api/v1/presentations/create` (`holder` permission required)
- `POST http://localhost:8001/api/v1/presentations/verify` (`verifier` permission required)
- `GET http://localhost:8001/api/v1/presentations/{presentationId}` (Bearer permission required)
- `POST http://localhost:8001/api/v1/presentations/{presentationId}/reconcile` (`admin` only)

Successful signing injects an issuer-owned `credentialStatus` entry before
creating the proof and atomically persists the signed credential and status
assignment in one MongoDB document. Duplicate credential IDs are rejected.
Validation, verification, capabilities, and login remain public; current-user
and signing/revocation operations use local Bearer authentication. The
credential-specific public status route remains a local verifier convenience.
The public Bitstring Status List routes provide versioned, cacheable,
issuer-scoped revocation publication; see the documented interoperability and
privacy limitations. These routes must not be exposed as a public production
service without the production gates in `docs/security.md`. Presentation
creation now requires an owned active wallet, wallet-bound credentials, and
an atomically consumed server challenge. Proofs bind challenge, domain,
audience, holder, credentials, and expiry. A lifecycle worker and admin-only
endpoint idempotently reconcile stale `PROCESSING` records.

New holder wallets receive a managed `PRESENTATION_SIGNING` key. The holder VP
signer resolves active MongoDB metadata and routes the canonical payload to
the configured provider without exporting private key material. The local
development provider is explicitly non-production. A generic HTTPS KMS
gateway adapter, lifecycle states, rotation, compromise/revocation, delayed
destruction, optimistic concurrency, durable audit, metrics, and bounded
reconciliation are implemented. No real vendor KMS/HSM has been deployed or
tested; see
[docs/external-kms-key-lifecycle.md](docs/external-kms-key-lifecycle.md).

## Guardian recovery endpoints

All Recovery Service application routes require the existing Identity Service
Bearer token. Wallet owners manage policies, Guardian assignments, requests,
and cancellation; assigned Guardians approve or reject only their own
assignment; administrators may reconcile a due/stale request.

- `POST/GET http://localhost:8003/api/v1/guardians`
- `GET/PATCH/DELETE http://localhost:8003/api/v1/guardians/{guardianId}`
- `GET/PUT http://localhost:8003/api/v1/recovery/policy`
- `POST/GET http://localhost:8003/api/v1/recovery/requests`
- `GET http://localhost:8003/api/v1/recovery/requests/{requestId}`
- `POST http://localhost:8003/api/v1/recovery/requests/{requestId}/approve`
- `POST http://localhost:8003/api/v1/recovery/requests/{requestId}/reject`
- `POST http://localhost:8003/api/v1/recovery/requests/{requestId}/cancel`
- `POST http://localhost:8003/api/v1/recovery/requests/{requestId}/reconcile` (`admin`)

The generic policy supports M-of-N and defaults to 3-of-5. Shamir splits a
dedicated 128-bit recovery authorization secret, never a KMS private key.
Shares are stored as request-bound AES-GCM envelopes. Quorum persists before
the time lock begins, and the background worker invokes only the existing
`ManagedKeyService` recovery/rotation path through a short-lived internal
service grant. See [docs/account-recovery.md](docs/account-recovery.md).

## Current implementation status

Implemented: monorepo layout, static web status page, API health endpoints, container definitions, threat model and trust boundaries, versioned API contracts, a tested v1 JSON Schema catalog, accepted prototype DID/VC architecture decisions, a network-free DID resolver, a local VC/VP proof core using RFC 8785/JCS, SHA-256 and Ed25519, atomic issuance persistence with status binding, versioned credential/status-list HTTP endpoints, immutable publication history and rollover, authenticated wallet-bound multi-credential VP creation/verification with server challenge replay protection, object-level ownership, stale-processing reconciliation, Argon2id synthetic-user authentication, short-lived JWT access tokens, local RBAC, MongoDB wallet/challenge/credential/presentation/managed-key and recovery lifecycle states, provider-aware holder VP signing, controlled key rotation/destruction/reconciliation, irreversible credential revocation, durable idempotent audit delivery, generic Guardian M-of-N recovery, encrypted Shamir authorization shares, time-lock enforcement, recovery audit records, metrics, and restart-safe recovery reconciliation.

The VC proof core is a local academic prototype. The issuer seed is
deterministic public test material; there is no production key protection,
issuer governance, externally validated status-list/VP interoperability, external DID
resolution, production identity provider, MFA, rate limiting, token
revocation, refresh-token rotation, deployed vendor KMS/HSM custody, external wallet
integration, or production-grade issuer operations.

Planned: production issuer trust, reviewed vendor KMS/HSM deployment and attestation, DID lifecycle
operations, network resolution, external status-list/VP conformance,
external/mobile wallet integration, selective disclosure, AI fraud detection, blockchain
contracts, cryptographically signed Guardian decisions, independently delivered shares,
and production recovery operations. API paths other than health and the implemented Identity and Recovery Service routes
listed above remain documentation-only and unimplemented.
See [docs/implementation-status.md](docs/implementation-status.md).

## Roadmap

1. [Completed] Define the initial threat model, trust boundaries, and planned API contracts.
2. [Completed] Add the initial shared, versioned schema catalog and structural tests.
3. [Completed] Select the prototype DID methods and credential proof format through ADRs.
4. [Completed] Build resolver validation and synthetic DID fixtures required by ADR 0001.
5. [Completed] Define versioned VC fixture and verification-result models required by ADR 0002.
6. [Completed] Prototype VC Data Model 2.0 signing and verification with synthetic data.
7. [Completed] Expose the bounded local credential core through a versioned HTTP API.
8. [Completed] Add synthetic local authentication and RBAC for credential signing.
9. [Completed] Add MongoDB connection, repository, mapping, index, concurrency, and soft-delete foundations.
10. [Completed] Add MongoDB-backed credential lifecycle status, irreversible revocation, RBAC, audit events, and status/revocation APIs.
11. [Completed] Add W3C-oriented Bitstring Status List publication, stable entry assignment, caching/versioning, and durable idempotent audit outbox delivery.
12. [Completed] Add issuance-time credential-status binding, atomic persistence, configurable rollover, immutable history, and interoperability fixtures.
13. [Completed] Add short-lived multi-credential Verifiable Presentations, holder proofs, challenge/domain binding, replay protection, Mongo persistence, RBAC, and audit events.
14. [Completed] Add holder wallets, object ownership, opaque key references, server challenges, and stale-presentation reconciliation.
15. [Completed] Add provider-neutral external KMS/HSM ports, generic HTTPS adapter, managed-key persistence, holder VP signer routing, rotation, lifecycle policy, reconciliation, audit, metrics, API, and tests.
16. [Completed] Add Guardian assignments, generic M-of-N policy with a 3-of-5 default, encrypted Shamir authorization shares, time-lock, recovery persistence, audit, reconciliation, and managed-key rotation orchestration.
17. [Next] Add explainable AI fraud detection as a separate advisory service without autonomous recovery authority.
18. Deploy and independently review one vendor-specific KMS/HSM adapter with hardware/provider attestation and operational ceremonies.
19. Design and review smart contracts before implementation.
20. Add broader security, external interoperability, and end-to-end tests.

## Security disclaimer

**This repository is currently an academic prototype and must not be used as a production identity system.**

Do not use real personal data, credentials, secrets, or funds. No production identity, fraud, blockchain, authentication, authorization, key-management, or recovery guarantees exist.

Future implementation must follow [docs/security.md](docs/security.md) and preserve the security invariants in [docs/threat-model.md](docs/threat-model.md).
