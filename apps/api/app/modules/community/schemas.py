import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.chat.schemas import AuthorOut

ContentKind = Literal["post", "comment", "question", "answer"]


class TagOut(BaseModel):
    id: str
    slug: str
    name: str


class TagListOut(BaseModel):
    items: list[TagOut]


class PostCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10_000)
    tag_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5)


class PostOut(BaseModel):
    id: str
    author: AuthorOut | None
    """``None`` once the author's account is gone."""
    body: str
    tags: list[TagOut]
    helpful_count: int
    comment_count: int
    my_helpful: bool
    mine: bool
    hidden: bool
    """Hidden after reports; only the author and report handlers still see it (§5.5)."""
    created_at: datetime


class PostPage(BaseModel):
    items: list[PostOut]
    next_cursor: str | None = None


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4_000)


class CommentOut(BaseModel):
    id: str
    post_id: str
    author: AuthorOut | None
    body: str
    mine: bool
    hidden: bool
    created_at: datetime


class CommentPage(BaseModel):
    items: list[CommentOut]
    next_cursor: str | None = None


class QuestionCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=1, max_length=20_000)
    tag_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5)


class QuestionOut(BaseModel):
    id: str
    author: AuthorOut | None
    title: str
    excerpt: str
    tags: list[TagOut]
    answer_count: int
    accepted: bool
    teacher_verified: bool
    mine: bool
    hidden: bool
    created_at: datetime


class QuestionPage(BaseModel):
    items: list[QuestionOut]
    next_cursor: str | None = None


class AnswerCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10_000)


class AnswerOut(BaseModel):
    id: str
    author: AuthorOut | None
    body: str
    score: int
    my_vote: Literal[-1, 0, 1]
    accepted: bool
    verified_by: AuthorOut | None
    mine: bool
    hidden: bool
    created_at: datetime


class QuestionDetailOut(BaseModel):
    id: str
    author: AuthorOut | None
    title: str
    body: str
    tags: list[TagOut]
    accepted_answer_id: str | None
    teacher_verified: bool
    mine: bool
    hidden: bool
    created_at: datetime
    answers: list[AnswerOut]
    can_verify: bool
    """Teachers and staff mark answers as verified (§6)."""


class AcceptIn(BaseModel):
    answer_id: uuid.UUID | None
    """``None`` clears the accepted answer."""


class VisibilityIn(BaseModel):
    hidden: bool


class PromotionIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    tag_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5)
