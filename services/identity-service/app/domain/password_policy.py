"""Password rules after NIST SP 800-63B-4: length and a blocklist, no composition rules.

The blocklist is a short built-in list, not a breached-password corpus.
"""

MINIMUM_LENGTH = 15
MAXIMUM_LENGTH = 1024
_BLOCKED_FRAGMENTS = (
    "password", "passw0rd", "qwerty", "123456", "111111", "letmein", "welcome",
    "iloveyou", "admin", "secure-ssi", "securessi",
)


def password_problem(password: str, *, username: str = "") -> str | None:
    """Returns why a new password is refused, or None if it is acceptable."""
    if len(password) < MINIMUM_LENGTH:
        return f"Use at least {MINIMUM_LENGTH} characters."
    if len(password) > MAXIMUM_LENGTH:
        return "This password is too long."
    lowered = password.casefold()
    if len(set(lowered)) < 5:
        return "This password is too repetitive."
    local_part = username.casefold().split("@")[0]
    if len(local_part) >= 4 and local_part in lowered:
        return "Do not use your account name in the password."
    if any(fragment in lowered for fragment in _BLOCKED_FRAGMENTS):
        return "This password is too common."
    return None
