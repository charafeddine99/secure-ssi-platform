"""Record a server-side Holder approval for an OID4VP session in API tests.

A verifier decision is ACCEPTED only after a session-bound Holder consent is
stored (see Oid4vpService.direct_post). Tests that exercise the direct_post
path without the wallet UI record that approval through the repository.
"""

from collections.abc import Mapping
from typing import Any


def record_holder_approval(
    session_id: str,
    credential: Mapping[str, Any],
    holder_did: str,
    repository: Any = None,
) -> None:
    from app.api.v1 import dependencies
    from app.domain.oid4vp import ConsentAction, ConsentDecision

    if repository is None:
        manager = dependencies.get_mongo_connection_manager()
        repository = dependencies.get_verification_session_repository(manager=manager)
    session = repository.get_by_session_id(session_id)
    assert session is not None
    subject = credential["credentialSubject"]
    repository.record_consent(
        session.session_id,
        consent_decision=ConsentDecision(
            session_id=session.session_id,
            verifier_did=session.verifier_did,
            client_id=session.client_id,
            purpose=session.purpose,
            nonce=session.nonce,
            holder_did=holder_did,
            decision=ConsentAction.APPROVE,
            approved_credentials=(credential["id"],),
            requested_claims=session.requested_fields,
            approved_claims={key: value for key, value in subject.items() if key != "id"},
            expires_at=session.expires_at,
        ),
        expected_version=session.version,
    )
