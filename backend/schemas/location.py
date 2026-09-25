import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LocationCreate(BaseModel):
    """What the client sends to create a location."""

    # Optional client-generated id. Sending the same id again returns the
    # location created by the earlier attempt instead of failing, so a retry
    # after a lost response is safe.
    id: uuid.UUID | None = None
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9\-]+$")
    display_name: str = Field(..., min_length=1, max_length=255)
    approval_required: bool = Field(default=True, strict=True)
    description: str | None = None
    reminder_email: str | None = None


class LocationUpdate(BaseModel):
    """Partial update — only send the fields you want to change.

    `null` for `display_name` or `approval_required` means "leave unchanged";
    `null` for `description` or `reminder_email` clears it.
    """

    display_name: str | None = Field(None, min_length=1, max_length=255)
    approval_required: bool | None = Field(None, strict=True)
    description: str | None = None
    reminder_email: str | None = None


class PublishedVersionSummary(BaseModel):
    id: uuid.UUID
    version_number: int
    kind: Literal["file", "link"]
    # The filename, or the link's host.
    label: str


class LocationResponse(BaseModel):
    """What the API returns for a location."""

    id: uuid.UUID
    slug: str
    display_name: str
    description: str | None
    reminder_email: str | None
    approval_required: bool
    current_approved_version_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    published_version: PublishedVersionSummary | None = None
    # When a version was last submitted here, whatever happened to it.
    last_submitted_at: datetime | None = None

    model_config = {"from_attributes": True}


class LocationListResponse(BaseModel):
    locations: list[LocationResponse]
    total: int


class SlugAvailabilityResponse(BaseModel):
    """Advisory only: it doesn't reserve the slug."""

    available: bool
    reason: Literal["invalid", "reserved", "retired", "taken"] | None
    # Only when the slug is taken by a location in the caller's organization.
    taken_by: str | None = None
    message: str | None = None
