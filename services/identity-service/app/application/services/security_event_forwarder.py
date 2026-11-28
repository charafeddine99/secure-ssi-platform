"""Forwards the durable audit trail to security intelligence.

The audit collection is the outbox: a cursor over `chainSeq` advances only after
the fraud service accepts a batch, so an outage delays events and loses none.
Only allowlisted, pseudonymised fields leave this service.
"""

import asyncio
import hashlib
import hmac
import logging
import os
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from app.config.environment_policy import is_production_like

_LOGGER = logging.getLogger(__name__)

DEVELOPMENT_KEY = "local-dev-security-event-pseudonym-key-not-for-production"
DEVELOPMENT_TOKEN = "local-dev-fraud-service-token-not-for-production"
CURSOR_COLLECTION = "security_event_forwarder"
CURSOR_ID = "audit_events"
BATCH_SIZE = 200
_CODE = re.compile(r"^[A-Za-z0-9_.:/-]{1,64}$")

EVENT_MAP = {
    "LOGIN_SUCCESS": "auth.login.success",
    "LOGIN_FAILURE": "auth.login.failure",
    "STEP_UP_SUCCEEDED": "auth.stepup.success",
    "STEP_UP_FAILED": "auth.stepup.failure",
    "VC_SIGNED": "oid4vci.credential.issued",
    "PRESENTATION_CREATED": "oid4vp.request.created",
    "PRESENTATION_VERIFIED": "presentation.verified",
    "PRESENTATION_REJECTED": "presentation.rejected",
    "PRESENTATION_CONSENT_REJECTED": "consent.rejected",
    "CONSENT_REJECTED": "consent.rejected",
    "CREDENTIAL_REVOKED": "credential.revoked",
    "HOLDER_OWNERSHIP_REJECTED": "wallet.ownership.rejected",
    "CHALLENGE_REJECTED": "wallet.challenge.rejected",
    "WALLET_BACKUP_CREATED": "wallet.backup.created",
    "WALLET_RESTORE_COMPLETED": "wallet.restore.completed",
    "WALLET_RESTORE_REJECTED": "wallet.restore.rejected",
    "KEY_ROTATION_COMPLETED": "key.rotation.completed",
    "KEY_ROTATION_FAILED": "key.rotation.failed",
    "MANAGED_KEY_COMPROMISED": "key.compromised",
    "MANAGED_KEY_DESTROYED": "key.destroyed",
    "UNAUTHORIZED_KEY_ACCESS": "key.unauthorized_access",
    "MANAGED_KEY_SIGNING_REJECTED": "key.signing_rejected",
    "KEY_PROVIDER_MISMATCH": "key.provider_mismatch",
    "TRUST_RECORD_CREATED": "trust.changed",
    "TRUST_RECORD_UPDATED": "trust.changed",
    "TRUST_RECORD_DEACTIVATED": "trust.changed",
    "TRUST_RECORD_REVOKED": "trust.changed",
    "USER_ISSUER_SCOPE_UPDATED": "admin.scope_changed",
    "ACCOUNT_REGISTERED": "account.registered",
    "ONBOARDING_REQUESTED": "onboarding.requested",
    "ONBOARDING_APPROVED": "onboarding.approved",
    "ONBOARDING_REJECTED": "onboarding.rejected",
    "ADMIN_INVITED": "admin.invited",
    "PLATFORM_BACKUP_CREATED": "backup.created",
    "PLATFORM_BACKUP_FAILED": "backup.failed",
    "PLATFORM_BACKUP_VERIFIED": "backup.verified",
    "PLATFORM_BACKUP_VERIFY_FAILED": "backup.verify_failed",
    "PLATFORM_RESTORE_PREVIEWED": "restore.previewed",
}
_LOGIN_TYPES = ("LOGIN_SUCCESS", "LOGIN_FAILURE")
_ATTRIBUTES = {"policy_result": "policy_result", "reason": "reason_code", "reason_code": "reason_code"}


