"""notifications: in-app rows, push and e-mail deliveries, preferences, push subscriptions

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORIES = ("announcements", "events", "schedule")
KINDS = (
    "announcement.published",
    "event.published",
    "event.changed",
    "event.cancelled",
    "schedule.changed",
)

# PostgreSQL 16 has no UUIDv7 generator; fan-out inserts many rows in one statement and need one in SQL.
# A random v4 UUID gets the Unix milliseconds in its first 48 bits and its version nibble set to 7.
UUID7_FUNCTION = """
CREATE FUNCTION uuid7() RETURNS uuid AS $$
  SELECT encode(
    set_bit(
      set_bit(
        overlay(uuid_send(gen_random_uuid())
          PLACING substring(int8send((extract(epoch FROM clock_timestamp()) * 1000)::bigint) FROM 3)
          FROM 1 FOR 6),
        52, 1),
      53, 1),
    'hex')::uuid
$$ LANGUAGE sql VOLATILE
"""


def upgrade() -> None:
    op.execute(UUID7_FUNCTION)
    category = postgresql.ENUM(*CATEGORIES, name="notification_category")
    category.create(op.get_bind())
    category_column = postgresql.ENUM(name="notification_category", create_type=False)

    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid7()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("category", category_column, nullable=False),
        sa.Column("kind", sa.Enum(*KINDS, name="notification_kind"), nullable=False),
        sa.Column("dedupe_key", sa.String(200), nullable=False),
        sa.Column("subject_type", sa.String(32), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("link", sa.String(300), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notifications_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
        sa.UniqueConstraint(
            "user_id", "dedupe_key", name=op.f("uq_notifications_user_id_dedupe_key")
        ),
    )
    op.create_index("ix_notifications_user_id_id", "notifications", ["user_id", "id"])
    op.create_index(
        "ix_notifications_unread",
        "notifications",
        ["user_id"],
        postgresql_where=sa.text("read_at IS NULL"),
    )
    op.create_index(op.f("ix_notifications_subject_id"), "notifications", ["subject_id"])

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid7()"), nullable=False),
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.Enum("push", "email", name="delivery_channel"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "sent", "suppressed", "failed", name="delivery_status"),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("reason", sa.String(40), nullable=True),
        sa.Column("attempts", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column(
            "not_before", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["notification_id"],
            ["notifications.id"],
            name=op.f("fk_notification_deliveries_notification_id_notifications"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_deliveries")),
        sa.UniqueConstraint(
            "notification_id",
            "channel",
            name=op.f("uq_notification_deliveries_notification_id_channel"),
        ),
    )
    op.create_index(
        "ix_notification_deliveries_pending",
        "notification_deliveries",
        ["not_before"],
        postgresql_where=sa.text("status = 'pending'"),
    )

    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.String(100), nullable=False),
        sa.Column("auth", sa.String(50), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_push_subscriptions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_push_subscriptions")),
        sa.UniqueConstraint("endpoint", name=op.f("uq_push_subscriptions_endpoint")),
    )
    op.create_index(op.f("ix_push_subscriptions_user_id"), "push_subscriptions", ["user_id"])

    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("category", category_column, nullable=False),
        sa.Column("push", sa.Boolean(), nullable=False),
        sa.Column("email", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notification_preferences_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "category", name=op.f("pk_notification_preferences")),
    )
    op.create_table(
        "notification_quiet_hours",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("starts_at", sa.Time(), nullable=False),
        sa.Column("ends_at", sa.Time(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notification_quiet_hours_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_notification_quiet_hours")),
    )


def downgrade() -> None:
    op.drop_table("notification_quiet_hours")
    op.drop_table("notification_preferences")
    op.drop_table("push_subscriptions")
    op.drop_table("notification_deliveries")
    op.drop_table("notifications")
    for name in (
        "delivery_status",
        "delivery_channel",
        "notification_kind",
        "notification_category",
    ):
        op.execute(f"DROP TYPE {name}")
    op.execute("DROP FUNCTION uuid7()")
