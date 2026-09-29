"""Deterministic Canonicalization and Cryptographic Digesting for Blockchain Anchoring.

Implements strict canonical serialization (RFC 8785 subset) to ensure identical
data structures always yield the exact same SHA-256 byte digest and bytes32 representation
regardless of key insertion order or whitespace variations.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


# Fields that must never enter canonical hashing payloads
SENSITIVE_FIELD_NAMES = frozenset({
    "private_key",
    "privateKey",
    "secret",
    "secrets",
    "password",
    "token",
    "access_token",
    "seed",
    "seed_phrase",
    "shares",
    "shamir_shares",
    "proofValue",  # VC signature/proof value should not be included if anchoring document structure
    "authorization",
})


def redact_sensitive_fields(obj: Any) -> Any:
    """Recursively redacts known secret / sensitive fields prior to canonicalization."""
    if isinstance(obj, Mapping):
        return {
            k: redact_sensitive_fields(v)
            for k, v in obj.items()
            if k not in SENSITIVE_FIELD_NAMES
        }
    if isinstance(obj, (list, tuple)):
        return [redact_sensitive_fields(item) for item in obj]
    return obj


def canonicalize_json(data: Any) -> bytes:
    """
    Serializes a Python dict / JSON-compatible object into a deterministic canonical UTF-8 byte string.
    Rules:
    - Keys are recursively sorted lexicographically.
    - Compact separators (no trailing or extraneous whitespace: ',' and ':').
    - UTF-8 encoding without ASCII escapes.
    - Sensitive fields are strictly excluded.
    """
    cleaned = redact_sensitive_fields(data)
    canonical_str = json.dumps(
        cleaned,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return canonical_str.encode("utf-8")


def compute_deterministic_hash(data: Any) -> tuple[bytes, str]:
    """
    Computes a deterministic SHA-256 digest from any JSON-serializable structure or raw bytes.
    Returns:
        (raw_32_bytes, "0x" + 64_hex_chars)
    """
    if isinstance(data, (bytes, bytearray)):
        raw_bytes = bytes(data)
    else:
        raw_bytes = canonicalize_json(data)

    digest = hashlib.sha256(raw_bytes).digest()
    hex_str = "0x" + digest.hex()
    return digest, hex_str


def to_bytes32(hex_or_bytes: str | bytes) -> bytes:
    """Converts a 0x-prefixed hex string or 32-byte sequence to strict bytes32."""
    if isinstance(hex_or_bytes, bytes):
        if len(hex_or_bytes) != 32:
            raise ValueError(f"Expected 32 bytes, got {len(hex_or_bytes)}")
        return hex_or_bytes
    hex_clean = hex_or_bytes[2:] if hex_or_bytes.startswith("0x") else hex_or_bytes
    b = bytes.fromhex(hex_clean)
    if len(b) != 32:
        raise ValueError(f"Expected 32 bytes for bytes32, got {len(b)}")
    return b
