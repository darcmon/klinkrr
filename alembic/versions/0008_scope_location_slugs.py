"""Make location slugs unique within each organization.

Revision ID: 0008
Revises: 0007
"""

from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_locations_organization_slug", "locations", ["organization_id", "slug"]
    )
    op.drop_constraint("locations_slug_key", "locations", type_="unique")


def downgrade() -> None:
    # Block writes until the global constraint has been restored.
    op.execute("LOCK TABLE locations IN ACCESS EXCLUSIVE MODE")
    duplicate = op.get_bind().execute(sa.text(
        "SELECT slug FROM locations GROUP BY slug HAVING COUNT(*) > 1 LIMIT 1"
    )).first()
    if duplicate is not None:
        raise RuntimeError(
            "Cannot restore global slug uniqueness: organizations share location "
            "slugs. Resolve duplicate slugs before downgrading; no data was deleted."
        )
    op.create_unique_constraint("locations_slug_key", "locations", ["slug"])
    op.drop_constraint("uq_locations_organization_slug", "locations", type_="unique")
