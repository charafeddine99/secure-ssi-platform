# Standards Baseline

Reviewed on 2026-07-23. Status labels are important: a draft is not presented as an endorsed standard.

| Area | Selected baseline | Status at review | Prototype use |
| --- | --- | --- | --- |
| DID data model | [DID Core v1.0](https://www.w3.org/TR/did-core/) | W3C Recommendation, 19 July 2022 | Required |
| DID Core next version | [DID Core v1.1](https://www.w3.org/TR/did-core/all/) | Candidate Recommendation Snapshot, 5 March 2026 | Monitor only |
| DID resolution | [DID Resolution v0.3](https://www.w3.org/TR/did-resolution/) | W3C Working Draft | Interface guidance only |
| Institutional DID method | [`did:web`](https://w3c-ccg.github.io/did-method-web/) | Unofficial community draft | Synthetic issuer |
| Holder fixture DID method | [`did:key` v0.9](https://w3c-ccg.github.io/did-key-spec/) | Community draft | Short-lived synthetic fixture only |
| Credential data model | [VC Data Model v2.0](https://www.w3.org/TR/vc-data-model-2.0/) | W3C Recommendation, 15 May 2025 | Required |
| Credential next version | [VC Data Model v2.1](https://www.w3.org/TR/vc-data-model/all/) | W3C Working Draft, 11 May 2026 | Monitor only |
| Embedded proof model | [VC Data Integrity v1.0](https://www.w3.org/TR/vc-data-integrity/) | W3C Recommendation, 15 May 2025 | Required |
| EdDSA proof suite | [Data Integrity EdDSA v1.0](https://www.w3.org/TR/vc-di-eddsa/) | W3C Recommendation, 15 May 2025 | `eddsa-jcs-2022` |
| Canonicalization | [RFC 8785 JCS](https://www.rfc-editor.org/rfc/rfc8785) | RFC, Informational, June 2020 | Required by selected suite |
| Signature primitive | [RFC 8032 EdDSA](https://www.rfc-editor.org/rfc/rfc8032) | RFC, Informational, January 2017 | Ed25519 |

## Update policy

- Recheck this table before beginning a new implementation milestone.
- Draft updates require a new ADR before adoption.
- Errata and implementation reports must be reviewed before claiming conformance.
- Method-specific community drafts require separate risk acceptance.
