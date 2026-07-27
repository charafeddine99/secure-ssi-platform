# Verifiable Presentation Framework

## Scope

The Identity Service implements a bounded W3C Verifiable Credentials Data
Model 2.0 presentation profile. An authenticated holder uses a managed wallet
to construct a short-lived, full-disclosure Verifiable Presentation (VP) from
one to eight credentials owned by that wallet. An authenticated verifier
issues the challenge and consumes the VP exactly once.

The flow re-checks wallet and credential ownership, holder and issuer proofs,
server challenge/domain/audience binding, validity, persistence integrity, and
current lifecycle/status-list state. This academic profile does not implement
Presentation Exchange, selective disclosure, external wallets, real KMS/HSM
custody, or external interoperability certification.

## Architecture

```text
Bearer holder                   Bearer verifier
      |                               |
      v                               v
HolderWalletService        PresentationChallengeService
      |                               |
      +---- wallet/owner/key ref      +---- random challenge evidence
                    \                 /
                     v               v
                 HolderPresentationService
                 |-- object ownership
                 |-- credential proof/status checks
                 |-- HolderSigner(opaque key reference)
                 v
              Mongo presentations (PENDING)
                           |
                           v
                 VerifierPresentationService
                 |-- PENDING -> PROCESSING
                 |-- proof/challenge/audience re-check
                 |-- PROCESSING -> VERIFIED|REJECTED
                           |
                stale threshold exceeded
                           v
              PresentationReconciliationService
                 |-- optimistic recovery claim
                 |-- same deterministic validation
                 |-- bounded background worker
                           |
                           v
              durable audit outbox -> audit_events
```

Domain and application code use repository, `HolderSigner`, and
`HolderKeyMetadataProvider` ports. PyMongo/ObjectId conversion and the
deterministic development signer remain infrastructure concerns. No raw
private key crosses the application port or enters a wallet document.

## Wallet and credential ownership

Wallet creation binds generated `walletId`, holder DID, and opaque key
reference to the authenticated `ownerUserId`. Creation returns only public
metadata. Wallet reads, credential inventory, and presentation reads require
both RBAC permission and exact object ownership; foreign and absent objects
use the same `404` response.

Credential issuance resolves the subject DID against active managed wallets.
A match persists `walletId` and `ownerUserId` on the credential. Presentation
creation rejects credentials that are unbound, belong to another wallet, or
belong to another authenticated owner.

## Server challenge lifecycle

1. An authenticated verifier posts normalized `domain`, `audience`, optional
   requested holder DID, and a 30-to-3,600-second lifetime.
2. The service generates a URL-safe challenge with a cryptographically secure
   random source and persists `ISSUED` evidence.
3. Only the issuing verifier or requested holder can read that evidence.
4. Presentation creation verifies holder, wallet, expiry, domain, and
   audience, then atomically consumes `ISSUED -> CONSUMED` using the expected
   version.
5. Both successful use and controlled binding rejection retain consumption
   evidence. Replay cannot return a challenge to `ISSUED`.
6. Expired, cancelled, consumed, mismatched, or missing evidence fails closed.

Client challenge/domain/audience properties remain optional in the schema for
backward compatibility. The production dependency composition never trusts
them as authority: if present they must equal the persisted server record.

## Presentation lifecycle

1. The holder submits an owned `walletId`, server `challengeId`, one-to-eight
   unique credential IDs, and a 30-to-600-second VP lifetime.
2. The service checks wallet state and owner, consumes challenge evidence, and
   verifies every credential is wallet-bound, active, uncorrupted, signed, and
   status-consistent.
3. The builder signs through the wallet's opaque key reference. The proof
   covers challenge, normalized domain, and audience.
4. MongoDB inserts the exact VP as `PENDING`.
5. Only the verifier that issued the challenge can atomically claim
   `PENDING -> PROCESSING`.
6. Verification re-checks persisted evidence, exact document equality,
   holder proof, embedded credential proofs, hashes, ownership, lifecycle,
   and status assignments.
7. The repository atomically completes `PROCESSING -> VERIFIED|REJECTED`.
   There is no reset-to-pending path.
8. Audit intents use deterministic event IDs and the durable outbox.

## Presentation model

