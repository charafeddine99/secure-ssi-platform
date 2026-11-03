"""The credential offer announces a transaction code the OpenID4VCI 1.0 way (tx_code)."""

import json
import urllib.parse
from datetime import datetime, timedelta, timezone

from app.domain.oid4vci import CredentialOffer, OfferStatus

GRANT = "urn:ietf:params:oauth:grant-type:pre-authorized_code"


def _offer(user_pin: str | None) -> CredentialOffer:
    now = datetime(2026, 11, 3, tzinfo=timezone.utc)
    return CredentialOffer(
        id="0" * 24,
        offer_id="offer_" + "a" * 32,
        credential_issuer="https://issuer.example.test",
        issuer_did="did:web:issuer.example.test",
        credential_configuration_ids=("UniversityAffiliationCredential",),
        subject_data={"affiliation": "student"},
        pre_authorized_code="code-123",
        status=OfferStatus.PENDING,
        created_at=now,
        expires_at=now + timedelta(minutes=10),
        user_pin=user_pin,
    )


def test_offer_with_pin_announces_tx_code_without_revealing_it() -> None:
    grant = _offer("4821").to_standard_offer_payload("https://issuer.example.test/")["grants"][GRANT]

    assert grant["pre-authorized_code"] == "code-123"
    assert grant["tx_code"]["input_mode"] == "numeric"
    assert grant["tx_code"]["length"] == 4
    assert "4821" not in json.dumps(grant)
    assert "user_pin_required" not in grant


def test_offer_without_pin_omits_tx_code() -> None:
    grant = _offer(None).to_standard_offer_payload("https://issuer.example.test")["grants"][GRANT]

    assert "tx_code" not in grant
    assert "user_pin_required" not in grant


def test_deep_link_carries_tx_code_for_the_wallet() -> None:
    link = _offer("12345678").to_deep_link_uri("https://issuer.example.test")
    raw = urllib.parse.parse_qs(urllib.parse.urlsplit(link).query)["credential_offer"][0]

    assert json.loads(raw)["grants"][GRANT]["tx_code"]["length"] == 8
