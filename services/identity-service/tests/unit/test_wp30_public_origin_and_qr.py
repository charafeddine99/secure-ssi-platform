"""WP-30: what a verifier QR may contain, and what the wallet card must not."""

from pathlib import Path

import pytest

from app.config.public_origin_settings import (
    load_public_origin_settings,
    reachable_from_a_phone,
)
from app.domain.persistence import PersistenceConfigurationError


WEB = Path(__file__).resolve().parents[4] / "apps" / "web" / "src"


def test_no_origin_means_no_phone_link() -> None:
    assert load_public_origin_settings({}).handoff_uri("session_x") is None


def test_handoff_is_an_https_link_with_only_an_opaque_handle() -> None:
    settings = load_public_origin_settings(
        {"IDENTITY_PUBLIC_ORIGIN": "https://wallet.example.org/"}
    )
    assert settings.handoff_uri("session_abc") == (
        "https://wallet.example.org/wallet/present?request=session_abc"
    )


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://identity-service:8000",
        "http://api-gateway:8000",
        "http://web",
        "http://wallet.localhost",
        "http://[::1]:3000",
    ],
)
def test_addresses_a_phone_cannot_reach_are_refused(origin: str) -> None:
    assert reachable_from_a_phone(origin) is False
    with pytest.raises(PersistenceConfigurationError):
        load_public_origin_settings({"IDENTITY_PUBLIC_ORIGIN": origin})


@pytest.mark.parametrize(
    "origin",
    ["ftp://x.example", "https://x.example/path", "https://x.example?a=1", "x"],
)
def test_only_a_bare_origin_is_accepted(origin: str) -> None:
    with pytest.raises(PersistenceConfigurationError):
        load_public_origin_settings({"IDENTITY_PUBLIC_ORIGIN": origin})


def test_production_needs_https() -> None:
    with pytest.raises(PersistenceConfigurationError):
        load_public_origin_settings(
            {
                "IDENTITY_ENVIRONMENT": "production",
                "IDENTITY_PUBLIC_ORIGIN": "http://wallet.example.org",
            }
        )


def test_lan_address_is_allowed_for_a_development_phone_test() -> None:
    settings = load_public_origin_settings(
        {"IDENTITY_PUBLIC_ORIGIN": "http://192.168.1.20:3000"}
    )
    assert settings.origin == "http://192.168.1.20:3000"


def test_wallet_card_has_no_identifier_qr() -> None:
    source = (WEB / "components" / "ssi" / "CredentialCard.tsx").read_text(
        encoding="utf-8"
    )
    assert "qrcode" not in source.casefold()
    assert "toDataURL" not in source
