import uuid

from pydantic import BaseModel


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
