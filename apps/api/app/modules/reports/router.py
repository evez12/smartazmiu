import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.core.deps import RedisDep, SessionDep
from app.core.errors import COMMON_ERROR_RESPONSES
from app.core.rbac import CurrentUserDep, require_permission
from app.modules.chat.deps import AccessDep
from app.modules.reports.models import ReportStatus
from app.modules.reports.schemas import (
    ReportCreatedOut,
    ReportIn,
    ReportOut,
    ReportPageOut,
    ReportStatusIn,
)
from app.modules.reports.service import ReportService
from app.modules.users.service import CurrentUser

REPORTS_READ = "admin.reports.read"
REPORTS_HANDLE = "admin.reports.handle"

router = APIRouter(tags=["reports"], responses=COMMON_ERROR_RESPONSES)
ReportReader = Annotated[CurrentUser, Depends(require_permission(REPORTS_READ))]
ReportHandler = Annotated[CurrentUser, Depends(require_permission(REPORTS_HANDLE))]


def get_reports(session: SessionDep, access: AccessDep, cache: RedisDep) -> ReportService:
    return ReportService(session, access, cache)


ReportsDep = Annotated[ReportService, Depends(get_reports)]


@router.post(
    "/reports",
    response_model=ReportCreatedOut,
    status_code=201,
    operation_id="createReport",
    summary="Report a message or a person (once per target)",
    responses={200: {"model": ReportCreatedOut, "description": "Reported before by this person"}},
)
async def create_report(
    user: CurrentUserDep, reports: ReportsDep, body: ReportIn, response: Response
) -> ReportCreatedOut:
    created = await reports.create(user, body.target_type, body.target_id, body.reason, body.note)
    if created.duplicate:
        response.status_code = 200
    return ReportCreatedOut(
        id=str(created.report.id), status=created.report.status, duplicate=created.duplicate
    )


@router.get(
    "/moderation/reports",
    response_model=ReportPageOut,
    operation_id="listReports",
    summary="Reports, newest first",
)
async def list_reports(
    _: ReportReader,
    reports: ReportsDep,
    status: ReportStatus | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> ReportPageOut:
    page = await reports.page(status, offset, limit)
    return ReportPageOut(items=page.items, total=page.total)


@router.patch(
    "/moderation/reports/{report_id}",
    response_model=ReportOut,
    operation_id="setReportStatus",
    summary="Mark a report as actioned or dismissed (or open it again)",
)
async def set_report_status(
    actor: ReportHandler, reports: ReportsDep, report_id: uuid.UUID, body: ReportStatusIn
) -> ReportOut:
    return await reports.set_status(actor, report_id, body.status)
