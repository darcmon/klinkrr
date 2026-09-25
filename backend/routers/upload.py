from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.db.session import get_db
from backend.dependencies import (
    get_current_admin,
    get_web_risk_client,
    require_permission,
)
from backend.errors import api_error
from backend.models.admin_user import AdminUser
from backend.models.file_version import FileVersion
from backend.models.location import Location
from backend.models.organization import Membership
from backend.schemas.file_version import (
    FileVersionUploadResponse,
    LinkVersionCreate,
    LinkVersionCreateResponse,
)
from backend.services.file_service import file_service
from backend.services.approval_service import VersionIdExists, approval_service
from backend.services.audit_service import audit_service
from backend.services.scoping import get_location
from backend.services.web_risk_client import WebRiskClient, WebRiskError

router = APIRouter(prefix="/admin", tags=["upload"])


def _replay(
    existing: FileVersion,
    location: Location,
    admin: AdminUser,
    response: Response,
    *,
    filename: str | None = None,
    link_url: str | None = None,
) -> FileVersion:
    """A version with the client's id already exists. The same submission
    arriving again (a retry after a lost response) gets the original result
    with 200; anything else is a conflict."""
    kind = "link" if link_url is not None else "file"
    same_submission = (
        existing.location_id == location.id
        and existing.uploaded_by_id == admin.id
        and existing.deleted_at is None
        and existing.kind == kind
        and (
            existing.link_url == link_url
            if kind == "link"
            else existing.original_filename == filename
        )
    )
    if not same_submission:
        raise api_error(
            409,
            "version_id_conflict",
            "This submission id was already used for different content.",
        )
    if existing.status not in ("pending", "approved"):
        raise api_error(
            409, "version_id_conflict", "This submission has already been processed."
        )

    response.status_code = 200
    return existing


@router.post(
    "/locations/{slug}/upload",
    response_model=FileVersionUploadResponse,
    status_code=201,
)
async def upload_file(
    slug: str,
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    # Optional client-generated id; resending it makes a retry safe.
    id: UUID | None = Form(None),
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    membership: Membership = Depends(require_permission("submit")),
):
    settings = get_settings()

    # 1. Find the location
    location = await get_location(db, membership.organization_id, slug)
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    # 2. Validate content type
    filename = file.filename
    content_type = file.content_type

    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    # A retry: answer before reading the file or touching S3.
    if id is not None and (existing := await db.get(FileVersion, id)):
        version = _replay(existing, location, admin, response, filename=filename)
        return FileVersionUploadResponse.from_version(version, location_slug=slug)

    if content_type is None or content_type not in settings.allowed_file_types_list:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{content_type}' is not allowed. "
            f"Allowed: {', '.join(settings.allowed_file_types_list)}",
        )

    # 3. Read and validate size
    file_data = await file.read()
    file_size = len(file_data)

    if file_size == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    if file_size > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {settings.max_upload_size_mb}MB.",
        )

    # 4. Upload to S3
    s3_key = file_service.generate_s3_key(slug, filename)
    await file_service.upload_file(s3_key, file_data, content_type)

    # 5. Create pending version in DB
    try:
        version = await approval_service.create_pending_version(
            db=db,
            location_id=location.id,
            original_filename=filename,
            content_type=content_type,
            file_size_bytes=file_size,
            s3_key=s3_key,
            uploaded_by=admin.email,
            uploaded_by_id=admin.id,
            version_id=id,
        )
    except VersionIdExists as e:
        # A concurrent retry won the race; the object stored above is unused.
        version = _replay(e.existing, location, admin, response, filename=filename)
        return FileVersionUploadResponse.from_version(version, location_slug=slug)

    await approval_service.apply_submission_governance(db, version, request=request)

    # 6. Audit log
    await audit_service.log(
        db=db,
        action="upload",
        entity_type="file_version",
        entity_id=version.id,
        actor=admin.email,
        actor_id=admin.id,
        organization_id=location.organization_id,
        request=request,
        details={
            "filename": file.filename,
            "content_type": file.content_type,
            "size_bytes": file_size,
            "location_slug": slug,
        },
    )

    return FileVersionUploadResponse.from_version(version, location_slug=slug)


@router.post(
    "/locations/{slug}/link",
    response_model=LinkVersionCreateResponse,
    status_code=201,
)
async def create_link(
    slug: str,
    payload: LinkVersionCreate,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    membership: Membership = Depends(require_permission("submit")),
    web_risk: WebRiskClient = Depends(get_web_risk_client),
):
    location = await get_location(db, membership.organization_id, slug)
    if location is None:
        raise HTTPException(status_code=404, detail="Location not found")

    # A retry: answer before calling the safety check.
    if payload.id is not None and (existing := await db.get(FileVersion, payload.id)):
        version = _replay(existing, location, admin, response, link_url=payload.link_url)
        return LinkVersionCreateResponse.from_version(version, location_slug=slug)

    try:
        flagged = await web_risk.is_flagged(payload.link_url)
    except WebRiskError as exc:
        raise HTTPException(
            status_code=503,
            detail="URL safety checking is unavailable",
        ) from exc

    if flagged:
        raise HTTPException(
            status_code=422,
            detail="URL was flagged by the safety check",
        )

    try:
        version = await approval_service.create_pending_link_version(
            db=db,
            location_id=location.id,
            link_url=payload.link_url,
            uploaded_by=admin.email,
            uploaded_by_id=admin.id,
            version_id=payload.id,
        )
    except VersionIdExists as e:
        version = _replay(e.existing, location, admin, response, link_url=payload.link_url)
        return LinkVersionCreateResponse.from_version(version, location_slug=slug)

    await approval_service.apply_submission_governance(db, version, request=request)

    await audit_service.log(
        db=db,
        action="create_link",
        entity_type="file_version",
        entity_id=version.id,
        actor=admin.email,
        actor_id=admin.id,
        organization_id=location.organization_id,
        request=request,
        details={"location_slug": slug, "link_mode": version.link_mode},
    )

    return LinkVersionCreateResponse.from_version(version, location_slug=slug)
