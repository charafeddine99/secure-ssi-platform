import base64
import binascii
import hashlib
import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from app.config.environment_policy import is_production_like
from app.domain.persistence import PersistenceConfigurationError


_DEVELOPMENT_MAC_KEY = hashlib.sha256(
    b"secure-ssi-development-revocation-ledger-key"
).digest()


@dataclass(frozen=True)
class RevocationLedgerSettings:
    environment: str
    uri: str | None = field(default=None, repr=False)
    database: str = "secure_revocation_ledger"
    mac_key: bytes = field(default=_DEVELOPMENT_MAC_KEY, repr=False)
    anchor_path: str | None = None
    anchor_bootstrap: bool = False
    full_verify_seconds: int = 60

    @property
    def separate_authority(self) -> bool:
        return self.uri is not None

    @property
    def uses_development_key(self) -> bool:
        return self.mac_key == _DEVELOPMENT_MAC_KEY


def load_revocation_ledger_settings(
    environ: Mapping[str, str] | None = None,
) -> RevocationLedgerSettings:
    values = os.environ if environ is None else environ
    environment = values.get("IDENTITY_ENVIRONMENT", "development")
    production = is_production_like(environment)
    uri = values.get("IDENTITY_REVOCATION_LEDGER_URI", "").strip() or None
    encoded = values.get("IDENTITY_REVOCATION_LEDGER_MAC_KEY_BASE64", "").strip()
    anchor = values.get("IDENTITY_REVOCATION_ANCHOR_PATH", "").strip() or None
    if production:
        if uri is None:
            raise PersistenceConfigurationError(
                "Production-like environments need a dedicated revocation "
                "ledger database principal."
            )
        if uri == values.get("IDENTITY_MONGO_URI", "").strip():
            raise PersistenceConfigurationError(
                "The revocation ledger cannot share the application database "
                "principal."
            )
        if not encoded:
            raise PersistenceConfigurationError(
                "A revocation ledger key is required."
            )
        if anchor is None:
            raise PersistenceConfigurationError(
                "A revocation ledger anchor location is required."
            )
    mac_key = _DEVELOPMENT_MAC_KEY
    if encoded:
        try:
            mac_key = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as error:
            raise PersistenceConfigurationError(
                "The revocation ledger key is not valid base64."
            ) from error
        if len(mac_key) < 32:
            raise PersistenceConfigurationError(
                "The revocation ledger key is too short."
            )
    return RevocationLedgerSettings(
        environment=environment,
        uri=uri,
        database=(
            values.get("IDENTITY_REVOCATION_LEDGER_DATABASE", "").strip()
            or "secure_revocation_ledger"
        ),
        mac_key=mac_key,
        anchor_path=anchor,
        anchor_bootstrap=(
            values.get("IDENTITY_REVOCATION_ANCHOR_BOOTSTRAP", "false")
            .strip()
            .casefold()
            == "true"
        ),
    )
