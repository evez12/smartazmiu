"""academic data, imports and audit log

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.ids import uuid7
from app.core.text import search_key

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AZ = "az-x-icu"
ENUMS = (
    "instruction_language",
    "semester_term",
    "enrollment_status",
    "import_kind",
    "import_status",
    "person_type",
)
PERMISSIONS = {
    "academics.import": ("Import academic data from CSV/XLSX", ("staff", "admin")),
}


def timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "faculties",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name_az", sa.String(200, collation=AZ), nullable=False),
        sa.Column("name_en", sa.String(200), nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_faculties")),
        sa.UniqueConstraint("code", name=op.f("uq_faculties_code")),
    )
    op.create_table(
        "specialties",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("faculty_id", sa.Uuid(), nullable=False),
        sa.Column("name_az", sa.String(200, collation=AZ), nullable=False),
        sa.Column("name_en", sa.String(200), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["faculty_id"], ["faculties.id"], name=op.f("fk_specialties_faculty_id_faculties")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_specialties")),
        sa.UniqueConstraint("code", name=op.f("uq_specialties_code")),
    )
    op.create_index(op.f("ix_specialties_faculty_id"), "specialties", ["faculty_id"])
    op.create_table(
        "academic_groups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(20, collation=AZ), nullable=False),
        sa.Column("specialty_id", sa.Uuid(), nullable=False),
        sa.Column("admission_year", sa.SmallInteger(), nullable=False),
        sa.Column(
            "language", sa.Enum("az", "en", "ru", name="instruction_language"), nullable=False
        ),
        sa.Column("curator_id", sa.Uuid(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["curator_id"],
            ["users.id"],
            name=op.f("fk_academic_groups_curator_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["specialty_id"],
            ["specialties.id"],
            name=op.f("fk_academic_groups_specialty_id_specialties"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_academic_groups")),
        sa.UniqueConstraint("code", name=op.f("uq_academic_groups_code")),
    )
    op.create_index(op.f("ix_academic_groups_curator_id"), "academic_groups", ["curator_id"])
    op.create_index(op.f("ix_academic_groups_specialty_id"), "academic_groups", ["specialty_id"])
    op.create_table(
        "subjects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name_az", sa.String(255, collation=AZ), nullable=False),
        sa.Column("name_en", sa.String(255), nullable=False),
        sa.Column("faculty_id", sa.Uuid(), nullable=False),
        sa.Column("credits", sa.SmallInteger(), nullable=False),
        *timestamps(),
        sa.CheckConstraint("credits BETWEEN 0 AND 60", name=op.f("ck_subjects_credits_range")),
        sa.ForeignKeyConstraint(
            ["faculty_id"], ["faculties.id"], name=op.f("fk_subjects_faculty_id_faculties")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subjects")),
        sa.UniqueConstraint("code", name=op.f("uq_subjects_code")),
    )
    op.create_index(op.f("ix_subjects_faculty_id"), "subjects", ["faculty_id"])
    op.create_table(
        "semesters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column(
            "term", sa.Enum("fall", "spring", "summer", name="semester_term"), nullable=False
        ),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        *timestamps(),
        sa.CheckConstraint("ends_on > starts_on", name=op.f("ck_semesters_dates_ordered")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_semesters")),
        sa.UniqueConstraint("year", "term", name=op.f("uq_semesters_year_term")),
    )
    op.create_table(
        "course_offerings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("semester_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(64, collation=AZ), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["semester_id"],
            ["semesters.id"],
            name=op.f("fk_course_offerings_semester_id_semesters"),
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"], ["subjects.id"], name=op.f("fk_course_offerings_subject_id_subjects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_course_offerings")),
        sa.UniqueConstraint(
            "subject_id",
            "semester_id",
            "code",
            name=op.f("uq_course_offerings_subject_id_semester_id_code"),
        ),
    )
    op.create_index(op.f("ix_course_offerings_semester_id"), "course_offerings", ["semester_id"])
    op.create_index(op.f("ix_course_offerings_subject_id"), "course_offerings", ["subject_id"])
    op.create_table(
        "course_offering_groups",
        sa.Column("course_offering_id", sa.Uuid(), nullable=False),
        sa.Column("academic_group_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["academic_group_id"],
            ["academic_groups.id"],
            name=op.f("fk_course_offering_groups_academic_group_id_academic_groups"),
        ),
        sa.ForeignKeyConstraint(
            ["course_offering_id"],
            ["course_offerings.id"],
            name=op.f("fk_course_offering_groups_course_offering_id_course_offerings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "course_offering_id", "academic_group_id", name=op.f("pk_course_offering_groups")
        ),
    )
    op.create_index(
        op.f("ix_course_offering_groups_academic_group_id"),
        "course_offering_groups",
        ["academic_group_id"],
    )
    op.create_table(
        "course_offering_teachers",
        sa.Column("course_offering_id", sa.Uuid(), nullable=False),
        sa.Column("teacher_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["course_offering_id"],
            ["course_offerings.id"],
            name=op.f("fk_course_offering_teachers_course_offering_id_course_offerings"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["teacher_id"], ["users.id"], name=op.f("fk_course_offering_teachers_teacher_id_users")
        ),
        sa.PrimaryKeyConstraint(
            "course_offering_id", "teacher_id", name=op.f("pk_course_offering_teachers")
        ),
    )
    op.create_index(
        op.f("ix_course_offering_teachers_teacher_id"), "course_offering_teachers", ["teacher_id"]
    )
    op.create_table(
        "enrollments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("course_offering_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "completed", "dropped", name="enrollment_status"),
            nullable=False,
        ),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("grade", sa.SmallInteger(), nullable=True),
        *timestamps(),
        sa.CheckConstraint(
            "(status = 'completed') = (passed IS NOT NULL)",
            name=op.f("ck_enrollments_result_when_completed"),
        ),
        sa.CheckConstraint(
            "grade IS NULL OR passed IS NOT NULL", name=op.f("ck_enrollments_grade_needs_result")
        ),
        sa.CheckConstraint("grade BETWEEN 0 AND 100", name=op.f("ck_enrollments_grade_range")),
        sa.ForeignKeyConstraint(
            ["course_offering_id"],
            ["course_offerings.id"],
            name=op.f("fk_enrollments_course_offering_id_course_offerings"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_enrollments_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_enrollments")),
        sa.UniqueConstraint(
            "user_id",
            "course_offering_id",
            name=op.f("uq_enrollments_user_id_course_offering_id"),
        ),
    )
    op.create_index(
        op.f("ix_enrollments_course_offering_id"), "enrollments", ["course_offering_id"]
    )
    op.create_index("ix_enrollments_user_id_status", "enrollments", ["user_id", "status"])

    op.create_table(
        "academic_imports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "faculties",
                "specialties",
                "subjects",
                "semesters",
                "teachers",
                "groups",
                "students",
                "offerings",
                "enrollments",
                name="import_kind",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("ready", "invalid", "applied", "failed", name="import_status"),
            nullable=False,
        ),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("encoding", sa.String(20), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("summary", postgresql.JSONB(), nullable=False),
        sa.Column("errors", postgresql.JSONB(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("applied_by", sa.Uuid(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["applied_by"],
            ["users.id"],
            name=op.f("fk_academic_imports_applied_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_academic_imports_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_academic_imports")),
    )
    op.create_index("ix_academic_imports_created_at", "academic_imports", ["created_at"])
    op.create_index(
        "ix_academic_imports_kind_file_sha256", "academic_imports", ["kind", "file_sha256"]
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=True),
        sa.Column("target_id", sa.String(64), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_audit_logs_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index("ix_audit_logs_occurred_at", "audit_logs", ["occurred_at"])
    op.create_index("ix_audit_logs_actor_id_occurred_at", "audit_logs", ["actor_id", "occurred_at"])
    op.create_index(
        "ix_audit_logs_target", "audit_logs", ["target_type", "target_id", "occurred_at"]
    )
    op.create_index("ix_audit_logs_action_occurred_at", "audit_logs", ["action", "occurred_at"])

    op.alter_column("users", "idp_subject", existing_type=sa.String(255), nullable=True)
    op.add_column("users", sa.Column("university_id", sa.String(32), nullable=True))
    # add_column, unlike create_table, does not create the enum type itself.
    postgresql.ENUM("student", "teacher", name="person_type").create(op.get_bind())
    op.add_column(
        "users",
        sa.Column("person_type", postgresql.ENUM(name="person_type", create_type=False)),
    )
    op.add_column("users", sa.Column("academic_group_id", sa.Uuid(), nullable=True))
    op.add_column(
        "users", sa.Column("search_key", sa.String(700), server_default="", nullable=False)
    )
    op.create_unique_constraint(op.f("uq_users_university_id"), "users", ["university_id"])
    op.create_index(op.f("ix_users_academic_group_id"), "users", ["academic_group_id"])
    op.create_foreign_key(
        op.f("fk_users_academic_group_id_academic_groups"),
        "users",
        "academic_groups",
        ["academic_group_id"],
        ["id"],
    )

    bind = op.get_bind()
    users = sa.table(
        "users",
        sa.column("id", sa.Uuid()),
        sa.column("given_name", sa.String()),
        sa.column("family_name", sa.String()),
        sa.column("email", sa.String()),
        sa.column("search_key", sa.String()),
    )
    for row in bind.execute(
        sa.select(users.c.id, users.c.given_name, users.c.family_name, users.c.email)
    ):
        bind.execute(
            users.update()
            .where(users.c.id == row.id)
            .values(search_key=search_key(row.given_name, row.family_name, row.email))
        )

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
    op.drop_table("audit_logs")
    op.drop_table("academic_imports")
    op.drop_table("enrollments")
    op.drop_table("course_offering_teachers")
    op.drop_table("course_offering_groups")
    op.drop_table("course_offerings")
    op.drop_table("semesters")
    op.drop_table("subjects")

    # Imported people who never signed in cannot exist without an identity-provider subject.
    op.execute("DELETE FROM users WHERE idp_subject IS NULL")
    op.drop_constraint(
        op.f("fk_users_academic_group_id_academic_groups"), "users", type_="foreignkey"
    )
    op.drop_index(op.f("ix_users_academic_group_id"), table_name="users")
    op.drop_constraint(op.f("uq_users_university_id"), "users", type_="unique")
    op.drop_column("users", "search_key")
    op.drop_column("users", "academic_group_id")
    op.drop_column("users", "person_type")
    op.drop_column("users", "university_id")
    op.alter_column("users", "idp_subject", existing_type=sa.String(255), nullable=False)

    op.drop_table("academic_groups")
    op.drop_table("specialties")
    op.drop_table("faculties")
    for name in ENUMS:
        sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)
