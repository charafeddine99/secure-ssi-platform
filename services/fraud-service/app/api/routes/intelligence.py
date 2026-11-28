"""Security intelligence API. Admin reads; trusted services write."""

from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import ValidationError
from pymongo.errors import PyMongoError

from app.core.security import FraudPrincipal, require_admin, require_incident_writer, require_internal_service, spend_step_up
from app.intelligence.analytics import anomalies, metrics, monitoring_coverage, posture, source_health
from app.intelligence.rules import RULES, RULESET_VERSION
from app.intelligence.schema import IncidentTransition, IngestRequest, SecurityEvent
from app.intelligence.store import TRANSITIONS, IncidentConflictError, IntelStore, IntelUnavailableError, runtime
from app.intelligence.taxonomy import EVENT_TYPES

router = APIRouter(prefix="/api/v1/fraud/intel", tags=["Security Intelligence"])

MAX_INGEST_BYTES = 1_048_576
Origin = Literal["OPERATIONAL", "SYNTHETIC_TEST"]


def _now() -> datetime:
    return datetime.now(UTC)


def _read(action: Callable[[IntelStore], dict[str, Any]]) -> dict[str, Any]:
    """Outage is a 503 with a reason, so no view can show it as zero."""
    try:
        return action(runtime.store())
    except IntelUnavailableError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Intelligence store {error}.") from error
    except PyMongoError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Intelligence store UNAVAILABLE.") from error


def _origin(origin: Origin | None) -> str:
    return origin or runtime.default_origin


def _iso(value: Any) -> Any:
    if isinstance(value, datetime):
        return (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()
    if isinstance(value, list):
        return [_iso(item) for item in value]
    if isinstance(value, dict):
        return {key: _iso(item) for key, item in value.items()}
    return value


def _incident(row: dict[str, Any]) -> dict[str, Any]:
    public = {k: v for k, v in row.items() if k not in ("_id", "dedupe_key", "open")}
    return _iso({"incident_id": row["_id"], "next_statuses": sorted(TRANSITIONS[row["status"]]), **public})


@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
async def ingest(
    request: Request,
    _principal: FraudPrincipal = Depends(require_internal_service),
) -> dict[str, Any]:
    body = await request.body()
    if len(body) > MAX_INGEST_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail="Batch is too large.")
    try:
        batch = IngestRequest.model_validate_json(body)
    except ValidationError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Batch is invalid.") from error
    accepted = duplicates = rejected = 0
    now = _now()

    def write(store: IntelStore) -> dict[str, Any]:
        nonlocal accepted, duplicates, rejected
        for raw in batch.events:
            try:
                event = SecurityEvent.model_validate(raw)
            except ValidationError:
                rejected += 1
                continue
            if event.source_service != batch.source:
                rejected += 1
                continue
            if store.ingest(event.model_dump(), now):
                accepted += 1
            else:
                duplicates += 1
        store.record_source(batch.source, batch.environment, batch.stats.model_dump(), accepted, duplicates, rejected, now)
        return {"accepted": accepted, "duplicates": duplicates, "rejected": rejected}

    return _read(write)


@router.get("/health")
async def health(
    origin: Origin | None = None,
    _principal: FraudPrincipal = Depends(require_admin),
) -> dict[str, Any]:
    now = _now()
    selected = _origin(origin)

    def view(store: IntelStore) -> dict[str, Any]:
        sources = source_health(store, now)
        return {
            "store": "AVAILABLE",
            "origin": selected,
            "as_of": now.isoformat(),
            "state": "HEALTHY" if all(s["state"] == "HEALTHY" for s in sources) else "DEGRADED",
            "sources": sources,
            "last_event_lag_seconds": store.latest_event_lag(selected),
            "monitoring": monitoring_coverage(store, selected, now),
        }

    return _read(view)


@router.get("/metrics")
async def get_metrics(
    hours: int = Query(24, ge=1, le=720),
    origin: Origin | None = None,
    _principal: FraudPrincipal = Depends(require_admin),
) -> dict[str, Any]:
    now = _now()
    selected = _origin(origin)
    return _read(lambda store: {"origin": selected, "as_of": now.isoformat(), **metrics(store, selected, hours, now)})


