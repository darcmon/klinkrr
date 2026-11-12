import uuid
from datetime import datetime, timedelta, timezone
from collections.abc import AsyncIterator
from typing import Annotated

import httpx

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.db.session import get_db
from backend.errors import api_error
from backend.models.admin_user import AdminUser
from backend.models.organization import Membership
from backend.permissions import Permission, has_permission
from backend.services.web_risk_client import WebRiskClient

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


ALGORITHM = "HS256"

security = HTTPBearer()


"""
    FastAPI dependency that:
    1. Extracts the JWT from the Authorization header
    2. Verifies the signature and expiration
    3. Looks up the user in the database
    4. Returns the user object (or raises 401)

    Use it in routes like:
        async def my_route(admin: AdminUser = Depends(get_current_admin)):
            # `admin` is the logged-in user
"""


def create_access_token(data: dict) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def create_user_token(user: AdminUser) -> str:
    # The subject is the user id, not the email, so an email change doesn't
    # invalidate sessions or break the link to the account.
    return create_access_token({"sub": str(user.id)})


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    token = credentials.credentials
    settings = get_settings()

    # Step 1: Decode and verify the JWT
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        user_id = uuid.UUID(payload.get("sub") or "")
    except ValueError:
        # Includes tokens issued before the subject became the user id.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    # Step 2: Look up the user in the db
    result = await db.execute(
        select(AdminUser).where(
            AdminUser.id == user_id,
            AdminUser.is_active.is_(True),
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


async def load_memberships(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[Membership]:
    result = await db.execute(
        select(Membership)
        .where(Membership.user_id == user_id)
        .order_by(Membership.organization_id)
    )
    return list(result.scalars().all())


def select_membership(
    memberships: list[Membership],
    organization_id: uuid.UUID | None,
) -> Membership | None:
    if organization_id is not None:
        for membership in memberships:
            if membership.organization_id == organization_id:
                return membership

        raise api_error(
            403,
            "organization_access_denied",
            "You don't have access to this organization.",
        )

    if len(memberships) == 1:
        return memberships[0]

    return None


async def get_current_membership(
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    organization_id: Annotated[
        uuid.UUID | None, Header(alias="X-Organization-ID")
    ] = None,
) -> Membership:
    """The signed-in user's membership, with its organization loaded.

    Looked up on every request rather than stored in the JWT, so role changes
    apply immediately.
    """
    memberships = await load_memberships(db, admin.id)
    membership = select_membership(memberships, organization_id)
    if membership is not None:
        return membership
    if not memberships:
        raise api_error(
            403,
            "organization_membership_required",
            "You are not a member of any organization.",
        )
    raise api_error(
        409,
        "organization_selection_required",
        "Select an organization to continue.",
    )


def require_permission(permission: Permission):
    """Dependency that returns the caller's membership if their role has
    `permission`, and raises 403 otherwise."""

    async def check(
        membership: Membership = Depends(get_current_membership),
    ) -> Membership:
        if not has_permission(membership.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your role doesn't allow this",
            )
        return membership

    return check


async def get_web_risk_client() -> AsyncIterator[WebRiskClient]:
    settings = get_settings()
    api_key = settings.web_risk_api_key.strip()

    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="URL safety checking is unavailable",
        )

    async with httpx.AsyncClient() as http_client:
        yield WebRiskClient(http_client, api_key=api_key)
