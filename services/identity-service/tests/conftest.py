from __future__ import annotations

from typing import Any, Generator
import pytest
from app.api.v1 import dependencies
from tests.support.fake_mongo import FakeDatabase


class FakeMongoConnectionManager:
    def __init__(self, database: FakeDatabase | None = None) -> None:
        self._database = database if database is not None else FakeDatabase()
        self.is_connected = True

    @property
    def database(self) -> Any:
        return self._database

    def connect(self) -> None:
        self.is_connected = True

    def close(self) -> None:
        pass


@pytest.fixture(autouse=True)
def test_persistence_manager(monkeypatch: pytest.MonkeyPatch) -> Generator[Any, None, None]:
    """
    Transparently provides an in-memory FakeMongoConnectionManager during test runs
    when a live MongoDB daemon is not running on localhost:27017.
    """
    if not dependencies._MONGO_MANAGER.is_connected:
        fake_db = FakeDatabase()
        fake_manager = FakeMongoConnectionManager(fake_db)
        monkeypatch.setattr(dependencies, "_MONGO_MANAGER", fake_manager)
        monkeypatch.setattr(dependencies, "get_mongo_connection_manager", lambda: fake_manager)
        yield fake_manager
    else:
        yield dependencies._MONGO_MANAGER
