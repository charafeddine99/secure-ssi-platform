from typing import Protocol, Mapping, Any
from app.domain.oid4vp import VerificationSession, VerificationSessionStatus, NinePointVerificationResult

class VerificationSessionRepository(Protocol):
    def add(self, session: VerificationSession) -> VerificationSession:
        ...

    def get_by_session_id(self, session_id: str) -> VerificationSession | None:
        ...

    def get_by_nonce(self, nonce: str) -> VerificationSession | None:
        ...

    def update_result(
        self,
        session_id: str,
        *,
        status: VerificationSessionStatus,
        presentation_id: str,
        verification_result: NinePointVerificationResult,
        disclosed_claims: Mapping[str, Any] | None,
        expected_version: int,
    ) -> VerificationSession:
        ...

    def list_by_verifier(
        self,
        verifier_did: str,
        *,
        limit: int = 50,
    ) -> tuple[VerificationSession, ...]:
        ...
