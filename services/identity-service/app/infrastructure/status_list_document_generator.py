import base64
import gzip
import re
import zlib
from collections.abc import Collection, Iterable, Mapping
from copy import deepcopy
from datetime import UTC, datetime
from io import BytesIO
from typing import Any

from app.application.ports.canonicalizer import CredentialCanonicalizer
from app.application.ports.credential_signer import CredentialSigner
from app.application.ports.key_provider import KeyProvider
from app.domain.bitstring_status_list import (
    MAXIMUM_STATUS_LIST_ENTRIES,
    MINIMUM_STATUS_LIST_ENTRIES,
    StatusListGenerationError,
)
from app.infrastructure.crypto.multibase import encode_base58_btc


class StatusListDocumentGenerator:
    def __init__(
        self,
        *,
        canonicalizer: CredentialCanonicalizer,
        signer: CredentialSigner,
        key_provider: KeyProvider,
    ) -> None:
        self._canonicalizer = canonicalizer
        self._signer = signer
        self._key_provider = key_provider

    def generate(
        self,
        *,
        status_list_url: str,
        issuer_did: str,
        encoded_list: str,
        ttl_seconds: int,
        published_at: datetime,
        status_purpose: str = "revocation",
    ) -> Mapping[str, Any]:
        if not status_list_url.startswith(("http://", "https://")):
            raise StatusListGenerationError(
                "Status list publication URL must use HTTP(S)."
            )
        if status_purpose not in {"revocation", "suspension"}:
            raise StatusListGenerationError(
                "Status list purpose must be revocation or suspension."
            )
        try:
            signing_key = self._key_provider.get_signing_key(issuer_did)
            unsigned: dict[str, Any] = {
                "@context": ["https://www.w3.org/ns/credentials/v2"],
                "id": status_list_url,
                "type": [
                    "VerifiableCredential",
                    "BitstringStatusListCredential",
                ],
                "issuer": issuer_did,
                "validFrom": _format_timestamp(published_at),
                "credentialSubject": {
                    "id": f"{status_list_url}#list",
                    "type": "BitstringStatusList",
                    "statusPurpose": status_purpose,
                    "encodedList": encoded_list,
                    "ttl": ttl_seconds * 1_000,
                },
            }
            proof: dict[str, Any] = {
                "type": "DataIntegrityProof",
                "cryptosuite": "eddsa-jcs-2022",
                "created": _format_timestamp(published_at),
                "verificationMethod": signing_key.verification_method,
                "proofPurpose": "assertionMethod",
            }
            signing_input = self._canonicalizer.create_signing_input(
                unsigned,
                proof,
            )
            proof["proofValue"] = encode_base58_btc(
                self._signer.sign(signing_input, signing_key)
            )
            document = deepcopy(unsigned)
            document["proof"] = proof
            return document
        except StatusListGenerationError:
            raise
        except Exception as error:
            raise StatusListGenerationError(
                "Status list credential could not be generated."
            ) from error


def encode_status_list(
    revoked_indices: Collection[int] | Iterable[int],
    *,
    list_length: int,
) -> str:
    if list_length < 1:
        raise ValueError("Status list length must be positive.")
    bitstring = bytearray((list_length + 7) // 8)
    for index in set(revoked_indices):
        if not 0 <= index < list_length:
            raise ValueError("Revoked status index is outside the list.")
        bitstring[index // 8] |= 1 << (7 - (index % 8))
    output = BytesIO()
    with gzip.GzipFile(
        filename="",
        mode="wb",
        fileobj=output,
        compresslevel=9,
        mtime=0,
    ) as stream:
        stream.write(bitstring)
    encoded = base64.urlsafe_b64encode(output.getvalue()).rstrip(b"=")
    return "u" + encoded.decode("ascii")


from functools import lru_cache


@lru_cache(maxsize=64)
def decompress_status_list(encoded_list: str) -> bytes:
    """Decode a bounded W3C multibase base64url-gzip status list."""
    if not isinstance(encoded_list, str) or not encoded_list.startswith("u"):
        raise ValueError("Status list must use the base64url multibase prefix.")

    encoded = encoded_list[1:]
    maximum_bytes = MAXIMUM_STATUS_LIST_ENTRIES // 8
    maximum_compressed_bytes = maximum_bytes + 65_536
    maximum_encoded_chars = 4 * ((maximum_compressed_bytes + 2) // 3)
    if (
        not encoded
        or len(encoded) > maximum_encoded_chars
        or re.fullmatch(r"[A-Za-z0-9_-]+", encoded) is None
    ):
        raise ValueError("Status list base64url encoding is invalid.")

    padded = encoded + "=" * (-len(encoded) % 4)
    try:
        compressed = base64.b64decode(
            padded.encode("ascii"),
            altchars=b"-_",
            validate=True,
        )
    except (ValueError, UnicodeEncodeError) as error:
        raise ValueError("Status list base64url encoding is invalid.") from error
    if (
        len(compressed) > maximum_compressed_bytes
        or base64.urlsafe_b64encode(compressed).rstrip(b"=").decode("ascii")
        != encoded
    ):
        raise ValueError("Status list base64url encoding is non-canonical.")

    try:
        with gzip.GzipFile(fileobj=BytesIO(compressed), mode="rb") as stream:
            bitstring = stream.read(maximum_bytes + 1)
    except (EOFError, OSError, zlib.error) as error:
        raise ValueError("Status list gzip data is invalid.") from error

    if len(bitstring) * 8 < MINIMUM_STATUS_LIST_ENTRIES:
        raise ValueError("Status list is shorter than the W3C minimum.")
    if len(bitstring) > maximum_bytes:
        raise ValueError("Status list exceeds the configured maximum.")
    return bitstring


def decode_status_list_bit(encoded_list: str, index: int) -> bool:
    if index < 0:
        raise ValueError("Status list index must be non-negative.")
    bitstring = decompress_status_list(encoded_list)
    byte_index = index // 8
    bit_index = 7 - (index % 8)
    if byte_index >= len(bitstring):
        raise ValueError("Status list index is outside the encoded bitstring.")
    return bool(bitstring[byte_index] & (1 << bit_index))


def _format_timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Status list publication time must be aware.")
    return (
        value.astimezone(UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
