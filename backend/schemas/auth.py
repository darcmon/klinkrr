import uuid
from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class OrganizationSummary(BaseModel):
    id: uuid.UUID
    name: str
    allow_self_approval: bool

    model_config = {"from_attributes": True}


class AdminUserResponse(BaseModel):
    """The signed-in user, their organization and what their role allows.

    The frontend decides what to show from `permissions`, never from `role`.
    `organization` and `role` are null for a user with no membership.
    """

    id: uuid.UUID
    email: str
    display_name: str
    organization: OrganizationSummary | None
    role: str | None
    permissions: list[str]
    sign_in_methods: list[Literal["password", "microsoft", "google"]]


class ProfileUpdate(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=255)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=12, max_length=128)
