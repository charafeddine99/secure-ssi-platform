from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_urlsafe
from typing import Annotated

from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application.ports.access_token_service import AccessTokenService
from app.application.ports.issuance import CredentialIssuanceRepository
from app.application.ports.key_management import (
    ExternalKeyProvider,
    ManagedKeyRepository,
)
from app.application.ports.auth_runtime import JtiGenerator
from app.application.ports.password_hasher import PasswordHasherPort
from app.application.ports.presentation import PresentationRepository
from app.application.ports.holder_wallet import (
    HolderWalletRepository,
    PresentationChallengeRepository,
)
from app.application.ports.repositories import (
    AuditEventRepository,
    CredentialRepository,
    RevocationRepository,
    UserRepository,
)
from app.application.ports.status_list_repositories import (
    AuditOutboxRepository,
    CredentialStatusEntryRepository,
    StatusListRepository,
)
from app.application.ports.user_provider import UserProvider
from app.application.services.authentication_service import AuthenticationService
from app.application.services.authorization_service import AuthorizationService
from app.application.services.audit_outbox_service import (
    AuditOutboxDeliveryService,
)
from app.application.services.credential_api_service import CredentialApiService
from app.application.services.credential_issuance_service import (
    CredentialIssuanceService,
)
from app.application.services.credential_proof_service import (
    CredentialProofService,
)
from app.application.services.credential_revocation_service import (
    CredentialRevocationService,
)
from app.application.services.holder_wallet_service import (
    HolderWalletService,
    PresentationChallengeService,
)
from app.application.services.managed_key_service import (
    ManagedKeyService,
    ProviderAwareHolderSigner,
)
from app.application.services.status_list_service import StatusListService
from app.application.services.internal_metrics import INTERNAL_METRICS
from app.application.services.presentation_proof_service import (
    PresentationBuilder,
    PresentationValidator,
)
from app.application.services.presentation_service import (
    HolderPresentationService,
    PresentationReconciliationService,
    VerifierPresentationService,
    build_credential_inspector,
)
from app.config.audit_outbox_settings import (
    AuditOutboxSettings,
    load_audit_outbox_settings,
)
from app.config.auth_settings import AuthSettings, load_auth_settings
from app.config.holder_wallet_settings import (
    HolderWalletSettings,
    load_holder_wallet_settings,
)
from app.config.mongo_settings import MongoSettings, load_mongo_settings
from app.config.key_management_settings import (
    ConfiguredKeyPolicy,
    KeyManagementSettings,
    load_key_management_settings,
)
from app.config.status_list_settings import (
    StatusListSettings,
    load_status_list_settings,
)
from app.domain.auth import AuthenticatedPrincipal
from app.domain.exceptions import AuthenticationRequiredError
from app.domain.permissions import Permission
from app.domain.persistence import PersistenceConfigurationError
from app.infrastructure.auth.argon2_password_hasher import Argon2PasswordHasher
from app.infrastructure.auth.jwt_access_token_service import (
    JwtAccessTokenService,
)
from app.infrastructure.auth.local_synthetic_user_provider import (
    LocalSyntheticUserProvider,
)
from app.infrastructure.auth.runtime import SecureJtiGenerator, SystemClock
from app.infrastructure.crypto.ed25519_signer import Ed25519CredentialSigner
from app.infrastructure.crypto.jcs_canonicalizer import JcsCanonicalizer
from app.infrastructure.crypto.local_issuer_key_provider import (
    LocalIssuerKeyProvider,
    SYNTHETIC_ISSUER_DID,
)
from app.infrastructure.crypto.local_issuer_signing_service import (
    LocalIssuerSigningService,
)
from app.infrastructure.crypto.local_holder_key_provider import (
    LocalDevelopmentHolderSigner,
    LocalHolderKeyProvider,
)
from app.infrastructure.key_management.development_provider import (
    DevelopmentExternalKeyProvider,
)
from app.infrastructure.key_management.generic_remote_kms import (
    EnvironmentBearerAuthentication,
    GenericRemoteKmsAdapter,
    NoProviderAuthentication,
    UrllibKmsHttpTransport,
)
from app.infrastructure.persistence.connection import MongoConnectionManager
from app.infrastructure.persistence.indexes import (
    AUDIT_EVENTS_COLLECTION,
    AUDIT_OUTBOX_COLLECTION,
    CREDENTIALS_COLLECTION,
    STATUS_LIST_ENTRIES_COLLECTION,
    STATUS_LISTS_COLLECTION,
    USERS_COLLECTION,
    PRESENTATIONS_COLLECTION,
    HOLDER_WALLETS_COLLECTION,
    PRESENTATION_CHALLENGES_COLLECTION,
    MANAGED_KEYS_COLLECTION,
)
from app.infrastructure.persistence.mongo_user_provider import (
    MongoUserProvider,
)
from app.infrastructure.persistence.mappers import new_object_id
from app.infrastructure.persistence.issuance_repository import (
    MongoCredentialIssuanceRepository,
)
from app.infrastructure.persistence.repositories import (
    MongoAuditEventRepository,
    MongoCredentialRepository,
    MongoRevocationRepository,
    MongoUserRepository,
)
from app.infrastructure.persistence.audit_outbox_repository import (
    MongoAuditOutboxRepository,
)
from app.infrastructure.persistence.status_list_repositories import (
    MongoCredentialStatusEntryRepository,
    MongoStatusListRepository,
)
from app.infrastructure.persistence.presentation_repository import (
    MongoPresentationRepository,
)
from app.infrastructure.persistence.holder_wallet_repositories import (
    MongoHolderWalletRepository,
    MongoPresentationChallengeRepository,
)
from app.infrastructure.persistence.managed_key_repository import (
    MongoManagedKeyRepository,
)
from app.infrastructure.status_list_document_generator import (
    StatusListDocumentGenerator,
)
from app.services.credential_validator import CredentialProfileValidator
from app.services.did_resolver import (
    CompositeDidResolver,
    DidKeyResolver,
    DidWebFixtureResolver,
)


