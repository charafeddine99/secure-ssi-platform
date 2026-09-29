"""In-memory and persistent token revocation store (blacklist).

Tracks revoked JWT identifiers (JTI) and revoked principals to enforce immediate
session termination upon logout, security incident quarantine, or emergency recovery.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Dict, Optional, Set


class TokenRevocationStore:
    """Thread-safe revocation registry for JWTs and compromised subjects."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # jti -> (revoked_at, expires_at, reason)
        self._revoked_jtis: Dict[str, tuple[datetime, Optional[datetime], str]] = {}
        # subject (user_id / did) -> (revoked_at, reason)
        self._revoked_subjects: Dict[str, tuple[datetime, str]] = {}

    def revoke_token(
        self,
        jti: str,
        expires_at: Optional[datetime] = None,
        reason: str = "logout",
    ) -> None:
        """Revokes a specific JWT by its JTI."""
        if not jti:
            return
        now = datetime.now(timezone.utc)
        with self._lock:
            self._revoked_jtis[jti] = (now, expires_at, reason)
            self._prune_expired_locked(now)

    def revoke_subject(
        self,
        subject: str,
        reason: str = "security_quarantine",
    ) -> None:
        """Revokes all current and future tokens for a given subject (user / DID)."""
        if not subject:
            return
        now = datetime.now(timezone.utc)
        with self._lock:
            self._revoked_subjects[subject] = (now, reason)

    def reinstate_subject(self, subject: str) -> None:
        """Lifts revocation for a subject (e.g. upon un-quarantine)."""
        with self._lock:
            self._revoked_subjects.pop(subject, None)

    def is_revoked(self, jti: str, subject: Optional[str] = None) -> bool:
        """Checks if a JTI or subject is actively revoked."""
        now = datetime.now(timezone.utc)
        with self._lock:
            if jti in self._revoked_jtis:
                _, expires_at, _ = self._revoked_jtis[jti]
                if expires_at and expires_at < now:
                    # Token expired naturally, remove from blacklist
                    del self._revoked_jtis[jti]
                else:
                    return True

            if subject and subject in self._revoked_subjects:
                return True

            return False

    def _prune_expired_locked(self, now: datetime) -> None:
        """Removes expired JTIs from memory to prevent unbounded memory growth."""
        expired_keys = [
            jti for jti, (_, exp, _) in self._revoked_jtis.items()
            if exp is not None and exp < now
        ]
        for key in expired_keys:
            del self._revoked_jtis[key]

    def count(self) -> int:
        """Returns the count of active revoked JTIs."""
        with self._lock:
            return len(self._revoked_jtis)

    def clear(self) -> None:
        """Clears all revocations (used in test isolation)."""
        with self._lock:
            self._revoked_jtis.clear()
            self._revoked_subjects.clear()


_DEFAULT_REVOCATION_STORE = TokenRevocationStore()


def get_token_revocation_store() -> TokenRevocationStore:
    return _DEFAULT_REVOCATION_STORE