```json
{
  "@context": ["https://www.w3.org/ns/credentials/v2"],
  "id": "urn:uuid:00000000-0000-4000-8000-000000000001",
  "type": ["VerifiablePresentation"],
  "holder": "did:key:z...",
  "verifiableCredential": [{"...": "..."}],
  "validFrom": "2026-06-01T12:00:00Z",
  "validUntil": "2026-06-01T12:05:00Z",
  "proof": {
    "@context": ["https://www.w3.org/ns/credentials/v2"],
    "type": "DataIntegrityProof",
    "cryptosuite": "eddsa-jcs-2022",
    "created": "2026-06-01T12:00:00Z",
    "verificationMethod": "did:key:z...#z...",
    "proofPurpose": "authentication",
    "challenge": "server_generated_nonce",
    "domain": "verifier.example",
    "audience": "https://verifier.example/callback",
    "proofValue": "z..."
  }
}
```

The proof input is the SHA-256 digest of the RFC 8785/JCS proof configuration
concatenated with the digest of the unsecured presentation. Embedded
credentials retain their issuer `assertionMethod` proofs.

## Validation and replay protection

Verification returns `200`, `valid=false`, and bounded reason codes after a
known VP is successfully claimed but fails content checks. It validates:

- pinned context, type, fields, UUIDv4 ID, size, and credential count;
- lifetime, proof timestamp, and exact persisted document;
- server challenge, normalized domain, audience, and verifier ownership;
- `authentication` purpose, cryptosuite, Ed25519 signature, holder DID
  document, and authorized verification method;
- exact wallet, owner, holder DID, and credential ID binding;
- each credential's current existence, lifecycle, hash, issuer proof,
  validity, holder, and issuance-time status mapping.

MongoDB uses unique challenge indexes plus state/version predicates. A second
claim returns `409 PRESENTATION_REPLAY_DETECTED`. Unknown or unauthorized
objects return `404`.

## PROCESSING recovery

The initial claim records `processingStartedAt`. The background service polls
in bounded batches for records older than the configured stale threshold.
Recovery atomically matches presentation ID, `PROCESSING` state, stale
timestamp, and optimistic version, then increments
`reconciliationAttempts` and records `lastReconciledAt`.

The worker re-validates only persisted wallet, key metadata, challenge, VP,
credential, and status evidence. Missing, inconsistent, or expired evidence
completes as controlled `REJECTED`; valid evidence completes as `VERIFIED`.
Repeated manual or automatic recovery of a terminal record is idempotent. The
manual endpoint is restricted explicitly to the `admin` role.

## MongoDB persistence

The `presentations` collection stores identity, wallet/owner/challenge
references, holder DID, domain/audience, ordered credential IDs, exact VP
document, lifecycle timestamps, processing/reconciliation metadata, bounded
rejection codes, and optimistic version.

Indexes enforce unique presentation ID and challenge/domain and support
holder history, lifecycle, expiry, wallet/owner access, and stale-processing
scans. `holder_wallets` and `presentation_challenges` collection/index details
are documented in [mongodb-persistence.md](mongodb-persistence.md).

## Authentication and authorization

- `holder`: wallet create/read/inventory, challenge read, presentation
  create/read;
- `verifier`: challenge create/read, presentation verify/read;
- `admin`: operational permissions and manual reconciliation;
- `issuer`: credential operations but no manual reconciliation authority.

Role permission does not override wallet, challenge, credential, or
presentation object ownership.

## Audit and metrics

Existing presentation created/verified/rejected events are retained. The
sprint adds wallet creation/state events, challenge issue/consume/reject
events, holder ownership rejection, and reconciliation success/failure.
Sensitive values such as raw keys, credentials, proofs, challenge values, and
hashes are excluded from audit metadata.

Process-local metrics record wallet and challenge activity, ownership
rejection, stale observations, and reconciliation success/failure. They reset
on restart and are not exposed through a public endpoint.

## Security considerations and limitations

- The VP fully discloses embedded credentials and remains correlatable.
- The deterministic development signer is intentionally not production key
  custody; no real KMS/HSM, key rotation, secure enclave, or mobile/external
  wallet integration is included.
- `did:key` and local `did:web` resolution remain bounded test fixtures.
- Standalone outbox insertion and presentation state mutation are separate
  MongoDB writes, leaving a crash gap that production transaction design or
  stronger reconciliation must address.
- Polling recovery relies on Mongo optimistic predicates; there is no
  distributed scheduler or operational metrics exporter.
- Consumed challenges and presentations have no retention/archival worker.
- No Presentation Exchange, selective disclosure, BBS, SD-JWT,
  zero-knowledge proofs, Redis, blockchain, AI, recovery, OAuth/OIDC, rate
  limiting, refresh tokens, or frontend is implemented.
- JCS is the selected local profile; external W3C conformance is not claimed.
