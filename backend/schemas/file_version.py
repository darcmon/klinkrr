import uuid
from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, field_validator

from backend.models.file_version import FileVersion
from backend.services.url_validator import validate_link_url


class LinkVersionCreate(BaseModel):
    """Validated input for creating a redirect link version."""

    # Optional client-generated id that makes retries safe; see the upload route.
    id: uuid.UUID | None = None
    link_url: str
    link_mode: Literal["redirect"] = "redirect"

    @field_validator("link_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return validate_link_url(value)


class LinkVersionCreateResponse(BaseModel):
    """Returned after a link version is submitted."""

    id: uuid.UUID
    location_slug: str
    link_url: str
    link_mode: Literal["redirect"]
    version_number: int
    status: Literal["pending", "approved"]
    uploaded_at: datetime

    @classmethod
    def from_version(cls, version: FileVersion, *, location_slug: str) -> Self:
        return cls.model_validate(
            {
                "id": version.id,
                "location_slug": location_slug,
                "link_url": version.link_url,
                "link_mode": version.link_mode,
                "version_number": version.version_number,
                "status": version.status,
                "uploaded_at": version.uploaded_at,
            }
        )


class FileVersionResponse(BaseModel):
    """Full version details for archive views."""

    id: uuid.UUID
    location_id: uuid.UUID
    kind: Literal["file", "link"]
    link_url: str | None
    link_mode: Literal["redirect"] | None
    original_filename: str | None
    content_type: str | None
    file_size_bytes: int | None
    status: Literal["pending", "approved", "rejected", "superseded"]
    version_number: int
    uploaded_by: str
    uploaded_at: datetime
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_notes: str | None

    model_config = {"from_attributes": True}


class FileVersionUploadResponse(BaseModel):
    """Returned after a successful upload."""

    id: uuid.UUID
    location_slug: str
    original_filename: str
    version_number: int
    status: Literal["pending", "approved"]
    uploaded_at: datetime

    @classmethod
    def from_version(cls, version: FileVersion, *, location_slug: str) -> Self:
        return cls.model_validate(
            {
                "id": version.id,
                "location_slug": location_slug,
                "original_filename": version.original_filename,
                "version_number": version.version_number,
                "status": version.status,
                "uploaded_at": version.uploaded_at,
            }
        )


class ApprovalRequest(BaseModel):
    """Optional notes when approving/rejecting."""

    notes: str | None = None


class ApprovalResponse(BaseModel):
    """Returned after approve/reject."""

    id: uuid.UUID
    status: Literal["approved", "rejected"]
    reviewed_by: str
    reviewed_at: datetime
    location_slug: str
    now_serving: bool

    @classmethod
    def from_version(
        cls,
        version: FileVersion,
        *,
        location_slug: str,
        now_serving: bool,
    ) -> Self:
        return cls.model_validate(
            {
                "id": version.id,
                "status": version.status,
                "reviewed_by": version.reviewed_by,
                "reviewed_at": version.reviewed_at,
                "location_slug": location_slug,
                "now_serving": now_serving,
            }
        )


class PendingVersionResponse(BaseModel):
    """A pending version shown in the dashboard."""

    id: uuid.UUID
    kind: Literal["file", "link"]
    link_url: str | None
    link_mode: Literal["redirect"] | None
    location_slug: str
    location_display_name: str
    original_filename: str | None
    content_type: str | None
    file_size_bytes: int | None
    version_number: int
    uploaded_by: str
    uploaded_by_id: uuid.UUID
    uploaded_at: datetime
    # What the requesting user may do to this version. `is_own and can_approve`
    # means approving it would be self-approval.
    is_own: bool
    can_approve: bool
    can_reject: bool

    @classmethod
    def from_version(
        cls,
        version: FileVersion,
        *,
        location_slug: str,
        location_display_name: str,
        is_own: bool,
        can_approve: bool,
        can_reject: bool,
    ) -> Self:
        return cls.model_validate(
            {
                "id": version.id,
                "kind": version.kind,
                "link_url": version.link_url,
                "link_mode": version.link_mode,
                "location_slug": location_slug,
                "location_display_name": location_display_name,
                "original_filename": version.original_filename,
                "content_type": version.content_type,
                "file_size_bytes": version.file_size_bytes,
                "version_number": version.version_number,
                "uploaded_by": version.uploaded_by,
                "uploaded_by_id": version.uploaded_by_id,
                "uploaded_at": version.uploaded_at,
                "is_own": is_own,
                "can_approve": can_approve,
                "can_reject": can_reject,
            }
        )


class VersionArchiveResponse(BaseModel):
    """Paginated list of versions for a location."""

    location_slug: str
    location_display_name: str
    versions: list[FileVersionResponse]
    total: int
    page: int
    per_page: int
