"""mentorship: guide profiles, advice requests, and their notifications

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_CATEGORIES = ("announcements", "events", "schedule", "chat")
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
)
NEW_KINDS = (
    "mentorship.invitation",
    "mentorship.request_received",
    "mentorship.request_accepted",
    "mentorship.request_declined",
    "mentorship.request_expired",
    "mentorship.advice_post",
)
ENUMS = {
    "grade_visibility": ("hidden", "range", "exact"),
    "mentor_availability": ("available", "busy", "paused"),
    "mentor_request_topic": (
        "exam",
        "workload",
        "materials",
        "teacher_expectations",
        "project",
        "other",
    ),
    "mentor_request_status": ("open", "accepted", "resolved", "declined", "expired"),
    "mentor_request_feedback": ("helpful", "not_helpful"),
}


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(name=name, create_type=False)


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE notification_category ADD VALUE IF NOT EXISTS 'mentorship'")
        for kind in NEW_KINDS:
            op.execute(f"ALTER TYPE notification_kind ADD VALUE IF NOT EXISTS '{kind}'")
    for name, values in ENUMS.items():
        postgresql.ENUM(*values, name=name).create(op.get_bind())

    op.create_table(
        "mentor_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "subject_id",
            sa.Uuid(),
            sa.ForeignKey("subjects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("semester_taken_id", sa.Uuid(), sa.ForeignKey("semesters.id"), nullable=False),
        sa.Column(
            "teacher_taken_with_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column(
            "grade_visibility",
            _enum("grade_visibility"),
            server_default="hidden",
            nullable=False,
        ),
        sa.Column("show_teacher", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("bio", sa.String(300), server_default="", nullable=False),
        sa.Column(
            "availability",
            _enum("mentor_availability"),
            server_default="available",
            nullable=False,
        ),
        sa.Column("max_open_requests", sa.SmallInteger(), server_default="3", nullable=False),
        sa.Column("helped_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("helpful_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("unhelpful_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("avg_response_minutes", sa.Integer()),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("user_id", "subject_id"),
        sa.CheckConstraint(
            "max_open_requests BETWEEN 1 AND 10",
            name="ck_mentor_profiles_max_open_requests_range",
        ),
    )
    op.create_index(
        "ix_mentor_profiles_subject_id_availability",
        "mentor_profiles",
        ["subject_id", "availability"],
    )

    op.create_table(
        "mentor_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "subject_id",
            sa.Uuid(),
            sa.ForeignKey("subjects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "requester_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("mentor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("topic", _enum("mentor_request_topic"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", _enum("mentor_request_status"), server_default="open", nullable=False),
        sa.Column("dm_channel_id", sa.Uuid(), sa.ForeignKey("channels.id", ondelete="SET NULL")),
        sa.Column("feedback", _enum("mentor_request_feedback")),
        sa.Column("feedback_note", sa.String(1000), server_default="", nullable=False),
        sa.Column("feedback_at", sa.DateTime(timezone=True)),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "uq_mentor_requests_open_addressed",
        "mentor_requests",
        ["requester_id", "mentor_id", "subject_id"],
        unique=True,
        postgresql_where=sa.text("status = 'open' AND mentor_id IS NOT NULL"),
    )
    op.create_index(
        "uq_mentor_requests_open_unaddressed",
        "mentor_requests",
        ["requester_id", "subject_id"],
        unique=True,
        postgresql_where=sa.text("status = 'open' AND mentor_id IS NULL"),
    )
    op.create_index(
        "ix_mentor_requests_status_created_at", "mentor_requests", ["status", "created_at"]
    )
    op.create_index(
        "ix_mentor_requests_mentor_id_status", "mentor_requests", ["mentor_id", "status"]
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
    op.drop_table("mentor_requests")
    op.drop_table("mentor_profiles")
    for name in ENUMS:
        postgresql.ENUM(name=name).drop(op.get_bind())
    op.execute("DELETE FROM notifications WHERE category::text = 'mentorship'")
    op.execute("DELETE FROM notification_preferences WHERE category::text = 'mentorship'")
    _rebuild("notification_kind", OLD_KINDS, [("notifications", "kind")])
    _rebuild(
        "notification_category",
        OLD_CATEGORIES,
        [("notifications", "category"), ("notification_preferences", "category")],
    )
