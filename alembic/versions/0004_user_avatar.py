"""Store the latest SSO profile picture."""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("admin_users", sa.Column("avatar_url", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("admin_users", "avatar_url")
