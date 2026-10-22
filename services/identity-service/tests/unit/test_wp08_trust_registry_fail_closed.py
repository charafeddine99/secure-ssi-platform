from unittest.mock import MagicMock

from app.application.services.oid4vp_service import Oid4vpService


def test_oid4vp_service_does_not_seed_a_trust_registry_when_unconfigured() -> None:
    service = Oid4vpService(
        session_repository=MagicMock(),
        credential_repository=MagicMock(),
        audit_repository=MagicMock(),
        verifier_presentation_service=MagicMock(),
        status_list_service=MagicMock(),
    )

    assert service._trust_registry is None
