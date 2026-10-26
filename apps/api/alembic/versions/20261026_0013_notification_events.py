"""notification events: NOTIFY on commit so open sockets refresh the bell

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-26
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # NOTIFY is delivered only when the inserting transaction commits, from the API and the worker alike, so a
    # bell never refreshes for a notification that was rolled back (D-062). Duplicate payloads in one
    # transaction are folded into one by PostgreSQL.
    op.execute(
        """
        CREATE FUNCTION announce_notifications() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            PERFORM pg_notify('notification_created', user_id::text)
            FROM (SELECT DISTINCT user_id FROM created) AS recipients;
            RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER notifications_announce AFTER INSERT ON notifications
        REFERENCING NEW TABLE AS created FOR EACH STATEMENT EXECUTE FUNCTION announce_notifications()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER notifications_announce ON notifications")
    op.execute("DROP FUNCTION announce_notifications()")
