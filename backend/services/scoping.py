"""Owner scoping for admin queries.

Every admin lookup of a location or version goes through here, so a record in
another owner context behaves exactly like one that doesn't exist (404, never
403). Public routes resolve an owner's namespace or a preserved legacy address
without requiring administrative access.
"""

from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.file_version import FileVersion
from backend.models.location import Location


def owner_clause(
    organization_id: UUID | None = None,
    *,
    owner_user_id: UUID | None = None,
) -> ColumnElement[bool]:
    """Return the location filter for exactly one owner context."""
    if (organization_id is None) == (owner_user_id is None):
        raise ValueError("Exactly one location owner is required")
    if organization_id is not None:
        return Location.organization_id == organization_id
    return Location.owner_user_id == owner_user_id


def active_locations(
    organization_id: UUID | None = None,
    *,
    owner_user_id: UUID | None = None,
) -> Select[tuple[Location]]:
    return select(Location).where(
        owner_clause(organization_id, owner_user_id=owner_user_id),
        Location.deleted_at.is_(None),
    )


async def get_location(
    db: AsyncSession,
    organization_id: UUID | None,
    slug: str,
    *,
    owner_user_id: UUID | None = None,
    for_update: bool = False,
) -> Location | None:
    query = active_locations(
        organization_id, owner_user_id=owner_user_id
    ).where(Location.slug == slug)
    if for_update:
        query = query.with_for_update().execution_options(populate_existing=True)
    return (await db.execute(query)).scalar_one_or_none()


async def get_version(
    db: AsyncSession,
    organization_id: UUID | None,
    version_id: UUID,
    *,
    owner_user_id: UUID | None = None,
) -> FileVersion | None:
    """A non-deleted version whose location belongs to the selected owner."""
    result = await db.execute(
        select(FileVersion)
        .join(Location, Location.id == FileVersion.location_id)
        .where(
            FileVersion.id == version_id,
            FileVersion.deleted_at.is_(None),
            owner_clause(organization_id, owner_user_id=owner_user_id),
        )
    )
    return result.scalar_one_or_none()
