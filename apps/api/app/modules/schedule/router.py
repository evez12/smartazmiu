from datetime import date, time, timedelta
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import Response
from sqlalchemy import select

from app.core.deps import SessionDep
from app.core.errors import COMMON_ERROR_RESPONSES, AppError
from app.core.rbac import CurrentUserDep
from app.core.time import baku_today, utc_now
from app.modules.academics.models import Semester
from app.modules.schedule import ics
from app.modules.schedule.parity import week_start
from app.modules.schedule.schemas import (
    ClassOut,
    MovedToOut,
    ScheduleDayOut,
    ScheduleOut,
    ScheduleRoomOut,
    ScheduleSubjectOut,
)
from app.modules.schedule.service import MAX_RANGE_DAYS, Occurrence, ScheduleService

router = APIRouter(prefix="/me", tags=["schedule"], responses=COMMON_ERROR_RESPONSES)


def _clock(value: time) -> str:
    return f"{value:%H:%M}"


def _class_out(occurrence: Occurrence) -> ClassOut:
    room = occurrence.room
    moved = occurrence.moved_to
    return ClassOut(
        id=f"{occurrence.entry_id}:{occurrence.original_day.isoformat()}",
        date=occurrence.day,
        starts_at=_clock(occurrence.starts_at),
        ends_at=_clock(occurrence.ends_at),
        subject=ScheduleSubjectOut(code=occurrence.subject.code, name=occurrence.subject.name_az),
        class_type=occurrence.class_type,
        room=ScheduleRoomOut(
            code=room.code, name=room.name, building=room.building_name, floor=room.floor_name
        )
        if room
        else None,
        teachers=occurrence.teachers,
        groups=occurrence.groups,
        status=occurrence.status,
        original_date=occurrence.original_day,
        original_starts_at=_clock(occurrence.original_starts_at),
        moved_to=MovedToOut(date=moved[0], starts_at=_clock(moved[1]), ends_at=_clock(moved[2]))
        if moved
        else None,
        room_changed=occurrence.room_changed,
        teacher_changed=occurrence.teacher_changed,
        note=occurrence.note,
    )


@router.get(
    "/schedule",
    response_model=ScheduleOut,
    operation_id="readMySchedule",
    summary="My classes per day (default: the current week)",
    responses={422: COMMON_ERROR_RESPONSES[422]},
)
async def read_my_schedule(
    user: CurrentUserDep,
    session: SessionDep,
    start: Annotated[
        date | None, Query(description="First day; default Monday of this week")
    ] = None,
    end: Annotated[
        date | None, Query(description="Last day (inclusive); default start + 6")
    ] = None,
) -> ScheduleOut:
    today = baku_today()
    first = start or week_start(today)
    last = end or first + timedelta(days=6)
    if last < first or (last - first).days >= MAX_RANGE_DAYS:
        raise AppError("schedule.invalid_range", 422)
    days = await ScheduleService(session).days(user.id, first, last)
    return ScheduleOut(
        start=first,
        end=last,
        today=today,
        days=[
            ScheduleDayOut(
                date=day.day,
                parity=day.parity,
                classes=[_class_out(occurrence) for occurrence in day.occurrences],
            )
            for day in days
        ],
    )


@router.get(
    "/schedule.ics",
    response_class=Response,
    operation_id="downloadMySchedule",
    summary="My classes of the current semester as an iCalendar file",
    responses={200: {"content": {"text/calendar": {}}, "description": "iCalendar file"}},
)
async def download_my_schedule(user: CurrentUserDep, session: SessionDep) -> Response:
    today = baku_today()
    # The running semester, or the next one during a break; an empty calendar when none is known.
    semester = await session.scalar(
        select(Semester).where(Semester.ends_on >= today).order_by(Semester.starts_on).limit(1)
    )
    occurrences: list[Occurrence] = []
    if semester is not None:
        days = await ScheduleService(session).days(user.id, semester.starts_on, semester.ends_on)
        occurrences = [occurrence for day in days for occurrence in day.occurrences]
    return Response(
        content=ics.calendar(occurrences, utc_now()),
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="ders-cedveli.ics"',
            "Cache-Control": "no-store",
        },
    )
