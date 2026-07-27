# DID Resolver Prototype

## Status and scope

The Identity Service contains an internal, network-free DID resolver prototype implementing the acceptance criteria in ADR 0001. It is not exposed through HTTP and it does not issue or verify credentials.

Supported prototype methods:

| Method | Source | Allowed use |
| --- | --- | --- |
| `did:key` | Deterministic local expansion | Short-lived synthetic Ed25519 holder fixtures |
| `did:web` | Explicitly registered local JSON fixture | Synthetic institutional issuer |

All other DID methods are rejected. The implementation contains no HTTP client and cannot silently fall back to a universal or public resolver.

## Code structure

- `app/domain/did.py`: immutable result/metadata types and explicit error codes.
- `app/services/did_resolver.py`: resolver protocol, method dispatch, Ed25519 `did:key` expansion, and local `did:web` fixture loading.
- `app/services/did_document_validator.py`: common document security profile.
- `tests/fixtures/issuer.did.json`: public synthetic issuer fixture without private key material.

## Validation profile

Every resolved document must:

- stay below the configured byte limit;
- have an `id` exactly matching the requested DID;
- start with the pinned DID Core v1 context;
- use only pinned contexts;
- contain between 1 and 16 verification methods;
- use unique absolute DID URL verification method identifiers;
- use a matching controller;
- use a base58-btc `Multikey`;
- authorize at least one declared verification method through `assertionMethod`;
- contain no field that could represent private or secret key material.

Local JSON fixtures also reject duplicate properties, invalid UTF-8, non-object roots, and malformed JSON.

## Explicit errors

- `INVALID_DID`
- `METHOD_NOT_SUPPORTED`
- `NOT_FOUND`
- `INVALID_DID_DOCUMENT`
- `DOCUMENT_TOO_LARGE`
- `PRIVATE_KEY_MATERIAL`
- `UNSUPPORTED_KEY_TYPE`

Errors contain the requested DID and a safe message. They never contain credential data or private material.

## Configuration

```text
MAX_DID_DOCUMENT_BYTES=16384
DID_NETWORK_RESOLUTION_ENABLED=false
```

`DID_NETWORK_RESOLUTION_ENABLED` documents the secure default. No network resolver exists in this milestone, so changing it does not enable network access.

## Tests

The test suite covers:

- deterministic resolution of an official-compatible Ed25519 `did:key` vector;
- local `did:web` issuer fixture resolution;
- allowlist dispatch;
- malformed identifiers;
- unsupported methods and key types;
- missing or undeclared assertion methods;
- mismatched document identifiers;
- oversized documents;
- duplicate JSON properties;
- unapproved contexts;
- private/secret key fields;
- confirmation that an unregistered `did:web` is not fetched from the network.

Run:

```powershell
cd services/identity-service
python -m pytest -q
```

## Deliberately not implemented

- Public or internal resolver HTTP endpoint.
- Network `did:web` resolution.
- Universal resolver integration.
- Resolver caching.
- DID creation, update, or deactivation.
- Holder key generation or storage.
- VC issuance, signing, presentation, or verification.

The next milestone may begin the synthetic VC fixture and verification-result model from ADR 0002. It must not add an issuance endpoint before negative fixture tests exist.