Clock = Callable[[], datetime]
_APP_ROOT = Path(__file__).resolve().parents[2]
_ISSUER_DID_FIXTURE = (
    _APP_ROOT / "infrastructure" / "fixtures" / "issuer.did.json"
)

_VALIDATOR = CredentialProfileValidator()
_CANONICALIZER = JcsCanonicalizer()
_SIGNER = Ed25519CredentialSigner()
_KEY_PROVIDER = LocalIssuerKeyProvider()
_HOLDER_KEY_PROVIDER = LocalHolderKeyProvider()
_HOLDER_SIGNER = LocalDevelopmentHolderSigner(_HOLDER_KEY_PROVIDER)
_DID_RESOLVER = CompositeDidResolver(
    {
        "web": DidWebFixtureResolver(
            {SYNTHETIC_ISSUER_DID: _ISSUER_DID_FIXTURE}
        )
    }
)
_HOLDER_DID_RESOLVER = CompositeDidResolver({"key": DidKeyResolver()})
_AUTH_SETTINGS = load_auth_settings()
_MONGO_SETTINGS = load_mongo_settings()
_STATUS_LIST_SETTINGS = load_status_list_settings()
_AUDIT_OUTBOX_SETTINGS = load_audit_outbox_settings()
_HOLDER_WALLET_SETTINGS = load_holder_wallet_settings()
_KEY_MANAGEMENT_SETTINGS = load_key_management_settings()
_MONGO_MANAGER = MongoConnectionManager(_MONGO_SETTINGS)
_PASSWORD_HASHER = Argon2PasswordHasher()
_USER_PROVIDER = LocalSyntheticUserProvider.default(
    enabled=_AUTH_SETTINGS.local_fixture_users_enabled
)
_FALLBACK_PASSWORD_HASH = LocalSyntheticUserProvider.default(
    enabled=False
).fallback_password_hash()
_SYSTEM_CLOCK = SystemClock()
_JTI_GENERATOR = SecureJtiGenerator()
_AUTHORIZATION_SERVICE = AuthorizationService()
_STATUS_LIST_GENERATOR = StatusListDocumentGenerator(
    canonicalizer=_CANONICALIZER,
    signer=_SIGNER,
    key_provider=_KEY_PROVIDER,
)

bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="BearerAuth",
    bearerFormat="JWT",
    description=(
        "Short-lived local prototype JWT. Synthetic accounts only; no "
        "refresh token or production identity provider."
    ),
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def get_clock() -> Clock:
    return utc_now


