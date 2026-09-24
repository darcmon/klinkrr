import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, ForeignKey, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP

from backend.db.session import Base

# Ordered lowest to highest; each role includes the permissions of those below it.
ROLES = ("uploader", "approver", "manager", "owner")


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # When true, a person may approve a version they uploaded. The approval is
    # still recorded as self-approved in the audit log.
    allow_self_approval: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Membership(Base):
    """A user's role within one organization. Roles live here, not on the user,
    so the same person can hold different roles in different organizations."""

    __tablename__ = "memberships"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id"), primary_key=True
    )

    role: Mapped[str] = mapped_column(String(20), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    organization = relationship("Organization", lazy="joined")

    __table_args__ = (
        CheckConstraint(
            "role IN ('uploader', 'approver', 'manager', 'owner')",
            name="ck_memberships_role",
        ),
        Index("idx_memberships_user", "user_id"),
    )
