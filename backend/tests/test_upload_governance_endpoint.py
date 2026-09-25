from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, ANY
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.dependencies import get_current_admin, get_current_membership
from backend.routers import upload


@pytest.mark.asyncio
@pytest.mark.parametrize("final_status", ["pending", "approved"])
async def test_upload_returns_submission_outcome(monkeypatch, final_status):
    db = MagicMock(spec=AsyncSession)
    location = SimpleNamespace(id=uuid4(), slug="documents", organization_id=uuid4())
    admin = SimpleNamespace(id=uuid4(), email="admin@example.com")

    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = location
    db.execute.return_value = query_result

    settings = SimpleNamespace(
        allowed_file_types_list=["application/pdf"],
        max_upload_size_bytes=1024,
        max_upload_size_mb=1,
    )
    monkeypatch.setattr(upload, "get_settings", lambda: settings)

    content = b"%PDF-1.7\nTest upload"
    s3_key = "uploads/documents/test.pdf"

    monkeypatch.setattr(
        upload.file_service,
        "generate_s3_key",
        MagicMock(return_value=s3_key),
    )
    store_file = AsyncMock()
    monkeypatch.setattr(upload.file_service, "upload_file", store_file)

    version = SimpleNamespace(
        id=uuid4(),
        original_filename="test.pdf",
        version_number=2,
        status="pending",
        uploaded_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
    )
    create_version = AsyncMock(return_value=version)
    monkeypatch.setattr(
        upload.approval_service,
        "create_pending_version",
        create_version,
    )

    async def apply_policy(db, version, *, request=None):
        version.status = final_status

    apply_governance = AsyncMock(side_effect=apply_policy)
    monkeypatch.setattr(
        upload.approval_service,
        "apply_submission_governance",
        apply_governance,
    )

    audit_log = AsyncMock()
    monkeypatch.setattr(upload.audit_service, "log", audit_log)

    app = FastAPI()
    app.include_router(upload.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_admin] = lambda: admin
    app.dependency_overrides[get_current_membership] = lambda: SimpleNamespace(
        role="owner",
        organization_id=uuid4(),
        organization=SimpleNamespace(allow_self_approval=True),
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/admin/locations/documents/upload",
            files={"file": ("test.pdf", content, "application/pdf")},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == str(version.id)
    assert body["original_filename"] == "test.pdf"
    assert body["location_slug"] == "documents"
    assert body["version_number"] == 2
    assert body["status"] == final_status

    store_file.assert_awaited_once_with(s3_key, content, "application/pdf")
    create_version.assert_awaited_once_with(
        db=db,
        location_id=location.id,
        original_filename="test.pdf",
        content_type="application/pdf",
        file_size_bytes=len(content),
        s3_key=s3_key,
        uploaded_by=admin.email,
        uploaded_by_id=admin.id,
        version_id=None,
    )
    apply_governance.assert_awaited_once_with(
        db,
        version,
        request=ANY,
    )

    expected_actions = ["upload"]

    calls = audit_log.await_args_list
    assert [call.kwargs["action"] for call in calls] == expected_actions

    for call in calls:
        assert call.kwargs["entity_id"] == version.id
        assert call.kwargs["actor"] == admin.email
