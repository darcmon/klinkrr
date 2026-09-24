from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.dependencies import get_current_admin, get_current_membership
from backend.models.admin_user import AdminUser
from backend.models.organization import Membership
from backend.schemas.file_version import (
    ApprovalRequest,
    ApprovalResponse,
    PendingVersionResponse,
)
from backend.permissions import review_capabilities
from backend.services.approval_service import (
    ReviewNotAllowed,
    VersionNotFound,
    approval_service,
    review_rights,
)
from backend.services.audit_service import audit_service

router = APIRouter(prefix="/admin", tags=["approval"])


@router.get("/versions/pending", response_model=list[PendingVersionResponse])
async def list_pending(
    filter: Literal["all", "waiting_on_me", "mine"] = Query("all"),
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    membership: Membership = Depends(get_current_membership),
):
    """List pending uploads across the organization's locations.

    `waiting_on_me` is other people's versions the caller can review;
    `mine` is the caller's own. Each item says what the caller may do to it.
    """
    can_approve_own, can_review_others = review_capabilities(membership)

    if filter == "waiting_on_me" and not can_review_others:
        return []

    rows = await approval_service.get_pending_versions(
        db,
        membership.organization_id,
        uploaded_by_id=admin.id if filter == "mine" else None,
        exclude_uploaded_by_id=admin.id if filter == "waiting_on_me" else None,
    )

    results: list[PendingVersionResponse] = []
    for version, location in rows:
        rights = review_rights(
            version.uploaded_by_id,
            admin.id,
            can_approve_own=can_approve_own,
            can_review_others=can_review_others,
        )
        results.append(
            PendingVersionResponse.from_version(
                version,
                location_slug=location.slug,
                location_display_name=location.display_name,
                is_own=version.uploaded_by_id == admin.id,
                can_approve=rights.can_approve,
                can_reject=rights.can_reject,
            )
        )
    return results


@router.post("/versions/{version_id}/approve", response_model=ApprovalResponse)
async def approve_version(
    version_id: UUID,
    request: Request,
    body: ApprovalRequest | None = None,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    membership: Membership = Depends(get_current_membership),
):
    can_approve_own, can_review_others = review_capabilities(membership)
    try:
        version, location = await approval_service.approve_version(
            db=db,
            version_id=version_id,
            reviewed_by=admin.email,
            reviewed_by_id=admin.id,
            organization_id=membership.organization_id,
            can_approve_own=can_approve_own,
            can_review_others=can_review_others,
            notes=body.notes if body else None,
        )
    except ReviewNotAllowed as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except VersionNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await audit_service.log(
        db=db,
        action="approve",
        entity_type="file_version",
        entity_id=version.id,
        actor=admin.email,
        actor_id=admin.id,
        organization_id=location.organization_id,
        request=request,
        details={
            "location_slug": location.slug,
            "notes": body.notes if body else None,
            "self_approved": version.uploaded_by_id == admin.id,
        },
    )

    return ApprovalResponse.from_version(
        version,
        location_slug=location.slug,
        now_serving=True,
    )


@router.post("/versions/{version_id}/reject", response_model=ApprovalResponse)
async def reject_version(
    version_id: UUID,
    request: Request,
    body: ApprovalRequest | None = None,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    membership: Membership = Depends(get_current_membership),
):
    """Reject a pending file version."""
    _, can_review_others = review_capabilities(membership)
    try:
        version, location = await approval_service.reject_version(
            db=db,
            version_id=version_id,
            reviewed_by=admin.email,
            reviewed_by_id=admin.id,
            organization_id=membership.organization_id,
            can_review_others=can_review_others,
            notes=body.notes if body else None,
        )
    except ReviewNotAllowed as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except VersionNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    await audit_service.log(
        db=db,
        entity_id=version.id,
        entity_type="file_version",
        actor=admin.email,
        actor_id=admin.id,
        organization_id=location.organization_id,
        action="reject",
        request=request,
        details={"location_slug": location.slug, "notes": body.notes if body else None},
    )

    return ApprovalResponse.from_version(
        version,
        location_slug=location.slug,
        now_serving=False,
    )
