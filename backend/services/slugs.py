"""Rules for location slugs, shared by location creation and the live
availability check so the two can never disagree.

Slugs are one global namespace across organizations (they are the public
URL), and a deleted location keeps its slug for good so a printed link never
starts serving someone else's content.
"""

import re
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.location import Location

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


async def slug_status(db: AsyncSession, slug: str) -> SlugStatus:
    if not is_valid_slug(slug):
        return SlugStatus("invalid")
    if slug in RESERVED_SLUGS:
        return SlugStatus("reserved")

    owner = (
        await db.execute(select(Location).where(Location.slug == slug))
    ).scalar_one_or_none()
    if owner is None:
        return SlugStatus(None)
    return SlugStatus("retired" if owner.deleted_at else "taken", owner)


def owner_name_for(status: SlugStatus, organization_id: UUID) -> str | None:
    """The owning location's name, only if the caller's organization owns it,
    so another tenant's location names are never revealed."""
    if status.reason == "taken" and status.owner.organization_id == organization_id:
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
