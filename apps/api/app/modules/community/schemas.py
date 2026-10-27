import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.community.models import ReportReason


class CursorPage(BaseModel):
    next_cursor: str | None = None


class PostCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10000)
    tag_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)


class PostOut(BaseModel):
    id: uuid.UUID
    author_id: uuid.UUID
    body: str
    helpful_count: int = 0
    comment_count: int = 0
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    version_id: int


class PostPage(CursorPage):
    items: list[PostOut]


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class CommentOut(BaseModel):
    id: uuid.UUID
    post_id: uuid.UUID
    author_id: uuid.UUID
    body: str
    created_at: datetime
    version_id: int


class CommunityReportIn(BaseModel):
    reason: ReportReason
    details: str = Field(default="", max_length=500)


class QuestionCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=1, max_length=20000)
    tag_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)


class QuestionOut(BaseModel):
    id: uuid.UUID
    author_id: uuid.UUID
    title: str
    body: str
    accepted_answer_id: uuid.UUID | None
    tags: list[str] = Field(default_factory=list)
    teacher_verified: bool = False
    created_at: datetime
    version_id: int


class QuestionPage(CursorPage):
    items: list[QuestionOut]


class QuestionDetailOut(QuestionOut):
    answers: list["AnswerOut"] = Field(default_factory=list)


class AnswerCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10000)


class AnswerOut(BaseModel):
    id: uuid.UUID
    question_id: uuid.UUID
    author_id: uuid.UUID
    body: str
    score: int
    teacher_verified: bool
    created_at: datetime
    version_id: int


class PromotionIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    tag_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)
