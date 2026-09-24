from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.dependencies import (
    get_current_admin,
    get_current_membership,
    require_permission,
)
from backend.permissions import has_permission, permissions_for
from backend.routers import archive, auth, locations


def membership(role, *, organization_id=None, allow_self_approval=True):
    return SimpleNamespace(
        role=role,
        organization_id=organization_id or uuid4(),
        organization=SimpleNamespace(
            id=uuid4(), name="Acme", allow_self_approval=allow_self_approval
        ),
    )


def client_for(router, db, admin, member):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_admin] = lambda: admin
    app.dependency_overrides[get_current_membership] = lambda: member
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def db_returning(value):
    db = MagicMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    db.execute.return_value = result
    return db


def test_roles_inherit_permissions_from_lower_roles():
    assert permissions_for("uploader") == ["submit", "create_location", "approve_own"]
    assert permissions_for("approver") == permissions_for("uploader") + ["review_any"]
    assert permissions_for("manager") == permissions_for("approver") + [
        "manage_locations"
    ]
    assert permissions_for("owner") == permissions_for("manager") + ["manage_members"]
    assert not has_permission("uploader", "review_any")
    assert has_permission("owner", "review_any")


@pytest.mark.asyncio
async def test_require_permission_rejects_roles_without_it():
    check = require_permission("review_any")

    assert await check(membership=membership("approver")) is not None
    with pytest.raises(HTTPException) as error:
        await check(membership=membership("uploader"))
    assert error.value.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "status"), [("uploader", 403), ("approver", 403), ("manager", 201)]
)
async def test_only_managers_create_locations_that_skip_approval(role, status):
    admin = SimpleNamespace(id=uuid4(), email="a@example.com")
    db = db_returning(None)

    async def flush():
        location = db.add.call_args.args[0]
        location.id = uuid4()
        location.created_at = location.updated_at = datetime.now(timezone.utc)

    db.flush.side_effect = flush

    async with client_for(locations.router, db, admin, membership(role)) as client:
        response = await client.post(
            "/admin/locations",
            json={"slug": "dock-a", "display_name": "Dock A", "approval_required": False},
        )

    assert response.status_code == status


def existing_location(created_by_id, approval_required=True):
    now = datetime.now(timezone.utc)
    location = SimpleNamespace(
        id=uuid4(),
        slug="dock-a",
        display_name="Dock A",
        description=None,
        reminder_email=None,
        approval_required=approval_required,
        created_by_id=created_by_id,
        organization_id=uuid4(),
        current_approved_version_id=None,
        created_at=now,
        updated_at=now,
    )
    return location


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "is_creator", "payload", "status"),
    [
        # Creators can edit details of their own locations.
        ("uploader", True, {"display_name": "Renamed"}, 200),
        ("uploader", False, {"display_name": "Renamed"}, 403),
        ("approver", False, {"description": "New"}, 403),
        ("manager", False, {"display_name": "Renamed"}, 200),
        # Changing the approval policy needs a manager, even for the creator.
        ("uploader", True, {"approval_required": False}, 403),
        ("manager", False, {"approval_required": False}, 200),
        # Sending the current policy unchanged is not a policy change.
        ("uploader", True, {"display_name": "Renamed", "approval_required": True}, 200),
    ],
)
async def test_location_edit_rules(role, is_creator, payload, status, monkeypatch):
    admin = SimpleNamespace(id=uuid4(), email="a@example.com")
    location = existing_location(admin.id if is_creator else uuid4())
    monkeypatch.setattr(locations.audit_service, "log", AsyncMock())

    async with client_for(
        locations.router, db_returning(location), admin, membership(role)
    ) as client:
        response = await client.patch("/admin/locations/dock-a", json=payload)

    assert response.status_code == status
    if status == 403:
        assert location.display_name == "Dock A"
        assert location.approval_required is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "own", "status"),
    [("uploader", True, 204), ("uploader", False, 403), ("approver", False, 403),
     ("manager", False, 204)],
)
async def test_version_delete_rules(role, own, status, monkeypatch):
    admin = SimpleNamespace(id=uuid4(), email="a@example.com")
    version = SimpleNamespace(id=uuid4(), uploaded_by_id=admin.id if own else uuid4())
    soft_delete = AsyncMock()
    monkeypatch.setattr(archive.approval_service, "soft_delete_version", soft_delete)

    async with client_for(
        archive.router, db_returning(version), admin, membership(role)
    ) as client:
        response = await client.delete(f"/admin/versions/{version.id}")

    assert response.status_code == status
    assert soft_delete.await_count == (1 if status == 204 else 0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path", ["/admin/locations/dock-a", "/admin/locations/dock-a/versions"]
)
async def test_other_organizations_locations_are_not_found(path):
    admin = SimpleNamespace(id=uuid4(), email="a@example.com")
    router = locations.router if path.count("/") == 3 else archive.router

    # The scoped lookup finds nothing, exactly as for a missing location.
    async with client_for(router, db_returning(None), admin, membership("owner")) as client:
        response = await client.get(path)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_me_returns_organization_role_and_permissions(monkeypatch):
    admin = SimpleNamespace(
        id=uuid4(),
        email="a@example.com",
        display_name="A",
        password_hash="hash",
        microsoft_sub=None,
        google_sub="google-sub",
    )
    member = membership("approver", allow_self_approval=False)
    monkeypatch.setattr(auth, "load_membership", AsyncMock(return_value=member))

    async with client_for(auth.router, MagicMock(), admin, member) as client:
        body = (await client.get("/admin/me")).json()

    assert body["id"] == str(admin.id)
    assert body["role"] == "approver"
    assert body["organization"] == {
        "id": str(member.organization.id),
        "name": "Acme",
        "allow_self_approval": False,
    }
    assert body["permissions"] == permissions_for("approver")
    assert body["sign_in_methods"] == ["password", "google"]


@pytest.mark.asyncio
async def test_me_works_without_a_membership(monkeypatch):
    admin = SimpleNamespace(
        id=uuid4(),
        email="a@example.com",
        display_name="A",
        password_hash=None,
        microsoft_sub="ms-sub",
        google_sub=None,
    )
    monkeypatch.setattr(auth, "load_membership", AsyncMock(return_value=None))

    async with client_for(auth.router, MagicMock(), admin, None) as client:
        response = await client.get("/admin/me")

    assert response.status_code == 200
    assert response.json()["organization"] is None
    assert response.json()["role"] is None
    assert response.json()["permissions"] == []
