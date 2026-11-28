"""Forwards recovery audit events to security intelligence.

`resource_ref` is the same wallet subject the risk check uses, so the fraud
service can answer from this wallet's real history. A cursor over `occurredAt`
advances only after a batch is accepted.
"""

import asyncio
import hashlib
import hmac
import logging
import os
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

import httpx

from app.core.environment_policy import is_production_like

_LOGGER = logging.getLogger(__name__)

DEVELOPMENT_KEY = "local-dev-security-event-pseudonym-key-not-for-production"
DEVELOPMENT_TOKEN = "local-dev-fraud-service-token-not-for-production"
CURSOR_COLLECTION = "security_event_forwarder"
CURSOR_ID = "recovery_audit_events"
BATCH_SIZE = 200

EVENT_MAP = {
    "RECOVERY_REQUESTED": "recovery.requested",
    "RECOVERY_APPROVED": "recovery.approved",
    "RECOVERY_REJECTED": "recovery.rejected",
    "GUARDIAN_PROOF_REJECTED": "recovery.proof_rejected",
    "UNAUTHORIZED_RECOVERY_ATTEMPT": "recovery.unauthorized",
    "SECRET_SHARE_VALIDATION_FAILED": "recovery.share_invalid",
    "RECOVERY_RISK_HOLD": "recovery.risk_hold",
    "RECOVERY_POLICY_UPDATED": "recovery.policy_changed",
    "RECOVERY_POLICY_CHANGE_SCHEDULED": "recovery.policy_weakened",
    "GUARDIAN_CHANGE_SCHEDULED": "recovery.policy_weakened",
    "RECOVERY_COMPLETED": "recovery.completed",
    "RECOVERY_CANCELLED": "recovery.cancelled",
    "RECOVERY_FAILED": "recovery.failed",
    "GUARDIAN_INVITED": "guardian.changed",
    "GUARDIAN_REMOVED": "guardian.changed",
    "GUARDIAN_SUSPENDED": "guardian.changed",
}


def wallet_subject(wallet_id: str) -> str:
    return "recovery:" + sha256(wallet_id.encode()).hexdigest()[:64]


def to_security_event(document: dict[str, Any], *, key: bytes, origin: str, wallet_id: str | None) -> dict[str, Any] | None:
    event_type = EVENT_MAP.get(document.get("eventType", ""))
    if event_type is None:
        return None
    occurred = document["occurredAt"]
    occurred = occurred if occurred.tzinfo else occurred.replace(tzinfo=UTC)
    actor = document.get("actorId")
    actor_ref = f"actor:{hmac.new(key, actor.encode(), hashlib.sha256).hexdigest()[:40]}" if actor else None
    return {
        "event_id": str(document["_id"]).replace("recovery_audit_", "recovery:"),
        "occurred_at": occurred.isoformat(),
        "source_service": "recovery-service",
        "source_component": "audit-forwarder",
        "event_type": event_type,
        "origin": origin,
        "actor_ref": actor_ref,
        "resource_type": "wallet",
        "resource_ref": wallet_subject(wallet_id) if wallet_id else None,
        "attributes": {},
    }


class SecurityEventForwarder:
    def __init__(self, database: Any, *, base_url: str, token: str, key: bytes, origin: str, environment: str, client: httpx.Client | None = None) -> None:
        self._audit = database["recovery_audit_events"]
        self._requests = database["recovery_requests"]
        self._cursor = database[CURSOR_COLLECTION]
        self._url = f"{base_url.rstrip('/')}/api/v1/fraud/intel/ingest"
        self._token = token
        self._key = key
        self._origin = origin
        self._environment = environment
        self._client = client or httpx.Client(timeout=5.0)
        self._failures = 0

    def _wallet_of(self, document: dict[str, Any]) -> str | None:
        wallet = (document.get("metadata") or {}).get("walletId")
        if wallet:
            return str(wallet)
        request = self._requests.find_one({"_id": document.get("aggregateId")})
        return str(request["walletId"]) if request else None

    def deliver_once(self) -> int:
        row = self._cursor.find_one({"_id": CURSOR_ID}) or {}
        since = row.get("last_at")
        seen = set(row.get("last_ids", []))
        query = {"occurredAt": {"$gte": since}} if since else {}
        rows = [r for r in self._audit.find(query).sort("occurredAt", 1).limit(BATCH_SIZE) if r["_id"] not in seen]
        events = [
            event
            for event in (
                to_security_event(r, key=self._key, origin=self._origin, wallet_id=self._wallet_of(r))
                for r in rows
            )
            if event
        ]
        response = self._client.post(
            self._url,
            headers={"X-Internal-Service-Token": self._token},
            json={
                "source": "recovery-service",
                "environment": self._environment,
                "stats": {"backlog": 0, "dropped": 0, "delivery_failures": self._failures},
                "events": events,
            },
        )
        response.raise_for_status()
        if rows:
            last = rows[-1]["occurredAt"]
            self._cursor.update_one(
                {"_id": CURSOR_ID},
                {"$set": {
                    "last_at": last,
                    "last_ids": [r["_id"] for r in rows if r["occurredAt"] == last],
                    "updated_at": datetime.now(UTC),
                }},
                upsert=True,
            )
        return len(rows)

    async def run(self, stop_event: asyncio.Event, interval_seconds: float = 5.0) -> None:
        while not stop_event.is_set():
            try:
                await asyncio.to_thread(self.deliver_once)
            except Exception as error:  # An outage must not stop later retries.
                self._failures += 1
                _LOGGER.warning("Security event delivery failed (%s)", type(error).__name__)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            except TimeoutError:
                continue


def build_forwarder(database: Any, settings: Any) -> SecurityEventForwarder | None:
    token = settings.fraud_service_token
    key = os.getenv("SECURITY_EVENT_PSEUDONYM_KEY", "")
    if len(token) < 32 or len(key) < 32:
        return None
    if is_production_like(settings.environment) and (key == DEVELOPMENT_KEY or token == DEVELOPMENT_TOKEN):
        _LOGGER.error("Security event forwarding is off: development secrets in a production-like mode.")
        return None
    return SecurityEventForwarder(
        database,
        base_url=settings.fraud_base_url,
        token=token,
        key=key.encode(),
        origin=os.getenv("SECURITY_EVENT_ORIGIN", "OPERATIONAL"),
        environment=settings.environment,
    )
