"""Regression tests for sanitized MongoDB persistence telemetry."""

from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from app.api.v1.dependencies import get_mongo_connection_manager
from app.api.v1.dependencies import get_current_principal
from app.domain.auth import AuthenticatedPrincipal, User
from app.domain.permissions import Role
from app.domain.persistence import PersistenceUnavailableError
from app.main import app
from tests.support.fake_mongo import FakeDatabase


class ConnectedMongoManager:
    is_connected = True

    def __init__(self, database: FakeDatabase) -> None:
        self.database = database


class DisconnectedMongoManager:
    is_connected = False

    @property
    def database(self) -> Any:
        raise PersistenceUnavailableError("MongoDB is disconnected.")


def _admin_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal.from_user(
        User(
            id="usr_test_admin",
            username="admin@example.test",
            display_name="Test Admin",
            roles=(Role.ADMIN,),
        ),
        authentication_source="test-fixture",
    )


@pytest.fixture
def telemetry_client():
    database = FakeDatabase()
    database["credentials"].insert_one(
        {"_id": "credential-1", "credentialId": "private-id"}
    )
    database["audit_events"].insert_one(
        {"_id": "audit-1", "metadata": {"private": "must-not-leak"}}
    )
    manager = ConnectedMongoManager(database)
    app.dependency_overrides[get_mongo_connection_manager] = lambda: cast(
        Any, manager
    )
    app.dependency_overrides[get_current_principal] = _admin_principal
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_database_stats_returns_only_verified_aggregate_counts(telemetry_client):
    response = telemetry_client.get("/api/v1/database/stats")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["authoritative_persistence"] == "MongoDB"
    assert data["active_runtime"] == "MongoDB"
    assert data["mongo_connected"] is True
    assert data["stats"]["credentials"] == 1
    assert data["stats"]["audit_logs"] == 1
    assert "private-id" not in response.text
    assert "must-not-leak" not in response.text


def test_database_stats_fails_when_authoritative_mongo_is_disconnected():
    app.dependency_overrides[get_mongo_connection_manager] = lambda: cast(
        Any, DisconnectedMongoManager()
    )
    app.dependency_overrides[get_current_principal] = _admin_principal
    try:
        response = TestClient(app).get("/api/v1/database/stats")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "PERSISTENCE_UNAVAILABLE"
    assert "stats" not in response.json()
