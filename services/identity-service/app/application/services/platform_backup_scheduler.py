import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo.errors import DuplicateKeyError, PyMongoError

from app.application.services.platform_backup_service import (
    PlatformBackupError,
    PlatformBackupService,
)


PLATFORM_BACKUP_LEASES_COLLECTION = "platform_backup_leases"
_LEASE_ID = "scheduled-backup"
_logger = logging.getLogger(__name__)


class PlatformBackupScheduler:
    """Runs one backup and verification per interval across all instances."""

    def __init__(
        self,
        service: PlatformBackupService,
        *,
        leases: Any,
        interval_seconds: int,
        owner: str,
        clock: Callable[[], datetime] | None = None,
        lease_seconds: int = 3600,
    ) -> None:
        self._service = service
        self._leases = leases
        self._interval = timedelta(seconds=interval_seconds)
        self._lease = timedelta(seconds=lease_seconds)
        self._owner = owner
        self._clock = clock or (lambda: datetime.now(UTC))

    def tick(self) -> str:
        now = self._clock().astimezone(UTC)
        self._service.recover_interrupted()
        if not self._claim(now):
            return "SKIPPED"
        try:
            record = self._service.create_backup(actor_id="system:scheduler")
            self._service.verify(record.backup_id, actor_id="system:scheduler")
        except PlatformBackupError as error:
            _logger.error("Scheduled backup failed: %s", error.code)
            return "FAILED"
        return "COMPLETED"

    def _claim(self, now: datetime) -> bool:
        """Takes the slot only if no instance ran within the interval."""
        fields = {
            "owner": self._owner,
            "nextRunAt": now + self._interval,
            "leaseUntil": now + self._lease,
        }
        try:
            result = self._leases.update_one(
                {"_id": _LEASE_ID, "nextRunAt": {"$lte": now}},
                {"$set": fields},
            )
            if result.matched_count == 1:
                return True
            if self._leases.find_one({"_id": _LEASE_ID}) is not None:
                return False
            self._leases.insert_one({"_id": _LEASE_ID, **fields})
            return True
        except DuplicateKeyError:
            return False
        except PyMongoError:
            _logger.error("Backup lease is unavailable.")
            return False


class PlatformBackupBackgroundService:
    def __init__(
        self,
        scheduler: PlatformBackupScheduler,
        *,
        poll_seconds: float = 60.0,
    ) -> None:
        self._scheduler = scheduler
        self._poll_seconds = poll_seconds

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                await asyncio.to_thread(self._scheduler.tick)
            except Exception:
                _logger.exception("Scheduled backup tick failed.")
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=self._poll_seconds,
                )
            except TimeoutError:
                continue
