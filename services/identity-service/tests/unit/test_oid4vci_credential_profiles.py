from unittest.mock import Mock

import pytest

from app.application.services.oid4vci_service import Oid4vciService
from app.domain.oid4vci import UnsupportedCredentialConfigurationError
from app.services.credential_validator import (
    CREDENTIAL_PROFILE_CONTEXTS,
    VC_V2_CONTEXT,
)


def _service() -> Oid4vciService:
    return Oid4vciService(
        offer_repository=Mock(),
        credential_repository=Mock(),
        audit_repository=Mock(),
        status_list_service=Mock(),
        credential_issuance_service=Mock(),
    )


def test_issuer_metadata_only_advertises_validated_credential_profiles() -> None:
    metadata = _service().get_issuer_metadata()

    configurations = metadata["credential_configurations_supported"]
    assert set(configurations) == set(CREDENTIAL_PROFILE_CONTEXTS)
    for credential_type, context in CREDENTIAL_PROFILE_CONTEXTS.items():
        assert configurations[credential_type]["format"] == "ldp_vc"
        assert configurations[credential_type]["credential_definition"] == {
            "@context": [VC_V2_CONTEXT, context],
            "type": ["VerifiableCredential", credential_type],
        }


@pytest.mark.parametrize(
    "credential_type",
    ["NationalIdCredential", "DriverLicenseCredential", "UnknownCredential"],
)
def test_offer_rejects_credential_types_without_a_validated_profile(
    credential_type: str,
) -> None:
    with pytest.raises(UnsupportedCredentialConfigurationError):
        Oid4vciService._validate_offer_subject(
            (credential_type,), {"sampleClaim": "synthetic"}
        )


def test_offer_accepts_the_qeaa_profile_with_scalar_subject_claims() -> None:
    Oid4vciService._validate_offer_subject(
        ("QualifiedElectronicAttestationCredential",),
        {"attestationName": "Synthetic prototype attestation"},
    )
