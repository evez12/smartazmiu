import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.core.deps import JobsDep, RedisDep, SessionDep, StorageDep
from app.core.errors import COMMON_ERROR_RESPONSES
from app.core.rbac import CurrentUserDep, require_permission
from app.modules.materials.models import MaterialReportStatus
from app.modules.materials.schemas import (
    MaterialCreateIn,
    MaterialDetailOut,
    MaterialDownloadOut,
    MaterialPresignIn,
    MaterialPresignOut,
    MaterialReportCreatedOut,
    MaterialReportIn,
    MaterialReportPageOut,
    MaterialReportStatusIn,
    MaterialSubjectListOut,
    SubjectCatalogOut,
    VersionCreateIn,
    VisibilityIn,
)
from app.modules.materials.service import MaterialService
from app.modules.users.service import CurrentUser

REPORTS_READ = "admin.reports.read"
REPORTS_HANDLE = "admin.reports.handle"

router = APIRouter(tags=["materials"], responses=COMMON_ERROR_RESPONSES)
ReportReader = Annotated[CurrentUser, Depends(require_permission(REPORTS_READ))]
ReportHandler = Annotated[CurrentUser, Depends(require_permission(REPORTS_HANDLE))]


def get_materials(
    session: SessionDep, storage: StorageDep, cache: RedisDep, jobs: JobsDep
) -> MaterialService:
    return MaterialService(session, storage, cache, jobs)


MaterialsDep = Annotated[MaterialService, Depends(get_materials)]


@router.get(
    "/materials/subjects",
    response_model=MaterialSubjectListOut,
    operation_id="listMaterialSubjects",
    summary="Subjects whose materials I can read, with the number of visible materials",
)
async def list_material_subjects(
    user: CurrentUserDep, materials: MaterialsDep
) -> MaterialSubjectListOut:
    return MaterialSubjectListOut(items=await materials.my_subjects(user))


@router.get(
    "/subjects/{subject_id}/materials",
    response_model=SubjectCatalogOut,
    operation_id="getSubjectMaterials",
    summary="A subject's materials, optionally for one semester",
)
async def get_subject_materials(
    user: CurrentUserDep,
    materials: MaterialsDep,
    subject_id: uuid.UUID,
    semester_id: uuid.UUID | None = None,
) -> SubjectCatalogOut:
    return await materials.catalog(user, subject_id, semester_id)


@router.post(
    "/materials/uploads/presign",
    response_model=MaterialPresignOut,
    operation_id="presignMaterialUpload",
    summary="Reserve an upload: a ten-minute URL to PUT one file to (PDF, DOCX, PPTX, ZIP, images, 50 MB)",
)
async def presign_material_upload(
    user: CurrentUserDep, materials: MaterialsDep, body: MaterialPresignIn
) -> MaterialPresignOut:
    upload = await materials.presign(
        user, body.subject_id, body.semester_id, body.filename, body.mime, body.size
    )
    return MaterialPresignOut(
        upload_id=str(upload.version.id),
        url=upload.url,
        object_key=upload.version.object_key,
        expires_at=upload.expires_at,
        headers={"Content-Type": upload.version.mime},
    )


@router.post(
    "/materials",
    response_model=MaterialDetailOut,
    status_code=201,
    operation_id="createMaterial",
    summary="Save an uploaded file as a new material (copyright confirmation required)",
)
async def create_material(
    user: CurrentUserDep, materials: MaterialsDep, body: MaterialCreateIn
) -> MaterialDetailOut:
    return await materials.create(
        user, body.upload_id, body.type, body.title, body.description, body.copyright_confirmed
    )


@router.get(
    "/materials/{material_id}",
    response_model=MaterialDetailOut,
    operation_id="getMaterial",
    summary="A material with its versions",
)
async def get_material(
    user: CurrentUserDep, materials: MaterialsDep, material_id: uuid.UUID
) -> MaterialDetailOut:
    return await materials.detail(user, material_id)


@router.post(
    "/materials/{material_id}/versions",
    response_model=MaterialDetailOut,
    status_code=201,
    operation_id="addMaterialVersion",
    summary="Save an uploaded file as the next version; older versions stay",
)
async def add_material_version(
    user: CurrentUserDep, materials: MaterialsDep, material_id: uuid.UUID, body: VersionCreateIn
) -> MaterialDetailOut:
    return await materials.add_version(
        user, material_id, body.upload_id, body.note, body.copyright_confirmed
    )


@router.get(
    "/materials/versions/{version_id}/download",
    response_model=MaterialDownloadOut,
    operation_id="downloadMaterialVersion",
    summary="A one-minute link to a clean version of a material I can read",
)
async def download_material_version(
    user: CurrentUserDep, materials: MaterialsDep, version_id: uuid.UUID, inline: bool = False
) -> MaterialDownloadOut:
    url, expires_at = await materials.download(user, version_id, inline=inline)
    return MaterialDownloadOut(url=url, expires_at=expires_at)


@router.post(
    "/materials/{material_id}/reports",
    response_model=MaterialReportCreatedOut,
    status_code=201,
    operation_id="reportMaterial",
    summary="Report a material (once per person)",
    responses={
        200: {"model": MaterialReportCreatedOut, "description": "Reported before by this person"}
    },
)
async def report_material(
    user: CurrentUserDep,
    materials: MaterialsDep,
    material_id: uuid.UUID,
    body: MaterialReportIn,
    response: Response,
) -> MaterialReportCreatedOut:
    report, duplicate = await materials.report(user, material_id, body.reason, body.note)
    if duplicate:
        response.status_code = 200
    return MaterialReportCreatedOut(id=str(report.id), status=report.status, duplicate=duplicate)


@router.get(
    "/moderation/material-reports",
    response_model=MaterialReportPageOut,
    operation_id="listMaterialReports",
    summary="Material reports, newest first",
)
async def list_material_reports(
    _: ReportReader,
    materials: MaterialsDep,
    status: MaterialReportStatus | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> MaterialReportPageOut:
    items, total = await materials.reports(status, offset, limit)
    return MaterialReportPageOut(items=items, total=total)


@router.patch(
    "/moderation/material-reports/{report_id}",
    status_code=204,
    operation_id="setMaterialReportStatus",
    summary="Mark a material report as actioned or dismissed (or open it again)",
)
async def set_material_report_status(
    actor: ReportHandler,
    materials: MaterialsDep,
    report_id: uuid.UUID,
    body: MaterialReportStatusIn,
) -> None:
    await materials.set_report_status(actor, report_id, body.status)


@router.patch(
    "/materials/{material_id}/visibility",
    status_code=204,
    operation_id="setMaterialVisibility",
    summary="Hide a material from the catalogue or show it again (staff)",
)
async def set_material_visibility(
    actor: CurrentUserDep, materials: MaterialsDep, material_id: uuid.UUID, body: VisibilityIn
) -> None:
    await materials.set_hidden(actor, material_id, body.hidden)
