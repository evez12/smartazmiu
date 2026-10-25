"""chat core: channels, members, reads, monthly-partitioned messages, blocks

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-26
"""

from collections.abc import Sequence
from datetime import UTC, date, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENUMS = {
    "channel_type": (
        "course_offering",
        "subject_community",
        "academic_group",
        "faculty",
        "announcement",
        "club",
        "private_group",
        "dm",
    ),
    "channel_member_role": ("owner", "moderator", "member", "readonly"),
    "notify_level": ("all", "mentions", "none"),
    "scan_status": ("pending", "clean", "infected", "failed"),
}
# The current month and the next three; the daily job keeps three future months from then on (ADR 0002).
INITIAL_MONTHS = 4


def enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*ENUMS[name], name=name, create_type=False)


def created_at() -> sa.Column[datetime]:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def fk(
    table: str, column: str, target: str, ondelete: str | None = None
) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], [f"{target}.id"], name=op.f(f"fk_{table}_{column}_{target}"), ondelete=ondelete
    )


def month_start(year: int, month: int) -> date:
    return date(year + (month - 1) // 12, (month - 1) % 12 + 1, 1)


def upgrade() -> None:
    for name, values in ENUMS.items():
        postgresql.ENUM(*values, name=name).create(op.get_bind())

    op.create_table(
        "channels",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid7()"), nullable=False),
        sa.Column("type", enum("channel_type"), nullable=False),
        sa.Column("name", sa.String(255, collation="az-x-icu"), nullable=False),
        sa.Column("subject_id", sa.Uuid()),
        sa.Column("course_offering_id", sa.Uuid()),
        sa.Column("academic_group_id", sa.Uuid()),
        sa.Column("faculty_id", sa.Uuid()),
        sa.Column("user_low_id", sa.Uuid()),
        sa.Column("user_high_id", sa.Uuid()),
        sa.Column("is_archived", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_readonly", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("slow_mode_seconds", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_by", sa.Uuid()),
        created_at(),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_channels")),
        fk("channels", "subject_id", "subjects"),
        fk("channels", "course_offering_id", "course_offerings"),
        fk("channels", "academic_group_id", "academic_groups"),
        fk("channels", "faculty_id", "faculties"),
        fk("channels", "user_low_id", "users"),
        fk("channels", "user_high_id", "users"),
        fk("channels", "created_by", "users", "SET NULL"),
        sa.CheckConstraint(
            "(type = 'dm') = (user_low_id IS NOT NULL AND user_high_id IS NOT NULL)"
            " AND (user_low_id IS NULL OR user_low_id < user_high_id)",
            name=op.f("ck_channels_dm_pair"),
        ),
        sa.CheckConstraint(
            "slow_mode_seconds >= 0", name=op.f("ck_channels_slow_mode_non_negative")
        ),
    )
    for column, kind in (
        ("course_offering_id", "course_offering"),
        ("subject_id", "subject_community"),
        ("academic_group_id", "academic_group"),
        ("faculty_id", "faculty"),
    ):
        op.create_index(
            f"uq_channels_{column}",
            "channels",
            [column],
            unique=True,
            postgresql_where=sa.text(f"type = '{kind}'"),
        )
    op.create_index(
        "uq_channels_dm_pair",
        "channels",
        ["user_low_id", "user_high_id"],
        unique=True,
        postgresql_where=sa.text("type = 'dm'"),
    )

    op.create_table(
        "channel_topics",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid7()"), nullable=False),
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("name", sa.String(100, collation="az-x-icu"), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_channel_topics")),
        fk("channel_topics", "channel_id", "channels", "CASCADE"),
    )
    op.create_index(
        "uq_channel_topics_channel_id_slug", "channel_topics", ["channel_id", "slug"], unique=True
    )

    op.create_table(
        "channel_members",
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", enum("channel_member_role"), nullable=False),
        sa.Column(
            "joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("notify_level", enum("notify_level"), server_default="all", nullable=False),
        sa.Column("muted_until", sa.DateTime(timezone=True)),
        sa.Column("posting_muted_until", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("channel_id", "user_id", name=op.f("pk_channel_members")),
        fk("channel_members", "channel_id", "channels", "CASCADE"),
        fk("channel_members", "user_id", "users", "CASCADE"),
    )
    op.create_index(op.f("ix_channel_members_user_id"), "channel_members", ["user_id"])

    op.create_table(
        "channel_reads",
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("last_read_message_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("channel_id", "user_id", name=op.f("pk_channel_reads")),
        fk("channel_reads", "channel_id", "channels", "CASCADE"),
        fk("channel_reads", "user_id", "users", "CASCADE"),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("topic_id", sa.Uuid()),
        sa.Column("author_id", sa.Uuid()),
        sa.Column("parent_id", sa.BigInteger()),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_anonymous", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_verified_answer", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("verified_by", sa.Uuid()),
        sa.Column("client_msg_id", sa.Uuid(), nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id", "created_at", name="pk_messages"),
        fk("messages", "channel_id", "channels", "CASCADE"),
        fk("messages", "topic_id", "channel_topics", "SET NULL"),
        fk("messages", "author_id", "users", "SET NULL"),
        fk("messages", "verified_by", "users", "SET NULL"),
        sa.CheckConstraint("char_length(body) <= 4000", name=op.f("ck_messages_body_length")),
        postgresql_partition_by="RANGE (created_at)",
    )
    op.create_index("ix_messages_channel_id_id", "messages", ["channel_id", sa.text("id DESC")])
    op.create_index("ix_messages_parent_id", "messages", ["parent_id"])
    today = datetime.now(UTC).date()
    for offset in range(INITIAL_MONTHS):
        start = month_start(today.year, today.month + offset)
        end = month_start(today.year, today.month + offset + 1)
        op.execute(
            f"CREATE TABLE IF NOT EXISTS messages_y{start.year}m{start.month:02d} PARTITION OF messages"
            f" FOR VALUES FROM ('{start.isoformat()}T00:00:00+00') TO ('{end.isoformat()}T00:00:00+00')"
        )

    op.create_table(
        "message_client_ids",
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("client_msg_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("message_created_at", sa.DateTime(timezone=True), nullable=False),
        created_at(),
        sa.PrimaryKeyConstraint("channel_id", "client_msg_id", name=op.f("pk_message_client_ids")),
        fk("message_client_ids", "channel_id", "channels", "CASCADE"),
    )
    op.create_index("ix_message_client_ids_created_at", "message_client_ids", ["created_at"])

    op.create_table(
        "message_attachments",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid7()"), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("object_key", sa.String(300), nullable=False),
        sa.Column("mime", sa.String(127), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.Column("scan_status", enum("scan_status"), server_default="pending", nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_message_attachments")),
    )
    op.create_index("ix_message_attachments_message_id", "message_attachments", ["message_id"])

    op.create_table(
        "message_reactions",
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("emoji", sa.String(32), nullable=False),
        created_at(),
        sa.PrimaryKeyConstraint(
            "message_id", "user_id", "emoji", name=op.f("pk_message_reactions")
        ),
        fk("message_reactions", "user_id", "users", "CASCADE"),
    )

    op.create_table(
        "message_mentions",
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("message_id", "user_id", name=op.f("pk_message_mentions")),
        fk("message_mentions", "user_id", "users", "CASCADE"),
    )
    op.create_index(op.f("ix_message_mentions_user_id"), "message_mentions", ["user_id"])

    op.create_table(
        "user_blocks",
        sa.Column("blocker_id", sa.Uuid(), nullable=False),
        sa.Column("blocked_id", sa.Uuid(), nullable=False),
        created_at(),
        sa.PrimaryKeyConstraint("blocker_id", "blocked_id", name=op.f("pk_user_blocks")),
        fk("user_blocks", "blocker_id", "users", "CASCADE"),
        fk("user_blocks", "blocked_id", "users", "CASCADE"),
        sa.CheckConstraint("blocker_id <> blocked_id", name=op.f("ck_user_blocks_not_self")),
    )
    op.create_index(op.f("ix_user_blocks_blocked_id"), "user_blocks", ["blocked_id"])


def downgrade() -> None:
    for table in (
        "user_blocks",
        "message_mentions",
        "message_reactions",
        "message_attachments",
        "message_client_ids",
        "messages",  # its partitions go with it
        "channel_reads",
        "channel_members",
        "channel_topics",
        "channels",
    ):
        op.drop_table(table)
    for name in reversed(ENUMS):
        op.execute(f"DROP TYPE {name}")
