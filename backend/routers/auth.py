from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.dependencies import (
    create_user_token,
    get_current_admin,
    hash_password,
    load_membership,
    verify_password,
)
from backend.models.admin_user import AdminUser
from backend.permissions import permissions_for
from backend.schemas.auth import (
    AdminUserResponse,
    LoginRequest,
    OrganizationSummary,
    PasswordChange,
    ProfileUpdate,
    TokenResponse,
)
from backend.services.audit_service import audit_service

router = APIRouter(prefix="/admin", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AdminUser).where(
            AdminUser.email == body.email,
            AdminUser.is_active.is_(True),
        )
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    token = create_user_token(user)
    return TokenResponse(access_token=token)


async def _me_response(db: AsyncSession, admin: AdminUser) -> AdminUserResponse:
    membership = await load_membership(db, admin.id)
    sign_in_methods = [
        method
        for method, linked in (
            ("password", admin.password_hash),
            ("microsoft", admin.microsoft_sub),
            ("google", admin.google_sub),
        )
        if linked
    ]
    return AdminUserResponse(
        id=admin.id,
        email=admin.email,
        display_name=admin.display_name,
        avatar_url=admin.avatar_url,
        organization=(
            OrganizationSummary.model_validate(membership.organization)
            if membership
            else None
        ),
        role=membership.role if membership else None,
        permissions=permissions_for(membership.role) if membership else [],
        sign_in_methods=sign_in_methods,
    )


@router.get("/me", response_model=AdminUserResponse)
async def get_me(
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await _me_response(db, admin)


@router.patch("/me", response_model=AdminUserResponse)
async def update_me(
    body: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    display_name = body.display_name.strip()
    if not display_name:
        raise HTTPException(status_code=422, detail="Display name can't be blank")

    admin.display_name = display_name
    await db.flush()
    return await _me_response(db, admin)


@router.post("/me/password", status_code=204)
async def change_password(
    body: PasswordChange,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    # 400 rather than 401 for a wrong current password: the client treats
    # 401 as "signed out".
    if not admin.password_hash:
        raise HTTPException(
            status_code=400,
            detail="Your account signs in with Microsoft or Google and has no password",
        )
    if not verify_password(body.current_password, admin.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    admin.password_hash = hash_password(body.new_password)
    await db.flush()

    await audit_service.log(
        db,
        action="password_changed",
        entity_type="admin_user",
        entity_id=admin.id,
        actor=admin.email,
        actor_id=admin.id,
        request=request,
    )
    return Response(status_code=204)
