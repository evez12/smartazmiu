"""Persist exam windows used by chat authorization.

Revision ID: 0025
Revises: 0024
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exam_slots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="CASCADE"),
        sa.CheckConstraint("ends_at > starts_at", name="exam_slot_valid_window"),
    )
    op.create_index(
        "ix_exam_slots_channel_window", "exam_slots", ["channel_id", "starts_at", "ends_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_exam_slots_channel_window", table_name="exam_slots")
    op.drop_table("exam_slots")
