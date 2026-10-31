"""Complete assignments and quizzes: scanned submission files, offering-scoped management, manual scores (D-092).

Revision ID: 0030
Revises: 0029
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.ids import uuid7

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Teachers manage the offerings they teach through their teaching assignment (D-071); these two let staff and
# administrators manage any offering. Migration 0028 created the routes without ever granting a permission.
PERMISSIONS = {
    "assignments.manage": (
        "Create and grade assignments of any course offering",
        ("staff", "admin"),
    ),
    "quizzes.manage": (
        "Create quizzes of any course offering and read their results",
        ("staff", "admin"),
    ),
}


def upgrade() -> None:
    scan_status = postgresql.ENUM(name="scan_status", create_type=False)
    op.create_table(
        "assignment_files",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "assignment_id",
            sa.Uuid(),
            sa.ForeignKey("assignments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        # NULL between the presigned upload and the submission being saved (like material versions, D-071).
        sa.Column(
            "submission_id",
            sa.Uuid(),
            sa.ForeignKey("assignment_submissions.id", ondelete="CASCADE"),
        ),
        sa.Column("version", sa.SmallInteger()),
        sa.Column("object_key", sa.String(300), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime", sa.String(127), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("scan_status", scan_status, server_default="pending", nullable=False),
        sa.Column("scan_attempts", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column(
            "scan_after", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("scanned_at", sa.DateTime(timezone=True)),
        sa.Column("purged_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("submission_id", "version"),
        sa.CheckConstraint("size_bytes > 0", name="positive_file_size"),
    )
    op.create_index("ix_assignment_files_assignment_id", "assignment_files", ["assignment_id"])
    op.create_index("ix_assignment_files_student_id", "assignment_files", ["student_id"])
    op.create_index(
        "ix_assignment_files_pending",
        "assignment_files",
        ["scan_after"],
        postgresql_where=sa.text("scan_status = 'pending' AND submission_id IS NOT NULL"),
    )
    op.create_index(
        "ix_assignment_files_unsaved",
        "assignment_files",
        ["created_at"],
        postgresql_where=sa.text("submission_id IS NULL"),
    )
    # The file now lives in assignment_files; the columns were written by a client-chosen key (D-092).
    for column in ("object_key", "filename", "mime", "size_bytes"):
        op.drop_column("assignment_submissions", column)
    # A teacher's points before the late penalty, so a regrade or an audit can see both numbers.
    op.add_column("assignment_grades", sa.Column("raw_points", sa.Numeric(7, 2)))
    op.execute("UPDATE assignment_grades SET raw_points = points")
    op.alter_column("assignment_grades", "raw_points", nullable=False)

    op.add_column(
        "quiz_attempts",
        sa.Column(
            "manual_scores",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_index(
        "uq_quiz_attempts_in_progress",
        "quiz_attempts",
        ["quiz_id", "student_id"],
        unique=True,
        postgresql_where=sa.text("status = 'in_progress'"),
    )

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
    op.drop_index("uq_quiz_attempts_in_progress", table_name="quiz_attempts")
    op.drop_column("quiz_attempts", "manual_scores")
    op.drop_column("assignment_grades", "raw_points")
    op.add_column("assignment_submissions", sa.Column("object_key", sa.String(300)))
    op.add_column("assignment_submissions", sa.Column("filename", sa.String(255)))
    op.add_column("assignment_submissions", sa.Column("mime", sa.String(127)))
    op.add_column("assignment_submissions", sa.Column("size_bytes", sa.Integer()))
    op.drop_index("ix_assignment_files_unsaved", table_name="assignment_files")
    op.drop_index("ix_assignment_files_pending", table_name="assignment_files")
    op.drop_index("ix_assignment_files_student_id", table_name="assignment_files")
    op.drop_index("ix_assignment_files_assignment_id", table_name="assignment_files")
    op.drop_table("assignment_files")
