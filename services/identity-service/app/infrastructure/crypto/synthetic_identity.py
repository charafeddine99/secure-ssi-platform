"""Public identifiers of the synthetic demo issuer. No key material lives here,
so importing this module never pulls a development key into a process."""

SYNTHETIC_ISSUER_DID = "did:web:issuer.example"
SYNTHETIC_VERIFICATION_METHOD = f"{SYNTHETIC_ISSUER_DID}#key-1"
