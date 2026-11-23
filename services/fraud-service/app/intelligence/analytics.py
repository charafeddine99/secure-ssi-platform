"""Metrics, baselines, source health and control coverage, from stored data only."""

import json
import statistics
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.intelligence.store import IntelStore
from app.intelligence.taxonomy import EVENT_TYPES, REQUIRED_DOMAINS, SOURCES

SOURCE_STALE_SECONDS = 180
ANOMALY_METHOD = "median-mad-hourly-1.0"
BASELINE_DAYS = 7
MIN_BASELINE_HOURS = 48
MIN_OBSERVED_COUNT = 10
MODIFIED_Z_THRESHOLD = 3.5
MAD_FLOOR = 1.0
ANOMALY_SERIES = {
    "Failed sign-ins": ("auth.login.failure", "gateway.login.rejected"),
    "Refused calls": ("authz.denied",),
    "Rate-limited calls": ("api.rate_limited",),
    "Rejected presentations": ("presentation.rejected", "oid4vp.request.failure"),
    "Issuance failures": ("oid4vci.token.failure", "oid4vci.credential.failure"),
    "Recovery signals": ("recovery.proof_rejected", "recovery.unauthorized", "recovery.rejected"),
    "API requests": ("api.request",),
}
RATES = (
    ("Sign-in failure rate", "percent", 100, ("auth.login.failure",), ("auth.login.success", "auth.login.failure")),
    ("Step-up failure rate", "percent", 100, ("auth.stepup.failure",), ("auth.stepup.success", "auth.stepup.failure")),
    ("Rate-limited calls", "per 1,000 requests", 1000, ("api.rate_limited",), ("api.request",)),
    ("Refused calls", "per 1,000 requests", 1000, ("authz.denied",), ("api.request",)),
    ("OID4VCI failures", "per 1,000 requests", 1000, ("oid4vci.token.failure", "oid4vci.credential.failure"), ("api.request",)),
    ("Rejected presentations", "percent", 100, ("presentation.rejected",), ("presentation.rejected", "presentation.verified")),
    ("Recovery signals", "percent", 100, ("recovery.proof_rejected", "recovery.unauthorized"), ("recovery.requested",)),
)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def source_health(store: IntelStore, now: datetime) -> list[dict[str, Any]]:
    rows = {row["_id"]: row for row in store.source_rows()}
    result = []
    for source in SOURCES:
        row = rows.get(source)
        if row is None:
            result.append({"source": source, "state": "MISSING", "last_seen_at": None, "age_seconds": None, "backlog": None, "dropped": None, "rejected": None, "accepted": None, "delivery_failures": None})
            continue
        age = (now - _aware(row["last_seen_at"])).total_seconds()
        result.append({
            "source": source,
            "state": "HEALTHY" if age <= SOURCE_STALE_SECONDS else "STALE",
            "last_seen_at": _aware(row["last_seen_at"]).isoformat(),
            "age_seconds": round(age),
            "backlog": row.get("backlog", 0),
            "dropped": row.get("dropped", 0),
            "rejected": row.get("rejected", 0),
            "accepted": row.get("accepted", 0),
            "delivery_failures": row.get("delivery_failures", 0),
        })
    return result


def monitoring_coverage(store: IntelStore, origin: str, now: datetime) -> dict[str, Any]:
    """A domain counts only if its producer is healthy and its events were really seen."""
    health = {row["source"]: row["state"] for row in source_health(store, now)}
    seen = store.seen_types(origin)
    domains = []
    for name, (producer, types) in REQUIRED_DOMAINS.items():
        observed = sorted(seen.intersection(types))
        if health.get(producer) != "HEALTHY":
            state = f'SOURCE_{health.get(producer, "MISSING")}'
        elif not observed:
            state = "NO_EVENTS_SEEN"
        else:
            state = "VERIFIED"
        domains.append({"domain": name, "producer": producer, "expected": list(types), "observed": observed, "state": state})
    verified = sum(1 for item in domains if item["state"] == "VERIFIED")
    return {
        "numerator": verified,
        "denominator": len(domains),
        "percent": round(100 * verified / len(domains), 1),
        "domains": domains,
    }


def _totals(rows: list[dict[str, Any]]) -> Counter:
    totals: Counter = Counter()
    for row in rows:
        totals[row["event_type"]] += row["count"]
    return totals


def metrics(store: IntelStore, origin: str, hours: int, now: datetime) -> dict[str, Any]:
    since = now - timedelta(hours=hours)
    rows = store.bucket_rows(origin, since)
    totals = _totals(rows)
    rates = []
    for name, unit, scale, numerator_types, denominator_types in RATES:
        numerator = sum(totals[t] for t in numerator_types)
        denominator = sum(totals[t] for t in denominator_types)
        rates.append({
            "name": name, "unit": unit, "numerator": numerator, "denominator": denominator,
            "numerator_types": list(numerator_types), "denominator_types": list(denominator_types),
            "value": round(scale * numerator / denominator, 2) if denominator else None,
        })
    by_category: Counter = Counter()
    for event_type, count in totals.items():
        if EVENT_TYPES[event_type].outcome in ("FAILURE", "DENIED"):
            by_category[EVENT_TYPES[event_type].category] += count
    return {
        "hours": hours,
        "window_start": since.isoformat(),
        "window_end": now.isoformat(),
        "rates": rates,
        "raw_signals_by_category": [{"category": k, "count": v} for k, v in by_category.most_common()],
        "event_counts": [{"event_type": k, "count": v} for k, v in sorted(totals.items())],
        "hourly": _hourly(rows),
    }


