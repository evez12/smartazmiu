"""message search vector: body_tsv with a GIN index, filled on insert

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Filled by the message service from normalize_az (§5.7.1); search itself arrives in Sprint 10 (D-060).
    op.add_column("messages", sa.Column("body_tsv", postgresql.TSVECTOR()))
    op.create_index("ix_messages_body_tsv", "messages", ["body_tsv"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("ix_messages_body_tsv", table_name="messages")
    op.drop_column("messages", "body_tsv")
