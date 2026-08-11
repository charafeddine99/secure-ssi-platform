import base64
import json
import os
import socket
import ssl
import time
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.domain.managed_key import (
    KeyAlgorithm,
    KeyPurpose,
    ProviderKeyMetadata,
    ProviderKeyNotFoundError,
    ProviderMetadataError,
    ProviderPermissionDeniedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


@dataclass(frozen=True)
class KmsHttpResponse:
    status: int
    body: bytes = b""


class KmsHttpTransport(Protocol):
    def request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> KmsHttpResponse: ...


class ProviderAuthentication(Protocol):
    def headers(self) -> dict[str, str]: ...


class NoProviderAuthentication:
    def headers(self) -> dict[str, str]:
        return {}


class EnvironmentBearerAuthentication:
    """Resolves a bearer secret at call time without retaining its value."""

    def __init__(self, environment_variable: str) -> None:
        if not environment_variable.strip():
            raise ValueError("KMS authentication environment name is empty.")
        self._environment_variable = environment_variable

    def headers(self) -> dict[str, str]:
        value = os.environ.get(self._environment_variable, "").strip()
        if not value:
            raise ProviderPermissionDeniedError(
                "KMS authentication is unavailable."
            )
        return {"Authorization": f"Bearer {value}"}

    def __repr__(self) -> str:
        return (
            "EnvironmentBearerAuthentication("
            f"environment_variable={self._environment_variable!r}, "
            "credential=<redacted>)"
        )


class UrllibKmsHttpTransport:
    def __init__(
        self,
        *,
        tls_verify: bool = True,
        client_certificate_path: str | None = None,
        client_key_path: str | None = None,
    ) -> None:
        context = ssl.create_default_context()
        if not tls_verify:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        if client_certificate_path and client_key_path:
            context.load_cert_chain(
                certfile=client_certificate_path,
                keyfile=client_key_path,
            )
        self._context = context

    def request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> KmsHttpResponse:
        request = Request(
            url=url,
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(
                request,
                timeout=timeout_seconds,
                context=self._context,
            ) as response:
                return KmsHttpResponse(
                    status=response.status,
                    body=response.read(),
                )
        except HTTPError as error:
            return KmsHttpResponse(status=error.code, body=error.read())


class GenericRemoteKmsAdapter:
    """Generic JSON/HTTPS KMS gateway adapter; not vendor-specific."""

    def __init__(
        self,
        *,
        name: str,
        base_url: str,
        transport: KmsHttpTransport,
        authentication: ProviderAuthentication | None = None,
        request_timeout_seconds: float = 5.0,
        retry_count: int = 2,
        retry_backoff_ms: int = 100,
        circuit_failure_threshold: int = 5,
        circuit_reset_seconds: int = 30,
    ) -> None:
        normalized_url = base_url.strip().rstrip("/")
        if not normalized_url.startswith("https://"):
            raise ValueError("Remote KMS base URL must use HTTPS.")
        self._name = name.strip().casefold()
        self._base_url = normalized_url
        self._transport = transport
        self._authentication = authentication or NoProviderAuthentication()
        self._timeout = request_timeout_seconds
        self._retry_count = retry_count
        self._retry_backoff = retry_backoff_ms / 1_000
        self._failure_threshold = circuit_failure_threshold
        self._circuit_reset_seconds = circuit_reset_seconds
        self._lock = Lock()
        self._consecutive_failures = 0
        self._circuit_opened_at: float | None = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def production_ready(self) -> bool:
        return True

    def create_key(
        self,
        *,
        key_id: str,
        algorithm: KeyAlgorithm,
        purpose: KeyPurpose,
        idempotency_key: str,
    ) -> ProviderKeyMetadata:
        data = self._json_request(
            "POST",
            "/v1/keys",
            {
                "keyId": key_id,
                "algorithm": algorithm.value,
                "purpose": purpose.value,
            },
            idempotency_key=idempotency_key,
        )
        return self._metadata(data)

    def get_key_metadata(
        self,
        provider_key_reference: str,
    ) -> ProviderKeyMetadata:
        data = self._json_request(
            "GET",
            f"/v1/keys/{quote(provider_key_reference, safe='')}",
        )
        return self._metadata(data)

    def sign(
        self,
        message: bytes,
        *,
        provider_key_reference: str,
        algorithm: KeyAlgorithm,
    ) -> bytes:
        data = self._json_request(
            "POST",
            f"/v1/keys/{quote(provider_key_reference, safe='')}:sign",
            {
                "algorithm": algorithm.value,
                "payload": _base64url(message),
                "payloadEncoding": "base64url",
            },
        )
        encoded = data.get("signature")
        if not isinstance(encoded, str):
            raise ProviderMetadataError(
                "KMS signing response is missing its signature."
            )
        try:
            return _base64url_decode(encoded)
        except (ValueError, UnicodeEncodeError) as error:
            raise ProviderMetadataError(
                "KMS signature encoding is invalid."
            ) from error

    def enable_key(self, provider_key_reference: str) -> None:
        self._action(provider_key_reference, "enable")

    def suspend_key(self, provider_key_reference: str) -> None:
        self._action(provider_key_reference, "suspend")

    def revoke_key(self, provider_key_reference: str) -> None:
        self._action(provider_key_reference, "revoke")

    def schedule_deletion(
        self,
        provider_key_reference: str,
        *,
        delete_at: datetime,
    ) -> None:
        self._action(
            provider_key_reference,
            "schedule-deletion",
            {"deleteAt": delete_at.isoformat()},
        )

    def cancel_scheduled_deletion(
        self,
        provider_key_reference: str,
    ) -> None:
        self._action(provider_key_reference, "cancel-deletion")

    def destroy_key(self, provider_key_reference: str) -> None:
        self._action(provider_key_reference, "destroy")

    def is_available(self) -> bool:
        try:
            self._json_request("GET", "/health")
        except ProviderUnavailableError:
            return False
        return True

    def _action(
        self,
        provider_key_reference: str,
        action: str,
        body: dict[str, object] | None = None,
    ) -> None:
        self._json_request(
            "POST",
            f"/v1/keys/{quote(provider_key_reference, safe='')}:{action}",
            body or {},
        )

    def _json_request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, object]:
        self._require_closed_circuit()
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            **self._authentication.headers(),
        }
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        body = (
            None
            if payload is None
            else json.dumps(
                payload,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        last_error: ProviderUnavailableError | None = None
        for attempt in range(self._retry_count + 1):
            try:
                response = self._transport.request(
                    method=method,
                    url=f"{self._base_url}{path}",
                    headers=headers,
                    body=body,
                    timeout_seconds=self._timeout,
                )
                self._raise_for_status(response.status)
                self._record_success()
                if not response.body:
                    return {}
                decoded = json.loads(response.body)
                if not isinstance(decoded, dict):
                    raise ProviderMetadataError(
                        "KMS response body must be a JSON object."
                    )
                return decoded
            except ProviderUnavailableError as error:
                last_error = error
                self._record_failure()
                if attempt < self._retry_count:
                    time.sleep(self._retry_backoff * (2**attempt))
            except (TimeoutError, socket.timeout):
                last_error = ProviderTimeoutError(
                    "The key provider request timed out."
                )
                self._record_failure()
                if attempt >= self._retry_count:
                    break
                time.sleep(self._retry_backoff * (2**attempt))
            except (URLError, OSError):
                last_error = ProviderUnavailableError(
                    "The key provider is temporarily unavailable."
                )
                self._record_failure()
                if attempt >= self._retry_count:
                    break
                time.sleep(self._retry_backoff * (2**attempt))
            except (json.JSONDecodeError, UnicodeDecodeError) as error:
                raise ProviderMetadataError(
                    "KMS response JSON is invalid."
                ) from error
        raise last_error or ProviderUnavailableError(
            "The key provider is temporarily unavailable."
        )

    def _metadata(self, data: dict[str, object]) -> ProviderKeyMetadata:
        try:
            return ProviderKeyMetadata(
                provider=str(data["provider"]),
                provider_key_reference=str(
                    data["providerKeyReference"]
                ),
                algorithm=KeyAlgorithm(str(data["algorithm"])),
                public_key_multibase=str(data["publicKeyMultibase"]),
                fingerprint=str(data["fingerprint"]),
                holder_did=str(data["holderDid"]),
                verification_method=str(data["verificationMethod"]),
                enabled=bool(data["enabled"]),
                destroyed=bool(data.get("destroyed", False)),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ProviderMetadataError(
                "KMS public metadata response is invalid."
            ) from error

    @staticmethod
    def _raise_for_status(status: int) -> None:
        if 200 <= status < 300:
            return
        if status == 404:
            raise ProviderKeyNotFoundError(
                "The provider key does not exist."
            )
        if status in {401, 403}:
            raise ProviderPermissionDeniedError(
                "The key provider denied the operation."
            )
        if status in {408, 504}:
            raise ProviderTimeoutError("The key provider request timed out.")
        if status == 429 or status >= 500:
            raise ProviderUnavailableError(
                "The key provider is temporarily unavailable."
            )
        raise ProviderMetadataError("The key provider rejected the request.")

    def _require_closed_circuit(self) -> None:
        with self._lock:
            if self._circuit_opened_at is None:
                return
            if (
                time.monotonic() - self._circuit_opened_at
                >= self._circuit_reset_seconds
            ):
                self._circuit_opened_at = None
                self._consecutive_failures = 0
                return
        raise ProviderUnavailableError(
            "The key provider circuit is temporarily open."
        )

    def _record_success(self) -> None:
        with self._lock:
            self._consecutive_failures = 0
            self._circuit_opened_at = None

    def _record_failure(self) -> None:
        with self._lock:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._failure_threshold:
                self._circuit_opened_at = time.monotonic()

    def __repr__(self) -> str:
        return (
            "GenericRemoteKmsAdapter("
            f"name={self.name!r}, base_url={self._base_url!r}, "
            "authentication=<redacted>)"
        )


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))
