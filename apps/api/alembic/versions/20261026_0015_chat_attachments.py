"""chat attachments: uploads before sending, scan bookkeeping, rejection notices

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = (
    "announcement.published",
    "event.published",
    "event.changed",
    "event.cancelled",
    "schedule.changed",
    "chat.mention",
    "chat.reply",
)


def upgrade() -> None:
    # Nothing writes attachments before this revision (D-060), so the table can change shape freely.
    op.alter_column("message_attachments", "message_id", nullable=True)
    op.add_column(
        "message_attachments",
        sa.Column(
            "uploader_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
    )
    op.add_column(
        "message_attachments",
        sa.Column(
            "channel_id",
            sa.Uuid(),
            sa.ForeignKey("channels.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.add_column(
        "message_attachments",
        sa.Column("filename", sa.String(255), server_default="", nullable=False),
    )
    op.add_column(
        "message_attachments",
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.add_column(
        "message_attachments", sa.Column("attached_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "message_attachments", sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "message_attachments",
        sa.Column("scan_attempts", sa.SmallInteger(), server_default="0", nullable=False),
    )
    op.add_column(
        "message_attachments",
        sa.Column(
            "scan_after", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.add_column(
        "message_attachments", sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        "ix_message_attachments_pending",
        "message_attachments",
        ["scan_after"],
        postgresql_where=sa.text("scan_status = 'pending' AND message_id IS NOT NULL"),
    )
    op.create_index(
        "ix_message_attachments_unsent",
        "message_attachments",
        ["created_at"],
        postgresql_where=sa.text("message_id IS NULL"),
    )
    op.execute("ALTER TYPE notification_kind ADD VALUE IF NOT EXISTS 'chat.attachment_rejected'")


def downgrade() -> None:
    op.execute("DELETE FROM notifications WHERE kind::text = 'chat.attachment_rejected'")
    op.execute("ALTER TYPE notification_kind RENAME TO notification_kind_old")
    postgresql.ENUM(*KINDS, name="notification_kind").create(op.get_bind())
    op.execute(
        "ALTER TABLE notifications ALTER COLUMN kind TYPE notification_kind"
        " USING kind::text::notification_kind"
    )
    op.execute("DROP TYPE notification_kind_old")
    op.drop_index("ix_message_attachments_unsent", table_name="message_attachments")
    op.drop_index("ix_message_attachments_pending", table_name="message_attachments")
    # Uploads that were never sent have no message; they cannot exist in the old shape.
    op.execute("DELETE FROM message_attachments WHERE message_id IS NULL")
    for column in (
        "purged_at",
        "scan_after",
        "scan_attempts",
        "scanned_at",
        "attached_at",
        "created_at",
        "filename",
        "channel_id",
        "uploader_id",
    ):
        op.drop_column("message_attachments", column)
    op.alter_column("message_attachments", "message_id", nullable=False)
