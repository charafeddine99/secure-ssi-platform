from typing import Any

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.core.config import RecoverySettings
from app.domain.recovery import RecoveryPersistenceError


class MongoRecoveryConnectionManager:
    def __init__(self, settings: RecoverySettings) -> None:
        self._settings = settings
        self._client: MongoClient[dict[str, Any]] | None = None
        self._database: Database[dict[str, Any]] | None = None

    @property
    def database(self) -> Database[dict[str, Any]]:
        if self._database is None:
            raise RecoveryPersistenceError("Recovery MongoDB is not connected.")
        return self._database

    def connect(self) -> None:
        if self._client is not None:
            return
        try:
            client: MongoClient[dict[str, Any]] = MongoClient(
                self._settings.mongo_uri,
                serverSelectionTimeoutMS=self._settings.mongo_timeout_ms,
                connectTimeoutMS=self._settings.mongo_timeout_ms,
                socketTimeoutMS=max(5000, self._settings.mongo_timeout_ms),
                retryReads=True,
                retryWrites=True,
                appname="secure-ssi-recovery-service",
            )
            client.admin.command("ping")
            self._client = client
            self._database = client[self._settings.mongo_database]
        except PyMongoError as error:
            self.close()
            raise RecoveryPersistenceError("Recovery MongoDB is unavailable.") from error

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None
        self._database = None
