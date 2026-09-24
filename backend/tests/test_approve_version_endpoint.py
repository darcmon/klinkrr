from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_current_admin, get_current_membership, get_db
from backend.routers import approval
from backend.services.approval_service import SelfApprovalNotAllowed
from backend.services.audit_service import AuditService


def build_app(db, admin, *, allow_self_approval=True):
    app = FastAPI()
    app.include_router(approval.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_admin] = lambda: admin
    app.dependency_overrides[get_current_membership] = lambda: SimpleNamespace(
        organization=SimpleNamespace(allow_self_approval=allow_self_approval)
    )
    return app


async def post_approve(app, version_id, json=None):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(f"/admin/versions/{version_id}/approve", json=json)


@pytest.mark.asyncio
@pytest.mark.parametrize("self_approved", [False, True])
async def test_approve_version_returns_success_and_records_audit(
    monkeypatch, self_approved
):
    db = MagicMock(spec=AsyncSession)
    admin = SimpleNamespace(id=uuid4(), email="admin@example.com")

    version = SimpleNamespace(
        id=uuid4(),
        status="approved",
        uploaded_by_id=admin.id if self_approved else uuid4(),
        reviewed_by=admin.email,
        reviewed_at=datetime(2026, 9, 14, tzinfo=timezone.utc),
    )
    location = SimpleNamespace(slug="documents", organization_id=uuid4())

    approve_version = AsyncMock(return_value=(version, location))
    monkeypatch.setattr(
        approval.approval_service,
        "approve_version",
        approve_version,
    )

    # Use the real audit method so invalid arguments cannot pass unnoticed.
    audit_service = AuditService()
    monkeypatch.setattr(approval, "audit_service", audit_service)

    response = await post_approve(
        build_app(db, admin), version.id, json={"notes": "Ready to publish"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(version.id)
    assert body["status"] == "approved"
    assert body["location_slug"] == "documents"
    assert body["now_serving"] is True

    approve_version.assert_awaited_once_with(
        db=db,
        version_id=version.id,
        reviewed_by=admin.email,
        reviewed_by_id=admin.id,
        notes="Ready to publish",
        allow_self_approval=True,
    )

    db.add.assert_called_once()
    audit_entry = db.add.call_args.args[0]
    assert audit_entry.action == "approve"
    assert audit_entry.entity_type == "file_version"
    assert audit_entry.entity_id == version.id
    assert audit_entry.actor == admin.email
    assert audit_entry.actor_id == admin.id
    assert audit_entry.organization_id == location.organization_id
    assert audit_entry.details == {
        "location_slug": "documents",
        "notes": "Ready to publish",
        "self_approved": self_approved,
    }
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_self_approval_is_forbidden_when_organization_disallows_it(monkeypatch):
    db = MagicMock(spec=AsyncSession)
    admin = SimpleNamespace(id=uuid4(), email="admin@example.com")

    approve_version = AsyncMock(
        side_effect=SelfApprovalNotAllowed(
            "Someone other than the uploader must approve this version"
        )
    )
    monkeypatch.setattr(approval.approval_service, "approve_version", approve_version)
    audit_log = AsyncMock()
    monkeypatch.setattr(approval.audit_service, "log", audit_log)

    version_id = uuid4()
    response = await post_approve(
        build_app(db, admin, allow_self_approval=False), version_id
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Someone other than the uploader must approve this version"
    }
    assert approve_version.await_args.kwargs["allow_self_approval"] is False
    audit_log.assert_not_called()
