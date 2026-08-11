# Security Development Baseline

## Current state

The repository is an academic prototype. The Identity Service has
network-free synthetic VC validation, status-bound signing, verification,
Mongo-backed credential lifecycle status, holder wallets, server-issued
presentation challenges, object-level credential ownership, and authenticated
short-lived Verifiable Presentation creation/verification/reconciliation
exposed through local routes.
Credential signing and revocation require a short-lived Bearer token and local
`credentials:sign` or `credentials:revoke` permission. Authentication uses
synthetic fixture users only; there is still no rate limiting, MFA, user
persistence workflow, token blacklist, secure production identity
provider/key custody, externally validated Status List/VP deployment,
production issuer policy, deployed vendor KMS/HSM custody, or external wallet integration,
so the service must not be publicly exposed.

MongoDB stores users, wallet/key-reference and managed public-key metadata, challenge replay evidence,
credential lifecycle fields, permanent revocation
metadata, stable status-list assignments/publications, durable audit outbox
records, short-lived presentation state, and append-only audit events through
explicit repository interfaces.
Mongo-backed authentication is opt-in. Successful signing atomically persists
the signed credential and embedded status assignment. Soft deletion remains
separate from revocation.

## Development rules

- Use synthetic identities, credentials, guardian data, and fraud signals.
- Never commit production private keys, seed phrases, credentials, tokens,
  `.env` files, or production endpoints. Publicly known synthetic test keys
  must be labeled and isolated under test/development infrastructure.
- Treat logs and test snapshots as possible data-exfiltration paths.
- Review dependency additions and keep lockfiles.
- Validate all external data at the receiving boundary.
- Deny access by default when authentication or authorization state is unavailable.
- Keep blockchain payloads free of personal or linkable identity data.
- Add a threat-model entry and tests for every security-sensitive workflow.
- Treat Mongo connection URIs and passwords as secrets; never include them in
  object representations, logs, error responses, or test output.
- Use optimistic versions for mutable user and credential records. Do not
  implement read-then-write updates that bypass the version predicate.
- Claim presentation verification with an atomic state/version predicate.
  Success and rejection both consume the challenge; never reset a completed
  VP to `PENDING`.
- Enforce wallet and credential ownership inside application services. RBAC
  alone never authorizes access to another user's object.
- Persist only opaque holder key references. Raw private key bytes, seeds, or
  signing handles never enter MongoDB, HTTP models, audit metadata, or logs.
- Permit managed signing only when the wallet and key are active, the purpose
  is `PRESENTATION_SIGNING`, the algorithm is Ed25519, the provider is enabled,
  and current public metadata matches the persisted fingerprint/reference.
- Treat `COMPROMISED`, `REVOKED`, `DESTROYED`, and `FAILED` as irreversible
  signing blocks. Never use provider availability as a reason to bypass local
  lifecycle state.
- Require compare-and-set state/version predicates for rotation and
  reconciliation. Never create two active keys for one wallet/purpose.
- Do not log provider requests/responses, canonical signing payloads,
  Authorization headers, provider credentials, or provider key references.
- Generate challenges server-side, bind domain/audience/optional holder, and
  atomically consume them once. Retain consumed replay evidence.
- Reconcile stale `PROCESSING` records with a state/time/version predicate;
  never reset a consumed challenge or duplicate terminal audit events.
- Keep audit events append-only and reject passwords, tokens, credentials,
  proof values, secrets, authorization values, and hashes from audit metadata.
- Apply data minimization and retention review before enabling raw credential
  JSON storage.

## Planned security gates

Implemented managed-key gates:

- Production-like configuration rejects development-only default custody.
- Remote KMS configuration requires HTTPS and production TLS verification.
- Private fields are recursively rejected by the managed-key BSON mapper.
- The HTTP response model omits provider references, idempotency digests,
  compromise details, provider credentials, and private material.
- Creation and rotation persist only a one-way idempotency digest.
- Provider identity, reference, algorithm, public encoding, fingerprint, DID,
  and verification method are validated before activation/signing.
- Rotation honors `did:key` immutability by generating a successor DID.
- Holder `did:web` rotation fails closed without a controlled publication
  pipeline.
- Compromise is blocked locally before provider suspension is attempted.
- Destruction requires admin permission, reason, exact key-ID confirmation,
  delay, audit, and provider confirmation.
- A bounded optimistic reconciliation lease repairs recoverable crash windows;
  retry exhaustion enters terminal `FAILED`.
