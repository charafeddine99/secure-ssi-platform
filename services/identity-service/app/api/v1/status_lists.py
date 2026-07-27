from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path, Response
from fastapi.responses import JSONResponse

from app.api.v1.dependencies import get_status_list_service
from app.application.services.status_list_service import StatusListService
from app.schemas.credential_api import ApiErrorResponse
from app.schemas.status_list_api import (
    BitstringStatusListCredentialResponse,
    StatusListHistoryResponse,
    StatusListMetadataResponse,
    StatusListVersionSummary,
)


router = APIRouter(prefix="/status-lists", tags=["status-lists"])
_STATUS_LIST_ID = r"^revocation-[0-9a-f]{24}(?:-[0-9]{6})?$"
_ERROR_RESPONSES = {
    404: {
        "model": ApiErrorResponse,
        "description": "The status list has no assigned credentials.",
    },
    409: {
        "model": ApiErrorResponse,
        "description": "The status list changed during publication.",
    },
    500: {
        "model": ApiErrorResponse,
        "description": "The status list could not be generated safely.",
    },
    503: {
        "model": ApiErrorResponse,
        "description": "MongoDB persistence is unavailable.",
    },
}


@router.get(
    "/{status_list_id}",
    response_model=BitstringStatusListCredentialResponse,
    summary="Publish a W3C Bitstring Status List credential",
    description=(
        "Returns the versioned, signed revocation bitstring for credentials "
        "assigned to the deterministic issuer status list."
    ),
    responses={
        304: {"description": "The cached publication is still current."},
        **_ERROR_RESPONSES,
    },
)
def get_status_list(
    status_list_id: Annotated[
        str,
        Path(pattern=_STATUS_LIST_ID),
    ],
    if_none_match: Annotated[
        str | None,
        Header(alias="If-None-Match"),
    ] = None,
    service: StatusListService = Depends(get_status_list_service),
) -> Response:
    publication = service.get_publication(status_list_id)
    headers = _cache_headers(publication.etag, publication.cache_control)
    if _etag_matches(if_none_match, publication.etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(
        content=dict(publication.document),
        headers=headers,
        media_type="application/vc+ld+json",
    )


@router.get(
    "/{status_list_id}/metadata",
    response_model=StatusListMetadataResponse,
    summary="Read status-list publication metadata",
    description=(
        "Returns version, cache, capacity, assignment, and revocation counts "
        "without returning the compressed bitstring."
    ),
    responses=_ERROR_RESPONSES,
)
def get_status_list_metadata(
    status_list_id: Annotated[
        str,
        Path(pattern=_STATUS_LIST_ID),
    ],
    response: Response,
    service: StatusListService = Depends(get_status_list_service),
) -> StatusListMetadataResponse:
    publication = service.get_publication(status_list_id)
    response.headers.update(
        _cache_headers(publication.etag, publication.cache_control)
    )
    return StatusListMetadataResponse(
        statusListId=publication.status_list_id,
        statusListCredential=service.status_list_url(
            publication.status_list_id
        ),
        statusPurpose=publication.status_purpose.value,
        issuer=publication.issuer_did,
        listLength=publication.list_length,
        capacity=publication.capacity,
        assignedEntries=publication.assigned_entries,
        revokedEntries=publication.revoked_entries,
        utilization=(
            publication.assigned_entries / publication.capacity
        ),
        active=service.is_active(publication),
        version=publication.version,
        etag=publication.etag,
        publishedAt=publication.published_at,
        ttlSeconds=publication.ttl_seconds,
        cacheControl=publication.cache_control,
    )


@router.get(
    "/{status_list_id}/history",
    response_model=StatusListHistoryResponse,
    summary="Read immutable status-list publication history",
    description=(
        "Returns append-only publication metadata for every material version "
        "of the selected status list."
    ),
    responses=_ERROR_RESPONSES,
)
def get_status_list_history(
    status_list_id: Annotated[
        str,
        Path(pattern=_STATUS_LIST_ID),
    ],
    response: Response,
    service: StatusListService = Depends(get_status_list_service),
) -> StatusListHistoryResponse:
    history = service.get_history(status_list_id)
    latest = history[-1]
    response.headers.update(
        _cache_headers(latest.etag, latest.cache_control)
    )
    return StatusListHistoryResponse(
        statusListId=status_list_id,
        statusListCredential=service.status_list_url(status_list_id),
        active=service.is_active(latest),
        latestVersion=latest.version,
        versions=[
            StatusListVersionSummary(
                version=publication.version,
                etag=publication.etag,
                contentHash=publication.content_hash,
                assignedEntries=publication.assigned_entries,
                revokedEntries=publication.revoked_entries,
                publishedAt=publication.published_at,
            )
            for publication in history
        ],
    )


@router.get(
    "/{status_list_id}/versions/{version}",
    response_model=BitstringStatusListCredentialResponse,
    summary="Read an immutable status-list publication version",
    description=(
        "Returns the exact signed publication document stored for one "
        "historical version."
    ),
    responses=_ERROR_RESPONSES,
)
def get_status_list_version(
    status_list_id: Annotated[
        str,
        Path(pattern=_STATUS_LIST_ID),
    ],
    version: Annotated[int, Path(ge=1)],
    service: StatusListService = Depends(get_status_list_service),
) -> Response:
    service.get_publication(status_list_id)
    publication = service.get_version(status_list_id, version)
    headers = _cache_headers(
        publication.etag,
        "public, max-age=31536000, immutable",
    )
    headers["X-Status-List-Version"] = str(publication.version)
    return JSONResponse(
        content=dict(publication.document),
        headers=headers,
        media_type="application/vc+ld+json",
    )


def _cache_headers(etag: str, cache_control: str) -> dict[str, str]:
    return {
        "ETag": etag,
        "Cache-Control": cache_control,
        "Vary": "Accept-Encoding",
    }


def _etag_matches(value: str | None, etag: str) -> bool:
    if value is None:
        return False
    return any(
        candidate.strip() in {"*", etag}
        for candidate in value.split(",")
    )
