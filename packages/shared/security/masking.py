"""Sensitive data masking and PII leakage prevention utilities.

Recursively scrubs credentials, cryptographic keys, seeds, and connection
strings from logs, HTTP representations, and exception diagnostics.
"""

from __future__ import annotations

import re
from typing import Any

SENSITIVE_FIELD_NAMES = frozenset({
    "password",
    "password_hash",
    "private_key",
    "private_key_pem",
    "private_key_bytes",
    "seed",
    "secret",
    "jwt_secret",
    "master_key",
    "authorization_secret",
    "raw_key",
    "signing_key",
    "mongo_uri",
    "database_uri",
    "connection_string",
    "token",
    "access_token",
    "refresh_token",
})

def mask_connection_string(uri: str) -> str:
    """Replaces username and password credentials in connection URIs with redaction markers."""
    if not isinstance(uri, str) or "://" not in uri or "@" not in uri:
        return uri
    scheme_idx = uri.find("://")
    last_at_idx = uri.rfind("@")
    user_pass = uri[scheme_idx + 3:last_at_idx]
    if ":" in user_pass:
        user = user_pass.split(":", 1)[0]
        return f"{uri[:scheme_idx + 3]}{user}:***REDACTED***{uri[last_at_idx:]}"
    return uri


def sanitize_sensitive_data(val: Any, depth: int = 0) -> Any:
    """
    Recursively scans and redacts sensitive field values in arbitrary data structures.
    Protects against infinite recursion with depth bounds (max 32).
    """
    if depth > 32:
        return "[MAX_DEPTH_REACHED]"

    if isinstance(val, dict):
        sanitized = {}
        for k, v in val.items():
            k_str = str(k).lower()
            if any(sensitive in k_str for sensitive in SENSITIVE_FIELD_NAMES):
                sanitized[k] = "***REDACTED***"
            else:
                sanitized[k] = sanitize_sensitive_data(v, depth + 1)
        return sanitized

    if isinstance(val, list):
        return [sanitize_sensitive_data(item, depth + 1) for item in val]

    if isinstance(val, tuple):
        return tuple(sanitize_sensitive_data(item, depth + 1) for item in val)

    if isinstance(val, str):
        if "://" in val and "@" in val:
            return mask_connection_string(val)
        return val

    return val
