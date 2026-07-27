# Shared Package

This package contains versioned, implementation-neutral contracts shared between planned services.

## Version 1 schema catalog

- `api-error.schema.json`
- `credential-issuance-request.schema.json`
- `credential-verification-result.schema.json`
- `data-integrity-proof.schema.json`
- `risk-assessment-request.schema.json`
- `risk-assessment-result.schema.json`
- `recovery-request.schema.json`
- `anchor-request.schema.json`
- `verifiable-credential.schema.json`

The credential and proof schemas define the narrow synthetic profile selected
in ADR 0002. Shape validation does not establish signature validity. The
remaining schemas define planned service boundaries and do not implement
fraud, blockchain, authentication, or recovery behavior.

The pinned extension context is stored in
`contexts/v1/university-affiliation.jsonld`. Runtime processing must use this
bundled document and must not fetch a context supplied by credential input.

Run the zero-dependency structural contract tests from the repository root:

```powershell
python -m unittest discover packages/shared/tests -v
```

Before any schema is used by an endpoint, add full JSON Schema validation, positive and negative fixtures, and a compatibility review.
