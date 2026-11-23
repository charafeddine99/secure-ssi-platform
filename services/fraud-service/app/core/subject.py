"""One pseudonymous key per subject, whichever service names it.

An unsalted hash is pseudonymous, not anonymous: anyone who already knows a DID
can compute its key.
"""

from hashlib import sha256

_PSEUDONYMOUS_PREFIXES = ("subject:", "recovery:")


def subject_key(value: str) -> str:
    if value.startswith(_PSEUDONYMOUS_PREFIXES):
        return value
    return "subject:" + sha256(value.encode()).hexdigest()
