import pytest

from app.infrastructure.auth.argon2_password_hasher import Argon2PasswordHasher


@pytest.fixture
def hasher() -> Argon2PasswordHasher:
    return Argon2PasswordHasher(
        time_cost=1,
        memory_cost=8_192,
        parallelism=1,
    )


def test_argon2id_hash_and_verification(
    hasher: Argon2PasswordHasher,
) -> None:
    password = "Synthetic-Password-2026!"
    password_hash = hasher.hash_password(password)

    assert password_hash.startswith("$argon2id$")
    assert password not in password_hash
    assert hasher.verify_password(password, password_hash) is True
    assert hasher.verify_password("wrong-password", password_hash) is False


def test_argon2id_uses_random_salts(
    hasher: Argon2PasswordHasher,
) -> None:
    first = hasher.hash_password("Synthetic-Password-2026!")
    second = hasher.hash_password("Synthetic-Password-2026!")

    assert first != second


def test_invalid_hash_is_a_controlled_false_result(
    hasher: Argon2PasswordHasher,
) -> None:
    assert hasher.verify_password("password", "not-an-argon-hash") is False


def test_empty_password_error_and_repr_do_not_leak_material(
    hasher: Argon2PasswordHasher,
) -> None:
    with pytest.raises(ValueError) as captured:
        hasher.hash_password("")

    assert "Synthetic-Password" not in str(captured.value)
    assert "password=<" not in repr(hasher).lower()
    assert "redacted" in repr(hasher)
