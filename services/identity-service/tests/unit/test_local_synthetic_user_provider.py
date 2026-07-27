from dataclasses import asdict

import pytest

from app.infrastructure.auth.argon2_password_hasher import Argon2PasswordHasher
from app.infrastructure.auth.local_synthetic_user_provider import (
    LocalSyntheticUserProvider,
)


@pytest.fixture
def provider() -> LocalSyntheticUserProvider:
    return LocalSyntheticUserProvider.default()


@pytest.mark.parametrize(
    ("username", "user_id"),
    [
        ("admin@example.test", "usr_local_admin"),
        ("issuer@example.test", "usr_local_issuer"),
        ("verifier@example.test", "usr_local_verifier"),
        ("holder@example.test", "usr_local_holder"),
    ],
)
def test_fixture_users_are_available_by_username(
    provider: LocalSyntheticUserProvider,
    username: str,
    user_id: str,
) -> None:
    record = provider.find_by_username(username)

    assert record is not None
    assert record.user.id == user_id
    assert provider.find_by_id(user_id) == record


def test_username_lookup_is_case_insensitive_and_unknown_is_absent(
    provider: LocalSyntheticUserProvider,
) -> None:
    assert provider.find_by_username(" ISSUER@EXAMPLE.TEST ") is not None
    assert provider.find_by_username("unknown@example.test") is None
    assert provider.find_by_id("usr_missing") is None


def test_disabled_user_state_is_preserved(
    provider: LocalSyntheticUserProvider,
) -> None:
    record = provider.find_by_username("disabled@example.test")

    assert record is not None
    assert record.user.enabled is False


def test_public_user_does_not_contain_password_hash(
    provider: LocalSyntheticUserProvider,
) -> None:
    record = provider.find_by_username("issuer@example.test")

    assert record is not None
    assert "password_hash" not in asdict(record.user)
    assert "password_hash" not in repr(record.user)
    assert "$argon2" not in repr(provider)
    assert "$argon2" not in repr(record)


def test_fixture_hashes_are_real_argon2id_records(
    provider: LocalSyntheticUserProvider,
) -> None:
    record = provider.find_by_username("issuer@example.test")

    assert record is not None
    assert Argon2PasswordHasher().verify_password(
        "Issuer-Prototype-2026!",
        record.password_hash,
    )

    holder = provider.find_by_username("holder@example.test")
    assert holder is not None
    assert Argon2PasswordHasher().verify_password(
        "Holder-Prototype-2026!",
        holder.password_hash,
    )


def test_disabled_fixture_registry_can_be_empty() -> None:
    provider = LocalSyntheticUserProvider.default(enabled=False)

    assert provider.find_by_username("issuer@example.test") is None
    assert provider.find_by_id("usr_local_issuer") is None
