import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Integer, String, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP

from backend.db.session import Base


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )

    # NULL for locations created before creators were recorded.
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True
    )

    # 0 publishes submissions immediately; 1 needs one approval. Values above 1
    # are reserved for multi-approver review, which isn't implemented yet.
    required_approvals: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )

    # Points to the currently approved file version.
    # This is NULL when no file has been approved yet.
    # use_alter=True is needed because FileVersion also references Location (circular FK).
    current_approved_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "file_versions.id",
            use_alter=True,
            name="fk_locations_current_approved_version",
        ),
        nullable=True,
    )

    reminder_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now
    )

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now, onupdate=datetime.now
    )

    # Soft delete
    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # Relationships
    versions = relationship(
        "FileVersion",
        back_populates="location",
        foreign_keys="FileVersion.location_id",
    )

    current_approved_version = relationship(
        "FileVersion",
        foreign_keys=[current_approved_version_id],
        uselist=False,
    )

    @property
    def approval_required(self) -> bool:
        # A new, unflushed Location has no value yet; the column default is 1.
        required = 1 if self.required_approvals is None else self.required_approvals
        return required > 0

    @approval_required.setter
    def approval_required(self, value: bool) -> None:
        # Turning approval on keeps any existing multi-approver requirement.
        if not value:
            self.required_approvals = 0
        elif not self.required_approvals:
            self.required_approvals = 1

    # Indexes
    __table_args__ = (
        Index("idx_locations_slug", "slug", postgresql_where=(deleted_at.is_(None))),
        Index("idx_locations_organization", "organization_id"),
        CheckConstraint(
            "required_approvals >= 0", name="ck_locations_required_approvals"
        ),
    )
