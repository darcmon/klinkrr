import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.dependencies import (
    get_current_admin,
    get_current_membership,
    require_permission,
)
from backend.errors import api_error
from backend.models.admin_user import AdminUser
from backend.models.location import Location
from backend.models.organization import Membership
from backend.permissions import has_permission
from backend.services import scoping
from backend.services.audit_service import audit_service
from backend.services.location_summaries import (
    last_submitted_subquery,
    location_responses,
)
from backend.services.slugs import (
    SlugStatus,
    owner_name_for,
    slug_error_message,
    slug_status,
)
from backend.schemas.location import (
    LocationCreate,
    LocationUpdate,
    LocationResponse,
    LocationListResponse,
    SlugAvailabilityResponse,
)

router = APIRouter(prefix="/admin/locations", tags=["locations"])


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("", response_model=LocationListResponse)
async def list_locations(
    q: str | None = Query(None, max_length=200),
    sort: Literal["slug", "name", "recent_submission"] = Query("slug"),
    limit: int | None = Query(None, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    membership: Membership = Depends(get_current_membership),
):
    """`q` matches display names and slugs, case-insensitively.
    `recent_submission` puts the locations with the latest submissions first."""
    query = scoping.active_locations(membership.organization_id)

    if q and q.strip():
        pattern = f"%{_escape_like(q.strip())}%"
        query = query.where(
            or_(
                Location.display_name.ilike(pattern, escape="\\"),
                Location.slug.ilike(pattern, escape="\\"),
            )
        )

    total = (
        await db.execute(select(func.count()).select_from(query.subquery()))
    ).scalar_one()

    if sort == "recent_submission":
        last = last_submitted_subquery()
        query = query.outerjoin(last, last.c.location_id == Location.id).order_by(
            last.c.last_submitted_at.desc().nulls_last(),
            func.lower(Location.display_name),
        )
    elif sort == "name":
        query = query.order_by(func.lower(Location.display_name), Location.slug)
    else:
        query = query.order_by(Location.slug)

    if limit is not None:
        query = query.limit(limit)

    locations = list((await db.execute(query)).scalars().all())
    return LocationListResponse(
        locations=await location_responses(db, locations),
        total=total,
    )


def _slug_error(status: SlugStatus, membership: Membership) -> HTTPException:
    taken_by = owner_name_for(status, membership.organization_id)
    extra = {"taken_by": taken_by} if taken_by else {}
    return api_error(
        409, f"slug_{status.reason}", slug_error_message(status, taken_by), **extra
    )


async def _replay_or_conflict(
    existing: Location,
    body: LocationCreate,
    membership: Membership,
    response: Response,
    db: AsyncSession,
) -> LocationResponse:
    """A location with the client's id already exists: the same request
    arriving again returns it; anything else is a conflict."""
    if (
        existing.slug == body.slug
        and existing.organization_id == membership.organization_id
        and existing.deleted_at is None
    ):
        response.status_code = 200
        return (await location_responses(db, [existing]))[0]
    raise api_error(409, "id_conflict", "This id belongs to a different location.")


@router.post("", response_model=LocationResponse, status_code=201)
async def create_location(
    body: LocationCreate,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    membership: Membership = Depends(require_permission("create_location")),
):
    if not body.approval_required and not has_permission(
        membership.role, "manage_locations"
    ):
        raise HTTPException(
            status_code=403,
            detail="Only managers can create a location that publishes without approval",
        )

    if body.id is not None:
        existing = await db.get(Location, body.id)
        if existing is not None:
            return await _replay_or_conflict(existing, body, membership, response, db)

    status = await slug_status(db, body.slug)
    if not status.available:
        raise _slug_error(status, membership)

    location = Location(
        id=body.id or uuid.uuid4(),
        slug=body.slug,
        display_name=body.display_name,
        description=body.description,
        reminder_email=body.reminder_email,
        organization_id=membership.organization_id,
        created_by_id=admin.id,
    )
    location.approval_required = body.approval_required

    try:
        async with db.begin_nested():
            db.add(location)
            await db.flush()
    except IntegrityError:
        # The slug or id was taken between the check above and the insert.
        if body.id is not None:
            existing = await db.get(Location, body.id)
            if existing is not None:
                return await _replay_or_conflict(
                    existing, body, membership, response, db
                )
        raise _slug_error(await slug_status(db, body.slug), membership)

    await audit_service.log(
        db,
        action="location_created",
        entity_type="location",
        entity_id=location.id,
        actor=admin.email,
        actor_id=admin.id,
        organization_id=location.organization_id,
        request=request,
        details={"slug": location.slug, "approval_required": location.approval_required},
    )

    return (await location_responses(db, [location]))[0]


# Declared before "/{slug}" so it isn't matched as a slug.
@router.get("/slug-availability", response_model=SlugAvailabilityResponse)
async def check_slug_availability(
    slug: str = Query(..., max_length=200),
    db: AsyncSession = Depends(get_db),
    membership: Membership = Depends(get_current_membership),
):
    """Uses the same rules as creation. Advisory only: it doesn't reserve the
    slug, so creation can still return 409."""
    status = await slug_status(db, slug)
    if status.available:
        return SlugAvailabilityResponse(available=True, reason=None)

    taken_by = owner_name_for(status, membership.organization_id)
    return SlugAvailabilityResponse(
        available=False,
        reason=status.reason,
        taken_by=taken_by,
        message=slug_error_message(status, taken_by),
    )


@router.get("/{slug}", response_model=LocationResponse)
async def get_location(
    slug: str,
    db: AsyncSession = Depends(get_db),
    membership: Membership = Depends(get_current_membership),
):
    location = await scoping.get_location(db, membership.organization_id, slug)
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    return (await location_responses(db, [location]))[0]


# Fields where `null` means "leave unchanged" rather than "clear".
NOT_CLEARABLE = ("display_name", "approval_required")


@router.patch("/{slug}", response_model=LocationResponse)
async def update_location(
    slug: str,
    body: LocationUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    membership: Membership = Depends(get_current_membership),
):
    location = await scoping.get_location(
        db, membership.organization_id, slug, for_update=True
    )
    if location is None:
        raise HTTPException(status_code=404, detail="Location not found")

    previous_approval_required = location.approval_required

    update_data = body.model_dump(exclude_unset=True)
    for field in NOT_CLEARABLE:
        if field in update_data and update_data[field] is None:
            del update_data[field]

    can_manage = has_permission(membership.role, "manage_locations")

    changes_policy = (
        "approval_required" in update_data
        and update_data["approval_required"] != previous_approval_required
    )
    if changes_policy and not can_manage:
        raise HTTPException(
            status_code=403,
            detail="Only managers can change a location's approval setting",
        )

    changes_details = any(field != "approval_required" for field in update_data)
    if changes_details and not (can_manage or location.created_by_id == admin.id):
        raise HTTPException(
            status_code=403,
            detail="You can only edit locations you created",
        )

    for field, value in update_data.items():
        setattr(location, field, value)

    location.updated_at = datetime.now(timezone.utc)
    await db.flush()

    if location.approval_required != previous_approval_required:
        await audit_service.log(
            db,
            action="governance_changed",
            entity_type="location",
            entity_id=location.id,
            actor=admin.email,
            actor_id=admin.id,
            organization_id=location.organization_id,
            request=request,
            details={
                "approval_required": {
                    "before": previous_approval_required,
                    "after": location.approval_required,
                },
            },
        )

    return (await location_responses(db, [location]))[0]
