import pytest
from pydantic import ValidationError

from backend.schemas.location import LocationCreate, LocationUpdate


def test_new_location_requires_approval_by_default():
    body = LocationCreate(slug="documents", display_name="Documents")

    assert body.approval_required is True


@pytest.mark.parametrize("required", [True, False])
def test_create_accepts_explicit_governance_choice(required):
    body = LocationCreate.model_validate(
        {
            "slug": "documents",
            "display_name": "Documents",
            "approval_required": required,
        }
    )

    assert body.approval_required is required


def test_unrelated_update_does_not_change_governance():
    body = LocationUpdate(display_name="test", description="Updated description")

    assert body.model_dump(exclude_unset=True) == {
        "display_name": "test",
        "description": "Updated description",
    }


@pytest.mark.parametrize("required", [True, False])
def test_update_preserves_explicit_governance_choice(required):
    body = LocationUpdate.model_validate(
        {
            "approval_required": required,
        }
    )

    assert body.model_dump(exclude_unset=True) == {
        "approval_required": required,
    }


@pytest.mark.parametrize("schema", [LocationCreate, LocationUpdate])
@pytest.mark.parametrize("invalid", [None, "false", "true", 0, 1])
def test_governance_rejects_non_boolean_values(schema, invalid):
    payload = {"approval_required": invalid}

    if schema is LocationCreate:
        payload.update(slug="documents", display_name="Documents")

    with pytest.raises(ValidationError) as error:
        schema.model_validate(payload)

    assert error.value.errors()[0]["loc"] == ("approval_required",)
