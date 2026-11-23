"""The verifier's request-object signing key.

``OID4VP_REQUEST_SIGNING_KEY`` holds a base64url Ed25519 private seed (32 bytes).
Production-like environments must set it. Development without it gets a key
that lives only as long as the process: requests created before a restart then
answer 410 and the verifier creates a new one.
"""

from __future__ import annotations

import base64
import logging
import os
from collections.abc import Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.config.environment_policy import is_production_like
from app.domain.persistence import PersistenceConfigurationError
from app.domain.request_object import RequestObjectSigner

_LOGGER = logging.getLogger(__name__)
_SIGNER: RequestObjectSigner | None = None


def load_request_object_signer(environ: Mapping[str, str] | None = None) -> RequestObjectSigner:
    values = os.environ if environ is None else environ
    seed = values.get("OID4VP_REQUEST_SIGNING_KEY", "").strip()
    if seed:
        try:
            raw = base64.urlsafe_b64decode(seed + "=" * (-len(seed) % 4))
        except ValueError as error:
            raise PersistenceConfigurationError("OID4VP_REQUEST_SIGNING_KEY is not base64url.") from error
        if len(raw) != 32:
            raise PersistenceConfigurationError("OID4VP_REQUEST_SIGNING_KEY must decode to 32 bytes.")
        return RequestObjectSigner(Ed25519PrivateKey.from_private_bytes(raw))
    if is_production_like(values.get("IDENTITY_ENVIRONMENT", "development")):
        raise PersistenceConfigurationError(
            "OID4VP_REQUEST_SIGNING_KEY is required in a production-like environment."
        )
    _LOGGER.warning("OID4VP request signing key is ephemeral (development only).")
    return RequestObjectSigner(Ed25519PrivateKey.generate())


def request_object_signer() -> RequestObjectSigner:
    global _SIGNER
    if _SIGNER is None:
        _SIGNER = load_request_object_signer()
    return _SIGNER
