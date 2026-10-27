from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.knowledge.models import TipStatus, WeeklyHours


class TipResourceIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    url: str | None = Field(default=None, max_length=500)
    material_id: str | None = None


class TipIn(BaseModel):
    semester_id: str
    difficulty: int = Field(ge=1, le=5)
    weekly_hours: WeeklyHours
    key_topics: str = Field(min_length=1, max_length=1000)
    resources: list[TipResourceIn] = Field(default_factory=list, max_length=10)
    exam_advice: str = Field(min_length=1, max_length=2000)
    retrospective: str = Field(min_length=1, max_length=2000)


class TipResourceOut(BaseModel):
    title: str
    url: str | None
    material_id: str | None


class TipOut(BaseModel):
    """A published tip as students see it: the semester, never the author's name or grade (D-084)."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    id: str
    semester: str
    difficulty: int
    weekly_hours: WeeklyHours
    key_topics: str
    resources: list[TipResourceOut]
    exam_advice: str
    retrospective: str
    upvotes: int
    upvoted: bool
    mine: bool
    updated_at: datetime


class WorkloadOut(BaseModel):
    weekly_hours: WeeklyHours
    count: int


class AggregatedResourceOut(BaseModel):
    title: str
    url: str | None
    material_id: str | None
    mentions: int


class SubjectTipsOut(BaseModel):
    subject_id: str
    subject_name: str
    subject_code: str
    tip_count: int
    average_difficulty: float | None
    workload: list[WorkloadOut]
    """Published tips per weekly-hours band, in band order."""
    resources: list[AggregatedResourceOut]
    tips: list[TipOut]
    """Most upvoted first."""


class MyTipOut(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    id: str
    subject_id: str
    semester_id: str
    semester: str
    status: TipStatus
    difficulty: int
    weekly_hours: WeeklyHours
    key_topics: str
    resources: list[TipResourceOut]
    exam_advice: str
    retrospective: str
    updated_at: datetime


class TipEligibilityOut(BaseModel):
    """A subject and semester the person passed, and their card for it if any."""

    subject_id: str
    subject_name: str
    semester_id: str
    semester: str
    tip_status: TipStatus | None


class TipModerationOut(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    id: str
    subject_name: str
    semester: str
    author_name: str | None
    status: TipStatus
    difficulty: int
    weekly_hours: WeeklyHours
    key_topics: str
    resources: list[TipResourceOut]
    exam_advice: str
    retrospective: str
    moderation_note: str
    upvotes: int
    reports: int
    updated_at: datetime


class TipModerationPageOut(BaseModel):
    items: list[TipModerationOut]
    total: int


class TipReviewIn(BaseModel):
    status: TipStatus
    note: str = Field(default="", max_length=500)
