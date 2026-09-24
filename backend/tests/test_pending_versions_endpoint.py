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
from backend.services.approval_service import review_rights

ORGANIZATION_ID = uuid4()
ME = uuid4()
SOMEONE_ELSE = uuid4()

LOCATION = SimpleNamespace(id=uuid4(), slug="handbook", display_name="Handbook")


def pending(uploaded_by_id, kind="link"):
    return SimpleNamespace(
        id=uuid4(),
        location_id=LOCATION.id,
        kind=kind,
        link_url="https://example.com/handbook",
        link_mode="redirect",
        original_filename=None,
        content_type=None,
        file_size_bytes=None,
        version_number=1,
        uploaded_by="someone@example.com",
        uploaded_by_id=uploaded_by_id,
        uploaded_at=datetime(2026, 9, 8, tzinfo=timezone.utc),
    )


async def get_pending_list(monkeypatch, *, role, allow_self_approval=True, query="",
                           rows=None):
    get_pending = AsyncMock(return_value=rows or [])
    monkeypatch.setattr(approval.approval_service, "get_pending_versions", get_pending)

    db = MagicMock(spec=AsyncSession)
    app = FastAPI()
    app.include_router(approval.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_admin] = lambda: SimpleNamespace(
        id=ME, email="me@example.com"
    )
    app.dependency_overrides[get_current_membership] = lambda: SimpleNamespace(
        role=role,
        organization_id=ORGANIZATION_ID,
        organization=SimpleNamespace(allow_self_approval=allow_self_approval),
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/admin/versions/pending{query}")
    return response, get_pending, db


@pytest.mark.asyncio
async def test_pending_list_includes_link_fields(monkeypatch):
    version = pending(SOMEONE_ELSE)
    response, get_pending, db = await get_pending_list(
        monkeypatch, role="owner", rows=[(version, LOCATION)]
    )

    assert response.status_code == 200
    [item] = response.json()
    assert item["id"] == str(version.id)
    assert item["location_slug"] == "handbook"
    assert item["location_display_name"] == "Handbook"
    assert item["kind"] == "link"
    assert item["link_url"] == version.link_url
    assert item["link_mode"] == "redirect"
    assert item["original_filename"] is None
    assert item["content_type"] is None
    assert item["file_size_bytes"] is None
    assert item["uploaded_by_id"] == str(SOMEONE_ELSE)

    # Locations come from the same query; no per-row lookup.
    db.get.assert_not_called()
    get_pending.assert_awaited_once_with(
        db, ORGANIZATION_ID, uploaded_by_id=None, exclude_uploaded_by_id=None
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "uploaded_by_id", "exclude_uploaded_by_id"),
    [
        ("", None, None),
        ("?filter=all", None, None),
        ("?filter=mine", ME, None),
        ("?filter=waiting_on_me", None, ME),
    ],
)
async def test_filters_are_applied_in_the_query(
    monkeypatch, query, uploaded_by_id, exclude_uploaded_by_id
):
    response, get_pending, db = await get_pending_list(
        monkeypatch, role="approver", query=query
    )

    assert response.status_code == 200
    get_pending.assert_awaited_once_with(
        db,
        ORGANIZATION_ID,
        uploaded_by_id=uploaded_by_id,
        exclude_uploaded_by_id=exclude_uploaded_by_id,
    )


@pytest.mark.asyncio
async def test_nothing_is_waiting_on_an_uploader(monkeypatch):
    response, get_pending, _ = await get_pending_list(
        monkeypatch, role="uploader", query="?filter=waiting_on_me"
    )

    assert response.status_code == 200
    assert response.json() == []
    get_pending.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_filter_is_rejected(monkeypatch):
    response, _, _ = await get_pending_list(
        monkeypatch, role="owner", query="?filter=everything"
    )
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "allow_self_approval", "own", "expected"),
    [
        # expected = (is_own, can_approve, can_reject)
        ("uploader", True, True, (True, True, True)),
        ("uploader", False, True, (True, False, True)),
        ("uploader", True, False, (False, False, False)),
        ("approver", True, False, (False, True, True)),
        ("approver", False, True, (True, False, True)),
        ("owner", True, True, (True, True, True)),
    ],
)
async def test_each_item_reports_the_callers_rights(
    monkeypatch, role, allow_self_approval, own, expected
):
    version = pending(ME if own else SOMEONE_ELSE)
    response, _, _ = await get_pending_list(
        monkeypatch,
        role=role,
        allow_self_approval=allow_self_approval,
        rows=[(version, LOCATION)],
    )

    [item] = response.json()
    assert (item["is_own"], item["can_approve"], item["can_reject"]) == expected


@pytest.mark.parametrize("own", [True, False])
@pytest.mark.parametrize("can_approve_own", [True, False])
@pytest.mark.parametrize("can_review_others", [True, False])
def test_review_rights_matrix(own, can_approve_own, can_review_others):
    rights = review_rights(
        ME,
        ME if own else SOMEONE_ELSE,
        can_approve_own=can_approve_own,
        can_review_others=can_review_others,
    )

    if own:
        assert rights.can_approve is can_approve_own
        assert rights.can_reject is True
    else:
        assert rights.can_approve is can_review_others
        assert rights.can_reject is can_review_others
