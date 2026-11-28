import ipaddress
import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

from app.config.environment_policy import is_production_like
from app.domain.persistence import PersistenceConfigurationError


_INTERNAL_HOSTS = frozenset(
    {
        "localhost",
        "identity-service",
        "api-gateway",
        "web",
        "recovery-service",
        "fraud-service",
        "mongodb",
        "redis",
    }
)


@dataclass(frozen=True)
class PublicOriginSettings:
    """The origin a person's phone can actually reach. Without it no QR for a
    phone is produced, because a stock camera cannot open openid4vp:// and a
    Docker host name means nothing outside the Compose network."""

    origin: str | None = None

    def handoff_uri(self, session_id: str) -> str | None:
        if self.origin is None:
            return None
        return f"{self.origin}/wallet/present?request={session_id}"


def reachable_from_a_phone(origin: str) -> bool:
    host = (urlsplit(origin).hostname or "").casefold()
    if not host or host in _INTERNAL_HOSTS or host.endswith(".localhost"):
        return False
    try:
        return not ipaddress.ip_address(host).is_loopback
    except ValueError:
        return True


def load_public_origin_settings(
    environ: Mapping[str, str] | None = None,
) -> PublicOriginSettings:
    values = os.environ if environ is None else environ
    origin = values.get("IDENTITY_PUBLIC_ORIGIN", "").strip().rstrip("/")
    production = is_production_like(
        values.get("IDENTITY_ENVIRONMENT", "development")
    )
    if not origin:
        return PublicOriginSettings()
    parts = urlsplit(origin)
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.path
        or parts.query
        or parts.fragment
    ):
        raise PersistenceConfigurationError(
            "IDENTITY_PUBLIC_ORIGIN must be a bare origin."
        )
    if not reachable_from_a_phone(origin):
        raise PersistenceConfigurationError(
            "IDENTITY_PUBLIC_ORIGIN must be reachable from outside this host."
        )
    if production and parts.scheme != "https":
        raise PersistenceConfigurationError(
            "A production-like public origin must use HTTPS."
        )
    return PublicOriginSettings(origin=origin)