def get_auth_settings() -> AuthSettings:
    return _AUTH_SETTINGS


def get_mongo_settings() -> MongoSettings:
    return _MONGO_SETTINGS


def get_status_list_settings() -> StatusListSettings:
    return _STATUS_LIST_SETTINGS


def get_audit_outbox_settings() -> AuditOutboxSettings:
    return _AUDIT_OUTBOX_SETTINGS


def get_holder_wallet_settings() -> HolderWalletSettings:
    return _HOLDER_WALLET_SETTINGS


def get_key_management_settings() -> KeyManagementSettings:
    return _KEY_MANAGEMENT_SETTINGS


def get_mongo_connection_manager() -> MongoConnectionManager:
    return _MONGO_MANAGER


def get_auth_clock() -> Clock:
    return _SYSTEM_CLOCK


def get_jti_generator() -> JtiGenerator:
    return _JTI_GENERATOR


def get_password_hasher() -> PasswordHasherPort:
    return _PASSWORD_HASHER


def get_user_provider(
    settings: AuthSettings = Depends(get_auth_settings),
    mongo_settings: MongoSettings = Depends(get_mongo_settings),
    mongo_manager: MongoConnectionManager = Depends(
        get_mongo_connection_manager
    ),
) -> UserProvider:
    if settings.user_provider == "mongodb":
        if not mongo_settings.enabled:
            raise PersistenceConfigurationError(
                "MongoDB authentication provider requires persistence."
            )
        return MongoUserProvider(
            MongoUserRepository(
                mongo_manager.database[USERS_COLLECTION]
            ),
            fallback_password_hash=_FALLBACK_PASSWORD_HASH,
        )
    if settings is _AUTH_SETTINGS:
        return _USER_PROVIDER
    return LocalSyntheticUserProvider.default(
        enabled=settings.local_fixture_users_enabled
    )


def get_user_repository(
    manager: MongoConnectionManager = Depends(
        get_mongo_connection_manager
    ),
) -> UserRepository:
    return MongoUserRepository(manager.database[USERS_COLLECTION])


def get_credential_repository(
    manager: MongoConnectionManager = Depends(
        get_mongo_connection_manager
    ),
) -> CredentialRepository:
    return MongoCredentialRepository(
        manager.database[CREDENTIALS_COLLECTION]
    )


def get_credential_issuance_repository(
    manager: MongoConnectionManager = Depends(
        get_mongo_connection_manager
    ),
) -> CredentialIssuanceRepository:
    return MongoCredentialIssuanceRepository(
        manager.database[CREDENTIALS_COLLECTION]
    )


def get_revocation_repository(
    manager: MongoConnectionManager = Depends(
        get_mongo_connection_manager
    ),
) -> RevocationRepository:
    return MongoRevocationRepository(
        manager.database[CREDENTIALS_COLLECTION]
    )


def get_audit_event_repository(
    manager: MongoConnectionManager = Depends(
        get_mongo_connection_manager
    ),
) -> AuditEventRepository:
    return MongoAuditEventRepository(
        manager.database[AUDIT_EVENTS_COLLECTION]
    )


def get_status_list_entry_repository(
    manager: MongoConnectionManager = Depends(
        get_mongo_connection_manager
    ),
) -> CredentialStatusEntryRepository:
    return MongoCredentialStatusEntryRepository(
        manager.database[STATUS_LIST_ENTRIES_COLLECTION],
        manager.database[CREDENTIALS_COLLECTION],
    )


def get_status_list_repository(
    manager: MongoConnectionManager = Depends(
        get_mongo_connection_manager
    ),
) -> StatusListRepository:
    return MongoStatusListRepository(
        manager.database[STATUS_LISTS_COLLECTION]
    )


def get_audit_outbox_repository(
    manager: MongoConnectionManager = Depends(
        get_mongo_connection_manager
    ),
) -> AuditOutboxRepository:
    return MongoAuditOutboxRepository(
        manager.database[AUDIT_OUTBOX_COLLECTION],
        manager.database[CREDENTIALS_COLLECTION],
    )


def get_presentation_repository(
    manager: MongoConnectionManager = Depends(
        get_mongo_connection_manager
    ),
    clock: Clock = Depends(get_clock),
) -> PresentationRepository:
    return MongoPresentationRepository(
        manager.database[PRESENTATIONS_COLLECTION],
        clock=clock,
    )