def pseudonym(key: bytes, kind: str, value: str | None) -> str | None:
    if not value:
        return None
    return f"{kind}:{hmac.new(key, value.encode(), hashlib.sha256).hexdigest()[:40]}"


def to_security_event(document: dict[str, Any], *, key: bytes, origin: str) -> dict[str, Any] | None:
    """Metadata is not copied: only named fields with code-shaped values pass."""
    event_type = EVENT_MAP.get(document.get("eventType", ""))
    if event_type is None:
        return None
    occurred = document["createdAt"]
    occurred = occurred if occurred.tzinfo else occurred.replace(tzinfo=UTC)
    metadata = document.get("metadata") or {}
    attributes = {
        target: str(metadata[name])
        for name, target in _ATTRIBUTES.items()
        if name in metadata and _CODE.fullmatch(str(metadata[name]))
    }
    is_login = document["eventType"] in _LOGIN_TYPES
    return {
        "event_id": f'audit:{document["_id"]}',
        "occurred_at": occurred.isoformat(),
        "source_service": "identity-service",
        "source_component": "audit-forwarder",
        "event_type": event_type,
        "origin": origin,
        "actor_ref": pseudonym(key, "actor", document.get("subjectId") if is_login else document.get("actorId")),
        "resource_ref": None if is_login else pseudonym(key, "res", document.get("subjectId")),
        "correlation_ref": pseudonym(key, "corr", document.get("correlationId")),
        "attributes": attributes,
    }


class SecurityEventForwarder:
    def __init__(self, database: Any, *, base_url: str, token: str, key: bytes, origin: str, environment: str, client: httpx.Client | None = None) -> None:
        self._audit = database["audit_events"]
        self._cursor = database[CURSOR_COLLECTION]
        self._url = f"{base_url.rstrip('/')}/api/v1/fraud/intel/ingest"
        self._token = token
        self._key = key
        self._origin = origin
        self._environment = environment
        self._client = client or httpx.Client(timeout=5.0)
        self._failures = 0

    def _position(self) -> int:
        row = self._cursor.find_one({"_id": CURSOR_ID})
        return int(row["last_seq"]) if row else 0

    def _head(self) -> int:
        row = next(iter(self._audit.find({"chainSeq": {"$gte": 1}}).sort("chainSeq", -1).limit(1)), None)
        return int(row["chainSeq"]) if row else 0

    def deliver_once(self) -> int:
        position = self._position()
        rows = list(self._audit.find({"chainSeq": {"$gt": position}}).sort("chainSeq", 1).limit(BATCH_SIZE))
        events = [e for e in (to_security_event(r, key=self._key, origin=self._origin) for r in rows) if e]
        last = rows[-1]["chainSeq"] if rows else position
        response = self._client.post(
            self._url,
            headers={"X-Internal-Service-Token": self._token},
            json={
                "source": "identity-service",
                "environment": self._environment,
                "stats": {"backlog": max(self._head() - last, 0), "dropped": 0, "delivery_failures": self._failures},
                "events": events,
            },
        )
        response.raise_for_status()
        if rows:
            self._cursor.update_one(
                {"_id": CURSOR_ID},
                {"$set": {"last_seq": last, "updated_at": datetime.now(UTC)}},
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


def build_forwarder(database: Any, environment: str) -> SecurityEventForwarder | None:
    """Returns None when not safely configured; the source then shows as MISSING."""
    token = os.getenv("FRAUD_INTERNAL_SERVICE_TOKEN", "")
    key = os.getenv("SECURITY_EVENT_PSEUDONYM_KEY", "")
    if len(token) < 32 or len(key) < 32:
        return None
    if is_production_like(environment) and (key == DEVELOPMENT_KEY or token == DEVELOPMENT_TOKEN):
        _LOGGER.error("Security event forwarding is off: development secrets in a production-like mode.")
        return None
    return SecurityEventForwarder(
        database,
        base_url=os.getenv("FRAUD_SERVICE_URL", "http://fraud-service:8000"),
        token=token,
        key=key.encode(),
        origin=os.getenv("SECURITY_EVENT_ORIGIN", "OPERATIONAL"),
        environment=environment,
    )
