import base64
import gzip
from datetime import UTC, datetime

from app.domain.bitstring_status_list import (
    MINIMUM_STATUS_LIST_ENTRIES,
    CredentialStatusEntry,
    StatusPurpose,
    deterministic_index_candidate,
    generate_status_list_id,
)
from app.infrastructure.crypto.ed25519_signer import Ed25519CredentialSigner
from app.infrastructure.crypto.jcs_canonicalizer import JcsCanonicalizer
from app.infrastructure.crypto.local_issuer_key_provider import (
    LocalIssuerKeyProvider,
    SYNTHETIC_ISSUER_DID,
)
from app.infrastructure.crypto.multibase import decode_base58_btc
from app.infrastructure.status_list_document_generator import (
    StatusListDocumentGenerator,
    encode_status_list,
)


NOW = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)


def test_credential_status_entry_is_deterministic_and_w3c_shaped() -> None:
    status_list_id = generate_status_list_id(SYNTHETIC_ISSUER_DID)
    entry = CredentialStatusEntry(
        id="64b64c0f0123456789abcdef",
        credential_id="urn:uuid:credential-1",
        issuer_did=SYNTHETIC_ISSUER_DID,
        status_list_id=status_list_id,
        status_list_index=42,
        status_purpose=StatusPurpose.REVOCATION,
        created_at=NOW,
        updated_at=NOW,
    )

    first = entry.to_credential_status(
        status_list_credential_url=(
            f"https://issuer.example/status-lists/{status_list_id}"
        )
    )
    second = entry.to_credential_status(
        status_list_credential_url=(
            f"https://issuer.example/status-lists/{status_list_id}"
        )
    )

    assert first == second
    assert first["type"] == "BitstringStatusListEntry"
    assert first["statusPurpose"] == "revocation"
    assert first["statusListIndex"] == "42"
    assert generate_status_list_id(SYNTHETIC_ISSUER_DID) == status_list_id
    assert deterministic_index_candidate(
        entry.credential_id
    ) == deterministic_index_candidate(entry.credential_id)


def test_bitstring_encoding_uses_msb_indexing_and_is_deterministic() -> None:
    indices = (0, 15, MINIMUM_STATUS_LIST_ENTRIES - 1)
    first = encode_status_list(
        indices,
        list_length=MINIMUM_STATUS_LIST_ENTRIES,
    )
    second = encode_status_list(
        tuple(reversed(indices)),
        list_length=MINIMUM_STATUS_LIST_ENTRIES,
    )
    payload = first[1:]
    payload += "=" * (-len(payload) % 4)
    bitstring = gzip.decompress(
        base64.urlsafe_b64decode(payload.encode("ascii"))
    )

    assert first == second
    assert len(bitstring) == MINIMUM_STATUS_LIST_ENTRIES // 8
    assert bitstring[0] == 0b10000000
    assert bitstring[1] == 0b00000001
    assert bitstring[-1] == 0b00000001


def test_status_list_document_is_signed_with_local_data_integrity_key() -> None:
    canonicalizer = JcsCanonicalizer()
    signer = Ed25519CredentialSigner()
    keys = LocalIssuerKeyProvider()
    generator = StatusListDocumentGenerator(
        canonicalizer=canonicalizer,
        signer=signer,
        key_provider=keys,
    )
    encoded = encode_status_list(
        (7,),
        list_length=MINIMUM_STATUS_LIST_ENTRIES,
    )

    document = dict(
        generator.generate(
            status_list_url=(
                "https://issuer.example/api/v1/status-lists/"
                f"{generate_status_list_id(SYNTHETIC_ISSUER_DID)}"
            ),
            issuer_did=SYNTHETIC_ISSUER_DID,
            encoded_list=encoded,
            ttl_seconds=300,
            published_at=NOW,
        )
    )
    proof = dict(document.pop("proof"))
    proof_value = proof.pop("proofValue")
    signing_input = canonicalizer.create_signing_input(document, proof)

    assert document["credentialSubject"]["ttl"] == 300_000
    assert signer.verify(
        signing_input,
        decode_base58_btc(proof_value),
        keys.get_verification_key(proof["verificationMethod"]),
    )