def get_holder_wallet_repository(
    manager: MongoConnectionManager = Depends(
        get_mongo_connection_manager
    ),
) -> HolderWalletRepository:
    return MongoHolderWalletRepository(
        manager.database[HOLDER_WALLETS_COLLECTION]
    )


def get_presentation_challenge_repository(
    manager: MongoConnectionManager = Depends(
        get_mongo_connection_manager
    ),
) -> PresentationChallengeRepository:
    return MongoPresentationChallengeRepository(
        manager.database[PRESENTATION_CHALLENGES_COLLECTION]
    )


def get_managed_key_repository(
    manager: MongoConnectionManager = Depends(
        get_mongo_connection_manager
    ),
) -> ManagedKeyRepository:
    return MongoManagedKeyRepository(
        manager.database[MANAGED_KEYS_COLLECTION]
    )


def get_optional_holder_wallet_repository(
    settings: MongoSettings = Depends(get_mongo_settings),
    manager: MongoConnectionManager = Depends(
        get_mongo_connection_manager
    ),
) -> HolderWalletRepository | None:
    if not settings.enabled:
        return None
    return MongoHolderWalletRepository(
        manager.database[HOLDER_WALLETS_COLLECTION]
    )


def get_status_list_service(
    entry_repository: CredentialStatusEntryRepository = Depends(
        get_status_list_entry_repository
    ),
    status_list_repository: StatusListRepository = Depends(
        get_status_list_repository
    ),
    settings: StatusListSettings = Depends(get_status_list_settings),
    clock: Clock = Depends(get_clock),
) -> StatusListService:
    return StatusListService(
        entry_repository=entry_repository,
        status_list_repository=status_list_repository,
        generator=_STATUS_LIST_GENERATOR,
        settings=settings,
        clock=clock,
        id_generator=new_object_id,
        metrics=INTERNAL_METRICS,
    )


def build_audit_outbox_delivery_service(
    manager: MongoConnectionManager,
    *,
    settings: AuditOutboxSettings,
    clock: Clock,
) -> AuditOutboxDeliveryService:
    return AuditOutboxDeliveryService(
        outbox_repository=MongoAuditOutboxRepository(
            manager.database[AUDIT_OUTBOX_COLLECTION],
            manager.database[CREDENTIALS_COLLECTION],
        ),
        audit_repository=MongoAuditEventRepository(
            manager.database[AUDIT_EVENTS_COLLECTION]
        ),
        settings=settings,
        clock=clock,
        metrics=INTERNAL_METRICS,
    )


def build_presentation_reconciliation_service(
    manager: MongoConnectionManager,
    *,
    settings: HolderWalletSettings,
    audit_settings: AuditOutboxSettings,
    clock: Clock,
) -> PresentationReconciliationService:
    credentials = MongoCredentialRepository(
        manager.database[CREDENTIALS_COLLECTION]
    )
    entries = MongoCredentialStatusEntryRepository(
        manager.database[STATUS_LIST_ENTRIES_COLLECTION],
        manager.database[CREDENTIALS_COLLECTION],
    )
    presentations = MongoPresentationRepository(
        manager.database[PRESENTATIONS_COLLECTION],
        clock=clock,
    )
    wallets = MongoHolderWalletRepository(
        manager.database[HOLDER_WALLETS_COLLECTION]
    )
    managed_keys = MongoManagedKeyRepository(
        manager.database[MANAGED_KEYS_COLLECTION]
    )
    audit_delivery = build_audit_outbox_delivery_service(
        manager,
        settings=audit_settings,
        clock=clock,
    )
    holder_key_router = _provider_aware_holder_signer(
        managed_keys,
        audit_delivery=audit_delivery,
    )
    challenge_service = PresentationChallengeService(
        challenge_repository=MongoPresentationChallengeRepository(
            manager.database[PRESENTATION_CHALLENGES_COLLECTION]
        ),
        wallet_repository=wallets,
        audit_delivery_service=audit_delivery,
        clock=clock,
        storage_id_generator=new_object_id,
        challenge_id_generator=_new_challenge_id,
        challenge_value_generator=_new_challenge_value,
        metrics=INTERNAL_METRICS,
    )
    inspector = build_credential_inspector(
        credential_repository=credentials,
        entry_repository=entries,
        credential_proof_service=_credential_proof_service(clock=clock),
        canonicalizer=_CANONICALIZER,
        status_list_settings=_STATUS_LIST_SETTINGS,
    )
    verifier = VerifierPresentationService(
        repository=presentations,
        credential_inspector=inspector,
        validator=PresentationValidator(
            canonicalizer=_CANONICALIZER,
            signer=_SIGNER,
            key_provider=_HOLDER_KEY_PROVIDER,
            did_resolver=_HOLDER_DID_RESOLVER,
        ),
        canonicalizer=_CANONICALIZER,
        audit_delivery_service=audit_delivery,
        clock=clock,
        challenge_service=challenge_service,
    )
    return PresentationReconciliationService(
        repository=presentations,
        verifier_service=verifier,
        challenge_service=challenge_service,
        audit_delivery_service=audit_delivery,
        settings=settings,
        clock=clock,
        metrics=INTERNAL_METRICS,
        wallet_repository=wallets,
        key_metadata_provider=holder_key_router,
    )


