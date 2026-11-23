"""Password rules and role permissions."""

import pytest

from app.domain.password_policy import password_problem
from app.domain.permissions import Permission, Role, permissions_for_roles


@pytest.mark.parametrize(("password", "fragment"), [
    ("short", "15"),
    ("aaaaaaaaaaaaaaaaaaaa", "repetitive"),
    ("my-password-is-long-enough", "common"),
    ("qwerty-long-enough-value", "common"),
    ("alice.smith-horse-staple-9", "account name"),
])
def test_weak_passwords_are_refused(password, fragment):
    assert fragment in password_problem(password, username="alice.smith@example.test")


def test_no_composition_rule_blocks_a_long_passphrase():
    assert password_problem("correct horse battery staple", username="alice@example.test") is None


def test_administrators_do_not_act_as_holders_or_issuers():
    granted = set(permissions_for_roles((Role.ADMIN,)))
    for permission in (
        Permission.CREDENTIALS_REVOKE, Permission.CREDENTIALS_SIGN, Permission.WALLETS_CREATE,
        Permission.WALLETS_READ, Permission.PRESENTATIONS_CREATE, Permission.WALLET_KEY_ROTATE,
    ):
        assert permission not in granted


def test_issuers_cannot_touch_wallets_or_administration():
    granted = {p.value for p in permissions_for_roles((Role.ISSUER,))}
    assert not {p for p in granted if p.startswith(("wallet", "admin:", "presentations"))}
    assert "trust-registry:write" not in granted


def test_every_permission_belongs_to_a_role_on_purpose():
    granted = {p for role in Role for p in permissions_for_roles((role,))}
    assert granted == set(Permission)
