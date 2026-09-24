from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.audit_log import AuditLog
from backend.models.file_version import FileVersion
from backend.models.location import Location
from backend.services.approval_service import ApprovalService


@pytest.mark.asyncio
@pytest.mark.parametrize("approval_required", [True, False])
@pytest.mark.parametrize("kind", ["file", "link"])
async def test_submission_governance(approval_required, kind):
    previous_version_id = uuid4()

    location = Location(
        id=uuid4(),
        slug="documents",
        display_name="Documents",
        approval_required=approval_required,
        current_approved_version_id=previous_version_id,
    )

    version = FileVersion(
        id=uuid4(),
        location_id=location.id,
        kind=kind,
        status="pending",
        version_number=2,
        uploaded_by="admin@example.com",
    )

    db = MagicMock(spec=AsyncSession)
    db.info = {}

    location_result = MagicMock()
    location_result.scalar_one_or_none.return_value = location
    db.execute.return_value = location_result

    service = ApprovalService()
    await service.apply_submission_governance(db, version)

    if approval_required:
        assert version.status == "pending"
        assert location.current_approved_version_id == previous_version_id
        assert db.info == {}
        db.flush.assert_not_awaited()
        db.add.assert_not_called()
    else:
        assert version.status == "approved"
        assert location.current_approved_version_id == version.id
        assert location.updated_at is not None
        assert db.info["cache_invalidation_slugs"] == {"documents"}
        db.add.assert_called_once()
        call = db.add.call_args
        assert call is not None

        entry = call.args[0]
        assert isinstance(entry, AuditLog)
        assert entry.action == "auto_publish"
        assert entry.entity_type == "file_version"
        assert entry.entity_id == version.id
        assert entry.actor == version.uploaded_by
        assert entry.details == {
            "location_slug": location.slug,
            "approval_required": False,
        }

        db.flush.assert_awaited()

    assert version.reviewed_by is None
    assert version.reviewed_at is None
    assert version.review_notes is None
    db.commit.assert_not_awaited()
