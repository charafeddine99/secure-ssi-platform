"""Copy the synthetic development accounts into the MongoDB user store.

Development only: run once before switching IDENTITY_AUTH_USER_PROVIDER to
"mongodb" so user administration works locally. Only the existing Argon2id
hashes are copied; no plaintext password is read or written. Existing
usernames are left untouched, so the command is safe to repeat.

    python -m app.infrastructure.persistence.local_user_seed
"""

import os
import sys

from bson import ObjectId

from app.config.auth_settings import is_production_like
from app.domain.persistence import PersistedUser
from app.infrastructure.auth.local_synthetic_user_provider import (
    LocalSyntheticUserProvider,
)

FIXTURE_USERNAMES = (
    "admin@example.test",
    "issuer@example.test",
    "verifier@example.test",
    "holder@example.test",
)


def seed(repository) -> list[str]:
    fixtures = LocalSyntheticUserProvider.default(enabled=True)
    created: list[str] = []
    for username in FIXTURE_USERNAMES:
        if repository.get_by_username(username) is not None:
            continue
        record = fixtures.find_by_username(username)
        if record is None:
            continue
        user = record.user
        repository.add(
            PersistedUser(
                id=str(ObjectId()),
                username=user.username,
                display_name=user.display_name,
                roles=tuple(user.roles),
                enabled=user.enabled,
                password_hash=record.password_hash,
                issuer_did=user.issuer_did,
            )
        )
        created.append(username)
    return created


def seed_on_startup(database, auth_settings) -> list[str]:
    """Seed the development accounts at startup when MongoDB is the user store.

    Runs only in a development environment with synthetic fixture users enabled
    and IDENTITY_AUTH_USER_PROVIDER=mongodb, so a fresh `docker compose up` can
    sign in and use user administration without a manual seeding step.
    """
    if (
        auth_settings.user_provider != "mongodb"
        or not auth_settings.local_fixture_users_enabled
        or is_production_like(auth_settings.environment)
    ):
        return []
    from app.infrastructure.persistence.indexes import USERS_COLLECTION
    from app.infrastructure.persistence.repositories import MongoUserRepository

    return seed(MongoUserRepository(database[USERS_COLLECTION]))


def main() -> int:
    environment = os.environ.get("IDENTITY_ENVIRONMENT", "development")
    if is_production_like(environment):
        print("Refusing to seed development accounts in a production-like environment.", file=sys.stderr)
        return 2
    from app.api.v1.dependencies import get_mongo_connection_manager, get_user_repository

    manager = get_mongo_connection_manager()
    manager.connect()
    repository = get_user_repository(manager=manager)
    created = seed(repository)
    print(f"Seeded {len(created)} account(s): {', '.join(created) or 'none (already present)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
