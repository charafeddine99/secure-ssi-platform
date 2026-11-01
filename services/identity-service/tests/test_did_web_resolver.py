import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import httpx

from app.domain.did import DidResolutionError, DidResolutionErrorCode
from app.services.did_document_validator import DidDocumentValidator
from app.services.did_resolver import DidWebResolver


ISSUER_DID = "did:web:issuer.example"
PUBLIC_KEY = "z6MkuG4LGc3sEyCZTFbKGVNi7ehNi1PT3zK3KcrUhKvUi3wd"
# Plain HTTP is only ever used for explicitly allowlisted development hosts.
TEST_HTTP_HOSTS = {"issuer.example", "unregistered.example"}


def valid_document(did: str = ISSUER_DID) -> dict[str, Any]:
    method_id = f"{did}#key-1"
    return {
        "@context": [
            "https://www.w3.org/ns/did/v1",
            "https://w3id.org/security/multikey/v1",
        ],
        "id": did,
        "verificationMethod": [
            {
                "id": method_id,
                "type": "Multikey",
                "controller": did,
                "publicKeyMultibase": PUBLIC_KEY,
            }
        ],
        "assertionMethod": [method_id],
    }


class MockResponse:
    def __init__(self, content: bytes, status_code: int = 200, headers: dict = None):
        self.content = content
        self.status_code = status_code
        self.headers = headers or {"Content-Type": "application/json"}
    
    def iter_bytes(self):
        yield self.content
        
    def __enter__(self):
        return self
        
    def __exit__(self, *args):
        pass

class MockClient:
    def __init__(self, document: dict[str, Any] = None, raw: bytes = None, status_code: int = 200, raise_err: Exception = None):
        if raw is not None:
            self.content = raw
        elif document is not None:
            self.content = json.dumps(document).encode("utf-8")
        else:
            self.content = b""
        self.status_code = status_code
        self.raise_err = raise_err
        
    def __enter__(self):
        return self
        
    def __exit__(self, *args):
        pass
        
    def stream(self, method, url, **kwargs):
        if self.raise_err:
            raise self.raise_err
        if "unregistered" in str(url):
            return MockResponse(b"", status_code=404)
        return MockResponse(self.content, status_code=self.status_code)

@pytest.fixture
def mock_httpx_client():
    with patch("httpx.Client") as mock_client_cls:
        yield mock_client_cls


def test_did_web_resolves_via_network(mock_httpx_client) -> None:
    mock_httpx_client.return_value = MockClient(document=valid_document())
    result = DidWebResolver(allow_insecure_http=True, insecure_http_hosts=TEST_HTTP_HOSTS).resolve(ISSUER_DID)

    assert result.did == ISSUER_DID
    assert result.metadata.method == "web"
    assert result.metadata.source == "network"
    assert result.did_document["id"] == ISSUER_DID
    assert result.did_document["assertionMethod"] == [
        "did:web:issuer.example#key-1"
    ]


def test_unregistered_did_web_is_not_found(mock_httpx_client) -> None:
    mock_httpx_client.return_value = MockClient()
    with pytest.raises(DidResolutionError) as captured:
        DidWebResolver(allow_insecure_http=True, insecure_http_hosts=TEST_HTTP_HOSTS).resolve("did:web:unregistered.example")

    assert captured.value.code == DidResolutionErrorCode.NOT_FOUND


def test_mismatched_document_id_is_rejected(mock_httpx_client) -> None:
    mock_httpx_client.return_value = MockClient(document=valid_document("did:web:other.example"))

    with pytest.raises(DidResolutionError) as captured:
        DidWebResolver(allow_insecure_http=True, insecure_http_hosts=TEST_HTTP_HOSTS).resolve(ISSUER_DID)

    assert captured.value.code == DidResolutionErrorCode.INVALID_DID_DOCUMENT


