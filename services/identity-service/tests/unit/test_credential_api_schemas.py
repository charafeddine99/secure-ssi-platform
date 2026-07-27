import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.main import app
from app.domain.credential_status import (
    CredentialStatus,
    CredentialStatusSnapshot,
)
from app.schemas.credential_api import (
    ApiError,
    ApiErrorResponse,
    CredentialCapabilitiesResponse,
    CredentialEnvelope,
    CredentialOperationsResponse,
    CredentialRevocationRequest,
    CredentialSignResponse,
    CredentialStatusResponse,
    DidMethodsResponse,
)


FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures"
UNSIGNED_CREDENTIAL_PATH = (
    FIXTURE_ROOT / "unsigned-university-affiliation.vc.json"
)


def load_unsigned_credential() -> dict[str, Any]:
    return json.loads(UNSIGNED_CREDENTIAL_PATH.read_text(encoding="utf-8"))


def test_request_envelope_accepts_a_credential_object() -> None:
    envelope = CredentialEnvelope(
        credential=load_unsigned_credential()
    )

    assert envelope.credential["issuer"] == "did:web:issuer.example"


def test_request_envelope_rejects_unknown_top_level_fields() -> None:
    with pytest.raises(ValidationError):
        CredentialEnvelope.model_validate(
            {
                "credential": load_unsigned_credential(),
                "unexpected": True,
            }
        )


def test_request_envelope_requires_credential() -> None:
    with pytest.raises(ValidationError):
        CredentialEnvelope.model_validate({})


def test_request_envelope_rejects_string_credential() -> None:
    with pytest.raises(ValidationError):
        CredentialEnvelope.model_validate({"credential": "not-an-object"})


def test_error_response_uses_the_central_shape() -> None:
    response = ApiErrorResponse(
        error=ApiError(
            code="CREDENTIAL_ALREADY_SIGNED",
            message="Credential already contains a proof.",
            details=[],
        ),
        request_id="request-123",
    )

    assert response.model_dump(by_alias=True) == {
        "error": {
            "code": "CREDENTIAL_ALREADY_SIGNED",
            "message": "Credential already contains a proof.",
            "details": [],
        },
        "requestId": "request-123",
    }


def test_capabilities_schema_contains_bounded_operations() -> None:
    response = CredentialCapabilitiesResponse(
        service="identity-service",
        api_version="v1",
        credential_model="W3C VC Data Model 2.0 local profile",
        proof_type="DataIntegrityProof",
        cryptosuites=["eddsa-jcs-2022"],
        did_methods=DidMethodsResponse(
            issuer=["did:web"],
            holder_fixtures=["did:key"],
        ),
        operations=CredentialOperationsResponse(
            validation_supported=True,
            sign=True,
            verify=True,
            persist=False,
            revoke=True,
            present=False,
        ),
        limitations=["local academic prototype"],
    )

    serialized = response.model_dump(by_alias=True)
    assert serialized["apiVersion"] == "v1"
    assert serialized["operations"] == {
        "validate": True,
        "sign": True,
        "verify": True,
        "persist": False,
        "revoke": True,
        "present": False,
    }


def test_revocation_request_and_status_response_are_strict() -> None:
    request = CredentialRevocationRequest(
        reason="  Affiliation ended  "
    )
    snapshot = CredentialStatusSnapshot(
        credential_id="urn:uuid:credential-1",
        status=CredentialStatus.REVOKED,
        expiration_date=None,
        revoked_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
        revocation_reason=request.reason,
        revoked_by="usr_local_issuer",
        version=2,
    )

    assert request.reason == "Affiliation ended"
    assert CredentialStatusResponse.from_domain(snapshot).model_dump(
        mode="json",
        by_alias=True,
    ) == {
        "credentialId": "urn:uuid:credential-1",
        "status": "REVOKED",
        "revoked": True,
        "revocationReason": "Affiliation ended",
        "revokedAt": "2026-07-24T12:00:00Z",
        "revokedBy": "usr_local_issuer",
    }
    with pytest.raises(ValidationError):
        CredentialRevocationRequest.model_validate(
            {"reason": "valid", "unexpected": True}
        )


def test_response_models_have_no_sensitive_key_fields() -> None:
    fields = {
        name.lower()
        for name in CredentialSignResponse.model_json_schema()[
            "properties"
        ]
    }

    assert not fields.intersection(
        {"privatekey", "privatekeyjwk", "seed", "secret", "signingkey"}
    )


def test_openapi_has_versioned_routes_and_no_sensitive_schema_properties() -> None:
    schema = app.openapi()
    expected_paths = {
        "/api/v1/credentials/validate",
        "/api/v1/credentials/sign",
        "/api/v1/credentials/verify",
        "/api/v1/credentials/{credential_id}/revoke",
        "/api/v1/credentials/{credential_id}/status",
        "/api/v1/credentials/capabilities",
    }

    assert expected_paths.issubset(schema["paths"])
    property_names = _collect_property_names(schema)
    normalized = {
        name.replace("_", "").replace("-", "").lower()
        for name in property_names
    }
    assert not normalized.intersection(
        {
            "privatekey",
            "privatekeyjwk",
            "privatekeymultibase",
            "secretkey",
            "secretkeyjwk",
            "seed",
            "rawprivatebytes",
            "signingcapability",
        }
    )


def _collect_property_names(value: Any) -> set[str]:
    names: set[str] = set()
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            properties = item.get("properties")
            if isinstance(properties, dict):
                names.update(str(name) for name in properties)
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return names
