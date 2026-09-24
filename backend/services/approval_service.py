from dataclasses import dataclass
from uuid import UUID
from fastapi import Request
from datetime import datetime, timezone


from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.location import Location
from backend.models.file_version import FileVersion
from backend.services.audit_service import audit_service


class VersionNotFound(ValueError):
    """No such version in the caller's organization."""


class ReviewNotAllowed(Exception):
    """The reviewer may not approve or reject this particular version."""


@dataclass(frozen=True)
class ReviewRights:
    can_approve: bool
    can_reject: bool


def review_rights(
    uploaded_by_id: UUID,
    reviewer_id: UUID,
    *,
    can_approve_own: bool,
    can_review_others: bool,
) -> ReviewRights:
    """What a reviewer may do to one version. The single source of these rules:
    enforcement and the dashboard's per-item flags both use it."""
    if uploaded_by_id == reviewer_id:
        # Rejecting your own pending version withdraws it, so it's always allowed.
        return ReviewRights(can_approve=can_approve_own, can_reject=True)
    return ReviewRights(can_approve=can_review_others, can_reject=can_review_others)


class ApprovalService:
    async def _get_version_for_review(
        self,
        db: AsyncSession,
        version_id: UUID,
        organization_id: UUID,
    ) -> tuple[FileVersion, Location]:
        version = await db.get(FileVersion, version_id)
        if version is None:
            raise VersionNotFound("Version not found")

        location_result = await db.execute(
            select(Location)
            .where(Location.id == version.location_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        location = location_result.scalar_one_or_none()
        if location is None:
            raise ValueError("Location not found")
        if location.organization_id != organization_id:
            raise VersionNotFound("Version not found")

        await db.refresh(version)
        return version, location

    async def _publish_version(
        self,
        db: AsyncSession,
        version: FileVersion,
        location: Location,
    ) -> None:
        """Publish a version while the caller holds the location row lock."""
        await db.execute(
            update(FileVersion)
            .where(
                FileVersion.location_id == location.id,
                FileVersion.status == "approved",
                FileVersion.deleted_at.is_(None),
            )
            .values(status="superseded")
        )

        version.status = "approved"
        location.current_approved_version_id = version.id
        location.updated_at = datetime.now(timezone.utc)

        await db.flush()
        db.info.setdefault("cache_invalidation_slugs", set()).add(location.slug)

    async def apply_submission_governance(
        self,
        db: AsyncSession,
        version: FileVersion,
        *,
        request: Request | None = None,
    ) -> None:
        """Apply the location policy to a newly created pending version."""
        result = await db.execute(
            select(Location)
            .where(
                Location.id == version.location_id,
                Location.deleted_at.is_(None),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        location = result.scalar_one_or_none()
        if location is None:
            raise ValueError("Location not found")

        if location.approval_required:
            return

        await self._publish_version(db, version, location)

        await audit_service.log(
            db=db,
            action="auto_publish",
            entity_type="file_version",
            entity_id=version.id,
            actor=version.uploaded_by,
            actor_id=version.uploaded_by_id,
            organization_id=location.organization_id,
            request=request,
            details={
                "location_slug": location.slug,
                "approval_required": False,
            },
        )

    async def approve_version(
        self,
        db: AsyncSession,
        version_id: UUID,
        reviewed_by: str,
        reviewed_by_id: UUID,
        organization_id: UUID,
        *,
        can_approve_own: bool,
        can_review_others: bool,
        notes: str | None = None,
    ) -> tuple[FileVersion, Location]:
        version, location = await self._get_version_for_review(
            db, version_id, organization_id
        )

        if version.status != "pending":
            raise ValueError(f"Cannot approve version with status '{version.status}'")
        if version.deleted_at is not None:
            raise ValueError("Cannot approve a deleted version")
        rights = review_rights(
            version.uploaded_by_id,
            reviewed_by_id,
            can_approve_own=can_approve_own,
            can_review_others=can_review_others,
        )
        if not rights.can_approve:
            raise ReviewNotAllowed(
                "Someone other than the uploader must approve this version"
                if version.uploaded_by_id == reviewed_by_id
                else "Your role doesn't allow approving other people's versions"
            )

        version.reviewed_by = reviewed_by
        version.reviewed_by_id = reviewed_by_id
        version.reviewed_at = datetime.now(timezone.utc)
        version.review_notes = notes

        await self._publish_version(db, version, location)
        return version, location

    async def reject_version(
        self,
        db: AsyncSession,
        version_id: UUID,
        reviewed_by: str,
        reviewed_by_id: UUID,
        organization_id: UUID,
        *,
        can_review_others: bool,
        notes: str | None = None,
    ) -> tuple[FileVersion, Location]:
        version, location = await self._get_version_for_review(
            db, version_id, organization_id
        )

        if version.status != "pending":
            raise ValueError(f"Cannot reject version with status '{version.status}'")
        if version.deleted_at is not None:
            raise ValueError("Cannot reject a deleted version")
        rights = review_rights(
            version.uploaded_by_id,
            reviewed_by_id,
            # Irrelevant to rejection; own versions can always be withdrawn.
            can_approve_own=False,
            can_review_others=can_review_others,
        )
        if not rights.can_reject:
            raise ReviewNotAllowed(
                "Your role doesn't allow rejecting other people's versions"
            )

        version.status = "rejected"
        version.reviewed_by = reviewed_by
        version.reviewed_by_id = reviewed_by_id
        version.reviewed_at = datetime.now(timezone.utc)
        version.review_notes = notes

        await db.flush()
        return version, location

    async def get_pending_versions(
        self,
        db: AsyncSession,
        organization_id: UUID,
        *,
        uploaded_by_id: UUID | None = None,
        exclude_uploaded_by_id: UUID | None = None,
    ) -> list[tuple[FileVersion, Location]]:
        """Pending versions in the organization, each with its location."""
        query = (
            select(FileVersion, Location)
            .join(Location, Location.id == FileVersion.location_id)
            .where(
                FileVersion.status == "pending",
                FileVersion.deleted_at.is_(None),
                Location.organization_id == organization_id,
            )
            .order_by(FileVersion.uploaded_at.desc())
        )
        if uploaded_by_id is not None:
            query = query.where(FileVersion.uploaded_by_id == uploaded_by_id)
        if exclude_uploaded_by_id is not None:
            query = query.where(FileVersion.uploaded_by_id != exclude_uploaded_by_id)

        result = await db.execute(query)
        return [(version, location) for version, location in result.all()]

    async def get_next_version_number(
        self,
        db: AsyncSession,
        location_id: UUID,
    ) -> int:
        location_result = await db.execute(
            select(Location.id).where(Location.id == location_id).with_for_update()
        )
        location_result.scalar_one()

        result = await db.execute(
            select(func.coalesce(func.max(FileVersion.version_number), 0) + 1).where(
                FileVersion.location_id == location_id
            )
        )
        return result.scalar_one()

    async def create_pending_version(
        self,
        db: AsyncSession,
        location_id: UUID,
        original_filename: str,
        content_type: str,
        file_size_bytes: int,
        s3_key: str,
        uploaded_by: str,
        uploaded_by_id: UUID,
    ) -> FileVersion:
        version_number = await self.get_next_version_number(db, location_id)
        version = FileVersion(
            location_id=location_id,
            original_filename=original_filename,
            content_type=content_type,
            file_size_bytes=file_size_bytes,
            s3_key=s3_key,
            uploaded_by=uploaded_by,
            uploaded_by_id=uploaded_by_id,
            version_number=version_number,
            status="pending",
        )
        db.add(version)
        await db.flush()
        return version

    async def create_pending_link_version(
        self,
        db: AsyncSession,
        location_id: UUID,
        link_url: str,
        uploaded_by: str,
        uploaded_by_id: UUID,
    ) -> FileVersion:
        version_number = await self.get_next_version_number(db, location_id)

        version = FileVersion(
            location_id=location_id,
            kind="link",
            link_url=link_url,
            link_mode="redirect",
            uploaded_by=uploaded_by,
            uploaded_by_id=uploaded_by_id,
            version_number=version_number,
            status="pending",
        )

        db.add(version)
        await db.flush()
        return version

    async def get_versions_for_location(
        self,
        db: AsyncSession,
        location_id: UUID,
        status: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[FileVersion], int]:
        """
        Returns (versions, total_count) for pagination.

        The query is built in two parts:
        1. A count query to get the total matching rows
        2. A data query to get just the current page

        Both share the same WHERE clause so the count matches the data.
        """

        # Base conditions shared by both queries
        base_conditions = [
            FileVersion.location_id == location_id,
            FileVersion.deleted_at.is_(None),
        ]

        if status:
            base_conditions.append(FileVersion.status == status)

        # Count query
        count_query = select(func.count(FileVersion.id)).where(*base_conditions)
        total = (await db.execute(count_query)).scalar_one()

        # Data query
        data_query = (
            select(FileVersion)
            .where(*base_conditions)
            .order_by(FileVersion.uploaded_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        versions = list((await db.execute(data_query)).scalars().all())

        return versions, total

    async def soft_delete_version(
        self,
        db: AsyncSession,
        version_id: UUID,
    ) -> FileVersion:
        version = await db.get(FileVersion, version_id)
        if not version:
            raise ValueError("Version not found")
        if version.status == "approved":
            raise ValueError("Cannot delete an approved version")

        version.deleted_at = datetime.now(timezone.utc)
        await db.flush()
        return version


approval_service = ApprovalService()
