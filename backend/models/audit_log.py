import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, Index, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP, JSONB, INET

from backend.db.session import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    action: Mapped[str] = mapped_column(String(50), nullable=False)

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)

    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # `actor` is the email at the time of the event and is never rewritten.
    actor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True
    )

    # NULL for events outside any organization, such as failed logins.
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True
    )

    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)

    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("idx_audit_logs_entity", "entity_type", "entity_id"),
        Index(
            "idx_audit_logs_created",
            "created_at",
        ),
        Index("idx_audit_logs_organization", "organization_id", "created_at"),
    )
