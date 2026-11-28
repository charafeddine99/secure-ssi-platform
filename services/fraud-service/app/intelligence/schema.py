"""Strict event envelope. Free text is not accepted anywhere in an event."""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.intelligence.taxonomy import EVENT_TYPES, ORIGINS, SCHEMA_VERSION, SOURCES

MAX_FUTURE_SKEW = timedelta(minutes=5)
MAX_AGE = timedelta(days=90)
MAX_BATCH = 500

_Ref = Annotated[str, StringConstraints(pattern=r"^[a-z]{1,12}:[A-Za-z0-9_-]{8,80}$")]
_Code = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.:/-]{1,64}$")]
_ALLOWED_ATTRIBUTES = frozenset({"reason_code", "route_group", "status_class", "http_status", "policy_result", "action"})


class SecurityEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.:-]{8,128}$")]
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    occurred_at: datetime
    source_service: str
    source_component: _Code
    event_type: str
    count: int = Field(default=1, ge=1, le=100_000)
    origin: str
    actor_role: _Code | None = None
    actor_ref: _Ref | None = None
    source_ref: _Ref | None = None
    resource_type: _Code | None = None
    resource_ref: _Ref | None = None
    correlation_ref: _Ref | None = None
    attributes: dict[str, _Code] = Field(default_factory=dict, max_length=6)

    @field_validator("event_type")
    @classmethod
    def _known_type(cls, value: str) -> str:
        if value not in EVENT_TYPES:
            raise ValueError("Unknown event type.")
        return value

    @field_validator("source_service")
    @classmethod
    def _known_source(cls, value: str) -> str:
        if value not in SOURCES:
            raise ValueError("Unknown source service.")
        return value

    @field_validator("origin")
    @classmethod
    def _known_origin(cls, value: str) -> str:
        if value not in ORIGINS:
            raise ValueError("Unknown origin.")
        return value

    @field_validator("attributes")
    @classmethod
    def _allowed_attributes(cls, value: dict[str, str]) -> dict[str, str]:
        unknown = set(value) - _ALLOWED_ATTRIBUTES
        if unknown:
            raise ValueError("Attribute is not on the allowlist.")
        return value

    @field_validator("occurred_at")
    @classmethod
    def _sane_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("occurred_at must carry a timezone.")
        value = value.astimezone(UTC)
        now = datetime.now(UTC)
        if value > now + MAX_FUTURE_SKEW:
            raise ValueError("occurred_at is in the future.")
        if value < now - MAX_AGE:
            raise ValueError("occurred_at is older than retention.")
        return value


class IngestStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backlog: int = Field(default=0, ge=0)
    dropped: int = Field(default=0, ge=0)
    delivery_failures: int = Field(default=0, ge=0)


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    environment: _Code
    stats: IngestStats = Field(default_factory=IngestStats)
    # Validated one by one, so a bad event cannot sink its batch.
    events: list[dict] = Field(default_factory=list, max_length=MAX_BATCH)

    @field_validator("source")
    @classmethod
    def _known_source(cls, value: str) -> str:
        if value not in SOURCES:
            raise ValueError("Unknown source service.")
        return value


class IncidentTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["TRIAGED", "CONFIRMED", "FALSE_POSITIVE", "MITIGATING", "RESOLVED", "CLOSED"]
    note: str = Field(min_length=3, max_length=500)
