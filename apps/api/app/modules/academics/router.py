import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import select

from app.core.deps import JobsDep, RedisDep, SessionDep
from app.core.errors import COMMON_ERROR_RESPONSES, AppError
from app.core.ratelimit import RateLimit, enforce_rate_limit
from app.core.rbac import CurrentUserDep, require_permission
from app.modules.academics.files import MAX_FILE_BYTES, FileEncoding, UnreadableFileError
from app.modules.academics.import_service import ImportService, expires_at
from app.modules.academics.models import AcademicImport, ImportKind, ImportStatus
from app.modules.academics.registry import SPECS
from app.modules.academics.schemas import (
    CourseOut,
    GroupPlacementOut,
    ImportCounts,
    ImportDetail,
    ImportIssueOut,
    ImportOut,
    ImportPageOut,
    MyAcademicsResponse,
    NamedCode,
    PersonRef,
    SemesterRef,
    SubjectRef,
    TeachingCourseOut,
)
from app.modules.academics.service import AcademicsService, Course
from app.modules.users.models import User
from app.modules.users.service import CurrentUser

IMPORT_PERMISSION = "academics.import"
IMPORT_UPLOADS = RateLimit("import_upload", limit=60, window_seconds=3600)
AUDIENCE_KINDS = frozenset(
    {ImportKind.GROUPS, ImportKind.STUDENTS, ImportKind.OFFERINGS, ImportKind.ENROLLMENTS}
)

router = APIRouter(responses=COMMON_ERROR_RESPONSES)
Importer = Annotated[CurrentUser, Depends(require_permission(IMPORT_PERMISSION))]


@router.get(
    "/me/academics",
    response_model=MyAcademicsResponse,
    operation_id="readMyAcademics",
    summary="My group and current subjects",
    tags=["academics"],
)
async def read_my_academics(user: CurrentUserDep, session: SessionDep) -> MyAcademicsResponse:
    overview = await AcademicsService(session).overview(user.id)
    placement = overview.placement
    return MyAcademicsResponse(
        group=GroupPlacementOut(
            code=placement.group.code,
            admission_year=placement.group.admission_year,
            language=placement.group.language,
            specialty=NamedCode(code=placement.specialty.code, name=placement.specialty.name_az),
            faculty=NamedCode(code=placement.faculty.code, name=placement.faculty.name_az),
        )
        if placement
        else None,
        courses=[CourseOut(**_course_fields(course)) for course in overview.courses],
        teaching=[
            TeachingCourseOut(**_course_fields(course), student_count=course.student_count)
            for course in overview.teaching
        ],
    )


def _course_fields(course: Course) -> dict[str, object]:
    return {
        "offering_id": str(course.offering.id),
        "offering_code": course.offering.code,
        "subject": SubjectRef(
            code=course.subject.code, name=course.subject.name_az, credits=course.subject.credits
        ),
        "semester": SemesterRef(year=course.semester.year, term=course.semester.term),
        "groups": course.group_codes,
        "teachers": course.teacher_names,
    }


imports = APIRouter(prefix="/admin/imports", tags=["imports"], responses=COMMON_ERROR_RESPONSES)


@imports.get("", response_model=ImportPageOut, operation_id="listImports", summary="Imports")
async def list_imports(
    _: Importer,
    session: SessionDep,
    kind: ImportKind | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> ImportPageOut:
    page = await ImportService(session).page(kind=kind, offset=offset, limit=limit)
    people = await _people(session, page.items)
    return ImportPageOut(
        items=[ImportOut(**_import_fields(record, people)) for record in page.items],
        total=page.total,
    )


@imports.post(
    "",
    response_model=ImportDetail,
    status_code=201,
    operation_id="createImport",
    summary="Upload a CSV/XLSX file and validate it (dry run)",
    responses={413: COMMON_ERROR_RESPONSES[422] | {"description": "File larger than 5 MB"}},
)
async def create_import(
    user: Importer,
    session: SessionDep,
    redis: RedisDep,
    kind: Annotated[ImportKind, Form()],
    file: Annotated[UploadFile, File()],
    encoding: Annotated[FileEncoding | None, Form()] = None,
) -> ImportDetail:
    await enforce_rate_limit(redis, IMPORT_UPLOADS, str(user.id))
    data = await file.read(MAX_FILE_BYTES + 1)
    try:
        record = await ImportService(session).create(
            kind, file.filename or "", data, encoding, user.id
        )
    except UnreadableFileError as exc:
        raise AppError(exc.code, 413 if exc.code == "import.file_too_large" else 422) from exc
    return await _detail(session, record)


@imports.get(
    "/templates/{kind}",
    response_class=Response,
    operation_id="downloadImportTemplate",
    summary="Empty CSV template with the expected header",
    responses={200: {"content": {"text/csv": {}}, "description": "CSV header row"}},
)
async def download_import_template(_: Importer, kind: ImportKind) -> Response:
    # The byte-order mark makes Excel open the file as UTF-8, so Azerbaijani letters survive a round trip.
    return Response(
        content=f"\ufeff{SPECS[kind].template()}\r\n",
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{kind.value}.csv"'},
    )


@imports.get(
    "/{import_id}", response_model=ImportDetail, operation_id="readImport", summary="Import"
)
async def read_import(_: Importer, session: SessionDep, import_id: uuid.UUID) -> ImportDetail:
    return await _detail(session, await ImportService(session).get(import_id))


@imports.post(
    "/{import_id}/apply",
    response_model=ImportDetail,
    operation_id="applyImport",
    summary="Apply a validated import in one transaction",
)
async def apply_import(
    user: Importer, session: SessionDep, jobs: JobsDep, import_id: uuid.UUID
) -> ImportDetail:
    record = await ImportService(session).apply(import_id, user.id)
    if record.status is ImportStatus.APPLIED and record.kind in AUDIENCE_KINDS:
        # Registry changes can move people into an audience; they receive its active announcements (§6.1).
        await jobs.sync_audiences()
    if record.status is ImportStatus.APPLIED and record.kind is ImportKind.SCHEDULE_CHANGES:
        await jobs.dispatch_notifications()
    return await _detail(session, record)


async def _detail(session: SessionDep, record: AcademicImport) -> ImportDetail:
    people = await _people(session, [record])
    return ImportDetail(
        **_import_fields(record, people),
        errors=[ImportIssueOut(**issue) for issue in record.errors],
        previously_applied_at=await ImportService(session).previously_applied_at(record),
    )


async def _people(session: SessionDep, records: list[AcademicImport]) -> dict[uuid.UUID, PersonRef]:
    ids = {i for record in records for i in (record.created_by, record.applied_by) if i}
    if not ids:
        return {}
    rows = await session.execute(select(User.id, User.display_name).where(User.id.in_(ids)))
    return {user_id: PersonRef(id=str(user_id), display_name=name) for user_id, name in rows}


def _import_fields(record: AcademicImport, people: dict[uuid.UUID, PersonRef]) -> dict[str, object]:
    return {
        "id": str(record.id),
        "kind": record.kind,
        "status": record.status,
        "file_name": record.file_name,
        "encoding": FileEncoding(record.encoding) if record.encoding else None,
        "row_count": record.row_count,
        "summary": ImportCounts(**record.summary),
        "error_count": record.error_count,
        "created_at": record.created_at,
        "created_by": people.get(record.created_by) if record.created_by else None,
        "applied_at": record.applied_at,
        "applied_by": people.get(record.applied_by) if record.applied_by else None,
        "expires_at": expires_at(record),
    }
