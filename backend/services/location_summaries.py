from urllib.parse import urlparse

from sqlalchemy import Subquery, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.file_version import FileVersion
from backend.models.location import Location
from backend.schemas.location import LocationResponse, PublishedVersionSummary


def last_submitted_subquery() -> Subquery:
    """location_id → latest uploaded_at among non-deleted versions."""
    return (
        select(
            FileVersion.location_id,
            func.max(FileVersion.uploaded_at).label("last_submitted_at"),
        )
        .where(FileVersion.deleted_at.is_(None))
        .group_by(FileVersion.location_id)
        .subquery()
    )


def _label(version: FileVersion) -> str:
    if version.kind == "link":
        return urlparse(version.link_url).hostname or version.link_url
    return version.original_filename


async def location_responses(
    db: AsyncSession, locations: list[Location]
) -> list[LocationResponse]:
    """Responses with the published version and last submission filled in,
    in two queries however many locations there are."""
    if not locations:
        return []

    ids = [location.id for location in locations]
    last = last_submitted_subquery()
    last_submitted = dict(
        (
            await db.execute(
                select(last.c.location_id, last.c.last_submitted_at).where(
                    last.c.location_id.in_(ids)
                )
            )
        ).all()
    )

    published_ids = [
        location.current_approved_version_id
        for location in locations
        if location.current_approved_version_id
    ]
    published = {}
    if published_ids:
        result = await db.execute(
            select(FileVersion).where(FileVersion.id.in_(published_ids))
        )
        published = {version.id: version for version in result.scalars()}

    responses = []
    for location in locations:
        version = published.get(location.current_approved_version_id)
        response = LocationResponse.model_validate(location)
        response.last_submitted_at = last_submitted.get(location.id)
        response.published_version = (
            PublishedVersionSummary(
                id=version.id,
                version_number=version.version_number,
                kind=version.kind,
                label=_label(version),
            )
            if version
            else None
        )
        responses.append(response)
    return responses
