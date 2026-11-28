"""One honest answer to "may this deployment take traffic?".

A blocker makes a production-like deployment unready. In development the same
findings are warnings, so the page still tells the truth without stopping work.
Codes only: nothing here may carry a secret or a connection string.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.config.environment_policy import is_production_like
from app.domain.persistence import PersistenceUnavailableError


@dataclass(frozen=True)
class ReadinessReport:
    environment: str
    ready: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    details: dict[str, Any]


def evaluate_readiness(
    *,
    environment: str,
    signing_uses_development_keys: bool,
    signing_providers: Iterable[Any],
    holder_providers: Iterable[Any],
    ledger: Any,
    ledger_settings: Any,
    backup: Any,
    backup_settings: Any,
    step_up_required: bool,
    clock: Callable[[], datetime] | None = None,
) -> ReadinessReport:
    now = (clock or (lambda: datetime.now(UTC)))().astimezone(UTC)
    findings: list[str] = []
    details: dict[str, Any] = {}

    if signing_uses_development_keys:
        findings.append("SIGNING_DEVELOPMENT_KEYS")
    remote = [item for item in signing_providers if hasattr(item, "is_available")]
    holders = list(holder_providers)
    if not holders or not all(item.production_ready for item in holders):
        findings.append("HOLDER_KEYS_NOT_IN_KMS")
    if not all(item.production_ready for item in remote):
        findings.append("KMS_NOT_PRODUCTION_READY")
    for provider in (*remote, *holders):
        if provider.production_ready and not provider.is_available():
            findings.append("KMS_UNAVAILABLE")
            break
    details["keyCustody"] = {
        "issuer": "DEVELOPMENT" if signing_uses_development_keys else "REMOTE_KMS",
        "holder": sorted(getattr(item, "name", "unknown") for item in holders),
        "liveKms": "NOT_VERIFIED",
    }

    head = None
    try:
        head = ledger.current_head()
    except PersistenceUnavailableError as error:
        findings.append("REVOCATION_LEDGER_UNAVAILABLE")
        details["ledgerError"] = getattr(error, "code", "UNAVAILABLE")
    if not ledger_settings.separate_authority:
        findings.append("REVOCATION_LEDGER_SHARED_AUTHORITY")
    if ledger_settings.anchor_path is None:
        findings.append("REVOCATION_ANCHOR_NOT_CONFIGURED")
    if ledger_settings.uses_development_key:
        findings.append("REVOCATION_LEDGER_DEVELOPMENT_KEY")
    details["ledger"] = {
        "sequence": 0 if head is None else head.sequence,
        "protection": "TAMPER_EVIDENT_NOT_WORM",
    }

    if not step_up_required:
        findings.append("STEP_UP_NOT_ENFORCED")

    findings.extend(
        _backup_findings(backup, backup_settings, now=now, details=details)
    )
    production = is_production_like(environment)
    unique = tuple(dict.fromkeys(findings))
    return ReadinessReport(
        environment=environment,
        ready=not production or not unique,
        blockers=unique if production else (),
        warnings=() if production else unique,
        details=details,
    )


def _backup_findings(
    backup: Any,
    settings: Any,
    *,
    now: datetime,
    details: dict[str, Any],
) -> list[str]:
    details["backup"] = {
        "offsite": "NOT_CONFIGURED",
        "immutable": "NOT_CONFIGURED",
        "pointInTime": "NOT_CONFIGURED",
        "lastVerifiedRestorePoint": None,
    }
    findings = ["BACKUP_OFFSITE_NOT_CONFIGURED", "BACKUP_PITR_NOT_CONFIGURED"]
    if not settings.enabled:
        return ["BACKUP_DISABLED", *findings]
    if settings.kms_key_reference is None:
        findings.append("BACKUP_KEY_NOT_IN_KMS")
    if settings.recovery_uri is None:
        findings.append("BACKUP_SCOPE_INCOMPLETE")
    if settings.interval_seconds <= 0:
        findings.append("BACKUP_SCHEDULE_NOT_CONFIGURED")
    if backup is None:
        return [*findings, "BACKUP_STATE_UNAVAILABLE"]
    last = backup.last_verified_restore_point()
    if last is None:
        findings.append("BACKUP_NO_VERIFIED_RESTORE_POINT")
        return findings
    details["backup"]["lastVerifiedRestorePoint"] = last.started_at.isoformat()
    limit = timedelta(seconds=max(settings.interval_seconds, 3600) * 2)
    if now - last.started_at > limit:
        findings.append("BACKUP_OVERDUE")
    return findings
