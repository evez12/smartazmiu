"""Blocked terms and message moderation state.

Revision ID: 0023
Revises: 0022
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    postgresql.ENUM("hold", "reject", name="blocked_term_action").create(op.get_bind())
    postgresql.ENUM("visible", "held", "hidden", name="message_moderation").create(op.get_bind())
    op.create_table(
        "blocked_terms",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("pattern", sa.String(128), nullable=False),
        sa.Column("is_regex", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "action", postgresql.ENUM(name="blocked_term_action", create_type=False), nullable=False
        ),
        sa.Column("lang", sa.String(2), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "messages",
        sa.Column(
            "moderation",
            postgresql.ENUM(name="message_moderation", create_type=False),
            nullable=False,
            server_default="visible",
        ),
    )


def downgrade() -> None:
    op.drop_column("messages", "moderation")
    op.drop_table("blocked_terms")
    postgresql.ENUM(name="message_moderation").drop(op.get_bind())
    postgresql.ENUM(name="blocked_term_action").drop(op.get_bind())
