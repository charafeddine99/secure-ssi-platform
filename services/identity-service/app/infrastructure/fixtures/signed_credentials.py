import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.application.ports.key_provider import KeyProvider
from app.application.services.credential_proof_service import (
    CredentialProofService,
)
from app.infrastructure.crypto.ed25519_signer import (
    Ed25519CredentialSigner,
)
from app.infrastructure.crypto.jcs_canonicalizer import JcsCanonicalizer
from app.infrastructure.crypto.local_issuer_key_provider import (
    LocalIssuerKeyProvider,
    SYNTHETIC_ISSUER_DID,
)
from app.services.credential_validator import CredentialProfileValidator
from app.services.did_resolver import CompositeDidResolver, DidWebFixtureResolver


IDENTITY_SERVICE_ROOT = Path(__file__).resolve().parents[3]
TEST_FIXTURE_ROOT = IDENTITY_SERVICE_ROOT / "tests" / "fixtures"
UNSIGNED_CREDENTIAL_PATH = (
    TEST_FIXTURE_ROOT / "unsigned-university-affiliation.vc.json"
)
ISSUER_DID_DOCUMENT_PATH = TEST_FIXTURE_ROOT / "issuer.did.json"
FIXED_PROOF_TIME = datetime(2026, 6, 1, tzinfo=UTC)


def load_unsigned_credential() -> dict[str, Any]:
    return json.loads(UNSIGNED_CREDENTIAL_PATH.read_text(encoding="utf-8"))


def build_local_proof_service(
    *,
    key_provider: KeyProvider | None = None,
    clock: Callable[[], datetime] | None = None,
) -> CredentialProofService:
    provider = key_provider or LocalIssuerKeyProvider()
    resolver = CompositeDidResolver(
        {
            "web": DidWebFixtureResolver(
                {SYNTHETIC_ISSUER_DID: ISSUER_DID_DOCUMENT_PATH}
            )
        }
    )
    return CredentialProofService(
        validator=CredentialProfileValidator(),
        canonicalizer=JcsCanonicalizer(),
        signer=Ed25519CredentialSigner(),
        key_provider=provider,
        did_resolver=resolver,
        clock=clock or (lambda: FIXED_PROOF_TIME),
    )


def build_signed_credential() -> dict[str, Any]:
    return build_local_proof_service().sign_credential(
        load_unsigned_credential()
    )


def build_signed_presentation(
    vc: dict[str, Any] | list[dict[str, Any]],
    *,
    nonce: str,
    domain: str = "http://testserver/verifier",
    holder_did: str | None = None,
    private_key: Any | None = None,
    verification_method: str | None = None,
    proof_purpose: str = "authentication",
    audience: str | None = None,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    import copy
    import uuid
    from datetime import timedelta, timezone
    from cryptography.hazmat.primitives import serialization
    from app.infrastructure.crypto.local_holder_key_provider import (
        LocalHolderKeyProvider,
        SYNTHETIC_HOLDER_KEY_REFERENCE,
        ED25519_MULTICODEC_PREFIX,
    )
    from app.infrastructure.crypto.multibase import encode_base58_btc

    vcs = [copy.deepcopy(vc)] if isinstance(vc, dict) else [copy.deepcopy(x) for x in vc]

    if private_key is None:
        key_prov = LocalHolderKeyProvider()
        signing_key = key_prov._private_key(SYNTHETIC_HOLDER_KEY_REFERENCE)
        effective_holder_did = holder_did or key_prov.holder_did
        effective_vm = verification_method or key_prov.verification_method
    else:
        signing_key = private_key
        pub_bytes = signing_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        multibase = encode_base58_btc(ED25519_MULTICODEC_PREFIX + pub_bytes)
        computed_did = f"did:key:{multibase}"
        effective_holder_did = holder_did or computed_did
        effective_vm = verification_method or f"{effective_holder_did}#{multibase}"

    # Synchronize credentialSubject.id with holder_did for unsigned credentials
    for c in vcs:
        if "proof" not in c:
            subj = c.get("credentialSubject")
            if isinstance(subj, dict):
                subj["id"] = effective_holder_did

    now = (clock() if clock else datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
    now_str = now.isoformat().replace("+00:00", "Z")
    exp_str = (now + timedelta(minutes=10)).isoformat().replace("+00:00", "Z")

    vp: dict[str, Any] = {
        "@context": ["https://www.w3.org/ns/credentials/v2"],
        "id": f"urn:uuid:{uuid.uuid4()}",
        "type": ["VerifiablePresentation"],
        "holder": effective_holder_did,
        "verifiableCredential": vcs,
        "validFrom": now_str,
        "validUntil": exp_str,
    }

    proof: dict[str, Any] = {
        "@context": ["https://www.w3.org/ns/credentials/v2"],
        "type": "DataIntegrityProof",
        "cryptosuite": "eddsa-jcs-2022",
        "created": now_str,
        "verificationMethod": effective_vm,
        "proofPurpose": proof_purpose,
        "challenge": nonce,
        "domain": domain,
    }
    if audience is not None:
        proof["audience"] = audience

    canonicalizer = JcsCanonicalizer()
    signing_input = canonicalizer.create_signing_input(vp, proof)
    signature_bytes = signing_key.sign(signing_input)
    proof["proofValue"] = encode_base58_btc(signature_bytes)
    vp["proof"] = proof
    return vp
