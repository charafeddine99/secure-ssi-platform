"""High-impact admin writes must ask for fresh authentication."""

import pytest

from app.api.v1.dependencies import get_step_up_service
from app.api.v1.platform_backups import router as backup_router
from app.api.v1.trust_registry import router as trust_router


def _route(router, name):
    return next(route for route in router.routes if route.name == name)


@pytest.mark.parametrize(
    ("router", "name"),
    [
        (trust_router, "register_trusted_issuer"),
        (trust_router, "update_trust_record"),
        (trust_router, "suspend_trusted_issuer"),
        (trust_router, "revoke_trusted_issuer"),
        (backup_router, "create_platform_backup"),
        (backup_router, "sweep_platform_backups"),
    ],
)
def test_write_route_takes_a_step_up_token(router, name) -> None:
    dependant = _route(router, name).dependant
    assert get_step_up_service in [item.call for item in dependant.dependencies]
    assert "X-Step-Up-Token" in [item.alias for item in dependant.header_params]
