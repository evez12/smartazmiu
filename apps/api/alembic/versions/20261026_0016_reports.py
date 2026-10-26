"""reports: reports of messages and people, and the permissions to review them

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.ids import uuid7

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = {
    "admin.reports.read": ("List reports of messages and people", ("staff", "admin")),
    "admin.reports.handle": ("Mark reports as actioned or dismissed", ("staff", "admin")),
}


def upgrade() -> None:
    target = postgresql.ENUM("message", "user", name="report_target", create_type=False)
    reason = postgresql.ENUM(
        "spam",
        "harassment",
        "hate",
        "exam_leak",
        "privacy",
        "other",
        name="report_reason",
        create_type=False,
    )
    status = postgresql.ENUM(
        "open", "actioned", "dismissed", name="report_status", create_type=False
    )
    for enum in (target, reason, status):
        enum.create(op.get_bind())
    op.create_table(
        "reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reporter_id", sa.Uuid(), nullable=True),
        sa.Column("target_type", target, nullable=False),
        sa.Column("target_id", sa.String(64), nullable=False),
        sa.Column("channel_id", sa.Uuid(), nullable=True),
        sa.Column("reason", reason, nullable=False),
        sa.Column("note", sa.String(500), server_default="", nullable=False),
        sa.Column("status", status, server_default="open", nullable=False),
        sa.Column("handled_by", sa.Uuid(), nullable=True),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["reporter_id"],
            ["users.id"],
            name=op.f("fk_reports_reporter_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["channel_id"],
            ["channels.id"],
            name=op.f("fk_reports_channel_id_channels"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["handled_by"],
            ["users.id"],
            name=op.f("fk_reports_handled_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reports")),
        sa.UniqueConstraint(
            "reporter_id",
            "target_type",
            "target_id",
            name=op.f("uq_reports_reporter_id_target_type_target_id"),
        ),
    )
    op.create_index("ix_reports_status_created_at", "reports", ["status", "created_at"])
    op.create_index("ix_reports_target", "reports", ["target_type", "target_id"])

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
    op.drop_index("ix_reports_target", table_name="reports")
    op.drop_index("ix_reports_status_created_at", table_name="reports")
    op.drop_table("reports")
    for name in ("report_status", "report_reason", "report_target"):
        op.execute(f"DROP TYPE {name}")
