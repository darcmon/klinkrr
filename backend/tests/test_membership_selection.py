from uuid import uuid4
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import Depends, FastAPI, HTTPException

from backend import dependencies
from backend.db.session import get_db
from backend.dependencies import select_membership
from backend.models.organization import Membership


def test_selection_requires_membership_and_never_falls_back():
    user_id = uuid4()
    first = Membership(organization_id=uuid4(), user_id=user_id, role="owner")
    second = Membership(organization_id=uuid4(), user_id=user_id, role="uploader")

    assert select_membership([], None) is None
    assert select_membership([first], None) is first
    assert select_membership([first, second], None) is None
    assert select_membership([first, second], second.organization_id) is second

    # A revoked selection must not fall back to the remaining membership.
    with pytest.raises(HTTPException) as error:
        select_membership([first], second.organization_id)

    assert error.value.status_code == 403
    assert error.value.detail["code"] == "organization_access_denied"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "selection, expected_status",
    [("owner", 200), ("uploader", 403), ("missing", 409),
     ("revoked", 403), ("malformed", 422)],
)
async def test_permission_uses_selected_organization(selection, expected_status, monkeypatch):
    user_id = uuid4()
    owner = Membership(organization_id=uuid4(), user_id=user_id, role="owner")
    uploader = Membership(organization_id=uuid4(), user_id=user_id, role="uploader")
    memberships = [owner] if selection == "revoked" else [owner, uploader]
    monkeypatch.setattr(dependencies, "load_memberships", AsyncMock(return_value=memberships))
    app = FastAPI()
    app.dependency_overrides[dependencies.get_current_admin] = lambda: SimpleNamespace(id=user_id)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    business_logic = MagicMock()

    @app.get("/protected")
    async def protected(member=Depends(dependencies.require_permission("manage_members"))):
        business_logic()
        return {"organization_id": str(member.organization_id)}

    headers = {}
    if selection != "missing":
        headers["X-Organization-ID"] = (
            "invalid" if selection == "malformed" else
            str(owner.organization_id if selection == "owner" else uploader.organization_id)
        )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
    ) as client:
        response = await client.get("/protected", headers=headers)
    assert response.status_code == expected_status
    if expected_status == 200:
        business_logic.assert_called_once()
        assert response.json()["organization_id"] == str(owner.organization_id)
    else:
        business_logic.assert_not_called()
    if selection == "revoked":
        assert response.json()["detail"]["code"] == "organization_access_denied"
