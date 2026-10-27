"""knowledge in channels: subject guide cards, upvotes, pins, polls, saved messages

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_KINDS = (
    "announcement.published",
    "event.published",
    "event.changed",
    "event.cancelled",
    "schedule.changed",
    "chat.mention",
    "chat.reply",
    "chat.attachment_rejected",
    "material.version_rejected",
    "mentorship.invitation",
    "mentorship.request_received",
    "mentorship.request_accepted",
    "mentorship.request_declined",
    "mentorship.request_expired",
    "mentorship.advice_post",
)
NEW_KINDS = ("mentorship.tip_prompt", "chat.answer_verified")
OLD_TARGETS = ("message", "user")
ENUMS = {
    "tip_weekly_hours": ("under_2", "2_4", "4_6", "6_10", "over_10"),
    "tip_status": ("pending", "published", "rejected", "hidden"),
}


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for kind in NEW_KINDS:
            op.execute(f"ALTER TYPE notification_kind ADD VALUE IF NOT EXISTS '{kind}'")
        op.execute("ALTER TYPE report_target ADD VALUE IF NOT EXISTS 'tip'")
    for name, values in ENUMS.items():
        postgresql.ENUM(*values, name=name).create(op.get_bind())

    op.create_table(
        "course_tips",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "subject_id",
            sa.Uuid(),
            sa.ForeignKey("subjects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("semester_taken_id", sa.Uuid(), sa.ForeignKey("semesters.id"), nullable=False),
        sa.Column("difficulty", sa.SmallInteger(), nullable=False),
        sa.Column(
            "weekly_hours",
            postgresql.ENUM(name="tip_weekly_hours", create_type=False),
            nullable=False,
        ),
        sa.Column("key_topics", sa.Text(), nullable=False),
        sa.Column("resources", postgresql.JSONB(), nullable=False),
        sa.Column("exam_advice", sa.Text(), nullable=False),
        sa.Column("retrospective", sa.Text(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="tip_status", create_type=False),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("upvotes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("moderation_note", sa.String(500), server_default="", nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("author_id", "subject_id", "semester_taken_id"),
        sa.CheckConstraint("difficulty BETWEEN 1 AND 5", name="ck_course_tips_difficulty_range"),
    )
    op.create_index("ix_course_tips_subject_id_status", "course_tips", ["subject_id", "status"])
    op.create_index("ix_course_tips_status_updated_at", "course_tips", ["status", "updated_at"])
    op.create_table(
        "tip_upvotes",
        sa.Column(
            "tip_id",
            sa.Uuid(),
            sa.ForeignKey("course_tips.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "pinned_messages",
        sa.Column(
            "channel_id",
            sa.Uuid(),
            sa.ForeignKey("channels.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("message_id", sa.BigInteger(), primary_key=True),
        sa.Column("pinned_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column(
            "pinned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "polls",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("message_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column(
            "channel_id",
            sa.Uuid(),
            sa.ForeignKey("channels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("multi", sa.Boolean(), nullable=False),
        sa.Column("closes_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "poll_options",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "poll_id", sa.Uuid(), sa.ForeignKey("polls.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("text", sa.String(200), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
    )
    op.create_index("ix_poll_options_poll_id", "poll_options", ["poll_id"])
    op.create_table(
        "poll_votes",
        sa.Column(
            "poll_id", sa.Uuid(), sa.ForeignKey("polls.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column(
            "option_id",
            sa.Uuid(),
            sa.ForeignKey("poll_options.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_poll_votes_poll_id_user_id", "poll_votes", ["poll_id", "user_id"])
    op.create_table(
        "saved_messages",
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("message_id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "channel_id",
            sa.Uuid(),
            sa.ForeignKey("channels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def _rebuild(type_name: str, values: tuple[str, ...], columns: list[tuple[str, str]]) -> None:
    op.execute(f"ALTER TYPE {type_name} RENAME TO {type_name}_old")
    postgresql.ENUM(*values, name=type_name).create(op.get_bind())
    for table, column in columns:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE {type_name}"
            f" USING {column}::text::{type_name}"
        )
    op.execute(f"DROP TYPE {type_name}_old")


def downgrade() -> None:
    for table in (
        "saved_messages",
        "poll_votes",
        "poll_options",
        "polls",
        "pinned_messages",
        "tip_upvotes",
        "course_tips",
    ):
        op.drop_table(table)
    for name in ENUMS:
        postgresql.ENUM(name=name).drop(op.get_bind())
    op.execute("DELETE FROM reports WHERE target_type::text = 'tip'")
    _rebuild("report_target", OLD_TARGETS, [("reports", "target_type")])
    op.execute(
        "DELETE FROM notifications WHERE kind::text IN ('mentorship.tip_prompt', 'chat.answer_verified')"
    )
    _rebuild("notification_kind", OLD_KINDS, [("notifications", "kind")])
