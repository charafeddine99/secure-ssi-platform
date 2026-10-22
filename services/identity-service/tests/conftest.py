import sys
from unittest.mock import MagicMock

if "ckzg" not in sys.modules:
    try:
        import ckzg  # noqa: F401
    except Exception:
        sys.modules["ckzg"] = MagicMock()

from typing import Any, Generator
import pytest
from pathlib import Path
from app.api.v1 import dependencies
from tests.support.fake_mongo import FakeDatabase

from app.services.did_resolver import CompositeDidResolver
from tests.support.did_web_test_fixture import DidWebTestFixtureResolver
from app.infrastructure.crypto.local_issuer_key_provider import SYNTHETIC_ISSUER_DID
from app.main import app


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
def test_quarantine_state_isolation() -> Generator[None, None, None]:
    """Prevent process-local quarantine decisions leaking between tests."""
    from app.infrastructure.cache_and_anchor import blockchain_anchor

    blockchain_anchor._quarantined_subjects.clear()
    yield
    blockchain_anchor._quarantined_subjects.clear()


@pytest.fixture(autouse=True)
def test_fraud_service_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep identity tests independent of any locally running Fraud Service state."""
    from app.application.services.oid4vp_service import fraud_client

    monkeypatch.setattr(fraud_client, "base_url", "http://127.0.0.1:1")
    monkeypatch.setattr(fraud_client, "report_event", lambda **kwargs: None)


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


@pytest.fixture(autouse=True)
def test_did_resolver(monkeypatch: pytest.MonkeyPatch) -> Generator[Any, None, None]:
    fixture_path = Path(__file__).parent.parent / "app" / "infrastructure" / "fixtures" / "issuer.did.json"
    fake_resolver = CompositeDidResolver(
        {
            "web": DidWebTestFixtureResolver(
                {SYNTHETIC_ISSUER_DID: fixture_path}
            )
        }
    )
    monkeypatch.setattr(dependencies, "_DID_RESOLVER", fake_resolver)
    yield fake_resolver
