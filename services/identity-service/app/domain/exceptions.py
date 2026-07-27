class CredentialProofError(Exception):
    """Base class for controlled credential proof failures."""


class CanonicalizationError(CredentialProofError):
    """The document cannot be represented by the RFC 8785 profile."""


class UnknownIssuerError(CredentialProofError):
    """The local key provider does not support the requested issuer."""


class UnknownVerificationMethodError(CredentialProofError):
    """The local key provider does not expose the requested public key."""


class ExistingProofError(CredentialProofError):
    """An unsigned credential was required but a proof was already present."""


class InvalidSigningTimeError(CredentialProofError):
    """The signing time is missing timezone information or is malformed."""


class SigningError(CredentialProofError):
    """The signing adapter could not produce a valid Ed25519 signature."""


class KeyMaterialError(CredentialProofError):
    """Synthetic key material does not match the configured public profile."""


class VerificationInfrastructureError(CredentialProofError):
    """A verifier dependency failed unexpectedly."""


class AuthenticationError(Exception):
    """Base class for controlled authentication and authorization failures."""


class AuthenticationRequiredError(AuthenticationError):
    """A protected operation was requested without Bearer authentication."""


class InvalidCredentialsError(AuthenticationError):
    """The supplied login credentials cannot authenticate a local user."""


class InvalidAccessTokenError(AuthenticationError):
    """An access token is malformed, untrusted, or inconsistent."""


class AccessTokenExpiredError(InvalidAccessTokenError):
    """The access token is past its expiration time."""


class AccessTokenNotActiveError(InvalidAccessTokenError):
    """The access token cannot be used at the current time."""


class AccessTokenInvalidIssuerError(InvalidAccessTokenError):
    """The access token issuer is not the configured local issuer."""


class AccessTokenInvalidAudienceError(InvalidAccessTokenError):
    """The access token audience does not target this service."""


class AccessTokenInvalidUseError(InvalidAccessTokenError):
    """The token is not an access token."""


class UserNotFoundError(AuthenticationError):
    """A signed token subject is not present in the current local registry."""


class UserDisabledError(AuthenticationError):
    """The current local user is disabled."""


class PermissionDeniedError(AuthenticationError):
    """An authenticated principal lacks a required permission."""


class AuthConfigurationError(AuthenticationError):
    """Authentication configuration is unsafe or incomplete."""


class InvalidRoleError(ValueError):
    """A role value is outside the closed local RBAC allowlist."""
