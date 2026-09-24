"""Add organizations and memberships, link records to user ids, and replace
approval_required with required_approvals.

Existing data moves into a single default organization and every existing
user becomes its owner. Email columns stay as display snapshots.
"""

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

DEFAULT_ORGANIZATION_NAME = "Default organization"


def _fail_on_unmatched_emails(column: str) -> None:
    bind = op.get_bind()
    unmatched = bind.execute(
        sa.text(
            f"SELECT DISTINCT {column} FROM file_versions "
            f"WHERE {column} IS NOT NULL AND {column}_id IS NULL"
        )
    ).scalars().all()
    if unmatched:
        raise RuntimeError(
            f"file_versions.{column} has emails with no matching admin user: "
            f"{', '.join(sorted(unmatched))}. Create or correct those users, "
            "then run the migration again."
        )


def upgrade() -> None:
    bind = op.get_bind()

    # Organizations and memberships
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "allow_self_approval",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "memberships",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('uploader', 'approver', 'manager', 'owner')",
            name="ck_memberships_role",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["admin_users.id"]),
        sa.PrimaryKeyConstraint("organization_id", "user_id"),
    )
    op.create_index("idx_memberships_user", "memberships", ["user_id"])

    organization_id = uuid.uuid4()
    bind.execute(
        sa.text("INSERT INTO organizations (id, name) VALUES (:id, :name)"),
        {"id": organization_id, "name": DEFAULT_ORGANIZATION_NAME},
    )
    bind.execute(
        sa.text(
            "INSERT INTO memberships (organization_id, user_id, role) "
            "SELECT :org, id, 'owner' FROM admin_users"
        ),
        {"org": organization_id},
    )

    # Locations: organization, creator, approval policy
    op.add_column(
        "locations",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    bind.execute(
        sa.text("UPDATE locations SET organization_id = :org"),
        {"org": organization_id},
    )
    op.alter_column("locations", "organization_id", nullable=False)
    op.create_foreign_key(
        "fk_locations_organization",
        "locations",
        "organizations",
        ["organization_id"],
        ["id"],
    )
    op.create_index("idx_locations_organization", "locations", ["organization_id"])

    op.add_column(
        "locations",
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_locations_created_by",
        "locations",
        "admin_users",
        ["created_by_id"],
        ["id"],
    )

    op.add_column(
        "locations",
        sa.Column(
            "required_approvals",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
    )
    op.execute(
        "UPDATE locations "
        "SET required_approvals = CASE WHEN approval_required THEN 1 ELSE 0 END"
    )
    op.create_check_constraint(
        "ck_locations_required_approvals", "locations", "required_approvals >= 0"
    )
    op.drop_column("locations", "approval_required")

    # File versions: who uploaded and who reviewed, by id
    op.add_column(
        "file_versions",
        sa.Column("uploaded_by_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "file_versions",
        sa.Column("reviewed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        "UPDATE file_versions fv SET uploaded_by_id = u.id "
        "FROM admin_users u WHERE lower(u.email) = lower(fv.uploaded_by)"
    )
    op.execute(
        "UPDATE file_versions fv SET reviewed_by_id = u.id "
        "FROM admin_users u WHERE lower(u.email) = lower(fv.reviewed_by)"
    )
    _fail_on_unmatched_emails("uploaded_by")
    _fail_on_unmatched_emails("reviewed_by")

    op.alter_column("file_versions", "uploaded_by_id", nullable=False)
    op.create_foreign_key(
        "fk_file_versions_uploaded_by",
        "file_versions",
        "admin_users",
        ["uploaded_by_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_file_versions_reviewed_by",
        "file_versions",
        "admin_users",
        ["reviewed_by_id"],
        ["id"],
    )
    op.create_index(
        "idx_file_versions_uploaded_by", "file_versions", ["uploaded_by_id"]
    )

    # Audit logs: actor id and organization. Unmatched actors (for example,
    # failed logins with unknown emails) keep a NULL actor_id.
    op.add_column(
        "audit_logs",
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "audit_logs",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        "UPDATE audit_logs a SET actor_id = u.id "
        "FROM admin_users u WHERE lower(u.email) = lower(a.actor)"
    )
    bind.execute(
        sa.text(
            "UPDATE audit_logs SET organization_id = :org "
            "WHERE entity_type IN ('location', 'file_version')"
        ),
        {"org": organization_id},
    )
    op.create_foreign_key(
        "fk_audit_logs_actor", "audit_logs", "admin_users", ["actor_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_audit_logs_organization",
        "audit_logs",
        "organizations",
        ["organization_id"],
        ["id"],
    )
    op.create_index(
        "idx_audit_logs_organization",
        "audit_logs",
        ["organization_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_audit_logs_organization", table_name="audit_logs")
    op.drop_constraint("fk_audit_logs_organization", "audit_logs", type_="foreignkey")
    op.drop_constraint("fk_audit_logs_actor", "audit_logs", type_="foreignkey")
    op.drop_column("audit_logs", "organization_id")
    op.drop_column("audit_logs", "actor_id")

    op.drop_index("idx_file_versions_uploaded_by", table_name="file_versions")
    op.drop_constraint(
        "fk_file_versions_reviewed_by", "file_versions", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_file_versions_uploaded_by", "file_versions", type_="foreignkey"
    )
    op.drop_column("file_versions", "reviewed_by_id")
    op.drop_column("file_versions", "uploaded_by_id")

    op.add_column(
        "locations",
        sa.Column(
            "approval_required",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
    )
    op.execute("UPDATE locations SET approval_required = (required_approvals > 0)")
    op.drop_constraint(
        "ck_locations_required_approvals", "locations", type_="check"
    )
    op.drop_column("locations", "required_approvals")

    op.drop_constraint("fk_locations_created_by", "locations", type_="foreignkey")
    op.drop_column("locations", "created_by_id")
    op.drop_index("idx_locations_organization", table_name="locations")
    op.drop_constraint("fk_locations_organization", "locations", type_="foreignkey")
    op.drop_column("locations", "organization_id")

    op.drop_index("idx_memberships_user", table_name="memberships")
    op.drop_table("memberships")
    op.drop_table("organizations")
