from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.models.location import Location
from backend.models.file_version import FileVersion
from backend.models.organization import Organization
from backend.services.file_service import file_service
from backend.services.audit_service import audit_service
from backend.services.content_disposition import content_disposition
from backend.services.cache_service import cache_service

router = APIRouter(tags=["public"])


async def _serve_location(
    cache_key: str,
    location_query: Select[tuple[Location]],
    request: Request,
    db: AsyncSession,
):
    # Check cache first
    cached = cache_service.get(cache_key)

    if not cached:
        generation = cache_service.get_generation()

        # 1. Resolve the address using the route's location query.
        result = await db.execute(location_query)
        location = result.scalar_one_or_none()
        if not location or not location.current_approved_version_id:
            raise HTTPException(status_code=404, detail="File not found")

        # 2. Get the approved file version
        version = await db.get(FileVersion, location.current_approved_version_id)
        if (
            version is None
            or version.deleted_at is not None
            or version.status != "approved"
        ):
            raise HTTPException(status_code=404, detail="Version not found")

        cached = cache_service.set(
            slug=cache_key,
            kind=version.kind,
            link_url=version.link_url,
            link_mode=version.link_mode,
            version_id=version.id,
            s3_key=version.s3_key,
            content_type=version.content_type,
            original_filename=version.original_filename,
            organization_id=location.organization_id,
            expected_generation=generation,
        )

    # 3. Log the access
    await audit_service.log(
        db=db,
        action="access",
        entity_type="file_version",
        entity_id=cached.version_id,
        organization_id=cached.organization_id,
        request=request,
    )

    if cached.kind == "link":
        if cached.link_mode != "redirect" or not cached.link_url:
            raise HTTPException(
                status_code=503,
                detail="Link is unavailable",
            )

        return RedirectResponse(
            url=cached.link_url,
            status_code=302,
            headers={"Cache-Control": "no-store"},
        )

    # 4. Stream the file content
    if cached.s3_key is None:
        raise HTTPException(status_code=503, detail="File is unavailable")

    return StreamingResponse(
        file_service.stream_file(cached.s3_key),
        media_type=cached.content_type,
        headers={
            "Content-Disposition": content_disposition(
                "inline", cached.original_filename
            ),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-cache, must-revalidate",
        },
    )


@router.get("/{organization_slug}/{location_slug}")
async def serve_namespaced_location(
    organization_slug: str,
    location_slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    location_query = (
        select(Location)
        .join(Organization, Organization.id == Location.organization_id)
        .where(
            Organization.slug == organization_slug,
            Location.slug == location_slug,
            Location.deleted_at.is_(None),
        )
    )
    return await _serve_location(
        f"{organization_slug}/{location_slug}", location_query, request, db
    )


@router.get("/{legacy_slug}")
async def serve_legacy_location(
    legacy_slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    location_query = select(Location).where(
        Location.legacy_slug == legacy_slug,
        Location.deleted_at.is_(None),
    )
    return await _serve_location(legacy_slug, location_query, request, db)
