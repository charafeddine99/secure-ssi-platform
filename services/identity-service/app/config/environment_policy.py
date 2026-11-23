"""The single rule that decides whether an environment may use development
fallbacks. Keep this file byte-identical in every service; a repository test
compares the copies.

Fail closed: only the names below are development. Everything else, including
blank values and typos such as "prd", is production-like.
"""

DEVELOPMENT_ENVIRONMENTS = frozenset(
    {"development", "dev", "local", "test", "testing"}
)


def normalize_environment(environment: str | None) -> str:
    return (environment or "").strip().casefold()


def is_production_like(environment: str | None) -> bool:
    return normalize_environment(environment) not in DEVELOPMENT_ENVIRONMENTS
