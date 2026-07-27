from datetime import datetime
from typing import Protocol

from app.domain.auth import AuthenticatedPrincipal, TokenClaims


class AccessTokenService(Protocol):
    @property
    def lifetime_seconds(self) -> int: ...

    def issue_access_token(
        self,
        principal: AuthenticatedPrincipal,
        *,
        issued_at: datetime,
        jwt_id: str,
    ) -> str: ...

    def decode_access_token(
        self,
        token: str,
        *,
        checked_at: datetime,
    ) -> TokenClaims: ...