def build_managed_key_service(
    manager: MongoConnectionManager,
    *,
    settings: KeyManagementSettings,
    audit_settings: AuditOutboxSettings,
    clock: Clock,
) -> ManagedKeyService:
    return ManagedKeyService(
        repository=MongoManagedKeyRepository(
            manager.database[MANAGED_KEYS_COLLECTION]
        ),
        wallet_repository=MongoHolderWalletRepository(
            manager.database[HOLDER_WALLETS_COLLECTION]
        ),
        providers=_KEY_PROVIDERS,
        policy=ConfiguredKeyPolicy(settings),
        audit_delivery_service=build_audit_outbox_delivery_service(
            manager,
            settings=audit_settings,
            clock=clock,
        ),
        clock=clock,
        storage_id_generator=new_object_id,
        key_id_generator=_new_key_id,
        default_provider=settings.default_provider,
        metrics=INTERNAL_METRICS,
        reconciliation_retry_limit=settings.reconciliation_retry_limit,
        reconciliation_lease_seconds=settings.reconciliation_lease_seconds,
    )


def get_audit_outbox_delivery_service(
    outbox_repository: AuditOutboxRepository = Depends(
        get_audit_outbox_repository
    ),
    audit_repository: AuditEventRepository = Depends(
        get_audit_event_repository
    ),
    settings: AuditOutboxSettings = Depends(get_audit_outbox_settings),
    clock: Clock = Depends(get_clock),
) -> AuditOutboxDeliveryService:
    return AuditOutboxDeliveryService(
        outbox_repository=outbox_repository,
        audit_repository=audit_repository,
        settings=settings,
        clock=clock,
        metrics=INTERNAL_METRICS,
    )


def _new_wallet_id() -> str:
    return f"wallet_{token_urlsafe(24)}"


def _new_challenge_id() -> str:
    return f"challenge_{token_urlsafe(24)}"


def _new_challenge_value() -> str:
    return token_urlsafe(32)


def _new_holder_key_reference() -> str:
    return f"local-dev:wallet:{token_urlsafe(24)}"


def _new_key_id() -> str:
    return f"key_{token_urlsafe(24)}"


def get_managed_key_service(
    repository: ManagedKeyRepository = Depends(
        get_managed_key_repository
    ),
    wallet_repository: HolderWalletRepository = Depends(
        get_holder_wallet_repository
    ),
    audit_delivery: AuditOutboxDeliveryService = Depends(
        get_audit_outbox_delivery_service
    ),
    settings: KeyManagementSettings = Depends(
        get_key_management_settings
    ),
    clock: Clock = Depends(get_clock),
) -> ManagedKeyService:
    return ManagedKeyService(
        repository=repository,
        wallet_repository=wallet_repository,
        providers=_KEY_PROVIDERS,
        policy=ConfiguredKeyPolicy(settings),
        audit_delivery_service=audit_delivery,
        clock=clock,
        storage_id_generator=new_object_id,
        key_id_generator=_new_key_id,
        default_provider=settings.default_provider,
        metrics=INTERNAL_METRICS,
        reconciliation_retry_limit=settings.reconciliation_retry_limit,
        reconciliation_lease_seconds=settings.reconciliation_lease_seconds,
    )


