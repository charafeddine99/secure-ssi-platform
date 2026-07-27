from typing import Any

import pytest
from pymongo.errors import ServerSelectionTimeoutError

from app.config.mongo_settings import MongoSettings
from app.domain.persistence import PersistenceUnavailableError
from app.infrastructure.persistence.connection import MongoConnectionManager


class FakeAdmin:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.pings = 0

    def command(self, name: str) -> None:
        assert name == "ping"
        self.pings += 1
        if self.fail:
            raise ServerSelectionTimeoutError("sensitive-host")


class FakeClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.admin = FakeAdmin(fail=fail)
        self.closed = False
        self.databases: dict[str, object] = {}

    def get_database(self, name: str) -> object:
        return self.databases.setdefault(name, object())

    def close(self) -> None:
        self.closed = True


def settings(*, enabled: bool = True) -> MongoSettings:
    return MongoSettings(
        enabled=enabled,
        uri="mongodb://app:secret@mongo.example.test:27017/identity",
        database_name="identity",
    )


def test_connection_manager_reuses_pool_and_closes_idempotently() -> None:
    created: list[tuple[str, dict[str, Any], FakeClient]] = []

    def factory(uri: str, **kwargs: Any) -> FakeClient:
        client = FakeClient()
        created.append((uri, kwargs, client))
        return client

    manager = MongoConnectionManager(
        settings(),
        client_factory=factory,
    )
    manager.connect()
    first_database = manager.database
    manager.connect()

    assert len(created) == 1
    assert first_database is manager.database
    assert created[0][1]["maxPoolSize"] == 50
    assert created[0][1]["tz_aware"] is True
    assert created[0][2].admin.pings == 1
    assert "secret" not in repr(manager)
    assert "mongo.example.test" not in repr(manager)

    manager.close()
    manager.close()
    assert created[0][2].closed is True
    assert manager.is_connected is False


def test_connection_manager_fails_closed_and_redacts_driver_error() -> None:
    client = FakeClient(fail=True)
    manager = MongoConnectionManager(
        settings(),
        client_factory=lambda *_args, **_kwargs: client,
    )

    with pytest.raises(
        PersistenceUnavailableError,
        match="could not be established",
    ) as captured:
        manager.connect()

    assert "sensitive-host" not in str(captured.value)
    assert client.closed is True
    assert manager.is_connected is False


def test_disabled_or_unconnected_manager_rejects_database_access() -> None:
    manager = MongoConnectionManager(settings(enabled=False))

    with pytest.raises(PersistenceUnavailableError):
        manager.connect()
    with pytest.raises(PersistenceUnavailableError):
        _ = manager.database
