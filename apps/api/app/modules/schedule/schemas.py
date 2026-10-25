import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.modules.schedule.models import ClassType
from app.modules.schedule.service import OccurrenceStatus


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class ScheduleSubjectOut(_Frozen):
    code: str
    name: str


class ScheduleRoomOut(_Frozen):
    code: str
    name: str
    building: str
    floor: str


class MovedToOut(_Frozen):
    date: dt.date
    starts_at: str
    ends_at: str


class ClassOut(_Frozen):
    id: str
    """Stable per occurrence: entry id and original date."""
    date: dt.date
    starts_at: str
    """Baku wall-clock time, ``HH:MM``."""
    ends_at: str
    subject: ScheduleSubjectOut
    class_type: ClassType
    room: ScheduleRoomOut | None
    teachers: list[str]
    groups: list[str]
    status: OccurrenceStatus
    original_date: dt.date
    original_starts_at: str
    moved_to: MovedToOut | None
    """Set on the original day of a class that was moved to another day."""
    room_changed: bool
    teacher_changed: bool
    note: str


class ScheduleDayOut(_Frozen):
    date: dt.date
    parity: Literal["upper", "lower"] | None
    """``upper`` or ``lower``; null on days outside every semester."""
    classes: list[ClassOut]


class ScheduleOut(_Frozen):
    start: dt.date
    end: dt.date
    today: dt.date
    """Today in Asia/Baku."""
    days: list[ScheduleDayOut]
