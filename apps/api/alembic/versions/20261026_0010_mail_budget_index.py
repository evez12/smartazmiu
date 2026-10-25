"""index for the e-mail budget of mass announcements

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The dispatcher counts e-mail sent in the last minute before each send (D-055).
    op.create_index(
        "ix_notification_deliveries_mail_sent",
        "notification_deliveries",
        ["updated_at"],
        postgresql_where=sa.text("channel = 'email' AND status = 'sent'"),
    )


def downgrade() -> None:
    op.drop_index("ix_notification_deliveries_mail_sent", table_name="notification_deliveries")
