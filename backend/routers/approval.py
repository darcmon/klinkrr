from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.dependencies import get_current_admin, get_current_membership
from backend.models.admin_user import AdminUser
from backend.models.location import Location
from backend.models.organization import Membership
from backend.schemas.file_version import (
    ApprovalRequest,
    ApprovalResponse,
    PendingVersionResponse,
)
from backend.services.approval_service import (
    SelfApprovalNotAllowed,
    approval_service,
)
from backend.services.audit_service import audit_service

router = APIRouter(prefix="/admin", tags=["approval"])


@router.get("/versions/pending", response_model=list[PendingVersionResponse])
async def list_pending(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """List all pending uploads across all locations."""
    versions = await approval_service.get_pending_versions(db)

    # Fetch location info for each version
    results: list[PendingVersionResponse] = []
    for version in versions:
        location = await db.get(Location, version.location_id)
        if location is None:
            raise RuntimeError("Version references a missing location")

        results.append(
            PendingVersionResponse.from_version(
                version,
                location_slug=location.slug,
                location_display_name=location.display_name,
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
    try:
        version, location = await approval_service.approve_version(
            db=db,
            version_id=version_id,
            reviewed_by=admin.email,
            reviewed_by_id=admin.id,
            notes=body.notes if body else None,
            allow_self_approval=membership.organization.allow_self_approval,
        )
    except SelfApprovalNotAllowed as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
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
):
    """Reject a pending file version."""
    try:
        version, location = await approval_service.reject_version(
            db=db,
            version_id=version_id,
            reviewed_by=admin.email,
            reviewed_by_id=admin.id,
            notes=body.notes if body else None,
        )
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
