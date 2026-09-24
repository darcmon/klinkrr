from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.dependencies import (
    create_access_token,
    get_current_admin,
    load_membership,
    verify_password,
)
from backend.models.admin_user import AdminUser
from backend.permissions import permissions_for
from backend.schemas.auth import (
    AdminUserResponse,
    LoginRequest,
    OrganizationSummary,
    TokenResponse,
)

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

    token = create_access_token({"sub": user.email})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=AdminUserResponse)
async def get_me(
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    membership = await load_membership(db, admin.id)
    return AdminUserResponse(
        id=admin.id,
        email=admin.email,
        display_name=admin.display_name,
        organization=(
            OrganizationSummary.model_validate(membership.organization)
            if membership
            else None
        ),
        role=membership.role if membership else None,
        permissions=permissions_for(membership.role) if membership else [],
    )
