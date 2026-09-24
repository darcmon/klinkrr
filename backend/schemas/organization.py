import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from pydantic_core import PydanticCustomError

Role = Literal["uploader", "approver", "manager", "owner"]

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class OrganizationUpdate(BaseModel):
    """Partial update — only send the fields you want to change."""

    name: str | None = Field(None, min_length=1, max_length=255)
    allow_self_approval: bool | None = Field(None, strict=True)


class MemberResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    display_name: str
    role: Role
    # NULL until the person signs in for the first time.
    last_login_at: datetime | None
    is_you: bool


class MemberListResponse(BaseModel):
    members: list[MemberResponse]


class MemberCreate(BaseModel):
    email: str = Field(..., max_length=255)
    role: Role
    display_name: str | None = Field(None, max_length=255)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        # SSO sign-in matches on the lowercased provider email.
        email = value.strip().lower()
        if not EMAIL_PATTERN.match(email):
            raise PydanticCustomError("email", "Enter a valid email address")
        return email


class MemberUpdate(BaseModel):
    role: Role
