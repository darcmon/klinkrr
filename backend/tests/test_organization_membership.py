from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.dependencies import (
    get_current_admin,
    get_current_membership,
)
from backend.models.location import Location
from backend.routers import locations
from backend.services.approval_service import (
    ApprovalService,
    ReviewNotAllowed,
    VersionNotFound,
)


ORGANIZATION_ID = uuid4()


def review_db(version, location):
    db = MagicMock(spec=AsyncSession)
    db.info = {}
    db.get.return_value = version
    location_result = MagicMock()
    location_result.scalar_one_or_none.return_value = location
    db.execute.side_effect = [location_result, MagicMock()]
    return db


def pending_version(uploader_id):
    return SimpleNamespace(
        id=uuid4(),
        location_id=uuid4(),
        status="pending",
        deleted_at=None,
        uploaded_by_id=uploader_id,
    )


def location_for(version, organization_id=ORGANIZATION_ID):
    return SimpleNamespace(
        id=version.location_id,
        slug="documents",
        organization_id=organization_id,
        current_approved_version_id=None,
    )


# (own version?, can_approve_own, can_review_others) -> allowed?
APPROVAL_CASES = [
    (True, True, False, True),
    (True, False, True, False),  # reviewing others doesn't cover your own
    (False, False, True, True),
    (False, True, False, False),  # approving your own doesn't cover others'
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("own", "can_approve_own", "can_review_others", "allowed"), APPROVAL_CASES
)
async def test_approval_rules(own, can_approve_own, can_review_others, allowed):
    uploader_id = uuid4()
    reviewer_id = uploader_id if own else uuid4()
    version = pending_version(uploader_id)

    async def approve():
        return await ApprovalService().approve_version(
            db=review_db(version, location_for(version)),
            version_id=version.id,
            reviewed_by="reviewer@example.com",
            reviewed_by_id=reviewer_id,
            organization_id=ORGANIZATION_ID,
            can_approve_own=can_approve_own,
            can_review_others=can_review_others,
        )

    if allowed:
        approved, _ = await approve()
        assert approved.status == "approved"
        assert approved.reviewed_by_id == reviewer_id
    else:
        with pytest.raises(ReviewNotAllowed):
            await approve()
        assert version.status == "pending"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("own", "can_review_others", "allowed"),
    [(True, False, True), (False, True, True), (False, False, False)],
)
async def test_rejection_rules(own, can_review_others, allowed):
    uploader_id = uuid4()
    reviewer_id = uploader_id if own else uuid4()
    version = pending_version(uploader_id)

    async def reject():
        return await ApprovalService().reject_version(
            db=review_db(version, location_for(version)),
            version_id=version.id,
            reviewed_by="reviewer@example.com",
            reviewed_by_id=reviewer_id,
            organization_id=ORGANIZATION_ID,
            can_review_others=can_review_others,
        )

    if allowed:
        rejected, _ = await reject()
        assert rejected.status == "rejected"
    else:
        with pytest.raises(ReviewNotAllowed):
            await reject()
        assert version.status == "pending"


@pytest.mark.asyncio
async def test_version_in_another_organization_is_not_found():
    version = pending_version(uuid4())
    other_organization = location_for(version, organization_id=uuid4())

    with pytest.raises(VersionNotFound):
        await ApprovalService().approve_version(
            db=review_db(version, other_organization),
            version_id=version.id,
            reviewed_by="reviewer@example.com",
            reviewed_by_id=uuid4(),
            organization_id=ORGANIZATION_ID,
            can_approve_own=True,
            can_review_others=True,
        )
    assert version.status == "pending"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("count", "detail"),
    [
        (0, "You are not a member of any organization"),
        (2, "Belonging to more than one organization is not supported yet"),
    ],
)
async def test_membership_dependency_rejects_missing_or_multiple(count, detail):
    db = MagicMock(spec=AsyncSession)
    result = MagicMock()
    result.scalars.return_value.all.return_value = [object()] * count
    db.execute.return_value = result

    with pytest.raises(HTTPException) as error:
        await get_current_membership(admin=SimpleNamespace(id=uuid4()), db=db)

    assert error.value.status_code == 403
    assert error.value.detail == detail


@pytest.mark.asyncio
async def test_membership_dependency_returns_single_membership():
    membership = object()
    db = MagicMock(spec=AsyncSession)
    result = MagicMock()
    result.scalars.return_value.all.return_value = [membership]
    db.execute.return_value = result

    assert (
        await get_current_membership(admin=SimpleNamespace(id=uuid4()), db=db)
        is membership
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(("approval_required", "expected"), [(True, 1), (False, 0)])
async def test_create_location_records_organization_creator_and_policy(
    approval_required, expected
):
    admin = SimpleNamespace(id=uuid4(), email="admin@example.com")
    membership = SimpleNamespace(organization_id=uuid4(), role="manager")

    db = MagicMock(spec=AsyncSession)
    existing = MagicMock()
    existing.scalar_one_or_none.return_value = None
    db.execute.return_value = existing

    async def flush():
        location = db.add.call_args.args[0]
        location.id = uuid4()
        location.created_at = location.updated_at = "2026-09-23T00:00:00+00:00"

    db.flush.side_effect = flush

    app = FastAPI()
    app.include_router(locations.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_admin] = lambda: admin
    app.dependency_overrides[get_current_membership] = lambda: membership

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/admin/locations",
            json={
                "slug": "dock-a",
                "display_name": "Dock A",
                "approval_required": approval_required,
            },
        )

    assert response.status_code == 201
    assert response.json()["approval_required"] is approval_required

    location = db.add.call_args.args[0]
    assert isinstance(location, Location)
    assert location.organization_id == membership.organization_id
    assert location.created_by_id == admin.id
    assert location.required_approvals == expected


def test_turning_approval_on_keeps_a_multi_approver_requirement():
    location = Location(required_approvals=2)
    location.approval_required = True
    assert location.required_approvals == 2

    location.approval_required = False
    assert location.required_approvals == 0
    assert location.approval_required is False
