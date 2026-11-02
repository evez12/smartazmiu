from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel

from app.modules.academics.models import SemesterTerm
from app.modules.cabinet.models import SyncOutcome, SyncTrigger
from app.modules.cabinet.provider import AppealStatus


class SourceState(StrEnum):
    OK = "ok"
    UNAVAILABLE = "unavailable"
    NEVER_SYNCED = "never_synced"


class SourceOut(BaseModel):
    """Whether the cabinet data is current. ``unavailable`` means the latest run failed: the figures shown are
    from the last successful one, at ``last_synced_at``."""

    state: SourceState
    last_synced_at: datetime | None


class TranscriptCourseOut(BaseModel):
    subject_code: str
    subject_name: str
    credits: int
    score: int
    passed: bool
    # The registry holds another grade for this course. The score shown is the registry one (D-126).
    differs: bool


class TranscriptSemesterOut(BaseModel):
    semester_year: int
    semester_term: SemesterTerm
    credits_attempted: int | None
    credits_earned: int | None
    average: float | None
    courses: list[TranscriptCourseOut]


class CabinetStudentOut(BaseModel):
    specialty_name: str
    credits_earned: int
    cumulative_average: float | None
    synced_at: datetime


class TranscriptOut(BaseModel):
    source: SourceOut
    student: CabinetStudentOut | None
    semesters: list[TranscriptSemesterOut]


class AppealOut(BaseModel):
    reference: str
    subject_code: str
    subject_name: str | None
    semester_year: int
    semester_term: SemesterTerm
    status: AppealStatus
    submitted_on: date
    decided_on: date | None


class AppealListOut(BaseModel):
    source: SourceOut
    items: list[AppealOut]


class SyncRunOut(BaseModel):
    id: str
    trigger: SyncTrigger
    outcome: SyncOutcome
    started_at: datetime
    finished_at: datetime
    students_synced: int
    students_not_found: int
    students_mismatched: int
    conflicts: int
    error_code: str | None


class SyncRunListOut(BaseModel):
    source: SourceOut
    items: list[SyncRunOut]


class ConflictOut(BaseModel):
    """Which course differs for whom. Neither grade is included (D-126)."""

    university_id: str
    subject_code: str
    semester_year: int
    semester_term: SemesterTerm
    detected_at: datetime


class ConflictListOut(BaseModel):
    items: list[ConflictOut]


class SyncRequestedOut(BaseModel):
    """The run is queued; its result appears in the list of runs."""

    queued: bool
