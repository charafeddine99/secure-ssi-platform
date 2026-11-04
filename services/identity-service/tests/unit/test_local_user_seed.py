from app.infrastructure.persistence import local_user_seed
from app.infrastructure.persistence.repositories import MongoUserRepository
from app.infrastructure.crypto.local_issuer_key_provider import SYNTHETIC_ISSUER_DID
from tests.support.fake_mongo import FakeDatabase


def test_seed_copies_hashed_fixture_accounts_once():
    users = MongoUserRepository(FakeDatabase()["users"])  # type: ignore[arg-type]

    created = local_user_seed.seed(users)
    again = local_user_seed.seed(users)

    assert created == list(local_user_seed.FIXTURE_USERNAMES)
    assert again == []
    issuer = users.get_by_username("issuer@example.test")
    assert issuer is not None
    assert issuer.password_hash.startswith("$argon2id$")
    assert issuer.issuer_did == SYNTHETIC_ISSUER_DID
    assert users.get_by_username("disabled@example.test") is None


def test_seed_refuses_production_like_environments(monkeypatch):
    monkeypatch.setenv("IDENTITY_ENVIRONMENT", "production")
    assert local_user_seed.main() == 2


class _Settings:
    def __init__(self, user_provider="mongodb", fixtures=True, environment="development"):
        self.user_provider = user_provider
        self.local_fixture_users_enabled = fixtures
        self.environment = environment


def test_startup_seed_runs_for_development_mongodb_users():
    database = FakeDatabase()

    assert local_user_seed.seed_on_startup(database, _Settings()) == list(local_user_seed.FIXTURE_USERNAMES)
    assert local_user_seed.seed_on_startup(database, _Settings()) == []


def test_startup_seed_is_skipped_unless_development_mongodb_fixtures():
    for settings in (
        _Settings(user_provider="synthetic"),
        _Settings(fixtures=False),
        _Settings(environment="production"),
    ):
        database = FakeDatabase()
        assert local_user_seed.seed_on_startup(database, settings) == []
        assert MongoUserRepository(database["users"]).get_by_username("admin@example.test") is None  # type: ignore[arg-type]
