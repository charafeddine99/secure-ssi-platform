import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

from app.domain.bitstring_status_list import MINIMUM_STATUS_LIST_ENTRIES
from app.domain.persistence import PersistenceConfigurationError


@dataclass(frozen=True)
class StatusListSettings:
    public_base_url: str
    list_length: int = MINIMUM_STATUS_LIST_ENTRIES
    capacity: int = MINIMUM_STATUS_LIST_ENTRIES
    ttl_seconds: int = 300

    def __post_init__(self) -> None:
        normalized = self.public_base_url.rstrip("/")
        parsed = urlsplit(normalized)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.query
            or parsed.fragment
        ):
            raise PersistenceConfigurationError(
                "Status-list public base URL must be an HTTP(S) URL."
            )
        if not (
            MINIMUM_STATUS_LIST_ENTRIES
            <= self.list_length
            <= 16_777_216
        ):
            raise PersistenceConfigurationError(
                "Status-list length is outside the supported range."
            )
        if not 1 <= self.capacity <= self.list_length:
            raise PersistenceConfigurationError(
                "Status-list capacity is outside the supported range."
            )
        if not 1 <= self.ttl_seconds <= 86_400:
            raise PersistenceConfigurationError(
                "Status-list TTL is outside the supported range."
            )
        object.__setattr__(self, "public_base_url", normalized)


def load_status_list_settings(
    environ: Mapping[str, str] | None = None,
) -> StatusListSettings:
    values = os.environ if environ is None else environ
    return StatusListSettings(
        public_base_url=values.get(
            "IDENTITY_STATUS_LIST_PUBLIC_BASE_URL",
            "http://localhost:8001/api/v1/status-lists",
        ),
        list_length=_parse_int(
            values.get(
                "IDENTITY_STATUS_LIST_LENGTH",
                str(MINIMUM_STATUS_LIST_ENTRIES),
            ),
            name="IDENTITY_STATUS_LIST_LENGTH",
        ),
        capacity=_parse_int(
            values.get(
                "IDENTITY_STATUS_LIST_CAPACITY",
                values.get(
                    "IDENTITY_STATUS_LIST_LENGTH",
                    str(MINIMUM_STATUS_LIST_ENTRIES),
                ),
            ),
            name="IDENTITY_STATUS_LIST_CAPACITY",
        ),
        ttl_seconds=_parse_int(
            values.get("IDENTITY_STATUS_LIST_TTL_SECONDS", "300"),
            name="IDENTITY_STATUS_LIST_TTL_SECONDS",
        ),
    )


def _parse_int(value: str, *, name: str) -> int:
    try:
        return int(value)
    except ValueError as error:
        raise PersistenceConfigurationError(
            f"{name} must be an integer."
        ) from error
