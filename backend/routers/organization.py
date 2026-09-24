from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.dependencies import get_current_admin, require_permission
from backend.models.admin_user import AdminUser
from backend.models.organization import Membership, Organization
from backend.schemas.auth import OrganizationSummary
from backend.schemas.organization import (
    MemberCreate,
    MemberListResponse,
    MemberResponse,
    MemberUpdate,
    OrganizationUpdate,
)
from backend.services.audit_service import audit_service

router = APIRouter(prefix="/admin", tags=["organization"])

LAST_OWNER = "The organization needs at least one owner"


async def _lock_organization(db: AsyncSession, organization_id: UUID) -> Organization:
    """Serializes membership changes within an organization, so concurrent
    demotions can't leave it without an owner."""
    result = await db.execute(
        select(Organization)
        .where(Organization.id == organization_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()


async def _owner_count(db: AsyncSession, organization_id: UUID) -> int:
    result = await db.execute(
        select(func.count()).where(
            Membership.organization_id == organization_id,
            Membership.role == "owner",
        )
    )
    return result.scalar_one()


async def _get_member(
    db: AsyncSession, organization_id: UUID, user_id: UUID
) -> tuple[Membership, AdminUser]:
    result = await db.execute(
        select(Membership, AdminUser)
        .join(AdminUser, AdminUser.id == Membership.user_id)
        .where(
            Membership.organization_id == organization_id,
            Membership.user_id == user_id,
        )
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Member not found")
    return row[0], row[1]


def _member_response(
    membership: Membership, user: AdminUser, admin: AdminUser
) -> MemberResponse:
    return MemberResponse(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=membership.role,
        last_login_at=user.last_login_at,
        is_you=user.id == admin.id,
    )


async def _audit(db, request, admin, organization_id, action, entity_id, details):
    await audit_service.log(
        db,
        action=action,
        entity_type="membership",
        entity_id=entity_id,
        actor=admin.email,
        actor_id=admin.id,
        organization_id=organization_id,
        request=request,
        details=details,
    )


@router.patch("/organization", response_model=OrganizationSummary)
async def update_organization(
    body: OrganizationUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    membership: Membership = Depends(require_permission("manage_members")),
):
    organization = await _lock_organization(db, membership.organization_id)

    changes = {}
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is None:
            continue
        if field == "name":
            value = value.strip()
            if not value:
                raise HTTPException(
                    status_code=422, detail="Organization name can't be blank"
                )
        before = getattr(organization, field)
        if before != value:
            setattr(organization, field, value)
            changes[field] = {"before": before, "after": value}

    if changes:
        await db.flush()
        await audit_service.log(
            db,
            action="organization_updated",
            entity_type="organization",
            entity_id=organization.id,
            actor=admin.email,
            actor_id=admin.id,
            organization_id=organization.id,
            request=request,
            details=changes,
        )

    return OrganizationSummary.model_validate(organization)


@router.get("/members", response_model=MemberListResponse)
async def list_members(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    membership: Membership = Depends(require_permission("manage_members")),
):
    result = await db.execute(
        select(Membership, AdminUser)
        .join(AdminUser, AdminUser.id == Membership.user_id)
        .where(Membership.organization_id == membership.organization_id)
        .order_by(func.lower(AdminUser.display_name), AdminUser.email)
    )
    return MemberListResponse(
        members=[_member_response(m, user, admin) for m, user in result.all()]
    )


@router.post("/members", response_model=MemberResponse, status_code=201)
async def add_member(
    body: MemberCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    membership: Membership = Depends(require_permission("manage_members")),
):
    """Add someone by email. If they have no account yet, one is created
    without a password; it links on their first Microsoft or Google sign-in
    with that email."""
    organization_id = membership.organization_id
    await _lock_organization(db, organization_id)

    email = body.email  # already trimmed and lowercased by the schema

    user = (
        await db.execute(select(AdminUser).where(func.lower(AdminUser.email) == email))
    ).scalar_one_or_none()
    new_account = user is None

    if user is None:
        display_name = (body.display_name or "").strip() or email.split("@")[0]
        user = AdminUser(email=email, display_name=display_name, is_active=True)
        db.add(user)
        await db.flush()
    else:
        if not user.is_active:
            raise HTTPException(status_code=409, detail="This account is deactivated")

        existing = (
            await db.execute(select(Membership).where(Membership.user_id == user.id))
        ).scalars().all()
        if any(m.organization_id == organization_id for m in existing):
            raise HTTPException(status_code=409, detail="Already a member")
        if existing:
            raise HTTPException(
                status_code=409,
                detail=(
                    "This person already belongs to another organization. "
                    "Belonging to more than one isn't supported yet."
                ),
            )

    added = Membership(organization_id=organization_id, user_id=user.id, role=body.role)
    db.add(added)
    await db.flush()

    await _audit(
        db, request, admin, organization_id, "member_added", user.id,
        {"email": email, "role": body.role, "new_account": new_account},
    )
    return _member_response(added, user, admin)


@router.patch("/members/{user_id}", response_model=MemberResponse)
async def change_member_role(
    user_id: UUID,
    body: MemberUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    membership: Membership = Depends(require_permission("manage_members")),
):
    organization_id = membership.organization_id
    await _lock_organization(db, organization_id)
    target, user = await _get_member(db, organization_id, user_id)

    before = target.role
    if before != body.role:
        if before == "owner" and await _owner_count(db, organization_id) == 1:
            raise HTTPException(status_code=409, detail=LAST_OWNER)

        target.role = body.role
        await db.flush()
        await _audit(
            db, request, admin, organization_id, "member_role_changed", user.id,
            {"email": user.email, "role": {"before": before, "after": body.role}},
        )

    return _member_response(target, user, admin)


@router.delete("/members/{user_id}", status_code=204)
async def remove_member(
    user_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    membership: Membership = Depends(require_permission("manage_members")),
):
    """Removes the membership, not the account."""
    organization_id = membership.organization_id
    await _lock_organization(db, organization_id)
    target, user = await _get_member(db, organization_id, user_id)

    if target.role == "owner" and await _owner_count(db, organization_id) == 1:
        raise HTTPException(status_code=409, detail=LAST_OWNER)

    await db.delete(target)
    await db.flush()
    await _audit(
        db, request, admin, organization_id, "member_removed", user.id,
        {"email": user.email, "role": target.role},
    )
    return Response(status_code=204)
