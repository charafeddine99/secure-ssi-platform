import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from app.domain.persistence import PersistenceConfigurationError


_DATABASE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass(frozen=True)
class MongoSettings:
    enabled: bool
    uri: str = field(repr=False)
    database_name: str
    server_selection_timeout_ms: int = 3_000
    connect_timeout_ms: int = 3_000
    socket_timeout_ms: int = 5_000
    max_pool_size: int = 50
    min_pool_size: int = 0
    retry_reads: bool = True
    retry_writes: bool = True
    app_name: str = "secure-ssi-identity-service"

    def __post_init__(self) -> None:
        parsed = urlsplit(self.uri)
        if parsed.scheme not in {"mongodb", "mongodb+srv"}:
            raise PersistenceConfigurationError(
                "MongoDB URI must use mongodb or mongodb+srv."
            )
        if not parsed.hostname:
            raise PersistenceConfigurationError(
                "MongoDB URI must contain a hostname."
            )
        if not _DATABASE_NAME_PATTERN.fullmatch(self.database_name):
            raise PersistenceConfigurationError(
                "MongoDB database name contains unsupported characters."
            )
        for name, value, minimum, maximum in (
            (
                "server selection timeout",
                self.server_selection_timeout_ms,
                100,
                60_000,
            ),
            ("connect timeout", self.connect_timeout_ms, 100, 60_000),
            ("socket timeout", self.socket_timeout_ms, 100, 120_000),
            ("maximum pool size", self.max_pool_size, 1, 1_000),
            ("minimum pool size", self.min_pool_size, 0, 1_000),
        ):
            if not minimum <= value <= maximum:
                raise PersistenceConfigurationError(
                    f"MongoDB {name} is outside the supported range."
                )
        if self.min_pool_size > self.max_pool_size:
            raise PersistenceConfigurationError(
                "MongoDB minimum pool size exceeds maximum pool size."
            )
        if not self.app_name.strip() or len(self.app_name) > 128:
            raise PersistenceConfigurationError(
                "MongoDB application name is empty or too long."
            )


def load_mongo_settings(
    environ: Mapping[str, str] | None = None,
) -> MongoSettings:
    values = os.environ if environ is None else environ
    return MongoSettings(
        enabled=_parse_bool(
            values.get("IDENTITY_MONGO_ENABLED", "false"),
            name="IDENTITY_MONGO_ENABLED",
        ),
        uri=values.get(
            "IDENTITY_MONGO_URI",
            "mongodb://localhost:27017/secure_identity",
        ),
        database_name=values.get(
            "IDENTITY_MONGO_DATABASE",
            "secure_identity",
        ),
        server_selection_timeout_ms=_parse_int(
            values.get(
                "IDENTITY_MONGO_SERVER_SELECTION_TIMEOUT_MS",
                "3000",
            ),
            name="IDENTITY_MONGO_SERVER_SELECTION_TIMEOUT_MS",
        ),
        connect_timeout_ms=_parse_int(
            values.get("IDENTITY_MONGO_CONNECT_TIMEOUT_MS", "3000"),
            name="IDENTITY_MONGO_CONNECT_TIMEOUT_MS",
        ),
        socket_timeout_ms=_parse_int(
            values.get("IDENTITY_MONGO_SOCKET_TIMEOUT_MS", "5000"),
            name="IDENTITY_MONGO_SOCKET_TIMEOUT_MS",
        ),
        max_pool_size=_parse_int(
            values.get("IDENTITY_MONGO_MAX_POOL_SIZE", "50"),
            name="IDENTITY_MONGO_MAX_POOL_SIZE",
        ),
        min_pool_size=_parse_int(
            values.get("IDENTITY_MONGO_MIN_POOL_SIZE", "0"),
            name="IDENTITY_MONGO_MIN_POOL_SIZE",
        ),
        retry_reads=_parse_bool(
            values.get("IDENTITY_MONGO_RETRY_READS", "true"),
            name="IDENTITY_MONGO_RETRY_READS",
        ),
        retry_writes=_parse_bool(
            values.get("IDENTITY_MONGO_RETRY_WRITES", "true"),
            name="IDENTITY_MONGO_RETRY_WRITES",
        ),
        app_name=values.get(
            "IDENTITY_MONGO_APP_NAME",
            "secure-ssi-identity-service",
        ),
    )


def _parse_bool(value: str, *, name: str) -> bool:
    normalized = value.strip().casefold()
    if normalized not in {"true", "false"}:
        raise PersistenceConfigurationError(f"{name} must be true or false.")
    return normalized == "true"


def _parse_int(value: str, *, name: str) -> int:
    try:
        return int(value)
    except ValueError as error:
        raise PersistenceConfigurationError(
            f"{name} must be an integer."
        ) from error
