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
