import os
from collections.abc import Mapping
from dataclasses import dataclass

from app.config.auth_settings import is_production_like
from app.domain.exceptions import AuthConfigurationError


@dataclass(frozen=True)
class DidResolutionSettings:
    """did:web network policy. HTTPS only unless a development host is allowlisted."""

    allow_insecure_http: bool = False
    insecure_http_hosts: frozenset[str] = frozenset()


def load_did_resolution_settings(
    environ: Mapping[str, str] | None = None,
) -> DidResolutionSettings:
    values = os.environ if environ is None else environ
    environment = values.get("IDENTITY_ENVIRONMENT", "development")
    raw_allow = values.get("IDENTITY_DID_WEB_ALLOW_INSECURE_HTTP", "false").strip().lower()
    if raw_allow not in {"true", "false"}:
        raise AuthConfigurationError("IDENTITY_DID_WEB_ALLOW_INSECURE_HTTP must be true or false.")
    allow = raw_allow == "true"
    hosts = frozenset(
        host.strip().lower()
        for host in values.get("IDENTITY_DID_WEB_INSECURE_HOSTS", "").split(",")
        if host.strip()
    )
    if allow and is_production_like(environment):
        raise AuthConfigurationError(
            "Plain-HTTP did:web resolution cannot be enabled in production-like mode."
        )
    if allow and not hosts:
        raise AuthConfigurationError(
            "Plain-HTTP did:web resolution needs an explicit host allowlist."
        )
    return DidResolutionSettings(allow_insecure_http=allow, insecure_http_hosts=hosts)
