"""materials: catalogue per subject and semester, versions, reports

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.ids import uuid7

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = {
    "materials.manage": (
        "Upload materials for any subject and hide reported ones",
        ("staff", "admin"),
    ),
}
AZ = "az-x-icu"


def upgrade() -> None:
    material_type = postgresql.ENUM(
        "lecture",
        "seminar",
        "lab",
        "syllabus",
        "exam_prep",
        "other",
        name="material_type",
        create_type=False,
    )
    reason = postgresql.ENUM(
        "copyright",
        "wrong_content",
        "inappropriate",
        "other",
        name="material_report_reason",
        create_type=False,
    )
    status = postgresql.ENUM(
        "open", "actioned", "dismissed", name="material_report_status", create_type=False
    )
    scan_status = postgresql.ENUM(name="scan_status", create_type=False)
    for enum in (material_type, reason, status):
        enum.create(op.get_bind())

    op.create_table(
        "materials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "subject_id",
            sa.Uuid(),
            sa.ForeignKey("subjects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "semester_id",
            sa.Uuid(),
            sa.ForeignKey("semesters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", material_type, nullable=False),
        sa.Column("title", sa.String(200, collation=AZ), nullable=False),
        sa.Column("description", sa.String(1000), server_default="", nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("hidden_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_materials_subject_id_semester_id", "materials", ["subject_id", "semester_id"]
    )

    op.create_table(
        "material_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("material_id", sa.Uuid(), sa.ForeignKey("materials.id", ondelete="CASCADE")),
        sa.Column("version", sa.SmallInteger()),
        sa.Column("uploader_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column(
            "subject_id",
            sa.Uuid(),
            sa.ForeignKey("subjects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "semester_id",
            sa.Uuid(),
            sa.ForeignKey("semesters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("object_key", sa.String(300), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime", sa.String(127), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("note", sa.String(300), server_default="", nullable=False),
        sa.Column("scan_status", scan_status, server_default="pending", nullable=False),
        sa.Column("scan_attempts", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column(
            "scan_after", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("scanned_at", sa.DateTime(timezone=True)),
        sa.Column("purged_at", sa.DateTime(timezone=True)),
        sa.Column("copyright_confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("copyright_text_version", sa.String(20)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("material_id", "version"),
    )
    op.create_index("ix_material_versions_material_id", "material_versions", ["material_id"])
    op.create_index(
        "ix_material_versions_pending",
        "material_versions",
        ["scan_after"],
        postgresql_where=sa.text("scan_status = 'pending' AND material_id IS NOT NULL"),
    )
    op.create_index(
        "ix_material_versions_unsaved",
        "material_versions",
        ["created_at"],
        postgresql_where=sa.text("material_id IS NULL"),
    )

    op.create_table(
        "material_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "material_id",
            sa.Uuid(),
            sa.ForeignKey("materials.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reporter_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("reason", reason, nullable=False),
        sa.Column("note", sa.String(500), server_default="", nullable=False),
        sa.Column("status", status, server_default="open", nullable=False),
        sa.Column("handled_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("handled_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("material_id", "reporter_id"),
    )
    op.create_index(
        "ix_material_reports_status_created_at", "material_reports", ["status", "created_at"]
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
    op.drop_table("material_reports")
    op.drop_table("material_versions")
    op.drop_table("materials")
    for name in ("material_report_status", "material_report_reason", "material_type"):
        op.execute(f"DROP TYPE {name}")
