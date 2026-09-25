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


router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(credentials_router)
router.include_router(status_lists_router)
router.include_router(presentations_router)
router.include_router(wallets_router)
router.include_router(presentation_challenges_router)
router.include_router(managed_keys_router)
router.include_router(oid4vci_router)
router.include_router(oid4vp_router)
