"""WP-30 unit tests. Real WebAuthn ceremonies run in the browser E2E with a
virtual authenticator, because they need a browser client."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.application.services.reissuance_service import (
    ReissuanceError,
    ReissuanceNotFoundError,
    ReissuanceService,
)
from app.application.services.webauthn_service import (
    WebAuthnService,
    WebAuthnSettings,
    load_webauthn_settings,
)
from app.application.services.step_up_service import StepUpRequiredError
from app.domain.exceptions import PermissionDeniedError
from app.domain.persistence import PersistenceConfigurationError
from app.infrastructure.persistence.memory_db import MemoryCollection


NOW = datetime(2026, 11, 4, tzinfo=UTC)
OLD, NEW = "did:key:zOld", "did:key:zNew"
ISSUER = "did:web:issuer.example"
CREDENTIAL = "urn:uuid:one"


class Wallets:
    def require_owned_active(self, wallet_id, *, owner_user_id, correlation_id):
        if owner_user_id != "holder":
            raise ReissuanceNotFoundError("hidden")
        return SimpleNamespace(wallet_id=wallet_id, holder_did=NEW)


class Credentials:
    def __init__(self, subject_id=OLD) -> None:
        self.record = SimpleNamespace(
            credential_id=CREDENTIAL,
            raw_credential={
                "type": ["VerifiableCredential", "UniversityAffiliationCredential"],
                "issuer": ISSUER,
                "credentialSubject": {"id": subject_id, "degree": "BSc"},
            },
        )

    def list_by_wallet(self, wallet_id, *, owner_user_id, limit):
        return (self.record,)

    def get_by_credential_id(self, credential_id):
        return self.record


class Ledger:
    def __init__(self, revoked=False) -> None:
        self.revoked = revoked

    def is_revoked(self, credential_id):
        return self.revoked


def service(**options) -> ReissuanceService:
    return ReissuanceService(
        requests=MemoryCollection(),
        wallets=Wallets(),
        credentials=options.get("credentials", Credentials()),
        ledger=options.get("ledger", Ledger()),
        clock=lambda: NOW,
    )


def test_old_did_credential_can_be_requested_and_is_not_edited() -> None:
    credentials = Credentials()
    target = service(credentials=credentials)
    request = target.request("wallet_x", CREDENTIAL, owner_user_id="holder")
    assert request.status == "PENDING"
    assert request.new_holder_did == NEW
    assert credentials.record.raw_credential["credentialSubject"]["id"] == OLD


def test_current_did_credential_needs_no_reissuance() -> None:
    with pytest.raises(ReissuanceError):
        service(credentials=Credentials(NEW)).request(
            "wallet_x", CREDENTIAL, owner_user_id="holder"
        )


def test_revoked_credential_cannot_be_reissued() -> None:
    with pytest.raises(ReissuanceError):
        service(ledger=Ledger(True)).request(
            "wallet_x", CREDENTIAL, owner_user_id="holder"
        )


def test_revocation_after_the_request_blocks_approval() -> None:
    ledger = Ledger()
    target = service(ledger=ledger)
    request = target.request("wallet_x", CREDENTIAL, owner_user_id="holder")
    ledger.revoked = True
    with pytest.raises(ReissuanceError):
        target.approve(
            request.request_id,
            issuer_did=ISSUER,
            create_offer=lambda *_: "offer",
        )


def test_another_holder_cannot_request() -> None:
    with pytest.raises(ReissuanceNotFoundError):
        service().request("wallet_x", CREDENTIAL, owner_user_id="stranger")


def test_a_repeat_request_returns_the_open_one() -> None:
    target = service()
    first = target.request("wallet_x", CREDENTIAL, owner_user_id="holder")
    second = target.request("wallet_x", CREDENTIAL, owner_user_id="holder")
    assert first.request_id == second.request_id


def test_only_the_original_issuer_can_decide() -> None:
    target = service()
    request = target.request("wallet_x", CREDENTIAL, owner_user_id="holder")
    with pytest.raises(PermissionDeniedError):
        target.approve(
            request.request_id,
            issuer_did="did:web:other.example",
            create_offer=lambda *_: "offer",
        )


def test_approval_offers_the_old_claims_to_the_new_did_once() -> None:
    target = service()
    request = target.request("wallet_x", CREDENTIAL, owner_user_id="holder")
    seen = {}

    def create_offer(credential_type, claims):
        seen.update(claims, type=credential_type)
        return "openid-credential-offer://?x"

    approved = target.approve(
        request.request_id, issuer_did=ISSUER, create_offer=create_offer
    )
    assert approved.status == "OFFERED"
    assert approved.offer_link
    assert seen["degree"] == "BSc"
    assert seen["recipient_did"] == NEW
    assert "id" not in seen
    with pytest.raises(ReissuanceError):
        target.approve(
            request.request_id, issuer_did=ISSUER, create_offer=create_offer
        )


def test_rejection_creates_no_offer() -> None:
    target = service()
    request = target.request("wallet_x", CREDENTIAL, owner_user_id="holder")
    rejected = target.reject(request.request_id, issuer_did=ISSUER)
    assert rejected.status == "REJECTED" and rejected.offer_link is None


def test_webauthn_is_not_configured_by_default() -> None:
    assert load_webauthn_settings({}).configured is False


def test_webauthn_needs_both_values() -> None:
    with pytest.raises(PersistenceConfigurationError):
        load_webauthn_settings({"IDENTITY_WEBAUTHN_RP_ID": "example.org"})


def test_production_webauthn_needs_https() -> None:
    with pytest.raises(PersistenceConfigurationError):
        load_webauthn_settings(
            {
                "IDENTITY_ENVIRONMENT": "production",
                "IDENTITY_WEBAUTHN_RP_ID": "example.org",
                "IDENTITY_WEBAUTHN_ORIGIN": "http://example.org",
            }
        )


def test_unconfigured_webauthn_refuses_every_ceremony() -> None:
    target = WebAuthnService(
        credentials=MemoryCollection(),
        challenges=MemoryCollection(),
        settings=WebAuthnSettings(),
        step_up=None,
        clock=lambda: NOW,
    )
    principal = SimpleNamespace(id="u", username="u", display_name="u", session_id="s")
    with pytest.raises(StepUpRequiredError):
        target.registration_options(principal)
    with pytest.raises(StepUpRequiredError):
        target.verify_step_up(principal, {}, action="a.b", resource="r")
