from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.academics.files import FileEncoding
from app.modules.academics.models import (
    ImportKind,
    ImportStatus,
    InstructionLanguage,
    SemesterTerm,
)


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class NamedCode(_Frozen):
    code: str
    name: str


class SemesterRef(_Frozen):
    year: int
    term: SemesterTerm


class SubjectRef(_Frozen):
    code: str
    name: str
    credits: int


class GroupPlacementOut(_Frozen):
    code: str
    admission_year: int
    language: InstructionLanguage
    specialty: NamedCode
    faculty: NamedCode


class CourseOut(_Frozen):
    offering_id: str
    offering_code: str
    subject: SubjectRef
    semester: SemesterRef
    groups: list[str]
    teachers: list[str]
    """Display names only; teachers' contact details are not part of this view."""


class TeachingCourseOut(CourseOut):
    student_count: int


class MyAcademicsResponse(_Frozen):
    """The signed-in user's group and current subjects. Grades are never part of this payload (§5.4)."""

    group: GroupPlacementOut | None
    courses: list[CourseOut]
    teaching: list[TeachingCourseOut]


class PersonRef(_Frozen):
    id: str
    display_name: str


class ImportCounts(_Frozen):
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    removed: int = 0
    """Timetable entries that the file no longer contains (schedule imports only)."""


class ImportIssueOut(_Frozen):
    row: int | None
    """Excel row number (the header is row 1); null for problems with the whole file."""
    column: str | None
    code: str


class ImportOut(_Frozen):
    id: str
    kind: ImportKind
    status: ImportStatus
    file_name: str
    encoding: FileEncoding | None
    row_count: int
    summary: ImportCounts
    error_count: int
    created_at: datetime
    created_by: PersonRef | None
    applied_at: datetime | None
    applied_by: PersonRef | None
    expires_at: datetime | None
    """Until when a ready preview can be applied."""


class ImportDetail(ImportOut):
    errors: list[ImportIssueOut]
    """At most the first 1 000 problems; ``error_count`` has the total."""
    previously_applied_at: datetime | None
    """Set when the same file was applied before, in which case applying it again changes nothing."""


class ImportPageOut(_Frozen):
    items: list[ImportOut]
    total: int
