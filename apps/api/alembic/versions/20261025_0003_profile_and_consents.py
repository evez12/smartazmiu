"""profile fields, privacy settings and consent records

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DM_POLICY = ("everyone", "shared_context", "guides_and_teachers", "nobody")
CONTACT_VISIBILITY = ("hidden", "shared_context", "everyone")


def upgrade() -> None:
    bind = op.get_bind()
    # add_column does not create enum types itself.
    postgresql.ENUM(*DM_POLICY, name="dm_policy").create(bind)
    postgresql.ENUM(*CONTACT_VISIBILITY, name="contact_visibility").create(bind)

    op.add_column("users", sa.Column("bio", sa.String(300), server_default="", nullable=False))
    op.add_column("users", sa.Column("photo_key", sa.String(200), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "dm_policy",
            postgresql.ENUM(name="dm_policy", create_type=False),
            server_default="shared_context",
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "contact_visibility",
            postgresql.ENUM(name="contact_visibility", create_type=False),
            server_default="hidden",
            nullable=False,
        ),
    )
    op.add_column(
        "users", sa.Column("profile_version", sa.Integer(), server_default="1", nullable=False)
    )

    op.create_table(
        "consent_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "purpose",
            sa.Enum("privacy_notice", "contact_sharing", "profile_photo", name="consent_purpose"),
            nullable=False,
        ),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("policy_version", sa.String(20), nullable=True),
        sa.Column(
            "recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_consent_records_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_consent_records")),
    )
    op.create_index(
        "ix_consent_records_user_id_purpose_recorded_at",
        "consent_records",
        ["user_id", "purpose", "recorded_at"],
    )


def downgrade() -> None:
    op.drop_table("consent_records")
    op.drop_column("users", "profile_version")
    op.drop_column("users", "contact_visibility")
    op.drop_column("users", "dm_policy")
    op.drop_column("users", "photo_key")
    op.drop_column("users", "bio")
    for name in ("consent_purpose", "contact_visibility", "dm_policy"):
        sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)
