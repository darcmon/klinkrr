"""Role → permission map. The single place that decides what each role can do.

Roles are ordered (see ROLES); each permission names the lowest role that has
it, and every role above inherits it.
"""

from typing import Literal

from backend.models.organization import ROLES

Permission = Literal[
    "submit",
    "create_location",
    "approve_own",
    "review_any",
    "manage_locations",
    "manage_members",
]

MINIMUM_ROLE: dict[Permission, str] = {
    "submit": "uploader",
    "create_location": "uploader",
    # Also needs the organization's allow_self_approval setting.
    "approve_own": "uploader",
    "review_any": "approver",
    # Edit any location, change approval policy, delete others' versions.
    "manage_locations": "manager",
    "manage_members": "owner",
}


def has_permission(role: str, permission: Permission) -> bool:
    return ROLES.index(role) >= ROLES.index(MINIMUM_ROLE[permission])


def permissions_for(role: str) -> list[Permission]:
    return [p for p in MINIMUM_ROLE if has_permission(role, p)]


def review_capabilities(membership) -> tuple[bool, bool]:
    """(can_approve_own, can_review_others) for a membership.

    Approving your own version needs both the role permission and the
    organization's allow_self_approval setting.
    """
    can_approve_own = membership.organization.allow_self_approval and has_permission(
        membership.role, "approve_own"
    )
    return can_approve_own, has_permission(membership.role, "review_any")
