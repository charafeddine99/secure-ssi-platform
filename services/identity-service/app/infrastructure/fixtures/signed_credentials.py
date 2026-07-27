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