def test_missing_assertion_method_is_rejected(mock_httpx_client) -> None:
    document = valid_document()
    document.pop("assertionMethod")
    mock_httpx_client.return_value = MockClient(document=document)

    with pytest.raises(DidResolutionError) as captured:
        DidWebResolver(allow_insecure_http=True, insecure_http_hosts=TEST_HTTP_HOSTS).resolve(ISSUER_DID)

    assert captured.value.code == DidResolutionErrorCode.INVALID_DID_DOCUMENT


def test_undeclared_assertion_method_is_rejected(mock_httpx_client) -> None:
    document = valid_document()
    document["assertionMethod"] = [f"{ISSUER_DID}#unknown"]
    mock_httpx_client.return_value = MockClient(document=document)

    with pytest.raises(DidResolutionError) as captured:
        DidWebResolver(allow_insecure_http=True, insecure_http_hosts=TEST_HTTP_HOSTS).resolve(ISSUER_DID)

    assert captured.value.code == DidResolutionErrorCode.INVALID_DID_DOCUMENT


@pytest.mark.parametrize(
    "private_field",
    ["privateKeyJwk", "privateKeyMultibase", "secretKeyMultibase"],
)
def test_private_key_material_is_rejected(
    mock_httpx_client,
    private_field: str,
) -> None:
    document = valid_document()
    document["verificationMethod"][0][private_field] = "synthetic-secret"
    mock_httpx_client.return_value = MockClient(document=document)

    with pytest.raises(DidResolutionError) as captured:
        DidWebResolver(allow_insecure_http=True, insecure_http_hosts=TEST_HTTP_HOSTS).resolve(ISSUER_DID)

    assert captured.value.code == DidResolutionErrorCode.PRIVATE_KEY_MATERIAL


def test_oversized_document_is_rejected_before_parsing(mock_httpx_client) -> None:
    mock_httpx_client.return_value = MockClient(document=valid_document())
    resolver = DidWebResolver(
        validator=DidDocumentValidator(max_document_bytes=64),
        allow_insecure_http=True,
        insecure_http_hosts=TEST_HTTP_HOSTS,
    )

    with pytest.raises(DidResolutionError) as captured:
        resolver.resolve(ISSUER_DID)

    assert captured.value.code == DidResolutionErrorCode.DOCUMENT_TOO_LARGE


def test_duplicate_json_properties_are_rejected(mock_httpx_client) -> None:
    raw_json = b'{"id":"did:web:issuer.example","id":"did:web:issuer.example"}'
    mock_httpx_client.return_value = MockClient(raw=raw_json)

    with pytest.raises(DidResolutionError) as captured:
        DidWebResolver(allow_insecure_http=True, insecure_http_hosts=TEST_HTTP_HOSTS).resolve(ISSUER_DID)

    assert captured.value.code == DidResolutionErrorCode.INVALID_DID_DOCUMENT


def test_unapproved_context_is_rejected(mock_httpx_client) -> None:
    document = valid_document()
    document["@context"].append("https://attacker.example/context")
    mock_httpx_client.return_value = MockClient(document=document)

    with pytest.raises(DidResolutionError) as captured:
        DidWebResolver(allow_insecure_http=True, insecure_http_hosts=TEST_HTTP_HOSTS).resolve(ISSUER_DID)

    assert captured.value.code == DidResolutionErrorCode.INVALID_DID_DOCUMENT


def test_unsupported_verification_method_type_is_rejected(mock_httpx_client) -> None:
    document = valid_document()
    document["verificationMethod"][0]["type"] = "JsonWebKey"
    mock_httpx_client.return_value = MockClient(document=document)

    with pytest.raises(DidResolutionError) as captured:
        DidWebResolver(allow_insecure_http=True, insecure_http_hosts=TEST_HTTP_HOSTS).resolve(ISSUER_DID)

    assert captured.value.code == DidResolutionErrorCode.UNSUPPORTED_KEY_TYPE

