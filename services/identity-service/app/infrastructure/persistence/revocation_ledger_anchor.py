import json
import os
import tempfile
from pathlib import Path
from threading import Lock

from app.domain.revocation_ledger import (
    LedgerHead,
    RevocationLedgerIntegrityError,
    RevocationLedgerUnavailableError,
    seal,
    seal_matches,
)


_ANCHOR_PURPOSE = "revocation-anchor"


class FileLedgerAnchor:
    """Keeps the ledger high-water mark on storage the database cannot reach.

    A database restore cannot rewind this file, which is what makes a rolled
    back ledger detectable. It is not WORM: whoever controls the host can still
    replace the file, and that limit must stay in the operator documentation.
    """

    def __init__(self, path: str, *, mac_key: bytes) -> None:
        self._path = Path(path)
        self._mac_key = mac_key
        self._lock = Lock()

    def read(self) -> LedgerHead | None:
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError as error:
            raise RevocationLedgerUnavailableError(
                "The revocation ledger anchor is unavailable."
            ) from error
        try:
            data = json.loads(raw)
            head = LedgerHead(int(data["sequence"]), str(data["eventHash"]))
            mac = str(data["mac"])
        except (KeyError, TypeError, ValueError) as error:
            raise RevocationLedgerIntegrityError(
                "LEDGER_ANCHOR_ALTERED"
            ) from error
        if not seal_matches(
            self._mac_key,
            _ANCHOR_PURPOSE,
            f"{head.sequence}:{head.event_hash}",
            mac,
        ):
            raise RevocationLedgerIntegrityError("LEDGER_ANCHOR_ALTERED")
        return head

    def advance(self, head: LedgerHead) -> None:
        with self._lock:
            current = self.read()
            if current is not None and current.sequence >= head.sequence:
                return
            payload = json.dumps(
                {
                    "sequence": head.sequence,
                    "eventHash": head.event_hash,
                    "mac": seal(
                        self._mac_key,
                        _ANCHOR_PURPOSE,
                        f"{head.sequence}:{head.event_hash}",
                    ),
                }
            )
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                descriptor, temporary = tempfile.mkstemp(
                    dir=self._path.parent,
                    prefix=".anchor-",
                )
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self._path)
            except OSError as error:
                raise RevocationLedgerUnavailableError(
                    "The revocation ledger anchor is unavailable."
                ) from error
