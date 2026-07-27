# Synthetic Identity and Credential Fixtures

These public DID documents, keys, and credential claims are synthetic
interoperability fixtures. They contain no private keys and must never be
reused as production identities or signing material.

- `issuer.did.json` is a network-free `did:web` issuer document.
- `unsigned-university-affiliation.vc.json` is an unsigned VC Data Model 2.0
  fixture. Its identifiers and allowlisted affiliation claims are synthetic.
- `valid-signed-university-affiliation.vc.json` is a deterministic local
  `eddsa-jcs-2022` fixture signed with the public test seed.
- `status-bound-university-affiliation.vc.json` is the same VC Data Model 2.0
  profile with an issuer-assigned Bitstring Status List entry included before
  its Data Integrity proof is created.
- `bitstring-status-list-v1.vc.json` is a signed, empty revocation publication
  fixture with the W3C minimum bitstring length.

The unsigned fixture intentionally has no `proof`. Tampered variants are built
by `app/infrastructure/fixtures/tampered_credentials.py`; all 15 variants must
fail with structured reason codes.

The deterministic issuer seed is publicly known test material and provides no
production security. It must never be reused outside local tests and
demonstrations.