def test_ssrf_protection_blocks_local_ip() -> None:
    resolver = DidWebResolver(allow_insecure_http=False)
    with pytest.raises(DidResolutionError) as captured:
        # 127.0.0.1 resolves to a non-global IP
        resolver.resolve("did:web:127.0.0.1")
    
    assert captured.value.code == DidResolutionErrorCode.NOT_FOUND


def test_plain_http_is_never_used_for_hosts_outside_the_allowlist() -> None:
    # allow_insecure_http alone is not enough: the host must be allowlisted,
    # otherwise HTTPS is required and the SSRF check runs (127.0.0.1 is blocked).
    resolver = DidWebResolver(allow_insecure_http=True, insecure_http_hosts={"other.example"})
    with patch("socket.getaddrinfo", return_value=[(None, None, None, "", ("127.0.0.1", 0))]):
        with pytest.raises(DidResolutionError) as captured:
            resolver.resolve(ISSUER_DID)
    assert "SSRF" in captured.value.args[0] or captured.value.code == DidResolutionErrorCode.NOT_FOUND


@pytest.mark.parametrize("address", ["::1", "fd00::1", "169.254.169.254", "10.0.0.5"])
def test_ssrf_protection_blocks_private_and_ipv6_addresses(address: str) -> None:
    resolver = DidWebResolver()
    with patch("socket.getaddrinfo", return_value=[(None, None, None, "", (address, 0))]):
        with pytest.raises(DidResolutionError):
            resolver.resolve(ISSUER_DID)


def test_ssrf_protection_rejects_mixed_public_and_private_answers() -> None:
    # DNS rebinding style answer: one public and one internal address.
    resolver = DidWebResolver()
    answers = [(None, None, None, "", ("93.184.216.34", 0)), (None, None, None, "", ("127.0.0.1", 0))]
    with patch("socket.getaddrinfo", return_value=answers):
        with pytest.raises(DidResolutionError):
            resolver.resolve(ISSUER_DID)


def test_https_request_is_pinned_to_the_vetted_address(mock_httpx_client) -> None:
    client = MockClient(document=valid_document())
    seen: dict[str, Any] = {}
    original = client.stream

    def capture(method, url, **kwargs):
        seen["url"] = str(url)
        seen.update(kwargs)
        return original(method, url, **kwargs)

    client.stream = capture
    mock_httpx_client.return_value = client
    with patch("socket.getaddrinfo", return_value=[(None, None, None, "", ("93.184.216.34", 0))]):
        result = DidWebResolver().resolve(ISSUER_DID)
    assert result.did == ISSUER_DID
    assert seen["url"].startswith("https://93.184.216.34/")
    assert seen["headers"]["Host"] == "issuer.example"
    assert seen["extensions"]["sni_hostname"] == "issuer.example"
    assert mock_httpx_client.call_args.kwargs.get("follow_redirects") is False


def test_pinned_resolver_serves_own_did_without_network(tmp_path: Path) -> None:
    from app.services.did_resolver import PinnedDidWebResolver

    document_path = tmp_path / "did.json"
    document_path.write_text(json.dumps(valid_document()), encoding="utf-8")
    with patch("httpx.Client") as client_cls:
        result = PinnedDidWebResolver({ISSUER_DID: document_path}).resolve(ISSUER_DID)
    client_cls.assert_not_called()
    assert result.metadata.source == "pinned"


def test_settings_refuse_plain_http_in_production_and_without_allowlist() -> None:
    from app.config.did_resolution_settings import load_did_resolution_settings
    from app.domain.exceptions import AuthConfigurationError

    with pytest.raises(AuthConfigurationError):
        load_did_resolution_settings({"IDENTITY_ENVIRONMENT": "production", "IDENTITY_DID_WEB_ALLOW_INSECURE_HTTP": "true", "IDENTITY_DID_WEB_INSECURE_HOSTS": "a.example"})
    with pytest.raises(AuthConfigurationError):
        load_did_resolution_settings({"IDENTITY_DID_WEB_ALLOW_INSECURE_HTTP": "true"})
    assert load_did_resolution_settings({}).allow_insecure_http is False
