from dataclasses import dataclass, field

from app.application.ports.repositories import UserRepository
from app.domain.auth import User
from app.domain.persistence import PersistedUser


@dataclass(frozen=True)
class MongoAuthenticationRecord:
    user: User
    password_hash: str = field(repr=False)


class MongoUserProvider:
    """Adapts the persistent user repository to the authentication port."""

    authentication_source = "mongodb"

    def __init__(
        self,
        repository: UserRepository,
        *,
        fallback_password_hash: str,
    ) -> None:
        self._repository = repository
        self._fallback_password_hash = fallback_password_hash

    def find_by_username(
        self,
        username: str,
    ) -> MongoAuthenticationRecord | None:
        record = self._repository.get_by_username(username)
        return self._to_authentication_record(record)

    def find_by_id(
        self,
        user_id: str,
    ) -> MongoAuthenticationRecord | None:
        record = self._repository.get_by_id(user_id)
        return self._to_authentication_record(record)

    def fallback_password_hash(self) -> str:
        return self._fallback_password_hash

    @staticmethod
    def _to_authentication_record(
        record: PersistedUser | None,
    ) -> MongoAuthenticationRecord | None:
        if record is None:
            return None
        return MongoAuthenticationRecord(
            user=record.to_public_user(),
            password_hash=record.password_hash,
        )

    def __repr__(self) -> str:
        return "MongoUserProvider(password_hashes=<redacted>)"
