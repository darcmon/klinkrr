from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_current_admin, get_db
from backend.services.audit_service import AuditService
from backend.routers import approval


@pytest.mark.asyncio
async def test_rejecting_reviewed_version_returns_readable_error(monkeypatch):
    db = MagicMock(spec=AsyncSession)
    admin = SimpleNamespace(email="admin@example.com")

    reject_version = AsyncMock(
        side_effect=ValueError("Cannot reject version with status 'approved'")
    )
    monkeypatch.setattr(
        approval.approval_service,
        "reject_version",
        reject_version,
    )

    audit_log = AsyncMock()
    monkeypatch.setattr(approval.audit_service, "log", audit_log)

    app = FastAPI()
    app.include_router(approval.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_admin] = lambda: admin

    version_id = uuid4()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(f"/admin/versions/{version_id}/reject")

    assert response.status_code == 400
    assert response.json() == {"detail": "Cannot reject version with status 'approved'"}
    reject_version.assert_awaited_once_with(
        db=db,
        version_id=version_id,
        reviewed_by=admin.email,
        notes=None,
    )
    audit_log.assert_not_called()
    db.get.assert_not_called()


@pytest.mark.asyncio
async def test_rejection_returns_review_and_records_audit(monkeypatch):
    db = MagicMock(spec=AsyncSession)
    admin = SimpleNamespace(email="admin@example.com")
    reviewed_at = datetime(2026, 9, 23, tzinfo=timezone.utc)

    version = SimpleNamespace(
        id=uuid4(),
        status="rejected",
        reviewed_by=admin.email,
        reviewed_at=reviewed_at,
    )
    location = SimpleNamespace(slug="documents")

    reject_version = AsyncMock(return_value=(version, location))
    monkeypatch.setattr(
        approval.approval_service,
        "reject_version",
        reject_version,
    )
    monkeypatch.setattr(approval, "audit_service", AuditService())

    app = FastAPI()
    app.include_router(approval.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_admin] = lambda: admin

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/admin/versions/{version.id}/reject",
            json={"notes": "Please update the document."},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(version.id)
    assert body["status"] == "rejected"
    assert body["reviewed_by"] == admin.email
    assert datetime.fromisoformat(body["reviewed_at"]) == reviewed_at
    assert body["location_slug"] == location.slug
    assert body["now_serving"] is False

    reject_version.assert_awaited_once_with(
        db=db,
        version_id=version.id,
        reviewed_by=admin.email,
        notes="Please update the document.",
    )
    db.get.assert_not_called()

    db.add.assert_called_once()
    call = db.add.call_args
    assert call is not None
    audit_entry = call.args[0]

    assert audit_entry.action == "reject"
    assert audit_entry.entity_type == "file_version"
    assert audit_entry.entity_id == version.id
    assert audit_entry.actor == admin.email
    assert audit_entry.details == {
        "location_slug": "documents",
        "notes": "Please update the document.",
    }
    db.flush.assert_awaited_once()
