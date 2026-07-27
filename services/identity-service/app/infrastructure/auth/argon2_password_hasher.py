from argon2 import PasswordHasher, Type
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)


class Argon2PasswordHasher:
    """Argon2id adapter with bounded local-prototype parameters."""

    def __init__(
        self,
        *,
        time_cost: int = 2,
        memory_cost: int = 19_456,
        parallelism: int = 1,
    ) -> None:
        self._hasher = PasswordHasher(
            time_cost=time_cost,
            memory_cost=memory_cost,
            parallelism=parallelism,
            hash_len=32,
            salt_len=16,
            type=Type.ID,
        )

    def hash_password(self, password: str) -> str:
        if not password:
            raise ValueError("Password must not be empty.")
        return self._hasher.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (InvalidHashError, VerificationError, VerifyMismatchError):
            return False

    def __repr__(self) -> str:
        return "Argon2PasswordHasher(type='argon2id', material=<redacted>)"
