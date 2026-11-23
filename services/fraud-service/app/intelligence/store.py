"""Durable intelligence store: its own database and its own Mongo principal."""

import logging
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.intelligence.rules import RULES_BY_TRIGGER, RULESET_VERSION, Rule

logger = logging.getLogger(__name__)

RETENTION_DAYS = 90
MAX_EVENT_REFS = 50
OPEN_STATUSES = ("NEW", "TRIAGED", "CONFIRMED", "MITIGATING")
TRANSITIONS = {
    "NEW": {"TRIAGED", "CONFIRMED", "FALSE_POSITIVE"},
    "TRIAGED": {"CONFIRMED", "FALSE_POSITIVE", "MITIGATING"},
    "CONFIRMED": {"MITIGATING", "RESOLVED"},
    "MITIGATING": {"RESOLVED"},
    "RESOLVED": {"CLOSED"},
    "FALSE_POSITIVE": {"CLOSED"},
    "CLOSED": set(),
}


class IntelUnavailableError(RuntimeError):
    """The store cannot answer. Callers must show that, never zero."""


class IncidentConflictError(RuntimeError):
    pass


def _hour(moment: datetime) -> datetime:
    return moment.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


class IntelStore:
    def __init__(self, database: Any) -> None:
        self.events = database["security_events"]
        self.buckets = database["event_buckets"]
        self.sources = database["event_sources"]
        self.incidents = database["incidents"]
        self.assessments = database["risk_assessments"]

    def ensure_indexes(self) -> None:
        retention = RETENTION_DAYS * 86400
        self.events.create_index([("ingested_at", ASCENDING)], expireAfterSeconds=retention, name="ttl_events")
        self.assessments.create_index([("assessed_at", ASCENDING)], expireAfterSeconds=retention, name="ttl_assessments")
        for ref in ("actor_ref", "source_ref", "resource_ref"):
            self.events.create_index(
                [(ref, ASCENDING), ("event_type", ASCENDING), ("origin", ASCENDING), ("occurred_at", DESCENDING)],
                name=f"ix_events_{ref}",
            )
        self.events.create_index([("event_type", ASCENDING), ("occurred_at", DESCENDING)], name="ix_events_type")
        self.buckets.create_index([("origin", ASCENDING), ("hour", DESCENDING)], name="ix_buckets_hour")
        self.incidents.create_index(
            [("dedupe_key", ASCENDING)], unique=True,
            partialFilterExpression={"open": True}, name="uq_incident_open",
        )
        self.incidents.create_index([("origin", ASCENDING), ("last_observed_at", DESCENDING)], name="ix_incidents_recent")

    # ---- ingest
    def ingest(self, event: dict[str, Any], now: datetime) -> bool:
        """Returns False for a duplicate, which then changes no count."""
        document = {**event, "_id": event["event_id"], "ingested_at": now}
        try:
            self.events.insert_one(document)
        except DuplicateKeyError:
            return False
        hour = _hour(event["occurred_at"])
        self.buckets.update_one(
            {"_id": f'{hour.isoformat()}|{event["origin"]}|{event["event_type"]}'},
            {
                "$inc": {"count": event.get("count", 1)},
                "$setOnInsert": {"hour": hour, "origin": event["origin"], "event_type": event["event_type"]},
            },
            upsert=True,
        )
        for rule in RULES_BY_TRIGGER.get(event["event_type"], ()):
            self._apply_rule(rule, event, now)
        return True

    def _count(self, rule: Rule, event: dict[str, Any], key: str) -> int:
        since = event["occurred_at"] - timedelta(seconds=rule.window_seconds)
        return self.events.count_documents({
            rule.group: key,
            "event_type": {"$in": list(rule.counted_types)},
            "origin": event["origin"],
            "occurred_at": {"$gte": since, "$lte": event["occurred_at"]},
        })

    def _apply_rule(self, rule: Rule, event: dict[str, Any], now: datetime) -> None:
        key = event.get(rule.group)
        if not key:
            return
        count = self._count(rule, event, key)
        if count < rule.threshold:
            return
        dedupe = f'{event["origin"]}|{rule.rule_id}|{key}'
        update = self.incidents.update_one(
            {"dedupe_key": dedupe, "open": True},
            {
                "$inc": {"signal_count": 1, "suppressed_alerts": 1},
                "$set": {"last_observed_at": event["occurred_at"]},
                "$push": {"event_refs": {"$each": [event["event_id"]], "$slice": -MAX_EVENT_REFS}},
            },
        )
        if update.matched_count:
            return
        incident = {
            "_id": f"inc_{uuid.uuid4().hex}",
            "dedupe_key": dedupe,
            "open": True,
            "origin": event["origin"],
            "status": "NEW",
            "detection_state": rule.state,
            "rule_id": rule.rule_id,
            "rule_version": RULESET_VERSION,
            "title": rule.title,
            "category": rule.category,
            "severity": rule.severity,
            "confidence": rule.confidence,
            "explanation": rule.explanation,
            "group": rule.group,
            "subject_ref": key,
            "service": event["source_service"],
            "threshold": rule.threshold,
            "window_seconds": rule.window_seconds,
            "observed_count": count,
            "signal_count": 1,
            "suppressed_alerts": 0,
            "event_refs": [event["event_id"]],
            "first_observed_at": event["occurred_at"],
            "last_observed_at": event["occurred_at"],
            "created_at": now,
            "delivery": "IN_APP_ONLY",
            "history": [{"status": "NEW", "at": now, "by": "detection", "note": f"{rule.rule_id} threshold reached."}],
        }
        try:
            self.incidents.insert_one(incident)
        except DuplicateKeyError:
            pass  # Another writer opened it first; its counters carry on.

    def record_source(self, source: str, environment: str, stats: dict[str, int], accepted: int, duplicates: int, rejected: int, now: datetime) -> None:
        self.sources.update_one(
            {"_id": source},
            {
                "$set": {"environment": environment, "last_seen_at": now, "backlog": stats["backlog"], "dropped": stats["dropped"], "delivery_failures": stats["delivery_failures"]},
                "$inc": {"accepted": accepted, "duplicates": duplicates, "rejected": rejected},
            },
            upsert=True,
        )

    # ---- reads
    def bucket_rows(self, origin: str, since: datetime) -> list[dict[str, Any]]:
        return list(self.buckets.find({"origin": origin, "hour": {"$gte": _hour(since)}}).sort("hour", ASCENDING).limit(50_000))

    def source_rows(self) -> list[dict[str, Any]]:
        return list(self.sources.find({}).sort("_id", ASCENDING).limit(20))

    def seen_types(self, origin: str) -> set[str]:
        since = datetime.now(UTC) - timedelta(days=RETENTION_DAYS)
        return {row["event_type"] for row in self.bucket_rows(origin, since)}

    def count_subject(self, resource_ref: str, types: list[str], since: datetime) -> int:
        return self.events.count_documents({
            "resource_ref": resource_ref, "event_type": {"$in": types}, "occurred_at": {"$gte": since},
        })

    def latest_event_lag(self, origin: str) -> float | None:
        row = next(iter(self.events.find({"origin": origin, "event_type": {"$ne": "api.request"}}).sort("ingested_at", DESCENDING).limit(1)), None)
        if row is None:
            return None
        ingested = row["ingested_at"] if row["ingested_at"].tzinfo else row["ingested_at"].replace(tzinfo=UTC)
        occurred = row["occurred_at"] if row["occurred_at"].tzinfo else row["occurred_at"].replace(tzinfo=UTC)
        return max((ingested - occurred).total_seconds(), 0.0)

    def incident_rows(self, origin: str, limit: int, offset: int = 0) -> list[dict[str, Any]]:
        return list(self.incidents.find({"origin": origin}).sort("last_observed_at", DESCENDING).skip(offset).limit(limit))

    def get_incident(self, incident_id: str) -> dict[str, Any] | None:
        return self.incidents.find_one({"_id": incident_id})

    def transition(self, incident_id: str, status: str, note: str, actor: str, now: datetime) -> dict[str, Any]:
        incident = self.get_incident(incident_id)
        if incident is None:
            raise KeyError(incident_id)
        if status not in TRANSITIONS[incident["status"]]:
            raise IncidentConflictError(f'{incident["status"]} cannot become {status}.')
        result = self.incidents.update_one(
            {"_id": incident_id, "status": incident["status"]},
            {
                "$set": {"status": status, "open": status in OPEN_STATUSES, "updated_at": now, "owner": actor},
                "$push": {"history": {"status": status, "at": now, "by": actor, "note": note}},
            },
        )
        if not result.matched_count:
            raise IncidentConflictError("The incident changed; reload it.")
        return self.get_incident(incident_id)

    def record_assessment(self, assessment: dict[str, Any]) -> None:
        self.assessments.insert_one(assessment)

    def assessment_rows(self, since: datetime, limit: int = 1000) -> list[dict[str, Any]]:
        return list(self.assessments.find({"assessed_at": {"$gte": since}}).sort("assessed_at", DESCENDING).limit(limit))

    def incident_label_counts(self, origin: str) -> dict[str, int]:
        return {
            status: self.incidents.count_documents({"origin": origin, "status": status})
            for status in ("CONFIRMED", "FALSE_POSITIVE")
        }


class IntelRuntime:
    """One lazy connection. No URI is NOT_CONFIGURED; a failed one is UNAVAILABLE."""

    def __init__(self) -> None:
        self.uri = os.getenv("FRAUD_INTEL_MONGO_URI", "")
        self.database = os.getenv("FRAUD_INTEL_MONGO_DATABASE", "secure_security_intel")
        self.default_origin = os.getenv("INTEL_ANALYTICS_ORIGIN", "OPERATIONAL")
        self._store: IntelStore | None = None

    @property
    def configured(self) -> bool:
        return bool(self.uri) or self._store is not None

    def use(self, store: IntelStore | None) -> None:
        self._store = store

    def store(self) -> IntelStore:
        if self._store is not None:
            return self._store
        if not self.uri:
            raise IntelUnavailableError("NOT_CONFIGURED")
        try:
            client = MongoClient(self.uri, serverSelectionTimeoutMS=2000, tz_aware=True)
            client.admin.command("ping")
            store = IntelStore(client[self.database])
            store.ensure_indexes()
        except PyMongoError as error:
            logger.warning("Intelligence store unavailable (%s)", type(error).__name__)
            raise IntelUnavailableError("UNAVAILABLE") from error
        self._store = store
        return store


runtime = IntelRuntime()
