from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.feedback.models import FeedbackCategory, FeedbackStatus


class FeedbackIn(BaseModel):
    category: FeedbackCategory
    message: str = Field(min_length=1, max_length=2000)
    page: str = Field(default="", max_length=300)
    contact_ok: bool = False


class FeedbackCreatedOut(BaseModel):
    id: str


class FeedbackPerson(BaseModel):
    id: str
    display_name: str
    email: str | None
    """Only when the sender allowed being contacted (§5.4)."""


class FeedbackOut(BaseModel):
    id: str
    category: FeedbackCategory
    message: str
    page: str
    contact_ok: bool
    status: FeedbackStatus
    sender: FeedbackPerson | None
    handled_by: str | None
    """Display name of the staff member who closed it."""
    handled_at: datetime | None
    created_at: datetime


class FeedbackPageOut(BaseModel):
    items: list[FeedbackOut]
    total: int


class FeedbackStatusIn(BaseModel):
    status: FeedbackStatus