def get_holder_wallet_service(
    wallet_repository: HolderWalletRepository = Depends(
        get_holder_wallet_repository
    ),
    credential_repository: CredentialRepository = Depends(
        get_credential_repository
    ),
    audit_delivery: AuditOutboxDeliveryService = Depends(
        get_audit_outbox_delivery_service
    ),
    clock: Clock = Depends(get_clock),
    managed_keys: ManagedKeyService = Depends(get_managed_key_service),
) -> HolderWalletService:
    return HolderWalletService(
        wallet_repository=wallet_repository,
        credential_repository=credential_repository,
        key_provider=_HOLDER_KEY_PROVIDER,
        audit_delivery_service=audit_delivery,
        clock=clock,
        storage_id_generator=new_object_id,
        wallet_id_generator=_new_wallet_id,
        key_reference_generator=_new_holder_key_reference,
        metrics=INTERNAL_METRICS,
        initial_key_provisioner=managed_keys,
    )


def get_presentation_challenge_service(
    challenge_repository: PresentationChallengeRepository = Depends(
        get_presentation_challenge_repository
    ),
    wallet_repository: HolderWalletRepository = Depends(
        get_holder_wallet_repository
    ),
    audit_delivery: AuditOutboxDeliveryService = Depends(
        get_audit_outbox_delivery_service
    ),
    clock: Clock = Depends(get_clock),
) -> PresentationChallengeService:
    return PresentationChallengeService(
        challenge_repository=challenge_repository,
        wallet_repository=wallet_repository,
        audit_delivery_service=audit_delivery,
        clock=clock,
        storage_id_generator=new_object_id,
        challenge_id_generator=_new_challenge_id,
        challenge_value_generator=_new_challenge_value,
        metrics=INTERNAL_METRICS,
    )


def get_credential_revocation_service(
    revocation_repository: RevocationRepository = Depends(
        get_revocation_repository
    ),
    status_list_service: StatusListService = Depends(
        get_status_list_service
    ),
    audit_delivery_service: AuditOutboxDeliveryService = Depends(
        get_audit_outbox_delivery_service
    ),
    clock: Clock = Depends(get_clock),
) -> CredentialRevocationService:
    return CredentialRevocationService(
        revocation_repository=revocation_repository,
        status_list_service=status_list_service,
        audit_delivery_service=audit_delivery_service,
        clock=clock,
        event_id_generator=new_object_id,
    )


def get_access_token_service(
    settings: AuthSettings = Depends(get_auth_settings),
) -> AccessTokenService:
    return JwtAccessTokenService(settings)


def get_authentication_service(
    settings: AuthSettings = Depends(get_auth_settings),
    user_provider: UserProvider = Depends(get_user_provider),
    password_hasher: PasswordHasherPort = Depends(get_password_hasher),
    token_service: AccessTokenService = Depends(get_access_token_service),
    clock: Clock = Depends(get_auth_clock),
    jti_generator: JtiGenerator = Depends(get_jti_generator),
) -> AuthenticationService:
    return AuthenticationService(
        user_provider=user_provider,
        password_hasher=password_hasher,
        access_token_service=token_service,
        clock=clock,
        jti_generator=jti_generator,
        enabled=settings.enabled,
    )


def get_authorization_service() -> AuthorizationService:
    return _AUTHORIZATION_SERVICE


def get_current_principal(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(bearer_scheme),
    ],
    service: AuthenticationService = Depends(get_authentication_service),
) -> AuthenticatedPrincipal:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise AuthenticationRequiredError(
            "Bearer authentication is required."
        )
    return service.authenticate_access_token(credentials.credentials)


def require_permission(
    permission: Permission,
) -> Callable[..., AuthenticatedPrincipal]:
    def authorize(
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
        service: AuthorizationService = Depends(get_authorization_service),
    ) -> AuthenticatedPrincipal:
        service.require_permission(principal, permission)
        return principal

    return authorize


def get_credential_api_service(
    clock: Clock = Depends(get_clock),
) -> CredentialApiService:
    proof_service = CredentialProofService(
        validator=_VALIDATOR,
        canonicalizer=_CANONICALIZER,
        signer=_SIGNER,
        key_provider=_KEY_PROVIDER,
        did_resolver=_DID_RESOLVER,
        clock=clock,
    )
    return CredentialApiService(
        validator=_VALIDATOR,
        proof_service=proof_service,
    )


