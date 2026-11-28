"""Canonical security event types. An unknown type is rejected, not guessed."""

from dataclasses import dataclass

SCHEMA_VERSION = "1.0"
ORIGINS = ("OPERATIONAL", "SYNTHETIC_TEST")
SOURCES = ("api-gateway", "identity-service", "recovery-service")
SEVERITIES = ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL")


@dataclass(frozen=True)
class EventType:
    category: str
    outcome: str
    severity: str


def _types(category: str, **items: tuple[str, str]) -> dict[str, EventType]:
    return {
        name.replace("__", "."): EventType(category, outcome, severity)
        for name, (outcome, severity) in items.items()
    }


EVENT_TYPES: dict[str, EventType] = {
    **_types(
        "authentication",
        auth__login__success=("SUCCESS", "INFO"),
        auth__login__failure=("FAILURE", "LOW"),
        auth__stepup__success=("SUCCESS", "INFO"),
        auth__stepup__failure=("FAILURE", "LOW"),
        auth__session__rejected=("DENIED", "LOW"),
        gateway__login__rejected=("DENIED", "LOW"),
    ),
    **_types(
        "api",
        authz__denied=("DENIED", "LOW"),
        api__rate_limited=("DENIED", "LOW"),
        api__request=("OBSERVED", "INFO"),
    ),
    **_types(
        "issuance",
        oid4vci__token__failure=("FAILURE", "LOW"),
        oid4vci__credential__failure=("FAILURE", "LOW"),
        oid4vci__credential__issued=("SUCCESS", "INFO"),
    ),
    **_types(
        "presentation",
        oid4vp__request__created=("SUCCESS", "INFO"),
        oid4vp__request__failure=("FAILURE", "LOW"),
        presentation__verified=("SUCCESS", "INFO"),
        presentation__rejected=("FAILURE", "LOW"),
        consent__rejected=("DENIED", "INFO"),
    ),
    **_types(
        "credential_status",
        credential__revoked=("SUCCESS", "INFO"),
        status__checked=("OBSERVED", "INFO"),
    ),
    **_types(
        "wallet",
        wallet__ownership__rejected=("DENIED", "MEDIUM"),
        wallet__challenge__rejected=("DENIED", "LOW"),
        wallet__restore__rejected=("DENIED", "LOW"),
        wallet__restore__completed=("SUCCESS", "INFO"),
        wallet__backup__created=("SUCCESS", "INFO"),
    ),
    **_types(
        "key_management",
        key__rotation__completed=("SUCCESS", "INFO"),
        key__rotation__failed=("FAILURE", "MEDIUM"),
        key__compromised=("SUCCESS", "HIGH"),
        key__destroyed=("SUCCESS", "MEDIUM"),
        key__unauthorized_access=("DENIED", "HIGH"),
        key__signing_rejected=("DENIED", "MEDIUM"),
        key__provider_mismatch=("FAILURE", "HIGH"),
    ),
    **_types(
        "trust_and_admin",
        trust__changed=("SUCCESS", "MEDIUM"),
        admin__scope_changed=("SUCCESS", "MEDIUM"),
        admin__invited=("SUCCESS", "MEDIUM"),
        account__registered=("SUCCESS", "INFO"),
        onboarding__requested=("SUCCESS", "INFO"),
        onboarding__approved=("SUCCESS", "MEDIUM"),
        onboarding__rejected=("SUCCESS", "INFO"),
    ),
    **_types(
        "backup",
        backup__created=("SUCCESS", "INFO"),
        backup__failed=("FAILURE", "MEDIUM"),
        backup__verified=("SUCCESS", "INFO"),
        backup__verify_failed=("FAILURE", "HIGH"),
        restore__previewed=("SUCCESS", "MEDIUM"),
    ),
    **_types(
        "recovery",
        recovery__requested=("SUCCESS", "MEDIUM"),
        recovery__approved=("SUCCESS", "INFO"),
        recovery__rejected=("DENIED", "LOW"),
        recovery__proof_rejected=("DENIED", "MEDIUM"),
        recovery__unauthorized=("DENIED", "HIGH"),
        recovery__share_invalid=("FAILURE", "HIGH"),
        recovery__risk_hold=("OBSERVED", "MEDIUM"),
        recovery__policy_changed=("SUCCESS", "INFO"),
        recovery__policy_weakened=("SUCCESS", "MEDIUM"),
        recovery__completed=("SUCCESS", "MEDIUM"),
        recovery__cancelled=("SUCCESS", "INFO"),
        recovery__failed=("FAILURE", "MEDIUM"),
        guardian__changed=("SUCCESS", "INFO"),
    ),
}

# Event domains the platform is expected to report. Each names its producer and
# the event types that prove the domain is really flowing.
REQUIRED_DOMAINS: dict[str, tuple[str, tuple[str, ...]]] = {
    "Authentication": ("identity-service", ("auth.login.success", "auth.login.failure")),
    "Step-up and MFA": ("identity-service", ("auth.stepup.success", "auth.stepup.failure")),
    "API authorization": ("api-gateway", ("authz.denied", "auth.session.rejected")),
    "API traffic and rate limits": ("api-gateway", ("api.request", "api.rate_limited")),
    "OID4VCI issuance": ("identity-service", ("oid4vci.credential.issued",)),
    "OID4VCI failures": ("api-gateway", ("oid4vci.token.failure", "oid4vci.credential.failure")),
    "OID4VP and presentations": ("identity-service", ("presentation.verified", "presentation.rejected")),
    "Credential revocation": ("identity-service", ("credential.revoked",)),
    "Key management": ("identity-service", ("key.rotation.completed", "key.compromised", "key.unauthorized_access")),
    "Trust registry and admin": ("identity-service", ("trust.changed", "admin.scope_changed")),
    "Platform backup": ("identity-service", ("backup.created", "backup.verified", "backup.failed")),
    "Wallet backup": ("identity-service", ("wallet.backup.created", "wallet.restore.completed")),
    "Guardian recovery": ("recovery-service", ("recovery.requested", "recovery.approved")),
}
