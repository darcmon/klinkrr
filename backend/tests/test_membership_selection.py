from uuid import uuid4

import pytest
from fastapi import HTTPException

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
