"""Organization scoping for admin queries.

Every admin lookup of a location or version goes through here, so a record in
another organization behaves exactly like one that doesn't exist (404, never
403). The public route is deliberately unscoped: slugs are one global
namespace.
"""

from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.file_version import FileVersion
from backend.models.location import Location


def active_locations(organization_id: UUID) -> Select[tuple[Location]]:
    return select(Location).where(
        Location.organization_id == organization_id,
        Location.deleted_at.is_(None),
    )


async def get_location(
    db: AsyncSession,
    organization_id: UUID,
    slug: str,
    *,
    for_update: bool = False,
) -> Location | None:
    query = active_locations(organization_id).where(Location.slug == slug)
    if for_update:
        query = query.with_for_update().execution_options(populate_existing=True)
    return (await db.execute(query)).scalar_one_or_none()


async def get_version(
    db: AsyncSession,
    organization_id: UUID,
    version_id: UUID,
) -> FileVersion | None:
    """A non-deleted version whose location belongs to the organization."""
    result = await db.execute(
        select(FileVersion)
        .join(Location, Location.id == FileVersion.location_id)
        .where(
            FileVersion.id == version_id,
            FileVersion.deleted_at.is_(None),
            Location.organization_id == organization_id,
        )
    )
    return result.scalar_one_or_none()
