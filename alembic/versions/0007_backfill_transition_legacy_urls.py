"""Preserve short URLs created during the namespace transition."""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    # Include deleted locations: their published addresses remain reserved.
    op.execute("UPDATE locations SET legacy_slug = slug WHERE legacy_slug IS NULL")


def downgrade():
    # Keep the preserved addresses; clearing them would lose compatibility data.
    pass
