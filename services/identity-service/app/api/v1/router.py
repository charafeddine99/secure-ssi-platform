from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.credentials import router as credentials_router
from app.api.v1.status_lists import router as status_lists_router
from app.api.v1.presentations import router as presentations_router
from app.api.v1.presentation_challenges import (
    router as presentation_challenges_router,
)
from app.api.v1.wallets import router as wallets_router
from app.api.v1.managed_keys import router as managed_keys_router
from app.api.v1.oid4vci import router as oid4vci_router
from app.api.v1.oid4vp import router as oid4vp_router
from app.api.v1.blockchain import router as blockchain_router
from app.api.v1.audit import router as audit_router
from app.api.v1.trust_registry import router as trust_registry_router
from app.api.v1.database import router as database_router
from app.api.v1.admin_users import router as admin_users_router
from app.api.v1.wallet_backups import router as wallet_backups_router
from app.api.v1.platform_backups import router as platform_backups_router
from app.api.v1.step_up import router as step_up_router
from app.api.v1.account_lifecycle import router as account_lifecycle_router
from app.api.v1.registration import router as registration_router
from app.api.v1.readiness import router as readiness_router


router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(step_up_router)
router.include_router(account_lifecycle_router)
router.include_router(registration_router)
router.include_router(readiness_router)
router.include_router(credentials_router)
router.include_router(status_lists_router)
router.include_router(presentations_router)
router.include_router(wallet_backups_router)
router.include_router(wallets_router)
router.include_router(presentation_challenges_router)
router.include_router(managed_keys_router)
router.include_router(oid4vci_router)
router.include_router(oid4vp_router)
router.include_router(blockchain_router)
router.include_router(audit_router)
router.include_router(trust_registry_router)
router.include_router(database_router)
router.include_router(admin_users_router)
router.include_router(platform_backups_router)
