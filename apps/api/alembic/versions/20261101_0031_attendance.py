"""QR attendance: meetings opened by a teacher and the check-ins recorded against them (D-094).

Revision ID: 0031
Revises: 0030
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.ids import uuid7

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Teachers run the meetings of offerings they teach (D-071); staff and administrators, the dean's office, run any.
PERMISSIONS = {
    "attendance.manage": (
        "Open attendance meetings, mark students and read attendance of any course offering",
        ("staff", "admin"),
    ),
}


def upgrade() -> None:
    method = postgresql.ENUM("qr", "code", "manual", name="attendance_method", create_type=False)
    method.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "attendance_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "course_offering_id",
            sa.Uuid(),
            sa.ForeignKey("course_offerings.id"),
            nullable=False,
        ),
        sa.Column("opened_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(120), server_default="", nullable=False),
        sa.Column(
            "opened_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("expires_at > opened_at", name="expires_after_open"),
    )
    op.create_index(
        "ix_attendance_sessions_course_offering_id", "attendance_sessions", ["course_offering_id"]
    )
    op.create_index(
        "uq_attendance_sessions_open",
        "attendance_sessions",
        ["course_offering_id"],
        unique=True,
        postgresql_where=sa.text("closed_at IS NULL"),
    )
    op.create_table(
        "attendance_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("attendance_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("method", method, nullable=False),
        sa.Column("marked_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("reason", sa.String(300)),
        sa.Column(
            "checked_in_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("session_id", "student_id"),
    )
    op.create_index("ix_attendance_records_student_id", "attendance_records", ["student_id"])

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
    op.drop_table("attendance_records")
    op.drop_table("attendance_sessions")
    postgresql.ENUM(name="attendance_method").drop(op.get_bind(), checkfirst=True)
