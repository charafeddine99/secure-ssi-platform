import base64
import gzip
from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime
from io import BytesIO
from typing import Any

from app.application.ports.canonicalizer import CredentialCanonicalizer
from app.application.ports.credential_signer import CredentialSigner
from app.application.ports.key_provider import KeyProvider
from app.domain.bitstring_status_list import StatusListGenerationError
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
    ) -> Mapping[str, Any]:
        if not status_list_url.startswith(("http://", "https://")):
            raise StatusListGenerationError(
                "Status list publication URL must use HTTP(S)."
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
                    "statusPurpose": "revocation",
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
    revoked_indices: tuple[int, ...],
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


def _format_timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Status list publication time must be aware.")
    return (
        value.astimezone(UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
