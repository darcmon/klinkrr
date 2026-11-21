"""Rules for location slugs, shared by location creation and the live
availability check so the two can never disagree.

Slugs are unique within an owner, and a deleted location keeps its slug for
good so a printed link never starts serving someone else's content.
"""

import re
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.location import Location
from backend.services.scoping import owner_clause

SLUG_PATTERN = re.compile(r"^[a-z0-9-]+$")
MAX_SLUG_LENGTH = 100

# Top-level paths the API serves itself, plus a few kept for future use. A
# location with one of these slugs could never be reached at its public URL.
RESERVED_SLUGS = frozenset(
    {"admin", "api", "docs", "health", "openapi", "redoc", "static"}
)

Unavailable = Literal["invalid", "reserved", "retired", "taken"]


@dataclass(frozen=True)
class SlugStatus:
    reason: Unavailable | None
    # The existing location when the slug is taken or retired.
    owner: Location | None = None

    @property
    def available(self) -> bool:
        return self.reason is None


def is_valid_slug(slug: str) -> bool:
    return 0 < len(slug) <= MAX_SLUG_LENGTH and bool(SLUG_PATTERN.match(slug))


async def slug_status(
    db: AsyncSession,
    slug: str,
    *,
    organization_id: UUID | None = None,
    owner_user_id: UUID | None = None,
) -> SlugStatus:
    if not is_valid_slug(slug):
        return SlugStatus("invalid")
    if slug in RESERVED_SLUGS:
        return SlugStatus("reserved")

    owner = (
        await db.execute(select(Location).where(
            owner_clause(organization_id, owner_user_id=owner_user_id),
            Location.slug == slug,
        ))
    ).scalar_one_or_none()
    if owner is None:
        return SlugStatus(None)
    return SlugStatus("retired" if owner.deleted_at else "taken", owner)


def owner_name_for(
    status: SlugStatus,
    organization_id: UUID | None = None,
    *,
    owner_user_id: UUID | None = None,
) -> str | None:
    """Return a taken location's name only in the caller's owner context."""
    if status.reason != "taken" or status.owner is None:
        return None
    if (
        status.owner.organization_id == organization_id
        and status.owner.owner_user_id == owner_user_id
    ):
        return status.owner.display_name
    return None


def slug_error_message(status: SlugStatus, taken_by: str | None) -> str:
    match status.reason:
        case "invalid":
            return "Use lowercase letters, numbers and hyphens, up to 100 characters."
        case "reserved":
            return "This path is reserved by klinkrr."
        case "retired":
            return (
                "This path belonged to a deleted location and can't be reused."
            )
        case "taken" if taken_by:
            return f"This path is taken by {taken_by}."
        case _:
            return "This path is already in use."
