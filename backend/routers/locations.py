from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.dependencies import (
    get_current_admin,
    get_current_membership,
    require_permission,
)
from backend.models.admin_user import AdminUser
from backend.models.location import Location
from backend.models.organization import Membership
from backend.permissions import has_permission
from backend.services import scoping
from backend.services.audit_service import audit_service
from backend.schemas.location import (
    LocationCreate,
    LocationUpdate,
    LocationResponse,
    LocationListResponse,
)

router = APIRouter(prefix="/admin/locations", tags=["locations"])


@router.get("", response_model=LocationListResponse)
async def list_locations(
    db: AsyncSession = Depends(get_db),
    membership: Membership = Depends(get_current_membership),
):
    query = scoping.active_locations(membership.organization_id)
    result = await db.execute(query.order_by(Location.slug))
    locations = result.scalars().all()
    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar_one()
    return LocationListResponse(
        locations=[LocationResponse.model_validate(location) for location in locations],
        total=total,
    )


@router.post("", response_model=LocationResponse, status_code=201)
async def create_location(
    body: LocationCreate,
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

    # Slugs are one global namespace across organizations (they are the
    # public URL), and deleted locations keep theirs, so this is unscoped.
    existing = await db.execute(select(Location).where(Location.slug == body.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Slug already exists")

    location = Location(
        slug=body.slug,
        display_name=body.display_name,
        description=body.description,
        reminder_email=body.reminder_email,
        organization_id=membership.organization_id,
        created_by_id=admin.id,
    )
    location.approval_required = body.approval_required
    db.add(location)
    await db.flush()
    return location


@router.get("/{slug}", response_model=LocationResponse)
async def get_location(
    slug: str,
    db: AsyncSession = Depends(get_db),
    membership: Membership = Depends(get_current_membership),
):
    location = await scoping.get_location(db, membership.organization_id, slug)
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    return location


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

    return location
