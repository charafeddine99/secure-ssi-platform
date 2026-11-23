import os

from app.config.environment_policy import is_production_like
from app.domain.persistence import PersistenceConfigurationError


def require_development_environment(component: str) -> None:
    """Refuse to build a repository-derivable key source outside development.

    Reads the process environment directly so that no caller can pass a
    friendlier value. An unset variable is the documented development default.
    """
    environment = os.environ.get("IDENTITY_ENVIRONMENT", "development")
    if is_production_like(environment):
        raise PersistenceConfigurationError(
            f"The {component} is not available in production-like "
            "environments."
        )