- Provider/wallet inconsistency never automatically authorizes deletion.
- Development and generic gateway adapter guarantees are tested, but no
  vendor KMS/HSM assurance is claimed.

Implemented gates for the synthetic DID resolver and local VC proof spike:

- Follow ADR 0001 and ADR 0002; do not silently broaden their method or proof-suite allowlists.
- Keep `did:web` issuer and `did:key` holder keys synthetic.
- Bundle or pin permitted JSON-LD contexts and prohibit arbitrary remote context retrieval.
- Add resolver rejection tests before issuance code.
- Reject duplicate properties, non-finite JSON numbers, malformed Unicode,
  oversized credentials, unknown claims, private-key fields, unsupported proof
  metadata, and malformed signatures.
- Use RFC 8785 canonicalization and the cryptography library's Ed25519
  verification operation.
- Match the local key provider public key to the issuer DID document and reject
  key substitution.
- Keep the deterministic issuer test seed inside the infrastructure adapter.
  It is public fixture material, not protected production key material.
- Reject oversized request bodies, excessive JSON nesting, duplicate
  properties, non-finite numbers, invalid UTF-8, and malformed JSON before
  request-model parsing.
- Reject unknown request-envelope fields and sanitize `4xx`/`5xx` errors.
- Return a bounded request ID without logging credential bodies or proof values.
- Keep all key material and signing capability fields out of HTTP models and
  OpenAPI schemas.
- Use Argon2id through a maintained library; never implement password hashing
  in project code.
- Pin JWT verification to HS256, require all bounded access-token claims, and
  validate issuer, audience, time window, token use, and signature.
- Resolve token subjects against the current provider on every request; reject
  disabled, missing, unknown-role, and stale-role principals.
- Require `credentials:sign` before invoking the credential signing service.
- Never log login bodies, passwords, Authorization headers, full JWTs, or
  authentication record hashes.
- Create unique user/credential indexes and query indexes idempotently during
  enabled startup. Only the explicitly named obsolete single-list index may
  be removed as part of the reviewed rollover migration.
- Convert ObjectId only in infrastructure mappers and reject malformed or
  incorrectly typed BSON documents.
- Exclude soft-deleted users and credentials from normal reads. Soft deletion
  is an application storage lifecycle control, not a revocation signal.
- Require `credentials:revoke` before loading or mutating revocation state;
  only `admin` and `issuer` receive it.
- Make `REVOKED` terminal. Match `credentialId`, current lifecycle state, and
  optimistic `version` in one atomic MongoDB update.
- Require bounded non-empty revocation reasons and record `revokedAt`,
  `revokedBy`, and `revocationReason`; never return a revoked credential to
  `ACTIVE`, `SUSPENDED`, or `EXPIRED`.
- Persist `CREDENTIAL_REVOKED` and `STATUS_CHECKED` delivery intent before
  attempting central audit publication, without raw credential JSON, hashes,
  proof values, or tokens.
- Commit the deterministic revocation event as an embedded outbox record in
  the same single-document update as terminal revocation metadata.
- Use bounded delivery leases, optimistic outbox versions, and capped
  exponential retry. Never delete a committed event because publication
  temporarily fails.
- Treat the immutable audit event ID as the idempotency key and reject an
  existing ID whose evidence differs.
- Derive status-list URLs only from typed configuration, never request host
  input; require HTTPS outside local development.
- Reserve each credential status index under unique Mongo indexes. Never
  reassign an existing credential to a different bit.
- Encode index zero as the most-significant bit, publish at least 131,072
  entries, and sign the resulting Status List credential.
- Return stable ETags for unchanged publication state and do not regenerate a
  new proof/timestamp on repeated reads.
- Reject client-supplied `credentialStatus` during issuance. Assign it before
  proof creation and verify the secured result before persistence.
- Commit the signed credential, status entry ID, list ID, and index in one
  credential insert. Enforce a unique partial list/index index so concurrent
  issuance cannot commit two credentials to one slot.
- Append every material publication version to immutable history and expose
  historical documents with immutable cache policy.
- Keep issuer signing, key-provider, and publication operations behind
  application ports so a future issuer KMS/HSM adapter does not change
  business rules.
- Require `presentations:create`, `presentations:verify`, or
  `presentations:read` before the corresponding VP application service.
