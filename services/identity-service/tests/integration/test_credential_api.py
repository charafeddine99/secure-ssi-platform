import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.v1.dependencies import (
    get_clock,
    get_credential_api_service,
    get_credential_issuance_repository,
    get_status_list_entry_repository,
)
from app.application.services.credential_api_service import CredentialApiService
from app.application.services.credential_proof_service import (
    CredentialProofService,
)
from app.infrastructure.crypto.ed25519_signer import Ed25519CredentialSigner
from app.infrastructure.crypto.jcs_canonicalizer import JcsCanonicalizer
from app.infrastructure.crypto.local_issuer_key_provider import (
    LocalIssuerKeyProvider,
    SYNTHETIC_ISSUER_DID,
)
from app.infrastructure.persistence.issuance_repository import (
    MongoCredentialIssuanceRepository,
)
from app.infrastructure.persistence.status_list_repositories import (
    MongoCredentialStatusEntryRepository,
)
from app.infrastructure.fixtures.tampered_credentials import (
    build_tampered_credentials,
)
from app.main import app
from app.services.credential_validator import CredentialProfileValidator
from app.services.did_resolver import CompositeDidResolver, DidWebFixtureResolver
from tests.support.fake_mongo import FakeDatabase


FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures"
UNSIGNED_PATH = FIXTURE_ROOT / "unsigned-university-affiliation.vc.json"
SIGNED_PATH = FIXTURE_ROOT / "valid-signed-university-affiliation.vc.json"
FIXED_TIME = datetime(2026, 6, 1, tzinfo=UTC)
PRIMARY_SEED_HEX = (
    "dbdd31e053d58e33fff0d0a842d9a510"
    "ee0b5c2b52662caa91e8e6d84821b419"
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def client() -> TestClient:
    database = FakeDatabase()
    app.dependency_overrides[get_clock] = lambda: (lambda: FIXED_TIME)
    app.dependency_overrides[
        get_credential_issuance_repository
    ] = lambda: MongoCredentialIssuanceRepository(
        database["credentials"]  # type: ignore[arg-type]
    )
    app.dependency_overrides[
        get_status_list_entry_repository
    ] = lambda: MongoCredentialStatusEntryRepository(
        database["credential_status_entries"],  # type: ignore[arg-type]
        database["credentials"],  # type: ignore[arg-type]
    )
    app.state.issuance_database = database
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def sign(client: TestClient) -> dict[str, Any]:
    token_response = client.post(
        "/api/v1/auth/token",
        json={
            "username": "issuer@example.test",
            "password": "Issuer-Prototype-2026!",
        },
    )
    assert token_response.status_code == 200
    response = client.post(
        "/api/v1/credentials/sign",
        json={"credential": load_json(UNSIGNED_PATH)},
        headers={
            "Authorization": (
                f"Bearer {token_response.json()['accessToken']}"
            )
        },
    )
    assert response.status_code == 201
    return response.json()["credential"]


def test_validate_accepts_unsigned_credential_without_signing(
    client: TestClient,
) -> None:
    credential = load_json(UNSIGNED_PATH)
    original = copy.deepcopy(credential)

    response = client.post(
        "/api/v1/credentials/validate",
        json={"credential": credential},
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert response.json()["cryptographicVerificationPerformed"] is False
    assert "credential" not in response.json()
    assert credential == original


def test_validate_accepts_signed_profile_without_claiming_verification(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/credentials/validate",
        json={"credential": load_json(SIGNED_PATH)},
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert response.json()["cryptographicVerificationPerformed"] is False


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (
            lambda value: value["credentialSubject"].update(
                {"unknownClaim": "rejected"}
            ),
            "UNSUPPORTED_CLAIM",
        ),
        (
            lambda value: value.update({"@context": ["invalid"]}),
            "UNSUPPORTED_CONTEXT",
        ),
        (
            lambda value: value.update({"type": ["VerifiableCredential"]}),
            "UNSUPPORTED_TYPE",
        ),
    ],
)
def test_validate_returns_controlled_profile_failures(
    client: TestClient,
    mutation: Any,
    reason: str,
) -> None:
    credential = load_json(UNSIGNED_PATH)
    mutation(credential)

    response = client.post(
        "/api/v1/credentials/validate",
        json={"credential": credential},
    )

    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert reason in response.json()["errors"]


def test_validate_returns_controlled_malformed_proof(
    client: TestClient,
) -> None:
    credential = load_json(SIGNED_PATH)
    credential["proof"]["proofValue"] = "not-multibase"

    response = client.post(
        "/api/v1/credentials/validate",
        json={"credential": credential},
    )

    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert "INVALID_PROOF_VALUE" in response.json()["errors"]


def test_credential_size_limit_maps_to_413(client: TestClient) -> None:
    credential = load_json(UNSIGNED_PATH)
    credential["padding"] = "x" * 33000

    response = client.post(
        "/api/v1/credentials/validate",
        json={"credential": credential},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "CREDENTIAL_TOO_LARGE"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"credential": "not-an-object"},
        {"credential": {}, "unexpected": True},
    ],
)
def test_invalid_envelope_uses_central_422_shape(
    client: TestClient,
    payload: dict[str, Any],
) -> None:
    response = client.post("/api/v1/credentials/validate", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REQUEST_VALIDATION_FAILED"
    assert response.json()["requestId"] == response.headers["x-request-id"]


def test_sign_returns_deterministic_data_integrity_proof(
    client: TestClient,
) -> None:
    original = load_json(UNSIGNED_PATH)
    credential = sign(client)
    proof = credential["proof"]
    status_entry = credential["credentialStatus"]

    assert proof["type"] == "DataIntegrityProof"
    assert proof["cryptosuite"] == "eddsa-jcs-2022"
    assert proof["proofPurpose"] == "assertionMethod"
    assert proof["verificationMethod"] == "did:web:issuer.example#key-1"
    assert proof["proofValue"].startswith("z")
    assert proof["created"] == "2026-06-01T00:00:00Z"
    assert status_entry["type"] == "BitstringStatusListEntry"
    assert status_entry["statusPurpose"] == "revocation"
    assert status_entry["statusListIndex"].isdecimal()
    assert status_entry["statusListCredential"].startswith(
        "http://localhost:8001/api/v1/status-lists/revocation-"
    )
    assert credential["id"] == original["id"]
    assert CredentialProfileValidator().validate(
        credential,
        require_proof=True,
    )


def test_sign_rejects_existing_proof_with_409(client: TestClient) -> None:
    headers = issuer_auth_headers(client)
    response = client.post(
        "/api/v1/credentials/sign",
        json={"credential": load_json(SIGNED_PATH)},
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "CREDENTIAL_ALREADY_SIGNED",
        "message": "Credential already contains a proof.",
        "details": [],
    }


def test_sign_rejects_unknown_issuer_without_leaking_domain_message(
    client: TestClient,
) -> None:
    credential = load_json(UNSIGNED_PATH)
    credential["issuer"] = "did:web:unknown.example"

    response = client.post(
        "/api/v1/credentials/sign",
        json={"credential": credential},
        headers=issuer_auth_headers(client),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNKNOWN_ISSUER"
    assert "local key provider" not in response.text


def test_sign_rejects_invalid_profile_and_never_returns_key_material(
    client: TestClient,
) -> None:
    credential = load_json(UNSIGNED_PATH)
    credential["credentialSubject"]["degree"] = "Unknown Degree"

    response = client.post(
        "/api/v1/credentials/sign",
        json={"credential": credential},
        headers=issuer_auth_headers(client),
    )

    assert response.status_code == 400
    lowered = response.text.lower()
    assert PRIMARY_SEED_HEX not in response.text
    assert "privatekey" not in lowered
    assert "secretkey" not in lowered


def test_sign_persists_credential_and_status_assignment_atomically(
    client: TestClient,
) -> None:
    credential = sign(client)
    database = client.app.state.issuance_database
    stored = database["credentials"].find_one(
        {"credentialId": credential["id"]}
    )

    assert stored is not None
    assert stored["rawCredential"] == credential
    assert stored["statusEntryId"] is not None
    assert stored["statusListId"] in credential["credentialStatus"][
        "statusListCredential"
    ]
    assert str(stored["statusListIndex"]) == credential[
        "credentialStatus"
    ]["statusListIndex"]
    assert database["credential_status_entries"].documents == []


def test_sign_rejects_duplicate_credential_id(client: TestClient) -> None:
    sign(client)

    response = client.post(
        "/api/v1/credentials/sign",
        json={"credential": load_json(UNSIGNED_PATH)},
        headers=issuer_auth_headers(client),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CREDENTIAL_ALREADY_ISSUED"


def test_verify_accepts_a_valid_signed_credential(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/credentials/verify",
        json={"credential": sign(client)},
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert response.json()["errors"] == []
    assert all(response.json()["checks"].values())


TAMPER_FIXTURE_NAMES = tuple(
    build_tampered_credentials(load_json(SIGNED_PATH))
)


@pytest.mark.parametrize("fixture_name", TAMPER_FIXTURE_NAMES)
def test_verify_rejects_all_tampered_fixtures_without_500(
    client: TestClient,
    fixture_name: str,
) -> None:
    tampered = build_tampered_credentials(load_json(SIGNED_PATH))[fixture_name]

    response = client.post(
        "/api/v1/credentials/verify",
        json={"credential": tampered},
    )

    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert response.json()["errors"]


def test_verify_does_not_mutate_credential(client: TestClient) -> None:
    credential = load_json(SIGNED_PATH)
    original = copy.deepcopy(credential)

    response = client.post(
        "/api/v1/credentials/verify",
        json={"credential": credential},
    )

    assert response.status_code == 200
    assert credential == original


def test_verify_rejects_unknown_proof_type_without_500(
    client: TestClient,
) -> None:
    credential = load_json(SIGNED_PATH)
    credential["proof"]["type"] = "UnknownProofType"

    response = client.post(
        "/api/v1/credentials/verify",
        json={"credential": credential},
    )

    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert "UNSUPPORTED_PROOF_TYPE" in response.json()["errors"]


def test_verify_rejects_key_substitution_through_http(
    client: TestClient,
    tmp_path: Path,
) -> None:
    document = load_json(FIXTURE_ROOT / "issuer.did.json")
    document["verificationMethod"][0]["publicKeyMultibase"] = (
        LocalIssuerKeyProvider.alternate_for_tests().public_key_multibase
    )
    substituted_path = tmp_path / "substituted.did.json"
    substituted_path.write_text(json.dumps(document), encoding="utf-8")
    validator = CredentialProfileValidator()
    proof_service = CredentialProofService(
        validator=validator,
        canonicalizer=JcsCanonicalizer(),
        signer=Ed25519CredentialSigner(),
        key_provider=LocalIssuerKeyProvider(),
        did_resolver=CompositeDidResolver(
            {
                "web": DidWebFixtureResolver(
                    {SYNTHETIC_ISSUER_DID: substituted_path}
                )
            }
        ),
        clock=lambda: FIXED_TIME,
    )
    service = CredentialApiService(
        validator=validator,
        proof_service=proof_service,
    )
    app.dependency_overrides[get_credential_api_service] = lambda: service

    response = client.post(
        "/api/v1/credentials/verify",
        json={"credential": load_json(SIGNED_PATH)},
    )

    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert "PUBLIC_KEY_MISMATCH" in response.json()["errors"]


def test_capabilities_are_explicit_and_non_sensitive(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/credentials/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["cryptosuites"] == ["eddsa-jcs-2022"]
    assert body["didMethods"]["issuer"] == ["did:web"]
    assert body["operations"]["persist"] is True
    assert body["operations"]["revoke"] is True
    assert body["operations"]["present"] is True
    assert "no production KMS or HSM" in body["limitations"]
    assert PRIMARY_SEED_HEX not in response.text
    assert "privateKey" not in response.text


def test_duplicate_json_property_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/credentials/validate",
        content='{"credential":{},"credential":{}}',
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "DUPLICATE_JSON_PROPERTY"


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_json_numbers_are_rejected(
    client: TestClient,
    constant: str,
) -> None:
    response = client.post(
        "/api/v1/credentials/validate",
        content=f'{{"credential":{{"value":{constant}}}}}',
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_JSON"


def test_invalid_utf8_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/credentials/validate",
        content=b'{"credential":{"value":"\xff"}}',
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_JSON"


def test_excessive_json_depth_is_rejected(client: TestClient) -> None:
    nested = '{"child":' * 33 + "{}" + "}" * 33
    response = client.post(
        "/api/v1/credentials/validate",
        content=f'{{"credential":{nested}}}',
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "JSON_TOO_DEEP"


def test_request_payload_limit_is_enforced(client: TestClient) -> None:
    response = client.post(
        "/api/v1/credentials/validate",
        content=b"x" * 36865,
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "REQUEST_TOO_LARGE"


def test_malformed_json_is_a_transport_error(client: TestClient) -> None:
    response = client.post(
        "/api/v1/credentials/verify",
        content='{"credential":',
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_JSON"


def test_json_content_type_is_required(client: TestClient) -> None:
    response = client.post(
        "/api/v1/credentials/validate",
        content='{"credential":{}}',
        headers={"content-type": "text/plain"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "JSON_CONTENT_TYPE_REQUIRED"


def test_request_id_is_reused_in_header_and_error_body(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/credentials/validate",
        json={},
        headers={"x-request-id": "test-request-42"},
    )

    assert response.headers["x-request-id"] == "test-request-42"
    assert response.json()["requestId"] == "test-request-42"


def test_unexpected_exception_returns_safe_500(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    credential = load_json(SIGNED_PATH)
    proof_value = credential["proof"]["proofValue"]

    class FailingService:
        def validate_credential(self, credential: Any) -> None:
            raise RuntimeError("SensitiveFailureClass secret internal detail")

    app.dependency_overrides[get_credential_api_service] = (
        lambda: FailingService()
    )

    response = client.post(
        "/api/v1/credentials/validate",
        json={"credential": credential},
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert "RuntimeError" not in response.text
    assert "SensitiveFailureClass" not in response.text
    assert "Traceback" not in response.text
    assert response.json()["requestId"] == response.headers["x-request-id"]
    assert proof_value not in caplog.text
    assert "SensitiveFailureClass" not in caplog.text
    assert json.dumps(credential) not in caplog.text


def issuer_auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/token",
        json={
            "username": "issuer@example.test",
            "password": "Issuer-Prototype-2026!",
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}
