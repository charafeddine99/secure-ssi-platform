import asyncio

from app.application.services.metrics import RecoveryMetrics
from app.application.services.recovery_service import (
    RecoveryReconciliationBackgroundService,
    RecoveryService,
)
from app.core.config import RecoverySettings
from app.infrastructure.managed_keys.identity_gateway import (
    IdentityManagedKeyRecoveryGateway,
)
from app.infrastructure.persistence.connection import (
    MongoRecoveryConnectionManager,
)
from app.infrastructure.persistence.indexes import ensure_recovery_indexes
from app.infrastructure.persistence.memory_repository import (
    MemoryRecoveryRepository,
)
from app.infrastructure.persistence.mongo_repository import (
    MongoRecoveryRepository,
)
from app.infrastructure.secret_sharing.pycryptodome_provider import (
    PyCryptodomeSecretSharingProvider,
)


class RecoveryRuntime:
    def __init__(self, settings: RecoverySettings) -> None:
        self.settings = settings
        self.metrics = RecoveryMetrics()
        self.connection = MongoRecoveryConnectionManager(settings)
        self.gateway = IdentityManagedKeyRecoveryGateway(settings)
        self.repository = MemoryRecoveryRepository()
        self.service = self._build_service()
        self.stop_event: asyncio.Event | None = None
        self.worker_task: asyncio.Task[None] | None = None

    @property
    def persistence_name(self) -> str:
        return "mongodb" if self.settings.mongo_enabled else "memory"

    async def start(self) -> None:
        if not self.settings.mongo_enabled:
            return
        self.connection.connect()
        ensure_recovery_indexes(self.connection.database)
        self.repository = MongoRecoveryRepository(self.connection.database)
        self.service = self._build_service()
        self.metrics.set_active_guardians(
            self.repository.count_active_guardians()
        )
        if self.settings.reconciliation_enabled:
            self.stop_event = asyncio.Event()
            worker = RecoveryReconciliationBackgroundService(
                self.service,
                poll_interval_ms=self.settings.reconciliation_poll_interval_ms,
            )
            self.worker_task = asyncio.create_task(
                worker.run(self.stop_event), name="recovery-reconciliation"
            )

    async def stop(self) -> None:
        if self.stop_event is not None:
            self.stop_event.set()
        if self.worker_task is not None:
            await self.worker_task
        self.gateway.close()
        self.connection.close()

    def _build_service(self) -> RecoveryService:
        return RecoveryService(
            repository=self.repository,
            secret_sharing=PyCryptodomeSecretSharingProvider(
                self.settings.envelope_master_key
            ),
            managed_keys=self.gateway,
            settings=self.settings,
            metrics=self.metrics,
        )