def get_credential_issuance_api_service(
    clock: Clock = Depends(get_clock),
    issuance_repository: CredentialIssuanceRepository = Depends(
        get_credential_issuance_repository
    ),
    entry_repository: CredentialStatusEntryRepository = Depends(
        get_status_list_entry_repository
    ),
    status_list_settings: StatusListSettings = Depends(
        get_status_list_settings
    ),
    wallet_repository: HolderWalletRepository | None = Depends(
        get_optional_holder_wallet_repository
    ),
) -> CredentialApiService:
    proof_service = CredentialProofService(
        validator=_VALIDATOR,
        canonicalizer=_CANONICALIZER,
        signer=_SIGNER,
        key_provider=_KEY_PROVIDER,
        did_resolver=_DID_RESOLVER,
        clock=clock,
    )
    signing_service = LocalIssuerSigningService(
        proof_service=proof_service,
        key_provider=_KEY_PROVIDER,
    )
    issuance_service = CredentialIssuanceService(
        validator=_VALIDATOR,
        signer=signing_service,
        issuance_repository=issuance_repository,
        entry_repository=entry_repository,
        canonicalizer=_CANONICALIZER,
        settings=status_list_settings,
        clock=clock,
        id_generator=new_object_id,
        metrics=INTERNAL_METRICS,
        wallet_repository=wallet_repository,
    )
    return CredentialApiService(
        validator=_VALIDATOR,
        proof_service=proof_service,
        issuance_service=issuance_service,
    )


def _credential_proof_service(*, clock: Clock) -> CredentialProofService:
    return CredentialProofService(
        validator=_VALIDATOR,
        canonicalizer=_CANONICALIZER,
        signer=_SIGNER,
        key_provider=_KEY_PROVIDER,
        did_resolver=_DID_RESOLVER,
        clock=clock,
    )


def get_holder_presentation_service(
    repository: PresentationRepository = Depends(
        get_presentation_repository
    ),
    credential_repository: CredentialRepository = Depends(
        get_credential_repository
    ),
    entry_repository: CredentialStatusEntryRepository = Depends(
        get_status_list_entry_repository
    ),
    audit_delivery: AuditOutboxDeliveryService = Depends(
        get_audit_outbox_delivery_service
    ),
    status_settings: StatusListSettings = Depends(
        get_status_list_settings
    ),
    wallet_service: HolderWalletService = Depends(
        get_holder_wallet_service
    ),
    challenge_service: PresentationChallengeService = Depends(
        get_presentation_challenge_service
    ),
    clock: Clock = Depends(get_clock),
    managed_keys: ManagedKeyRepository = Depends(
        get_managed_key_repository
    ),
) -> HolderPresentationService:
    inspector = build_credential_inspector(
        credential_repository=credential_repository,
        entry_repository=entry_repository,
        credential_proof_service=_credential_proof_service(clock=clock),
        canonicalizer=_CANONICALIZER,
        status_list_settings=status_settings,
    )
    holder_key_router = _provider_aware_holder_signer(
        managed_keys,
        audit_delivery=audit_delivery,
    )
    return HolderPresentationService(
        repository=repository,
        credential_inspector=inspector,
        builder=PresentationBuilder(
            canonicalizer=_CANONICALIZER,
            signer=_SIGNER,
            key_provider=holder_key_router,
            holder_signer=holder_key_router,
            key_metadata_provider=holder_key_router,
        ),
        audit_delivery_service=audit_delivery,
        clock=clock,
        id_generator=new_object_id,
        wallet_service=wallet_service,
        challenge_service=challenge_service,
    )


