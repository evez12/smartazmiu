import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response

from app.core.deps import RedisDep, SessionDep, SettingsDep
from app.core.errors import COMMON_ERROR_RESPONSES
from app.core.rbac import CurrentUserDep
from app.modules.attendance import export
from app.modules.attendance.schemas import (
    AttendanceCheckInIn,
    AttendanceCheckInOut,
    AttendanceCodeOut,
    AttendanceMarkIn,
    AttendanceOfferingListOut,
    AttendanceReportOut,
    AttendanceRosterEntryOut,
    AttendanceSessionDetailOut,
    AttendanceSessionListOut,
    AttendanceSessionOpenIn,
    AttendanceSessionOut,
    MyAttendanceListOut,
    MyAttendanceOut,
)
from app.modules.attendance.service import AttendanceService

router = APIRouter(prefix="/attendance", tags=["attendance"], responses=COMMON_ERROR_RESPONSES)


def get_attendance(
    session: SessionDep, cache: RedisDep, settings: SettingsDep
) -> AttendanceService:
    return AttendanceService(session, cache, settings)


AttendanceDep = Annotated[AttendanceService, Depends(get_attendance)]


@router.get(
    "/offerings",
    response_model=AttendanceOfferingListOut,
    operation_id="listAttendanceOfferings",
    summary="Offerings whose attendance I run or read as a curator",
)
async def list_offerings(user: CurrentUserDep, service: AttendanceDep) -> AttendanceOfferingListOut:
    return AttendanceOfferingListOut(items=await service.offerings(user))


@router.get(
    "/sessions",
    response_model=AttendanceSessionListOut,
    operation_id="listAttendanceSessions",
    summary="Meetings of one offering, newest first",
)
async def list_sessions(
    user: CurrentUserDep, service: AttendanceDep, offering_id: Annotated[uuid.UUID, Query()]
) -> AttendanceSessionListOut:
    return AttendanceSessionListOut(items=await service.sessions(user, offering_id))


@router.post(
    "/sessions",
    response_model=AttendanceSessionOut,
    status_code=201,
    operation_id="openAttendanceSession",
    summary="Open a meeting for check-in",
)
async def open_session(
    user: CurrentUserDep, service: AttendanceDep, body: AttendanceSessionOpenIn
) -> AttendanceSessionOut:
    return await service.open_session(user, body)


@router.get(
    "/sessions/{session_id}",
    response_model=AttendanceSessionDetailOut,
    operation_id="getAttendanceSession",
    summary="A meeting with its roster",
)
async def get_session(
    user: CurrentUserDep, service: AttendanceDep, session_id: uuid.UUID
) -> AttendanceSessionDetailOut:
    return await service.detail(user, session_id)


@router.get(
    "/sessions/{session_id}/code",
    response_model=AttendanceCodeOut,
    operation_id="getAttendanceCode",
    summary="The code to show on the teacher screen now",
)
async def get_code(
    user: CurrentUserDep, service: AttendanceDep, session_id: uuid.UUID
) -> AttendanceCodeOut:
    return await service.current_code(user, session_id)


@router.post(
    "/sessions/{session_id}/close",
    response_model=AttendanceSessionOut,
    operation_id="closeAttendanceSession",
    summary="Stop check-in for a meeting",
)
async def close_session(
    user: CurrentUserDep, service: AttendanceDep, session_id: uuid.UUID
) -> AttendanceSessionOut:
    return await service.close_session(user, session_id)


@router.put(
    "/sessions/{session_id}/students/{student_id}",
    response_model=AttendanceRosterEntryOut,
    operation_id="markAttendance",
    summary="Mark or unmark a student by hand, with a reason",
)
async def mark(
    user: CurrentUserDep,
    service: AttendanceDep,
    session_id: uuid.UUID,
    student_id: uuid.UUID,
    body: AttendanceMarkIn,
) -> AttendanceRosterEntryOut:
    return await service.mark(user, session_id, student_id, body)


@router.post(
    "/check-in",
    response_model=AttendanceCheckInOut,
    operation_id="checkInAttendance",
    summary="Check in with a scanned code or the six digits",
)
async def check_in(
    request: Request, user: CurrentUserDep, service: AttendanceDep, body: AttendanceCheckInIn
) -> AttendanceCheckInOut:
    device = request.client.host if request.client else "unknown"
    return await service.check_in(user, body, device)


@router.get(
    "/my",
    response_model=MyAttendanceListOut,
    operation_id="listMyAttendance",
    summary="My attendance rate in each course",
)
async def my_attendance(user: CurrentUserDep, service: AttendanceDep) -> MyAttendanceListOut:
    return MyAttendanceListOut(items=await service.mine(user))


@router.get(
    "/my/{offering_id}",
    response_model=MyAttendanceOut,
    operation_id="getMyAttendance",
    summary="My attendance in one course, meeting by meeting",
)
async def my_attendance_in(
    user: CurrentUserDep, service: AttendanceDep, offering_id: uuid.UUID
) -> MyAttendanceOut:
    return await service.mine_in(user, offering_id)


@router.get(
    "/offerings/{offering_id}/report",
    response_model=AttendanceReportOut,
    operation_id="getAttendanceReport",
    summary="Attendance of every student in an offering",
)
async def report(
    user: CurrentUserDep, service: AttendanceDep, offering_id: uuid.UUID
) -> AttendanceReportOut:
    return await service.report(user, offering_id)


@router.get(
    "/offerings/{offering_id}/report.{extension}",
    response_class=Response,
    operation_id="exportAttendanceReport",
    summary="The attendance report as CSV or XLSX",
    responses={200: {"content": {"text/csv": {}, export.XLSX_TYPE: {}}, "description": "File"}},
)
async def export_report(
    user: CurrentUserDep,
    service: AttendanceDep,
    offering_id: uuid.UUID,
    extension: Literal["csv", "xlsx"],
) -> Response:
    data = await service.report(user, offering_id)
    if extension == "csv":
        content, media_type = export.to_csv(data), "text/csv; charset=utf-8"
    else:
        content, media_type = export.to_xlsx(data), export.XLSX_TYPE
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="attendance.{extension}"'},
    )
