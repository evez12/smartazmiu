"""Mail priority for deliveries (D-111).

Revision ID: 0035
Revises: 0034
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0035"
down_revision: str | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notification_deliveries",
        sa.Column("priority", sa.SmallInteger(), server_default="0", nullable=False),
    )
    # Announcements and events outrank every other category; the dispatcher reads the high ones first.
    op.execute(
        """
        UPDATE notification_deliveries d SET priority = 1
        FROM notifications n
        WHERE n.id = d.notification_id AND n.category IN ('announcements', 'events')
        """
    )
    op.drop_index("ix_notification_deliveries_pending", table_name="notification_deliveries")
    op.create_index(
        "ix_notification_deliveries_pending",
        "notification_deliveries",
        [sa.text("priority DESC"), "not_before"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.drop_index("ix_notification_deliveries_mail_sent", table_name="notification_deliveries")
    op.create_index(
        "ix_notification_deliveries_mail_sent",
        "notification_deliveries",
        ["updated_at", "priority"],
        postgresql_where=sa.text("channel = 'email' AND status = 'sent'"),
    )


def downgrade() -> None:
    op.drop_index("ix_notification_deliveries_mail_sent", table_name="notification_deliveries")
    op.create_index(
        "ix_notification_deliveries_mail_sent",
        "notification_deliveries",
        ["updated_at"],
        postgresql_where=sa.text("channel = 'email' AND status = 'sent'"),
    )
    op.drop_index("ix_notification_deliveries_pending", table_name="notification_deliveries")
    op.create_index(
        "ix_notification_deliveries_pending",
        "notification_deliveries",
        ["not_before"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.drop_column("notification_deliveries", "priority")
