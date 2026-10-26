"""chat interactions: @channel flag on messages, chat notifications

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_CATEGORIES = ("announcements", "events", "schedule")
OLD_KINDS = (
    "announcement.published",
    "event.published",
    "event.changed",
    "event.cancelled",
    "schedule.changed",
)
NEW_KINDS = ("chat.mention", "chat.reply")


def upgrade() -> None:
    # A constant default is stored in the catalogue, so existing partitions are not rewritten.
    op.add_column(
        "messages",
        sa.Column("mentions_channel", sa.Boolean(), server_default="false", nullable=False),
    )
    op.execute("ALTER TYPE notification_category ADD VALUE IF NOT EXISTS 'chat'")
    for kind in NEW_KINDS:
        op.execute(f"ALTER TYPE notification_kind ADD VALUE IF NOT EXISTS '{kind}'")


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
    # Postgres cannot drop enum values: chat notifications and preferences go, then the types are rebuilt.
    op.execute("DELETE FROM notifications WHERE category::text = 'chat'")
    op.execute("DELETE FROM notification_preferences WHERE category::text = 'chat'")
    _rebuild("notification_kind", OLD_KINDS, [("notifications", "kind")])
    _rebuild(
        "notification_category",
        OLD_CATEGORIES,
        [("notifications", "category"), ("notification_preferences", "category")],
    )
    op.drop_column("messages", "mentions_channel")
