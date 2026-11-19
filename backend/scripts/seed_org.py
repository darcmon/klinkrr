"""Give an existing account a membership in an organization, for local testing
of organization switching and revocation.

    python -m backend.scripts.seed_org you@example.com second-org
    python -m backend.scripts.seed_org you@example.com second-org --role uploader
    python -m backend.scripts.seed_org you@example.com second-org --remove

Creates the organization if its slug is new, and sets the role if the
membership already exists, so it is safe to re-run. `--remove` deletes the
membership, as a revocation would, while the browser stays signed in.

The account must exist already (sign in once first). Refuses to run in
production.

ponytail: dev-only stand-in for organization creation and invitations; the
real flows replace it.
"""

import argparse
import asyncio

from sqlalchemy import func, select

from backend.config import get_settings
from backend.db.session import async_session_factory, engine
from backend.models import AdminUser, Membership, Organization
from backend.models.organization import ROLES
from backend.services.slugs import RESERVED_SLUGS, is_valid_slug


async def seed(email: str, slug: str, name: str, role: str, remove: bool) -> str:
    async with async_session_factory() as db:
        user = (
            await db.execute(
                select(AdminUser).where(func.lower(AdminUser.email) == email.lower())
            )
        ).scalar_one_or_none()
        if user is None:
            raise SystemExit(f"No account for {email}. Sign in once first.")

        organization = (
            await db.execute(select(Organization).where(Organization.slug == slug))
        ).scalar_one_or_none()

        if remove:
            if organization is None:
                raise SystemExit(f"No organization /{slug}.")
            membership = await db.get(Membership, (organization.id, user.id))
            if membership is None:
                return f"{email} is not a member of /{slug}; nothing to remove."
            await db.delete(membership)
            await db.commit()
            return f"Removed {email} from /{slug}."

        if organization is None:
            organization = Organization(name=name, slug=slug)
            db.add(organization)
            await db.flush()

        membership = await db.get(Membership, (organization.id, user.id))
        if membership is None:
            db.add(Membership(organization_id=organization.id, user_id=user.id, role=role))
        else:
            membership.role = role
        await db.commit()
        return f"{email} is {role} of {organization.name} (/{slug})."


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("email")
    parser.add_argument("slug", help="organization's permanent address, e.g. second-org")
    parser.add_argument("--name", help="display name for a new organization")
    parser.add_argument("--role", choices=ROLES, default="owner")
    parser.add_argument("--remove", action="store_true", help="revoke the membership")
    args = parser.parse_args()

    if get_settings().is_production:
        parser.error("refusing to run in production")
    if not is_valid_slug(args.slug) or args.slug in RESERVED_SLUGS:
        parser.error("slug must be lowercase letters, numbers and hyphens, and not reserved")
    name = args.name or args.slug.replace("-", " ").title()

    try:
        print(await seed(args.email, args.slug, name, args.role, args.remove))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