- Bound presentations to one-to-eight credentials, 65,536 canonical bytes,
  and a 30-to-600-second lifetime.
- Require URL-safe 16-to-128-character verifier challenges and normalized DNS
  domains. Cover challenge, domain, holder, credentials, and expiry with the
  holder `authentication` proof.
- Enforce unique Mongo indexes for `presentationId` and `challenge + domain`.
  Claim `PENDING -> PROCESSING` atomically before validation and complete only
  as `VERIFIED` or `REJECTED`.
- Re-check every embedded credential against current persisted lifecycle
  state, issuer proof, SHA-256 digest, holder binding, and exact
  issuance-time `credentialStatus` mapping.
- Persist `PRESENTATION_CREATED`, `PRESENTATION_VERIFIED`, and
  `PRESENTATION_REJECTED` through the durable outbox without VP JSON,
  challenges, proofs, hashes, or credential material in audit metadata.
- Require `wallets:*` and `presentation-challenges:*` permissions before
  object-level ownership checks. Return not found for absent and foreign
  wallet/challenge/presentation resources.
- Require active, non-deleted wallet state and exact
  `ownerUserId + walletId + holderDid` credential binding before signing.
- Keep `HolderKeyProvider`, `HolderKeyMetadataProvider`, and `HolderSigner`
  separate from cryptography and provider SDKs. The application receives only
  opaque references and public metadata.
- Use a cryptographically secure random source for challenges. Make challenge
  ID/value unique, apply expiry, and atomically match state, version, domain,
  audience, and optional holder restriction during consumption.
- Persist `processingStartedAt`, reconciliation attempts, and last
  reconciliation time. Claim only stale records and fail closed when wallet,
  key, or challenge evidence is incomplete.
- Restrict manual reconciliation to the admin role and keep the background
  worker idempotent.
- Audit wallet, challenge, ownership, and reconciliation changes through the
  durable outbox without challenge values, key references, credentials, or
  proof material.

Required before any public or production credential API:

- Define issuer governance and trust policy.
- Complete external W3C Bitstring Status List conformance testing, CDN
  behavior, historical retention policy, and monitored caching/availability
  policy.
- Configure and independently review a concrete vendor KMS/HSM or governed
  external-wallet provider behind the implemented managed-key lifecycle;
  disable the deterministic development provider.
- Close the remaining crash window between wallet/challenge/presentation
  state commits and standalone outbox insertion.
- Replace the synthetic in-memory key with a KMS, HSM, or secure wallet.
- Add authenticated workload identity, authorization, audit, rate limits, and
  production secret management.
- Deploy MongoDB with TLS, least-privilege accounts, managed credentials,
  network isolation, monitoring, tested backup/restore, retention controls,
  capacity planning, and a reviewed migration process.
- Define encryption and privacy controls before storing raw credentials or
  real identifiers.
- Add MFA, credential-stuffing protections, durable token lifecycle/revocation,
  production user governance, and an externally reviewed identity provider.
- Complete external interoperability and security review.
- Add operational alerting for outbox age/retry volume and test Mongo
  replica/backup recovery. The durable outbox is implemented, but production
  monitoring and disaster recovery are not.

The current local API is deliberately allowed before these production gates
only as a synthetic, network-free academic test surface. It is not an exception
to the production requirements.

Before implementing fraud detection:

- Approve the allowed signal catalog and retention period.
- Define model versioning, reason codes, monitoring, and human review.
- Define protected-group and fairness evaluation.

Before implementing recovery:

- Define guardian threshold, independence assumptions, expiry, and cooling-off period.
- Define signed approval and replay-prevention formats.
- Define holder notification, cancellation, appeal, and incident handling.

Before implementing blockchain:

- Confirm that the use case cannot be satisfied with a less permanent store.
- Document network, finality, RPC trust, upgrades, and privileged roles.
- Complete contract tests, static analysis, and independent review.

## Secret handling

`.env.example` files contain names and safe placeholders only. Real local
`.env` files are ignored by Git. The deterministic issuer test seed is
intentionally public and provides no production security. A future deployment
must use a secret manager, KMS/HSM or secure wallet, and workload identity;
Compose Mongo root/application credentials and URI values are development
placeholders. `MongoSettings` and the connection manager redact the URI from
their representations and controlled failures.

## Vulnerability reporting

Do not include real user data or secrets in reports. Record the affected component, reproduction using synthetic data, impact, and suggested containment. A private reporting channel must be established before external testing.
