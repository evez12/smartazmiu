"""Notification kinds for new or moved exams and for decisions on past papers (D-105).

Revision ID: 0034
Revises: 0033
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_KINDS = ("exam.scheduled", "exam.moved", "past_paper.approved", "past_paper.rejected")
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
    "mentorship.tip_prompt",
    "chat.answer_verified",
)


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for kind in NEW_KINDS:
            op.execute(f"ALTER TYPE notification_kind ADD VALUE IF NOT EXISTS '{kind}'")


def downgrade() -> None:
    # Postgres cannot drop enum values: notifications of the new kinds go, then the type is rebuilt.
    op.execute(
        sa.text("DELETE FROM notifications WHERE kind::text IN :kinds").bindparams(
            sa.bindparam("kinds", NEW_KINDS, expanding=True)
        )
    )
    op.execute("ALTER TYPE notification_kind RENAME TO notification_kind_old")
    postgresql.ENUM(*OLD_KINDS, name="notification_kind").create(op.get_bind())
    op.execute(
        "ALTER TABLE notifications ALTER COLUMN kind TYPE notification_kind"
        " USING kind::text::notification_kind"
    )
    op.execute("DROP TYPE notification_kind_old")
