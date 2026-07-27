# Synthetic Verifiable Credential Profile

## Scope

This local academic prototype implements the narrow credential profile selected
by [ADR 0002](adr/0002-vc-data-model-and-proof-format.md):

- VC Data Model 2.0 structure;
- `DataIntegrityProof`;
- `eddsa-jcs-2022`;
- RFC 8785 JSON Canonicalization Scheme (JCS);
- SHA-256 proof/document hashing;
- Ed25519 signing and verification;
- base58-btc multibase proof values;
- a claim-free structured verification result.

This is not a claim of complete W3C interoperability or production
compliance. The profile is available through the bounded local routes in
[credential-api.md](credential-api.md).

## Version 1 profile

The shared contracts are:

- `packages/shared/schemas/v1/verifiable-credential.schema.json`;
- `packages/shared/schemas/v1/data-integrity-proof.schema.json`;
- `packages/shared/schemas/v1/credential-verification-result.schema.json`.

The credential requires:

- `https://www.w3.org/ns/credentials/v2` as the first context;
- the bundled university-affiliation context as the only extension context;
- `VerifiableCredential` and `UniversityAffiliationCredential` types;
- an opaque canonical `urn:uuid` credential identifier;
- the local `did:web` issuer;
- a short-lived synthetic `did:key` subject;
- UTC `validFrom` and `validUntil` timestamps;
- only `id`, `affiliation`, `programCode`, `degree`, and `graduationYear`
  subject fields.

The extension context is bundled at
`packages/shared/contexts/v1/university-affiliation.jsonld`. Credential input
does not trigger network or arbitrary JSON-LD context retrieval.

## Proof profile

A secured credential contains:

- proof type `DataIntegrityProof`;
- cryptosuite `eddsa-jcs-2022`;
- proof purpose `assertionMethod`;
- UTC `created`;
- the same pinned contexts as the credential;
- `did:web:issuer.example#key-1`;
- a base58-btc multibase encoded 64-byte Ed25519 signature.

The credential `proof` is removed before document canonicalization.
`proofValue` is removed before proof-configuration canonicalization. The proof
configuration still binds type, cryptosuite, creation time, verification
method, purpose, and contexts to the signature. See
[VC signing and verification](vc-signing.md).

## Verification-result semantics

The result model exposes individual outcomes for:

- document structure;
- context and type;
- issuer DID resolution;
- verification-method authorization;
- cryptosuite;
- proof purpose;
- proof timestamp;
- signature;
- content integrity;
- validity window;
- credential status;
- issuer trust.

`verified` is derived, not caller supplied. It is true only when all required
checks pass. Credential status remains `notApplicable` inside this
cryptographic verification result because verification does not call MongoDB;
clients must query the separate local status endpoint for an already persisted
credential. Issuer trust means only that the issuer and public key match
the local synthetic allowlist; it does not establish real institutional trust
or claim truth.

Results contain check states and reason codes. They do not echo credential
claims, DIDs, proof values, or private key material.

## Input controls

The internal profile validator:

- enforces a configurable 32 KiB credential limit;
- rejects invalid UTF-8, malformed JSON, NaN, and Infinity;
- rejects duplicate JSON properties;
- rejects unknown fields and unapproved claims;
- rejects private or secret key fields recursively;
- pins context and type ordering;
- validates identifier methods and UTC timestamps;
- requires `validUntil` later than `validFrom`;
- rejects unsupported proof types, suites, purposes, key URLs, and encodings.

The proof service additionally:

- resolves only the registered local issuer DID document;
- requires the key to be authorized for `assertionMethod`;
- requires an Ed25519 Multikey;
- compares the DID document key with the local trusted key;
- rejects key substitution, malformed signatures, tampering, and expiry;
- uses the cryptography library verification operation rather than comparing
  signatures itself.

## Synthetic fixtures

Fixtures are under `services/identity-service/tests/fixtures`:

- `issuer.did.json`;
- `unsigned-university-affiliation.vc.json`;
- `valid-signed-university-affiliation.vc.json`.

The infrastructure fixture builders also create 15 deterministic tamper
variants covering claims, identifiers, proof metadata, contexts, signatures,
unknown fields, key mismatch, and another issuer key. All values are synthetic.

## Deferred work

Not implemented:

- automatic persistence of signed credentials;
- JSON-LD RDF canonicalization;
- external `did:web` resolution;
- persistent key storage;
- KMS, HSM, or secure wallet integration;
- key rotation;
- credential-status integration into cryptographic verification;
- interoperable W3C Bitstring Status List publication;
- selective disclosure;
- presentation challenge, audience, nonce, or holder binding;
- blockchain anchoring;
- production issuer governance.

Production use requires a reviewed trust policy, status mechanism, replay
controls, secure key custody, external interoperability testing, and a new
security review.
