import secrets
from datetime import UTC, datetime


class SystemClock:
    def __call__(self) -> datetime:
        return datetime.now(UTC)


class SecureJtiGenerator:
    def __call__(self) -> str:
        return secrets.token_urlsafe(24)