@router.get("/anomalies")
async def get_anomalies(
    origin: Origin | None = None,
    _principal: FraudPrincipal = Depends(require_admin),
) -> dict[str, Any]:
    now = _now()
    selected = _origin(origin)
    return _read(lambda store: {"origin": selected, "as_of": now.isoformat(), **anomalies(store, selected, now)})


@router.get("/incidents")
async def list_incidents(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=10_000),
    origin: Origin | None = None,
    _principal: FraudPrincipal = Depends(require_admin),
) -> dict[str, Any]:
    selected = _origin(origin)
    return _read(lambda store: {"origin": selected, "items": [_incident(r) for r in store.incident_rows(selected, limit, offset)]})


@router.post("/incidents/{incident_id}/transition")
async def transition_incident(
    incident_id: str,
    payload: IncidentTransition,
    principal: FraudPrincipal = Depends(require_incident_writer),
    authorization: str | None = Header(default=None),
    step_up_token: str | None = Header(default=None, alias="X-Step-Up-Token"),
) -> dict[str, Any]:
    # Confirming or dismissing a case is the decision that matters, so it needs fresh proof.
    if payload.status in ("CONFIRMED", "FALSE_POSITIVE"):
        await spend_step_up(authorization, step_up_token, action="incident.review", resource=incident_id)

    def write(store: IntelStore) -> dict[str, Any]:
        try:
            return _incident(store.transition(incident_id, payload.status, payload.note, principal.subject, _now()))
        except KeyError as error:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Incident not found.") from error
        except IncidentConflictError as error:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error)) from error

    return _read(write)


@router.get("/risk")
async def risk_summary(
    hours: int = Query(24, ge=1, le=720),
    _principal: FraudPrincipal = Depends(require_admin),
) -> dict[str, Any]:
    since = _now() - timedelta(hours=hours)

    def view(store: IntelStore) -> dict[str, Any]:
        rows = store.assessment_rows(since)
        levels: dict[str, int] = {}
        types: dict[str, int] = {}
        for row in rows:
            levels[row["risk_level"]] = levels.get(row["risk_level"], 0) + 1
            types[row["assessment_type"]] = types.get(row["assessment_type"], 0) + 1
        recent = [{k: v for k, v in row.items() if k != "_id"} for row in rows[:25]]
        return {
            "hours": hours,
            "assessments": len(rows),
            "truncated": len(rows) >= 1000,
            "levels": levels,
            "types": types,
            "score_semantics": "Rule-based risk score from 0 to 1. Uncalibrated: it is not a probability.",
            "recent": _iso(recent),
        }

    return _read(view)


@router.get("/rules")
async def list_rules(_principal: FraudPrincipal = Depends(require_admin)) -> dict[str, Any]:
    return {
        "ruleset_version": RULESET_VERSION,
        "change_control": "Rules change only through a code release. There is no runtime editor.",
        "event_types": len(EVENT_TYPES),
        "rules": [
            {
                "rule_id": r.rule_id, "title": r.title, "category": r.category, "state": r.state,
                "severity": r.severity, "confidence": r.confidence, "trigger": list(r.trigger),
                "counted": list(r.counted_types), "group": r.group, "threshold": r.threshold,
                "window_seconds": r.window_seconds, "attack": list(r.attack), "reference": r.reference,
                "explanation": r.explanation,
            }
            for r in RULES
        ],
    }


@router.get("/posture")
async def get_posture(
    origin: Origin | None = None,
    _principal: FraudPrincipal = Depends(require_admin),
) -> dict[str, Any]:
    selected = _origin(origin)
    now = _now()
    try:
        store = runtime.store()
    except IntelUnavailableError:
        store = None  # Control coverage is still true; monitoring shows as unknown.
    return {"origin": selected, "as_of": now.isoformat(), **posture(store, selected, now)}


@router.get("/model")
async def model_status(
    origin: Origin | None = None,
    _principal: FraudPrincipal = Depends(require_admin),
) -> dict[str, Any]:
    selected = _origin(origin)
    return _read(lambda store: {
        "model_status": "NOT_TRAINED",
        "training_data_status": "INSUFFICIENT_OR_NOT_AUTHORIZED",
        "detection_mode": "RULE_BASED_AND_STATISTICAL",
        "origin": selected,
        "reviewed_labels": store.incident_label_counts(selected),
        "metrics": None,
        "explanation": "No model is trained or loaded. Human-reviewed incidents are the only label source, and they are not yet a dataset.",
    })
