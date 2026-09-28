import logging
from contextlib import asynccontextmanager
from starlette.middleware.sessions import SessionMiddleware

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db.session import engine, async_session_factory
from backend.dependencies import hash_password
from backend.routers.auth import router as auth_router
from backend.routers.oauth import router as oauth_router
from backend.routers.approval import router as approval_router
from backend.routers.locations import router as locations_router
from backend.routers.organization import router as organization_router
from backend.routers.archive import router as archive_router
from backend.routers.public import router as public_router
from backend.routers.upload import router as upload_router
from backend.config import get_settings
from backend.middleware.security import SecurityHeaderMiddleware
from backend.models import AdminUser, Membership, Organization

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs once at startup and once at shutdown.

    The code BEFORE `yield` runs at startup.
    The code AFTER `yield` runs at shutdown.
    """
    settings = get_settings()

    # Seed an admin user if none exists
    async with async_session_factory() as db:
        from sqlalchemy import select

        result = await db.execute(select(AdminUser).limit(1))
        has_users = result.scalar_one_or_none() is not None
        can_seed = bool(settings.admin_email and settings.admin_password)

        if has_users and settings.is_production and settings.admin_password:
            logger.warning(
                "ADMIN_PASSWORD is still set. It's only used to create the first "
                "admin; remove it from the environment."
            )
        elif not has_users and not can_seed:
            logger.warning(
                "No users exist. Set ADMIN_EMAIL and ADMIN_PASSWORD for the first "
                "boot to create an owner."
            )

        if not has_users and can_seed:
            admin = AdminUser(
                email=settings.admin_email.strip().lower(),
                password_hash=hash_password(settings.admin_password),
                display_name="Admin",
            )
            db.add(admin)

            # Migration 0003 creates the default organization; a fresh
            # database seeded without it still needs one.
            organization = (
                await db.execute(select(Organization).limit(1))
            ).scalar_one_or_none()
            if organization is None:
                organization = Organization(name="Default organization")
                db.add(organization)

            await db.flush()
            db.add(
                Membership(
                    organization_id=organization.id,
                    user_id=admin.id,
                    role="owner",
                )
            )
            await db.commit()
            logger.info(f"Seeded admin user: {admin.email}")
    yield

    await engine.dispose()
    logger.info("Shut down")


def create_app() -> FastAPI:
    settings = get_settings()

    if settings.is_production:
        problems = settings.production_problems()
        if problems:
            raise RuntimeError(
                "Refusing to start with unsafe production settings:\n- "
                + "\n- ".join(problems)
            )
    app = FastAPI(title="klinkrr", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    # Only used for the OAuth state during sign-in.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        https_only=settings.is_production,
        same_site="lax",
    )
    app.add_middleware(SecurityHeaderMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router)
    app.include_router(oauth_router)
    app.include_router(upload_router)
    app.include_router(locations_router)
    app.include_router(organization_router)
    app.include_router(approval_router)
    app.include_router(archive_router)

    # Public routes (MUST be last — /{slug} catches everything)
    app.include_router(public_router)

    return app


app = create_app()
