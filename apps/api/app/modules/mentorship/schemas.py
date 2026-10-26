from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.mentorship.models import (
    Availability,
    GradeVisibility,
    RequestFeedback,
    RequestStatus,
    RequestTopic,
)

GradeRange = Literal["51-70", "71-90", "91-100"]


class MentorPersonOut(BaseModel):
    id: str
    display_name: str
    photo_url: str | None


class EligibleSubjectOut(BaseModel):
    """A subject the signed-in person may guide, with their profile if they opted in."""

    subject_id: str
    subject_code: str
    subject_name: str
    semester: str
    """When they passed it, e.g. "2025 Payız"."""
    teacher_name: str | None
    grade: int | None
    """Their own grade, shown to them only (to choose a visibility)."""
    opted_in: bool


class GuideProfileIn(BaseModel):
    consent: bool
    grade_visibility: GradeVisibility = GradeVisibility.HIDDEN
    show_teacher: bool = False
    bio: str = Field(default="", max_length=300)
    availability: Availability = Availability.AVAILABLE
    max_open_requests: int = Field(default=3, ge=1, le=10)


class GuideProfilePatch(BaseModel):
    grade_visibility: GradeVisibility | None = None
    show_teacher: bool | None = None
    bio: str | None = Field(default=None, max_length=300)
    availability: Availability | None = None
    max_open_requests: int | None = Field(default=None, ge=1, le=10)


class GuideStatsOut(BaseModel):
    helped_count: int
    helpful_count: int
    unhelpful_count: int
    helpful_rate: float | None
    """Share of "helpful" among rated requests; None before the first rating."""
    avg_response_minutes: int | None


class MyGuideProfileOut(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    subject_id: str
    subject_name: str
    semester: str
    grade_visibility: GradeVisibility
    show_teacher: bool
    bio: str
    availability: Availability
    max_open_requests: int
    active: bool
    """False once a results correction revoked the status (§5.2)."""
    stats: GuideStatsOut


class GuideOut(BaseModel):
    """A guide in the directory: what the guide chose to show, never contact data (§5.4)."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    user: MentorPersonOut
    semester: str
    semester_id: str
    teacher_name: str | None
    """Only when the guide allows it."""
    teacher_id: str | None
    specialty_name: str | None
    specialty_id: str | None
    grade_exact: int | None
    grade_range: GradeRange | None
    bio: str
    availability: Availability
    same_teacher: bool
    same_specialty: bool
    stats: GuideStatsOut


class FilterOptionOut(BaseModel):
    id: str
    label: str


class GuideDirectoryOut(BaseModel):
    subject_id: str
    subject_name: str
    subject_code: str
    guides: list[GuideOut]
    specialties: list[FilterOptionOut]
    semesters: list[FilterOptionOut]
    teachers: list[FilterOptionOut]
    i_am_guide: bool


class MentorRequestIn(BaseModel):
    subject_id: str
    mentor_id: str | None = None
    topic: RequestTopic
    body: str = Field(min_length=1, max_length=2000)


class MentorRequestOut(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    id: str
    subject_id: str
    subject_name: str
    requester: MentorPersonOut
    mentor: MentorPersonOut | None
    topic: RequestTopic
    body: str
    status: RequestStatus
    dm_channel_id: str | None
    feedback: RequestFeedback | None
    """Visible to the two people involved; the private note never is."""
    created_at: datetime
    expires_at: datetime | None
    role: Literal["requester", "mentor", "candidate"]
    """How the viewer relates to it: candidate = a guide who may accept an unaddressed request."""
    can_accept: bool
    can_decline: bool
    can_resolve: bool
    can_give_feedback: bool


class MentorRequestListOut(BaseModel):
    items: list[MentorRequestOut]


class MentorFeedbackIn(BaseModel):
    feedback: RequestFeedback
    note: str = Field(default="", max_length=1000)


class FeedbackNoteOut(BaseModel):
    """Staff view of feedback with a private note (§5.2)."""

    request_id: str
    subject_name: str
    mentor: MentorPersonOut | None
    feedback: RequestFeedback
    note: str
    created_at: datetime


class FeedbackNotePageOut(BaseModel):
    items: list[FeedbackNoteOut]
    total: int
