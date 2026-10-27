import uuid
from datetime import datetime
from enum import StrEnum
from typing import ClassVar

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7


def _enum(enum: type[StrEnum], name: str) -> Enum:
    return Enum(enum, name=name, values_callable=lambda values: [v.value for v in values])


class ReportReason(StrEnum):
    SPAM = "spam"
    ABUSE = "abuse"
    MISINFORMATION = "misinformation"
    OTHER = "other"


class CommunityTag(Base):
    __tablename__ = "community_tags"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(120))


class FeedPost(Base):
    __tablename__ = "feed_posts"
    __table_args__ = (Index("ix_feed_posts_created_at", "created_at", "id"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    __mapper_args__: ClassVar[dict[str, object]] = {"version_id_col": version_id}  # type: ignore[misc]


class FeedPostTag(Base):
    __tablename__ = "feed_post_tags"
    post_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feed_posts.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("community_tags.id", ondelete="CASCADE"), primary_key=True
    )


class FeedComment(Base):
    __tablename__ = "feed_comments"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    post_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feed_posts.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    __mapper_args__: ClassVar[dict[str, object]] = {"version_id_col": version_id}  # type: ignore[misc]


class HelpfulReaction(Base):
    __tablename__ = "helpful_reactions"
    post_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feed_posts.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CommunityReport(Base):
    __tablename__ = "community_reports"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    reporter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    target_type: Mapped[str] = mapped_column(String(20))
    target_id: Mapped[uuid.UUID] = mapped_column()
    reason: Mapped[ReportReason] = mapped_column(_enum(ReportReason, "community_report_reason"))
    details: Mapped[str] = mapped_column(String(500), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("reporter_id", "target_type", "target_id"),)


class ForumQuestion(Base):
    __tablename__ = "forum_questions"
    __table_args__ = (Index("ix_forum_questions_created_at", "created_at", "id"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    accepted_answer_id: Mapped[uuid.UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    __mapper_args__: ClassVar[dict[str, object]] = {"version_id_col": version_id}  # type: ignore[misc]


class ForumQuestionTag(Base):
    __tablename__ = "forum_question_tags"
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("forum_questions.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("community_tags.id", ondelete="CASCADE"), primary_key=True
    )


class ForumAnswer(Base):
    __tablename__ = "forum_answers"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("forum_questions.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text)
    teacher_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    __mapper_args__: ClassVar[dict[str, object]] = {"version_id_col": version_id}  # type: ignore[misc]


class ForumVote(Base):
    __tablename__ = "forum_votes"
    answer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("forum_answers.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    value: Mapped[int] = mapped_column(Integer)
