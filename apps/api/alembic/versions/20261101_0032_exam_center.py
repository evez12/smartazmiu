"""Exam center: exam slots per course offering with a room, the past papers archive, import warnings (D-097).

Revision ID: 0032
Revises: 0031
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.ids import uuid7

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

IMPORT_KINDS = (
    "faculties",
    "specialties",
    "subjects",
    "semesters",
    "teachers",
    "groups",
    "students",
    "offerings",
    "enrollments",
    "buildings",
    "floors",
    "rooms",
    "week_parity",
    "schedule",
    "schedule_changes",
)

PERMISSIONS = {
    "exams.manage": (
        "Create, edit and delete exam slots and review past papers of any subject",
        ("staff", "admin"),
    ),
}


def upgrade() -> None:
    # --- exam slots: from a channel to a course offering (§5.7) ---------------------------------
    op.add_column("exam_slots", sa.Column("course_offering_id", sa.Uuid()))
    # Only slots of a course channel name their offering. Slots of other channels could not be created through
    # the product (there was no way to create any), so none are expected; they are dropped rather than guessed.
    op.execute(
        "UPDATE exam_slots s SET course_offering_id = c.course_offering_id"
        " FROM channels c WHERE c.id = s.channel_id AND c.type = 'course_offering'"
    )
    op.execute("DELETE FROM exam_slots WHERE course_offering_id IS NULL")
    op.alter_column("exam_slots", "course_offering_id", nullable=False)
    op.create_foreign_key(
        "fk_exam_slots_course_offering_id",
        "exam_slots",
        "course_offerings",
        ["course_offering_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_index("ix_exam_slots_channel_window", table_name="exam_slots")
    op.drop_column("exam_slots", "channel_id")
    op.add_column("exam_slots", sa.Column("room_code", sa.String(20)))
    op.add_column(
        "exam_slots",
        sa.Column("room_id", sa.Uuid(), sa.ForeignKey("rooms.id", ondelete="SET NULL")),
    )
    op.add_column(
        "exam_slots",
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    # The natural key of the import: one offering does not sit two exams starting at the same minute.
    op.create_unique_constraint(
        "uq_exam_slots_offering_start", "exam_slots", ["course_offering_id", "starts_at"]
    )
    op.create_index("ix_exam_slots_window", "exam_slots", ["starts_at", "ends_at"])

    # --- import wizard: the new kind and warnings that do not block applying ---------------------
    op.execute("ALTER TYPE import_kind ADD VALUE IF NOT EXISTS 'exam_slots'")
    op.add_column(
        "academic_imports",
        sa.Column(
            "warnings",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )

    # --- past papers -----------------------------------------------------------------------------
    kind = postgresql.ENUM("midterm", "final", "retake", name="past_paper_kind")
    status = postgresql.ENUM("pending", "approved", "rejected", name="past_paper_status")
    scan_status = postgresql.ENUM(name="scan_status", create_type=False)
    op.create_table(
        "past_papers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "subject_id",
            sa.Uuid(),
            sa.ForeignKey("subjects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "uploader_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        # The details below are NULL between the presigned upload and the form being saved (like materials).
        sa.Column("semester_id", sa.Uuid(), sa.ForeignKey("semesters.id", ondelete="CASCADE")),
        sa.Column("kind", kind),
        sa.Column("title", sa.String(200)),
        sa.Column("consented_at", sa.DateTime(timezone=True)),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
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
        sa.Column("status", status, server_default="pending", nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_note", sa.String(300)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("size_bytes > 0", name="positive_file_size"),
    )
    op.create_index("ix_past_papers_subject_id_status", "past_papers", ["subject_id", "status"])
    op.create_index("ix_past_papers_uploader_id", "past_papers", ["uploader_id"])
    op.create_index(
        "ix_past_papers_pending_scan",
        "past_papers",
        ["scan_after"],
        postgresql_where=sa.text("scan_status = 'pending' AND submitted_at IS NOT NULL"),
    )
    op.create_index(
        "ix_past_papers_unsaved",
        "past_papers",
        ["created_at"],
        postgresql_where=sa.text("submitted_at IS NULL"),
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
    op.drop_table("past_papers")
    op.execute("DROP TYPE past_paper_status")
    op.execute("DROP TYPE past_paper_kind")

    op.drop_column("academic_imports", "warnings")
    # Postgres cannot drop enum values: imports of the new kind go, then the type is rebuilt.
    op.execute("DELETE FROM academic_imports WHERE kind::text = 'exam_slots'")
    op.execute("ALTER TYPE import_kind RENAME TO import_kind_old")
    postgresql.ENUM(*IMPORT_KINDS, name="import_kind").create(op.get_bind())
    op.execute(
        "ALTER TABLE academic_imports ALTER COLUMN kind TYPE import_kind"
        " USING kind::text::import_kind"
    )
    op.execute("DROP TYPE import_kind_old")

    op.drop_index("ix_exam_slots_window", table_name="exam_slots")
    op.drop_constraint("uq_exam_slots_offering_start", "exam_slots", type_="unique")
    op.drop_column("exam_slots", "updated_at")
    op.drop_column("exam_slots", "room_id")
    op.drop_column("exam_slots", "room_code")
    op.add_column("exam_slots", sa.Column("channel_id", sa.Uuid()))
    op.execute(
        "UPDATE exam_slots s SET channel_id = c.id"
        " FROM channels c WHERE c.type = 'course_offering' AND c.course_offering_id = s.course_offering_id"
    )
    op.execute("DELETE FROM exam_slots WHERE channel_id IS NULL")
    op.alter_column("exam_slots", "channel_id", nullable=False)
    op.create_foreign_key(
        "exam_slots_channel_id_fkey",
        "exam_slots",
        "channels",
        ["channel_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_exam_slots_channel_window", "exam_slots", ["channel_id", "starts_at", "ends_at"]
    )
    op.drop_constraint("fk_exam_slots_course_offering_id", "exam_slots", type_="foreignkey")
    op.drop_column("exam_slots", "course_offering_id")
