"""Chat schema (§5.7). ``messages`` is partitioned by month and keyed by snowflake ids (ADR 0002): nothing
references it with a foreign key, so tables about messages carry ``message_id`` and are checked in services."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7
from app.modules.users.models import AZ_COLLATION


def _enum(enum: type[StrEnum], name: str) -> Enum:
    return Enum(enum, name=name, values_callable=lambda members: [m.value for m in members])


class ChannelType(StrEnum):
    COURSE_OFFERING = "course_offering"
    SUBJECT_COMMUNITY = "subject_community"
    ACADEMIC_GROUP = "academic_group"
    FACULTY = "faculty"
    ANNOUNCEMENT = "announcement"
    CLUB = "club"
    PRIVATE_GROUP = "private_group"
    DM = "dm"


# Channels whose membership the provisioning job derives from the registry (§5.1).
PROVISIONED_TYPES = frozenset(
    {
        ChannelType.COURSE_OFFERING,
        ChannelType.SUBJECT_COMMUNITY,
        ChannelType.ACADEMIC_GROUP,
        ChannelType.FACULTY,
    }
)


class MemberRole(StrEnum):
    OWNER = "owner"
    MODERATOR = "moderator"
    MEMBER = "member"
    READONLY = "readonly"


class NotifyLevel(StrEnum):
    ALL = "all"
    MENTIONS = "mentions"
    NONE = "none"


class ScanStatus(StrEnum):
    PENDING = "pending"
    CLEAN = "clean"
    INFECTED = "infected"
    FAILED = "failed"
    """The content did not match its declared type, or the uploaded object was missing (D-068)."""


class Channel(Base):
    __tablename__ = "channels"
    __table_args__ = (
        # One channel per registry entity and per pair of people; the other types have no natural key.
        Index(
            "uq_channels_course_offering_id",
            "course_offering_id",
            unique=True,
            postgresql_where=text("type = 'course_offering'"),
        ),
        Index(
            "uq_channels_subject_id",
            "subject_id",
            unique=True,
            postgresql_where=text("type = 'subject_community'"),
        ),
        Index(
            "uq_channels_academic_group_id",
            "academic_group_id",
            unique=True,
            postgresql_where=text("type = 'academic_group'"),
        ),
        Index(
            "uq_channels_faculty_id",
            "faculty_id",
            unique=True,
            postgresql_where=text("type = 'faculty'"),
        ),
        Index(
            "uq_channels_dm_pair",
            "user_low_id",
            "user_high_id",
            unique=True,
            postgresql_where=text("type = 'dm'"),
        ),
        CheckConstraint(
            "(type = 'dm') = (user_low_id IS NOT NULL AND user_high_id IS NOT NULL)"
            " AND (user_low_id IS NULL OR user_low_id < user_high_id)",
            name="dm_pair",
        ),
        CheckConstraint("slow_mode_seconds >= 0", name="slow_mode_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    type: Mapped[ChannelType] = mapped_column(_enum(ChannelType, "channel_type"))
    name: Mapped[str] = mapped_column(String(255, collation=AZ_COLLATION))
    subject_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("subjects.id"))
    course_offering_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("course_offerings.id"))
    academic_group_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("academic_groups.id"))
    faculty_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("faculties.id"))
    user_low_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    user_high_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_readonly: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    slow_mode_seconds: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChannelTopic(Base):
    __tablename__ = "channel_topics"
    __table_args__ = (
        Index("uq_channel_topics_channel_id_slug", "channel_id", "slug", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    channel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"))
    # Transliterated ASCII for URLs; the display name keeps Azerbaijani letters (§5.1).
    slug: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(100, collation=AZ_COLLATION))
    position: Mapped[int] = mapped_column(SmallInteger)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class ChannelMember(Base):
    __tablename__ = "channel_members"

    channel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    role: Mapped[MemberRole] = mapped_column(_enum(MemberRole, "channel_member_role"))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    notify_level: Mapped[NotifyLevel] = mapped_column(
        _enum(NotifyLevel, "notify_level"),
        default=NotifyLevel.ALL,
        server_default=NotifyLevel.ALL.value,
    )
    # The member's own notification snooze ("mute channel", §5.3).
    muted_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # A moderator's mute (§5.5): the member cannot post until then. Set only by moderation actions (D-058).
    posting_muted_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChannelRead(Base):
    __tablename__ = "channel_reads"

    channel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    last_read_message_id: Mapped[int] = mapped_column(BigInteger)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Message(Base):
    """Partitioned by ``created_at`` (monthly); ``created_at`` is derived from the snowflake id (ADR 0002)."""

    __tablename__ = "messages"
    __table_args__ = (
        PrimaryKeyConstraint("id", "created_at", name="pk_messages"),
        Index("ix_messages_channel_id_id", "channel_id", text("id DESC")),
        Index("ix_messages_parent_id", "parent_id"),
        Index("ix_messages_body_tsv", "body_tsv", postgresql_using="gin"),
        CheckConstraint("char_length(body) <= 4000", name="body_length"),
        {"postgresql_partition_by": "RANGE (created_at)"},
    )

    id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    channel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"))
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("channel_topics.id", ondelete="SET NULL")
    )
    # NULL once the author's account is deleted ("Silinmiş istifadəçi", §13.2).
    author_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    parent_id: Mapped[int | None] = mapped_column(BigInteger)
    body: Mapped[str] = mapped_column(Text)
    # Both normalize_az forms of the body (§5.7.1), written with the message; searched from Sprint 10.
    body_tsv: Mapped[str | None] = mapped_column(TSVECTOR)
    # The author used @channel and was allowed to (§5.3); explicit @user mentions live in message_mentions.
    mentions_channel: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_verified_answer: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    client_msg_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MessageClientId(Base):
    """Which message a client id produced, so a retried send returns the same message (D-058).

    Unpartitioned, so the key can be unique; rows are purged after seven days.
    """

    __tablename__ = "message_client_ids"
    __table_args__ = (Index("ix_message_client_ids_created_at", "created_at"),)

    channel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), primary_key=True
    )
    client_msg_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    message_id: Mapped[int] = mapped_column(BigInteger)
    message_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MessageAttachment(Base):
    """An upload: created when the upload is presigned, bound to a message when sent, visible to others once
    clean (D-068)."""

    __tablename__ = "message_attachments"
    __table_args__ = (
        Index("ix_message_attachments_message_id", "message_id"),
        Index(
            "ix_message_attachments_pending",
            "scan_after",
            postgresql_where=text("scan_status = 'pending' AND message_id IS NOT NULL"),
        ),
        Index(
            "ix_message_attachments_unsent",
            "created_at",
            postgresql_where=text("message_id IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    # NULL until the message is sent; no foreign key to the partitioned table (ADR 0002).
    message_id: Mapped[int | None] = mapped_column(BigInteger)
    uploader_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"))
    object_key: Mapped[str] = mapped_column(String(300))
    filename: Mapped[str] = mapped_column(String(255), default="", server_default="")
    mime: Mapped[str] = mapped_column(String(127))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    scan_status: Mapped[ScanStatus] = mapped_column(
        _enum(ScanStatus, "scan_status"),
        default=ScanStatus.PENDING,
        server_default=ScanStatus.PENDING.value,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    attached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scan_attempts: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    scan_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MessageReaction(Base):
    __tablename__ = "message_reactions"

    message_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    emoji: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MessageMention(Base):
    __tablename__ = "message_mentions"

    message_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class UserBlock(Base):
    """The blocker no longer sees the blocked person's messages expanded, and neither can DM the other (§5.4)."""

    __tablename__ = "user_blocks"
    __table_args__ = (CheckConstraint("blocker_id <> blocked_id", name="not_self"),)

    blocker_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    blocked_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
