"""Add stable organization slugs."""

import re
import unicodedata

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


MAX_SLUG_LENGTH = 100

RESERVED_SLUGS = {
    "admin",
    "api",
    "docs",
    "health",
    "openapi",
    "redoc",
    "static",
}


def _slugify(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower())
    return slug.strip("-")[:MAX_SLUG_LENGTH].rstrip("-")


def _unique_slug(name: str, used: set[str]) -> str:
    base = _slugify(name) or "organization"

    if base in RESERVED_SLUGS:
        base = f"{base}-org"

    candidate = base
    number = 2

    while candidate in used:
        suffix = f"-{number}"
        shortened = base[: MAX_SLUG_LENGTH - len(suffix)].rstrip("-")
        candidate = f"{shortened}{suffix}"
        number += 1

    used.add(candidate)
    return candidate


def upgrade():
    op.add_column(
        "organizations",
        sa.Column("slug", sa.String(100), nullable=True),
    )

    connection = op.get_bind()
    organizations = connection.execute(
        sa.text("SELECT id, name FROM organizations ORDER BY id")
    ).mappings()

    used: set[str] = set()

    for organization in organizations:
        slug = _unique_slug(organization["name"], used)
        connection.execute(
            sa.text(
                "UPDATE organizations "
                "SET slug = :slug "
                "WHERE id = :organization_id"
            ),
            {
                "slug": slug,
                "organization_id": organization["id"],
            },
        )

    op.alter_column(
        "organizations",
        "slug",
        existing_type=sa.String(100),
        nullable=False,
    )
    op.create_unique_constraint(
        "uq_organizations_slug",
        "organizations",
        ["slug"],
    )


def downgrade():
    op.drop_constraint(
        "uq_organizations_slug",
        "organizations",
        type_="unique",
    )
    op.drop_column("organizations", "slug")
