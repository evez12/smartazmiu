"""Moderator actions, bans and thread locks.

Revision ID: 0024
Revises: 0023
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIONS = (
    "delete_message",
    "mute",
    "kick",
    "ban",
    "global_ban",
    "lock_thread",
    "slow_mode",
    "restore_message",
)


def upgrade() -> None:
    postgresql.ENUM(*ACTIONS, name="moderation_action_kind").create(op.get_bind())
    op.create_table(
        "channel_bans",
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("banned_by", sa.Uuid()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["banned_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("channel_id", "user_id"),
    )
    op.create_table(
        "global_chat_bans",
        sa.Column("user_id", sa.Uuid(), primary_key=True),
        sa.Column("banned_by", sa.Uuid()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["banned_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_table(
        "thread_locks",
        sa.Column("message_id", sa.BigInteger(), primary_key=True),
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("locked_by", sa.Uuid()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["locked_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_table(
        "moderation_actions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("moderator_id", sa.Uuid()),
        sa.Column(
            "action",
            postgresql.ENUM(name="moderation_action_kind", create_type=False),
            nullable=False,
        ),
        sa.Column("target_user_id", sa.Uuid()),
        sa.Column("channel_id", sa.Uuid()),
        sa.Column("message_id", sa.BigInteger()),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("reason", sa.String(500), server_default="", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["moderator_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_moderation_actions_channel_created", "moderation_actions", ["channel_id", "created_at"]
    )
    connection = op.get_bind()
    permission_id = connection.execute(
        sa.text(
            "INSERT INTO permissions (id, code, description) VALUES (gen_random_uuid(), 'chat.moderate', 'Moderate assigned chat channels') ON CONFLICT (code) DO UPDATE SET description = EXCLUDED.description RETURNING id"
        )
    ).scalar_one()
    connection.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) SELECT id, :permission_id FROM roles WHERE code = 'moderator' ON CONFLICT DO NOTHING"
        ),
        {"permission_id": permission_id},
    )
    connection.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) SELECT r.id, p.id FROM roles r CROSS JOIN permissions p WHERE r.code = 'moderator' AND p.code IN ('admin.reports.read', 'admin.reports.handle') ON CONFLICT DO NOTHING"
        )
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id = (SELECT id FROM permissions WHERE code = 'chat.moderate')"
        )
    )
    connection.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE role_id = (SELECT id FROM roles WHERE code = 'moderator') AND permission_id IN (SELECT id FROM permissions WHERE code IN ('admin.reports.read', 'admin.reports.handle'))"
        )
    )
    connection.execute(sa.text("DELETE FROM permissions WHERE code = 'chat.moderate'"))
    op.drop_table("moderation_actions")
    op.drop_table("thread_locks")
    op.drop_table("global_chat_bans")
    op.drop_table("channel_bans")
    postgresql.ENUM(name="moderation_action_kind").drop(op.get_bind())
