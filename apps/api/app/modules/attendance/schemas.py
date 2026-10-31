import uuid
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from app.modules.academics.coursework import CourseOfferingOut


class AttendanceOfferingOut(CourseOfferingOut):
    """An offering whose attendance the user runs (``manager``) or only reads as a group curator."""

    role: Literal["manager", "curator"]


class AttendanceOfferingListOut(BaseModel):
    items: list[AttendanceOfferingOut]


class AttendanceSessionOpenIn(BaseModel):
    course_offering_id: uuid.UUID
    title: str = Field(default="", max_length=120)
    duration_minutes: int = Field(default=90, ge=5, le=240)


class AttendanceSessionOut(BaseModel):
    id: str
    offering: CourseOfferingOut
    title: str
    opened_at: AwareDatetime
    expires_at: AwareDatetime
    closed_at: AwareDatetime | None
    is_open: bool
    present: int
    enrolled: int


class AttendanceSessionListOut(BaseModel):
    items: list[AttendanceSessionOut]


class AttendanceRosterEntryOut(BaseModel):
    student_id: str
    display_name: str
    university_id: str | None
    group: str | None
    present: bool
    method: Literal["qr", "code", "manual"] | None
    checked_in_at: AwareDatetime | None
    reason: str | None


class AttendanceSessionDetailOut(AttendanceSessionOut):
    roster: list[AttendanceRosterEntryOut]


class AttendanceCodeOut(BaseModel):
    """What the teacher's screen shows now; ``valid_until`` is when the next code replaces it."""

    qr: str
    digits: str
    valid_until: AwareDatetime
    server_time: AwareDatetime
    present: int
    enrolled: int
    is_open: bool


class AttendanceMarkIn(BaseModel):
    present: bool
    reason: str = Field(min_length=3, max_length=300)


class AttendanceCheckInIn(BaseModel):
    qr: str | None = Field(default=None, max_length=200)
    digits: str | None = Field(default=None, pattern=r"^\s*\d{6}\s*$")

    @model_validator(mode="after")
    def exactly_one(self) -> "AttendanceCheckInIn":
        if (self.qr is None) == (self.digits is None):
            raise ValueError("send either the scanned code or the six digits")
        return self


class AttendanceCheckInOut(BaseModel):
    session_id: str
    offering: CourseOfferingOut
    checked_in_at: AwareDatetime
    already_present: bool


class MyAttendanceSessionOut(BaseModel):
    id: str
    title: str
    opened_at: AwareDatetime
    present: bool


class MyAttendanceOut(BaseModel):
    offering: CourseOfferingOut
    attended: int
    total: int
    rate: float
    sessions: list[MyAttendanceSessionOut] = []


class MyAttendanceListOut(BaseModel):
    items: list[MyAttendanceOut]


class AttendanceReportSessionOut(BaseModel):
    id: str
    title: str
    opened_at: AwareDatetime


class AttendanceReportRowOut(BaseModel):
    student_id: str
    display_name: str
    university_id: str | None
    group: str | None
    attended: int
    total: int
    rate: float
    marks: list[bool]


class AttendanceReportOut(BaseModel):
    offering: CourseOfferingOut
    sessions: list[AttendanceReportSessionOut]
    rows: list[AttendanceReportRowOut]
