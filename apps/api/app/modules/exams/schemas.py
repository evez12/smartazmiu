import uuid
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from app.modules.academics.coursework import CourseOfferingOut
from app.modules.exams.models import PastPaperKind, PastPaperStatus


class ExamOverlapOut(BaseModel):
    """Another exam that runs at the same time for the same students, the same offering or in the same room."""

    kind: Literal["offering", "group", "room"]
    slot_id: str
    offering: CourseOfferingOut
    starts_at: AwareDatetime
    ends_at: AwareDatetime


class ExamSlotOut(BaseModel):
    id: str
    offering: CourseOfferingOut
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    room_code: str | None
    overlaps: list[ExamOverlapOut] = []
    """Filled for staff only."""


class ExamSlotListOut(BaseModel):
    items: list[ExamSlotOut]


class ExamModeSubjectOut(BaseModel):
    id: str
    code: str
    name: str
    exam_mode: bool
    """False when staff switched exam mode off for the subject (D-104)."""
    upcoming_exams: int


class ExamModeSubjectListOut(BaseModel):
    items: list[ExamModeSubjectOut]


class ExamModeIn(BaseModel):
    enabled: bool


class ExamSlotIn(BaseModel):
    course_offering_id: uuid.UUID
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    room_code: str | None = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def ordered(self) -> "ExamSlotIn":
        if self.ends_at <= self.starts_at:
            raise ValueError("an exam ends after it starts")
        return self


class ExamSlotUpdateIn(BaseModel):
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    room_code: str | None = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def ordered(self) -> "ExamSlotUpdateIn":
        if self.ends_at <= self.starts_at:
            raise ValueError("an exam ends after it starts")
        return self


class PaperUploadIn(BaseModel):
    subject_id: uuid.UUID
    filename: str = Field(min_length=1, max_length=255)
    mime: str = Field(min_length=1, max_length=127)
    size: int = Field(gt=0)


class PaperUploadOut(BaseModel):
    upload_id: str
    url: str
    expires_at: AwareDatetime
    required_headers: dict[str, str]


class PaperIn(BaseModel):
    upload_id: uuid.UUID
    semester_id: uuid.UUID
    kind: PastPaperKind
    title: str = Field(min_length=3, max_length=200)
    consent: bool
    """The uploader's confirmation that the paper is from a finished semester and may be shared."""


class PaperReviewIn(BaseModel):
    approve: bool
    note: str = Field(default="", max_length=300)


class PaperOut(BaseModel):
    id: str
    subject_id: str
    semester: str
    kind: PastPaperKind
    title: str
    filename: str
    size_bytes: int
    status: PastPaperStatus
    scan_status: Literal["pending", "clean", "infected", "failed"]
    uploaded_by_me: bool
    can_review: bool
    can_download: bool
    review_note: str | None
    created_at: AwareDatetime


class PaperListOut(BaseModel):
    subject_id: str
    subject_name: str
    can_upload: bool
    items: list[PaperOut]


class PaperSubjectOut(BaseModel):
    id: str
    code: str
    name: str
    pending: int
    """Papers waiting for the user's decision; 0 when they cannot review."""


class PaperSubjectListOut(BaseModel):
    items: list[PaperSubjectOut]


class FinishedSemesterOut(BaseModel):
    id: str
    label: str


class PaperFormOut(BaseModel):
    """The finished semesters a paper can belong to: the integrity rule keeps the current one out (D-097)."""

    semesters: list[FinishedSemesterOut]


class PaperDownloadOut(BaseModel):
    url: str
    filename: str
    expires_at: datetime
