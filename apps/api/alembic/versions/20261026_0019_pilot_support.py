"""pilot support: the support channel type, feedback, and the permissions to read and handle feedback

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.ids import uuid7

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHANNEL_TYPES = (
    "course_offering",
    "subject_community",
    "academic_group",
    "faculty",
    "announcement",
    "club",
    "private_group",
    "dm",
)
# Partial indexes and the check on channels.type, which must be rebuilt when the type is swapped back.
TYPE_INDEXES = (
    ("uq_channels_course_offering_id", ["course_offering_id"], "type = 'course_offering'"),
    ("uq_channels_subject_id", ["subject_id"], "type = 'subject_community'"),
    ("uq_channels_academic_group_id", ["academic_group_id"], "type = 'academic_group'"),
    ("uq_channels_faculty_id", ["faculty_id"], "type = 'faculty'"),
    ("uq_channels_dm_pair", ["user_low_id", "user_high_id"], "type = 'dm'"),
)
DM_PAIR = (
    "(type = 'dm') = (user_low_id IS NOT NULL AND user_high_id IS NOT NULL)"
    " AND (user_low_id IS NULL OR user_low_id < user_high_id)"
)
PERMISSIONS = {
    "admin.feedback.read": ("List feedback sent through the form", ("staff", "admin")),
    "admin.feedback.handle": ("Close and reopen feedback", ("staff", "admin")),
}


def upgrade() -> None:
    # A new enum value is usable only after its transaction commits; the index below needs it.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE channel_type ADD VALUE IF NOT EXISTS 'support'")
    op.create_index(
        "uq_channels_support",
        "channels",
        ["type"],
        unique=True,
        postgresql_where=sa.text("type = 'support'"),
    )

    category = postgresql.ENUM(
        "problem", "suggestion", "question", "other", name="feedback_category", create_type=False
    )
    status = postgresql.ENUM("open", "closed", name="feedback_status", create_type=False)
    for enum in (category, status):
        enum.create(op.get_bind())
    op.create_table(
        "feedback",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("category", category, nullable=False),
        sa.Column("message", sa.String(2000), nullable=False),
        sa.Column("page", sa.String(300), server_default="", nullable=False),
        sa.Column("contact_ok", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("status", status, server_default="open", nullable=False),
        sa.Column("handled_by", sa.Uuid(), nullable=True),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_feedback_user_id_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["handled_by"],
            ["users.id"],
            name=op.f("fk_feedback_handled_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feedback")),
    )
    op.create_index("ix_feedback_status_created_at", "feedback", ["status", "created_at"])

    bind = op.get_bind()
    permissions = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("description", sa.String()),
    )
    role_permissions = sa.table(
        "role_permissions", sa.column("role_id", sa.Uuid()), sa.column("permission_id", sa.Uuid())
    )
    roles = sa.table("roles", sa.column("id", sa.Uuid()), sa.column("code", sa.String()))
    for code, (description, role_codes) in PERMISSIONS.items():
        permission_id = uuid7()
        op.bulk_insert(
            permissions, [{"id": permission_id, "code": code, "description": description}]
        )
        for role_id in bind.scalars(sa.select(roles.c.id).where(roles.c.code.in_(role_codes))):
            op.bulk_insert(role_permissions, [{"role_id": role_id, "permission_id": permission_id}])


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM permissions WHERE code IN :codes").bindparams(
            sa.bindparam("codes", tuple(PERMISSIONS), expanding=True)
        )
    )
    op.drop_index("ix_feedback_status_created_at", table_name="feedback")
    op.drop_table("feedback")
    for name in ("feedback_status", "feedback_category"):
        op.execute(f"DROP TYPE {name}")

    op.drop_index("uq_channels_support", table_name="channels")
    # Its members, topics and messages cascade; the channel cannot exist without the enum value.
    op.execute("DELETE FROM channels WHERE type::text = 'support'")
    for name, _, _ in TYPE_INDEXES:
        op.drop_index(name, table_name="channels")
    op.drop_constraint(op.f("ck_channels_dm_pair"), "channels", type_="check")
    op.execute("ALTER TYPE channel_type RENAME TO channel_type_old")
    postgresql.ENUM(*CHANNEL_TYPES, name="channel_type").create(op.get_bind())
    op.execute(
        "ALTER TABLE channels ALTER COLUMN type TYPE channel_type USING type::text::channel_type"
    )
    op.execute("DROP TYPE channel_type_old")
    op.create_check_constraint(op.f("ck_channels_dm_pair"), "channels", sa.text(DM_PAIR))
    for name, columns, predicate in TYPE_INDEXES:
        op.create_index(name, "channels", columns, unique=True, postgresql_where=sa.text(predicate))
