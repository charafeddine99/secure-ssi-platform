# Recovery Service

FastAPI service implementing the Guardian-based account-recovery prototype.

It provides wallet-scoped Guardian lifecycle, generic M-of-N policies with a
3-of-5 default, encrypted request-bound Shamir authorization shares, parallel
idempotent approvals, persisted time-lock and expiry state, MongoDB repository
adapters, typed audit records, process-local metrics, and restart-safe
reconciliation. Once authorized, it calls the Identity Service's existing
`ManagedKeyService` through a short-lived request-bound service grant.

The Shamir secret authorizes one recovery workflow; it is never a KMS/private
key. Every approval and rejection requires a short-lived EdDSA JWT signed by
the registered Guardian Ed25519 `did:key` verification method. The Recovery
Service verifies the signature and binds the issuer, Guardian assignment,
audience, request, session, wallet, decision, and challenge before persisting
the proof digest. The Identity Service creates this proof with the
authenticated Guardian account's managed key. This is cryptographic
DID-bound proof, but the signing key remains server-managed: it is not an
independent Guardian-device signature or self-custody. Unsupported DID methods
fail closed; `did:web` signing is not supported. Encrypted share envelopes
remain centrally stored.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8003
```

The default host runtime uses the in-memory repository. Compose sets
`RECOVERY_MONGO_ENABLED=true` and connects to the dedicated `secure_recovery`
database. Copy `.env.example` values only for local development; production
mode requires explicitly supplied JWT, service-grant, and envelope secrets.

## Tests

```powershell
python -m pytest -q
python -m ruff check app tests
python -m pytest -q -s tests/performance/test_recovery_benchmark.py
```

See [Guardian-Based Account Recovery](../../docs/account-recovery.md) for the
architecture, API, state machine, threat analysis, traceability, performance
method, and limitations.
