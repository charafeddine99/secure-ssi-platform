# Local VC Signing and Verification

## Status

This module is a local academic implementation of the project profile in
[ADR 0002](adr/0002-vc-data-model-and-proof-format.md). It follows the core
`eddsa-jcs-2022` processing shape but does not claim complete W3C
interoperability, certification, production key management, or support for
arbitrary JSON-LD credentials.

The existing service is exposed through the bounded local endpoints documented
in [credential-api.md](credential-api.md). The cryptographic flow still
performs no network call.

## Layering

```text
application/services/credential_proof_service.py
        |
        +-- application/services/credential_api_service.py
        +-- api/v1/credentials.py
        +-- api/v1/dependencies.py
        |
        +-- ports/canonicalizer.py
        +-- ports/credential_signer.py
        +-- ports/key_provider.py
        |
        +-- infrastructure/crypto/jcs_canonicalizer.py
        +-- infrastructure/crypto/ed25519_signer.py
        +-- infrastructure/crypto/local_issuer_key_provider.py
        |
        +-- services/credential_validator.py
        +-- services/did_resolver.py
```

The domain and application ports do not depend on FastAPI. The application
service receives an opaque signing capability; private key bytes are not
returned by a port, serialized into a model, or included in an exception.
The router does not call cryptographic adapters or the key provider directly.

## Canonicalization and signing input

The `rfc8785` package produces UTF-8 RFC 8785/JCS bytes. It supplies
deterministic property ordering, number serialization, string processing, and
minimal JSON encoding. Arrays retain their original order.

For signing:

1. Validate the unsigned credential profile.
2. Reject an existing `proof`.
3. Build proof options containing context, type, cryptosuite, UTC `created`,
   verification method, and proof purpose.
4. Canonicalize the credential after removing `proof`.
5. Canonicalize proof options after removing `proofValue`.
6. Calculate SHA-256 of each canonical byte sequence.
7. Concatenate `proofConfigHash || credentialHash`.
8. Sign the resulting 64 bytes with Ed25519.
9. Encode the 64-byte signature as base58-btc multibase (`z...`).
10. Attach the proof and validate the secured credential again.

The proof configuration is signed indirectly through its digest. Changing a
validly formatted `created`, cryptosuite, purpose, verification method, or
context therefore invalidates the signature.

This implementation does not perform JSON-LD RDF dataset canonicalization.

## Ed25519 and proofValue

Ed25519 operations use `cryptography`; no signature primitive or timing
comparison is implemented in project code. Verification uses the library's
`Ed25519PublicKey.verify` operation and accepts only exactly 64 signature
bytes.

`proofValue` uses base58-btc multibase because that is the representation used
by the selected Data Integrity EdDSA profile. Encoding is deterministic and
decoding is bounded by the credential schema and profile validator.

## Synthetic local issuer key

`LocalIssuerKeyProvider` contains a deterministic, publicly known test seed.
It is deliberately reproducible and therefore not secret. The corresponding
public key exactly matches `tests/fixtures/issuer.did.json`.

The provider:

- supports only `did:web:issuer.example`;
- uses only `did:web:issuer.example#key-1`;
- exposes an opaque signing handle, not private bytes;
- provides a public verification-key value;
- redacts the signing object and provider representations;
- has a second deterministic test-only key for substitution attacks.

This is not persistent or secure key management. Production signing requires
a KMS, HSM, or secure wallet, access policy, audit, rotation, backup,
deactivation, and incident-response procedures.

## Verification flow

Verification performs:

1. credential and proof profile validation;
2. validity-window evaluation using an injectable clock;
3. local issuer DID resolution;
4. exact verification-method lookup;
5. `assertionMethod` authorization;
6. Multikey/Ed25519 validation;
7. DID-document key comparison with the local trusted key;
8. base58-btc decoding and 64-byte signature-length enforcement;
9. proof/document canonicalization and SHA-256 hashing;
10. cryptography-library Ed25519 verification;
11. structured check and reason-code production.

Expected credential failures return `CredentialVerificationResult`. Unexpected
infrastructure or programming failures may use typed exceptions.

A valid signature means only that the secured bytes match the locally resolved
synthetic key. It does not prove issuer governance, claim accuracy, current
credential status, holder control, audience binding, or non-replay.

## Dependencies

- `cryptography==49.0.0`: maintained Ed25519 implementation under Apache-2.0
  OR BSD-3-Clause. The project does not implement Ed25519 itself.
- `rfc8785==0.1.4`: small, no-dependency RFC 8785 implementation under
  Apache-2.0.

`rfc8785` is marked Beta and has a smaller maintenance surface than
`cryptography`. Its pinned version, license, repository activity, RFC test
coverage, and security posture must be re-reviewed before any production or
external interoperability work. Dependency pin updates require the full
canonicalization and signature regression suite.
