from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.dependencies import get_current_admin
from backend.routers import locations


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "initial, payload, expected, should_audit",
    [
        (True, {"approval_required": False}, False, True),
        (False, {"approval_required": True}, True, True),
        (True, {"approval_required": True}, True, False),
        (False, {"approval_required": False}, False, False),
        (False, {"description": "Updated description"}, False, False),
    ],
)
async def test_governance_update_preserves_publication_and_audits_changes(
    monkeypatch,
    initial,
    payload,
    expected,
    should_audit,
):
    now = datetime.now(timezone.utc)
    published_version_id = uuid4()

    location = SimpleNamespace(
        id=uuid4(),
        slug="documents",
        display_name="Documents",
        description=None,
        reminder_email=None,
        approval_required=initial,
        organization_id=uuid4(),
        current_approved_version_id=published_version_id,
        created_at=now,
        updated_at=now,
    )
    admin = SimpleNamespace(id=uuid4(), email="admin@example.com")

    db = MagicMock(spec=AsyncSession)
    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = location
    db.execute.return_value = query_result

    audit_log = AsyncMock()
    monkeypatch.setattr(locations.audit_service, "log", audit_log)

    app = FastAPI()
    app.include_router(locations.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_admin] = lambda: admin

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.patch(
            "/admin/locations/documents",
            json=payload,
        )

    assert response.status_code == 200
    assert response.json()["approval_required"] is expected
    assert response.json()["current_approved_version_id"] == str(published_version_id)
    assert location.current_approved_version_id == published_version_id

    db.flush.assert_awaited_once()
    if "description" in payload:
        assert response.json()["description"] == payload["description"]

    if initial == expected:
        if not should_audit:
            audit_log.assert_not_called()
            return
        audit_log.assert_not_called()
        return
    audit_log.assert_awaited_once()

    call = audit_log.await_args
    assert call is not None

    assert call.args == (db,)
    assert call.kwargs["action"] == "governance_changed"
    assert call.kwargs["entity_type"] == "location"
    assert call.kwargs["entity_id"] == location.id
    assert call.kwargs["actor"] == admin.email
    assert call.kwargs["details"] == {
        "approval_required": {
            "before": initial,
            "after": expected,
        },
    }


@pytest.mark.asyncio
async def test_governance_update_returns_404_for_missing_location(monkeypatch):
    db = MagicMock(spec=AsyncSession)
    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = None
    db.execute.return_value = query_result

    admin = SimpleNamespace(id=uuid4(), email="admin@example.com")

    audit_log = AsyncMock()
    monkeypatch.setattr(locations.audit_service, "log", audit_log)

    app = FastAPI()
    app.include_router(locations.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_admin] = lambda: admin

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.patch(
            "/admin/locations/missing",
            json={"approval_required": False},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Location not found"}

    db.flush.assert_not_awaited()
    audit_log.assert_not_called()
