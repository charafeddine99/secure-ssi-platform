from collections.abc import Mapping
from typing import Any

from app.domain.auth import AuthenticatedPrincipal
from app.domain.exceptions import PermissionDeniedError
from app.domain.permissions import Role


def require_issuer_did(principal: AuthenticatedPrincipal) -> str:
    """Return the issuer DID bound to this server-authenticated issuer."""
    if Role.ISSUER not in principal.roles:
        raise PermissionDeniedError(
            "An issuer role is required for issuer-scoped operations."
        )
    issuer_did = principal.issuer_did
    # Preserve DID-subject authentication used by existing deployments.
    if issuer_did is None and principal.id.startswith("did:"):
        issuer_did = principal.id
    if (
        issuer_did is None
        or len(issuer_did) <= len("did:web:")
        or not issuer_did.startswith("did:web:")
        or any(character.isspace() for character in issuer_did)
    ):
        raise PermissionDeniedError(
            "This issuer account has no server-assigned did:web scope."
        )
    return issuer_did


def issuer_did_for_authorization(
    principal: AuthenticatedPrincipal,
) -> str | None:
    if Role.ISSUER not in principal.roles:
        return None
    return require_issuer_did(principal)


def credential_issuer_did(credential: Mapping[str, Any]) -> str | None:
    issuer = credential.get("issuer")
    if isinstance(issuer, str):
        return issuer
    if isinstance(issuer, Mapping):
        identifier = issuer.get("id")
        return identifier if isinstance(identifier, str) else None
    return None
