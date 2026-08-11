from dataclasses import asdict

import pytest

from app.domain.auth import AuthenticatedPrincipal, User
from app.domain.exceptions import InvalidRoleError
from app.domain.permissions import (
    Permission,
    Role,
    normalize_roles,
    permissions_for_roles,
)


def test_supported_roles_are_closed_enum_values() -> None:
    assert {role.value for role in Role} == {
        "admin",
        "holder",
        "issuer",
        "verifier",
    }


def test_admin_has_all_permissions() -> None:
    assert set(permissions_for_roles((Role.ADMIN,))) == set(Permission)


def test_issuer_preserves_existing_permissions_but_cannot_manage_keys() -> None:
    permissions = set(permissions_for_roles((Role.ISSUER,)))

    assert Permission.CREDENTIALS_SIGN in permissions
    assert Permission.PRESENTATIONS_RECONCILE in permissions
    assert not any(
        permission.value.startswith(("wallet:key:", "admin:key:"))
        for permission in permissions
    )


def test_verifier_permissions_exclude_signing_and_revocation() -> None:
    permissions = permissions_for_roles((Role.VERIFIER,))

    assert permissions == (
        Permission.AUTH_SELF_READ,
        Permission.CREDENTIALS_VALIDATE,
        Permission.CREDENTIALS_VERIFY,
        Permission.PRESENTATIONS_READ,
        Permission.PRESENTATIONS_VERIFY,
        Permission.PRESENTATION_CHALLENGES_CREATE,
        Permission.PRESENTATION_CHALLENGES_READ,
    )
    assert Permission.CREDENTIALS_SIGN not in permissions
    assert Permission.CREDENTIALS_REVOKE not in permissions


def test_holder_can_create_and_read_but_not_verify_presentations() -> None:
    permissions = permissions_for_roles((Role.HOLDER,))

    assert permissions == (
        Permission.AUTH_SELF_READ,
        Permission.PRESENTATIONS_CREATE,
        Permission.PRESENTATIONS_READ,
        Permission.WALLETS_CREATE,
        Permission.WALLETS_READ,
        Permission.WALLETS_CREDENTIALS_READ,
        Permission.PRESENTATION_CHALLENGES_READ,
        Permission.WALLET_KEY_CREATE,
        Permission.WALLET_KEY_READ,
        Permission.WALLET_KEY_ROTATE,
        Permission.WALLET_KEY_SUSPEND,
        Permission.WALLET_KEY_RESUME,
        Permission.WALLET_KEY_REVOKE,
    )
    assert Permission.PRESENTATIONS_VERIFY not in permissions


def test_duplicate_roles_are_normalized_in_enum_order() -> None:
    assert normalize_roles(
        ("verifier", Role.ADMIN, "verifier", "admin")
    ) == (Role.ADMIN, Role.VERIFIER)


def test_unknown_role_is_rejected() -> None:
    with pytest.raises(InvalidRoleError):
        normalize_roles(("owner",))


def test_principal_public_model_contains_no_secret_fields() -> None:
    principal = AuthenticatedPrincipal.from_user(
        User(
            id="usr_test",
            username="test@example.test",
            display_name="Test User",
            roles=(Role.ISSUER,),
        ),
        authentication_source="local-synthetic-fixture",
    )

    serialized = asdict(principal)
    assert set(serialized) == {
        "id",
        "username",
        "display_name",
        "roles",
        "permissions",
        "authentication_source",
    }
    assert "password" not in repr(principal).lower()
    assert "secret" not in repr(principal).lower()
