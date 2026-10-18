"""Preserve existing short location URLs."""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "locations",
        sa.Column("legacy_slug", sa.String(100), nullable=True),
    )
    op.execute("UPDATE locations SET legacy_slug = slug")
    op.create_unique_constraint(
        "uq_locations_legacy_slug",
        "locations",
        ["legacy_slug"],
    )


def downgrade():
    op.drop_constraint(
        "uq_locations_legacy_slug",
        "locations",
        type_="unique",
    )
    op.drop_column("locations", "legacy_slug")
