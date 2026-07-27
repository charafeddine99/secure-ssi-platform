from typing import Protocol

from app.domain.auth import User


class AuthenticationRecord(Protocol):
    @property
    def user(self) -> User: ...

    @property
    def password_hash(self) -> str: ...


class UserProvider(Protocol):
    authentication_source: str

    def find_by_username(
        self,
        username: str,
    ) -> AuthenticationRecord | None: ...

    def find_by_id(self, user_id: str) -> AuthenticationRecord | None: ...

    def fallback_password_hash(self) -> str: ...
