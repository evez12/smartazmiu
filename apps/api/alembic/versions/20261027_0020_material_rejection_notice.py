"""material records: copyright consent in consent_records, and the notice for a rejected version

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-27
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = (
    "announcement.published",
    "event.published",
    "event.changed",
    "event.cancelled",
    "schedule.changed",
    "chat.mention",
    "chat.reply",
    "chat.attachment_rejected",
)
PURPOSES = ("privacy_notice", "contact_sharing", "profile_photo")


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE notification_kind ADD VALUE IF NOT EXISTS 'material.version_rejected'"
        )
        op.execute("ALTER TYPE consent_purpose ADD VALUE IF NOT EXISTS 'material_copyright'")
    # Versions saved before this revision carry their consent only on the version row; copy it over.
    op.execute(
        "INSERT INTO consent_records (id, user_id, purpose, granted, policy_version, recorded_at)"
        " SELECT uuid7(), uploader_id, 'material_copyright', true, copyright_text_version,"
        " copyright_confirmed_at FROM material_versions"
        " WHERE uploader_id IS NOT NULL AND copyright_confirmed_at IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DELETE FROM notifications WHERE kind::text = 'material.version_rejected'")
    op.execute("ALTER TYPE notification_kind RENAME TO notification_kind_old")
    postgresql.ENUM(*KINDS, name="notification_kind").create(op.get_bind())
    op.execute(
        "ALTER TABLE notifications ALTER COLUMN kind TYPE notification_kind"
        " USING kind::text::notification_kind"
    )
    op.execute("DROP TYPE notification_kind_old")
    op.execute("DELETE FROM consent_records WHERE purpose::text = 'material_copyright'")
    op.execute("ALTER TYPE consent_purpose RENAME TO consent_purpose_old")
    postgresql.ENUM(*PURPOSES, name="consent_purpose").create(op.get_bind())
    op.execute(
        "ALTER TABLE consent_records ALTER COLUMN purpose TYPE consent_purpose"
        " USING purpose::text::consent_purpose"
    )
    op.execute("DROP TYPE consent_purpose_old")
