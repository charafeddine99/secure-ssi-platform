from app.domain.auth import AuthenticatedPrincipal
from app.domain.exceptions import PermissionDeniedError
from app.domain.permissions import Permission


class AuthorizationService:
    def require_permission(
        self,
        principal: AuthenticatedPrincipal,
        permission: Permission,
    ) -> None:
        if permission not in principal.permissions:
            raise PermissionDeniedError(
                "The authenticated principal lacks the required permission."
            )
