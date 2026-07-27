from threading import Lock
from typing import Any

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError
from pymongo.server_api import ServerApi

from app.config.mongo_settings import MongoSettings
from app.domain.persistence import PersistenceUnavailableError


class MongoConnectionManager:
    """Owns one process-wide MongoClient and its connection pool."""

    def __init__(
        self,
        settings: MongoSettings,
        *,
        client_factory: Any = MongoClient,
    ) -> None:
        self._settings = settings
        self._client_factory = client_factory
        self._client: MongoClient[dict[str, Any]] | None = None
        self._lock = Lock()

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    @property
    def database(self) -> Database[dict[str, Any]]:
        client = self._client
        if client is None:
            raise PersistenceUnavailableError(
                "MongoDB connection has not been initialized."
            )
        return client.get_database(self._settings.database_name)

    def connect(self) -> None:
        if not self._settings.enabled:
            raise PersistenceUnavailableError(
                "MongoDB persistence is disabled."
            )
        with self._lock:
            if self._client is not None:
                return
            client: MongoClient[dict[str, Any]] | None = None
            try:
                client = self._client_factory(
                    self._settings.uri,
                    appname=self._settings.app_name,
                    serverSelectionTimeoutMS=(
                        self._settings.server_selection_timeout_ms
                    ),
                    connectTimeoutMS=self._settings.connect_timeout_ms,
                    socketTimeoutMS=self._settings.socket_timeout_ms,
                    maxPoolSize=self._settings.max_pool_size,
                    minPoolSize=self._settings.min_pool_size,
                    retryReads=self._settings.retry_reads,
                    retryWrites=self._settings.retry_writes,
                    tz_aware=True,
                    server_api=ServerApi("1"),
                )
                client.admin.command("ping")
            except PyMongoError as error:
                if client is not None:
                    client.close()
                raise PersistenceUnavailableError(
                    "MongoDB connection could not be established."
                ) from error
            self._client = client

    def close(self) -> None:
        with self._lock:
            client, self._client = self._client, None
        if client is not None:
            client.close()

    def __enter__(self) -> "MongoConnectionManager":
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return (
            "MongoConnectionManager("
            f"enabled={self._settings.enabled}, "
            f"database={self._settings.database_name!r}, "
            f"connected={self.is_connected}, uri=<redacted>)"
        )