def _hourly(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    series: dict[str, Counter] = {}
    for row in rows:
        if EVENT_TYPES[row["event_type"]].outcome in ("FAILURE", "DENIED"):
            hour = _aware(row["hour"]).isoformat()
            series.setdefault(hour, Counter())["signals"] += row["count"]
    return [{"hour": hour, "signals": values["signals"]} for hour, values in sorted(series.items())]


def anomalies(store: IntelStore, origin: str, now: datetime) -> dict[str, Any]:
    """Robust baseline per series. Too little history is reported, never guessed."""
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    rows = store.bucket_rows(origin, current_hour - timedelta(days=BASELINE_DAYS))
    first_seen = min((_aware(row["hour"]) for row in rows), default=None)
    per_hour: dict[str, Counter] = {}
    for row in rows:
        per_hour.setdefault(_aware(row["hour"]).isoformat(), Counter())[row["event_type"]] += row["count"]
    baseline_hours = []
    cursor = current_hour - timedelta(hours=1)
    while first_seen is not None and cursor >= first_seen and len(baseline_hours) < BASELINE_DAYS * 24:
        baseline_hours.append(cursor.isoformat())
        cursor -= timedelta(hours=1)
    items = []
    for name, types in ANOMALY_SERIES.items():
        values = [sum(per_hour.get(hour, Counter())[t] for t in types) for hour in baseline_hours]
        current = sum(per_hour.get(current_hour.isoformat(), Counter())[t] for t in types)
        item: dict[str, Any] = {
            "series": name, "event_types": list(types), "method": ANOMALY_METHOD,
            "baseline_hours": len(values), "required_hours": MIN_BASELINE_HOURS,
            "current_hour": current_hour.isoformat(), "current_count": current,
            "threshold": MODIFIED_Z_THRESHOLD, "minimum_count": MIN_OBSERVED_COUNT,
        }
        if len(values) < MIN_BASELINE_HOURS:
            items.append({**item, "state": "INSUFFICIENT_BASELINE", "median": None, "mad": None, "modified_z": None})
            continue
        median = statistics.median(values)
        mad = statistics.median(abs(value - median) for value in values)
        z = 0.6745 * (current - median) / max(mad, MAD_FLOOR)
        anomalous = z >= MODIFIED_Z_THRESHOLD and current >= MIN_OBSERVED_COUNT
        items.append({**item, "state": "ANOMALY" if anomalous else "NORMAL", "median": median, "mad": mad, "modified_z": round(z, 2)})
    return {"method": ANOMALY_METHOD, "baseline_days": BASELINE_DAYS, "series": items}


COVERAGE_FILE = Path(__file__).parent / "data" / "control_coverage.json"
EVIDENCE_REVIEW_DAYS = 30


def posture(store: IntelStore | None, origin: str, now: datetime) -> dict[str, Any]:
    snapshot = json.loads(COVERAGE_FILE.read_text(encoding="utf-8"))
    controls = [c for c in snapshot["controls"] if c["applicable"]]
    denominator = len(controls)
    implemented = [c for c in controls if c["level"] in ("L1", "L2", "L3", "L4")]
    verified = [c for c in controls if c["level"] in ("L3", "L4")]
    fresh_cutoff = (now - timedelta(days=EVIDENCE_REVIEW_DAYS)).date().isoformat()
    fresh = [c for c in verified if c["evidence_date"] >= fresh_cutoff]
    tests = snapshot["tests"]
    executed = tests["passed"] + tests["failed"]
    pct = lambda n, d: round(100 * n / d, 1) if d else None  # noqa: E731
    monitoring = monitoring_coverage(store, origin, now) if store is not None else None
    return {
        "matrix_version": snapshot["matrix_version"],
        "generated_on": snapshot["generated_on"],
        "source": snapshot["source"],
        "evidence_review_days": EVIDENCE_REVIEW_DAYS,
        "implementation_coverage": {"numerator": len(implemented), "denominator": denominator, "percent": pct(len(implemented), denominator)},
        "verified_control_coverage": {"numerator": len(verified), "denominator": denominator, "percent": pct(len(verified), denominator)},
        "evidence_freshness": {"numerator": len(fresh), "denominator": len(verified), "percent": pct(len(fresh), len(verified))},
        "test_pass_rate": {"numerator": tests["passed"], "denominator": executed, "percent": pct(tests["passed"], executed), "failed": tests["failed"], "skipped": tests["skipped"], "not_run": tests["not_run"]},
        "monitoring_coverage": monitoring,
        "open_findings": snapshot["open_findings"],
        "not_verified": [{"id": c["id"], "level": c["level"], "gap": c["gap"]} for c in controls if c["level"] not in ("L3", "L4")],
    }
