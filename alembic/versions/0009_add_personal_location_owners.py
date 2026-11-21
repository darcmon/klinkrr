"""Add personal owners to locations.

Revision ID: 0009
Revises: 0008
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "locations",
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_locations_owner_user_id",
        "locations",
        "admin_users",
        ["owner_user_id"],
        ["id"],
    )
    op.alter_column("locations", "organization_id", nullable=True)
    op.create_check_constraint(
        "ck_locations_exactly_one_owner",
        "locations",
        "(organization_id IS NULL) <> (owner_user_id IS NULL)",
    )
    op.create_unique_constraint(
        "uq_locations_owner_user_slug",
        "locations",
        ["owner_user_id", "slug"],
    )


def downgrade() -> None:
    personal_location = op.get_bind().execute(
        sa.text("SELECT 1 FROM locations WHERE owner_user_id IS NOT NULL LIMIT 1")
    ).first()
    if personal_location is not None:
        raise RuntimeError(
            "Cannot remove personal ownership while personal locations exist. "
            "Move or delete them before downgrading; no data was changed."
        )

    op.drop_constraint("uq_locations_owner_user_slug", "locations", type_="unique")
    op.drop_constraint("ck_locations_exactly_one_owner", "locations", type_="check")
    op.alter_column("locations", "organization_id", nullable=False)
    op.drop_constraint("fk_locations_owner_user_id", "locations", type_="foreignkey")
    op.drop_column("locations", "owner_user_id")