def get_verifier_presentation_service(
    repository: PresentationRepository = Depends(
        get_presentation_repository
    ),
    credential_repository: CredentialRepository = Depends(
        get_credential_repository
    ),
    entry_repository: CredentialStatusEntryRepository = Depends(
        get_status_list_entry_repository
    ),
    audit_delivery: AuditOutboxDeliveryService = Depends(
        get_audit_outbox_delivery_service
    ),
    status_settings: StatusListSettings = Depends(
        get_status_list_settings
    ),
    challenge_service: PresentationChallengeService = Depends(
        get_presentation_challenge_service
    ),
    clock: Clock = Depends(get_clock),
) -> VerifierPresentationService:
    inspector = build_credential_inspector(
        credential_repository=credential_repository,
        entry_repository=entry_repository,
        credential_proof_service=_credential_proof_service(clock=clock),
        canonicalizer=_CANONICALIZER,
        status_list_settings=status_settings,
    )
    return VerifierPresentationService(
        repository=repository,
        credential_inspector=inspector,
        validator=PresentationValidator(
            canonicalizer=_CANONICALIZER,
            signer=_SIGNER,
            key_provider=_HOLDER_KEY_PROVIDER,
            did_resolver=_HOLDER_DID_RESOLVER,
        ),
        canonicalizer=_CANONICALIZER,
        audit_delivery_service=audit_delivery,
        clock=clock,
        challenge_service=challenge_service,
    )


def get_presentation_reconciliation_service(
    repository: PresentationRepository = Depends(
        get_presentation_repository
    ),
    verifier_service: VerifierPresentationService = Depends(
        get_verifier_presentation_service
    ),
    challenge_service: PresentationChallengeService = Depends(
        get_presentation_challenge_service
    ),
    audit_delivery: AuditOutboxDeliveryService = Depends(
        get_audit_outbox_delivery_service
    ),
    settings: HolderWalletSettings = Depends(
        get_holder_wallet_settings
    ),
    wallet_repository: HolderWalletRepository = Depends(
        get_holder_wallet_repository
    ),
    clock: Clock = Depends(get_clock),
    managed_keys: ManagedKeyRepository = Depends(
        get_managed_key_repository
    ),
) -> PresentationReconciliationService:
    return PresentationReconciliationService(
        repository=repository,
        verifier_service=verifier_service,
        challenge_service=challenge_service,
        audit_delivery_service=audit_delivery,
        settings=settings,
        clock=clock,
        metrics=INTERNAL_METRICS,
        wallet_repository=wallet_repository,
        key_metadata_provider=_provider_aware_holder_signer(
            managed_keys,
            audit_delivery=audit_delivery,
        ),
    )


def _provider_aware_holder_signer(
    repository: ManagedKeyRepository,
    *,
    audit_delivery: AuditOutboxDeliveryService | None = None,
) -> ProviderAwareHolderSigner:
    return ProviderAwareHolderSigner(
        repository=repository,
        providers=_KEY_PROVIDERS,
        legacy_provider=_HOLDER_KEY_PROVIDER,
        legacy_signer=_HOLDER_SIGNER,
        allow_legacy_fallback=(
            _KEY_MANAGEMENT_SETTINGS.environment
            not in {"production", "prod", "staging"}
        ),
        metrics=INTERNAL_METRICS,
        audit_delivery_service=audit_delivery,
    )


def _build_key_providers(
    settings: KeyManagementSettings,
) -> dict[str, ExternalKeyProvider]:
    providers: dict[str, ExternalKeyProvider] = {}
    if (
        settings.development_provider_enabled
        and "development" in settings.enabled_providers
    ):
        development = DevelopmentExternalKeyProvider()
        providers[development.name] = development
    if settings.remote_provider_name in settings.enabled_providers:
        authentication = (
            NoProviderAuthentication()
            if settings.remote_auth_token_env is None
            else EnvironmentBearerAuthentication(
                settings.remote_auth_token_env
            )
        )
        remote = GenericRemoteKmsAdapter(
            name=settings.remote_provider_name,
            base_url=settings.remote_base_url or "",
            transport=UrllibKmsHttpTransport(
                tls_verify=settings.tls_verify,
                client_certificate_path=(
                    settings.client_certificate_path
                ),
                client_key_path=settings.client_key_path,
            ),
            authentication=authentication,
            request_timeout_seconds=settings.request_timeout_seconds,
            retry_count=settings.retry_count,
            retry_backoff_ms=settings.retry_backoff_ms,
            circuit_failure_threshold=(
                settings.circuit_failure_threshold
            ),
            circuit_reset_seconds=settings.circuit_reset_seconds,
        )
        providers[remote.name] = remote
    return providers


_KEY_PROVIDERS = _build_key_providers(_KEY_MANAGEMENT_SETTINGS)
