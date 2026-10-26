from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.chat.schemas import AuthorOut
from app.modules.reports.models import ReportReason, ReportStatus, ReportTarget


class ReportIn(BaseModel):
    target_type: ReportTarget
    target_id: str = Field(min_length=1, max_length=64)
    reason: ReportReason
    note: str = Field(default="", max_length=500)


class ReportCreatedOut(BaseModel):
    id: str
    status: ReportStatus
    duplicate: bool
    """True when this person had already reported this target: nothing new was recorded (§5.5)."""


class ReportedMessageOut(BaseModel):
    id: str
    channel_id: str
    channel_name: str
    author: AuthorOut | None
    body: str
    """The text as reported, so staff can judge it even after the author deleted the message."""
    deleted: bool
    created_at: datetime


class ReportOut(BaseModel):
    id: str
    target_type: ReportTarget
    reason: ReportReason
    note: str
    status: ReportStatus
    created_at: datetime
    reporter: AuthorOut | None
    reported_user: AuthorOut | None
    """The reported person, or the author of the reported message."""
    message: ReportedMessageOut | None
    handled_by: AuthorOut | None
    handled_at: datetime | None
    reporters: int
    """How many different people reported the same target."""


class ReportPageOut(BaseModel):
    items: list[ReportOut]
    total: int


class ReportStatusIn(BaseModel):
    status: ReportStatus
