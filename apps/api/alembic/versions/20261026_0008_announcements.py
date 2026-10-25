"""announcements with target audiences and their recipients

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.ids import uuid7

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUDIENCE_TYPES = ("university", "faculty", "specialty", "group", "course_offering")
TARGETS = ("faculty_id", "specialty_id", "academic_group_id", "course_offering_id")
PERMISSIONS = {
    "announcements.publish": ("Publish, edit and archive announcements", ("staff", "admin")),
}


def audience_check() -> str:
    rules = [f"(audience_type = 'university' AND num_nonnulls({', '.join(TARGETS)}) = 0)"]
    for kind, column in zip(AUDIENCE_TYPES[1:], TARGETS, strict=True):
        others = ", ".join(c for c in TARGETS if c != column)
        rules.append(
            f"(audience_type = '{kind}' AND {column} IS NOT NULL AND num_nonnulls({others}) = 0)"
        )
    return " OR ".join(rules)


def grant(permissions: dict[str, tuple[str, tuple[str, ...]]]) -> None:
    bind = op.get_bind()
    table = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("description", sa.String()),
    )
    links = sa.table(
        "role_permissions", sa.column("role_id", sa.Uuid()), sa.column("permission_id", sa.Uuid())
    )
    roles = sa.table("roles", sa.column("id", sa.Uuid()), sa.column("code", sa.String()))
    for code, (description, role_codes) in permissions.items():
        permission_id = uuid7()
        op.bulk_insert(table, [{"id": permission_id, "code": code, "description": description}])
        for role_id in bind.scalars(sa.select(roles.c.id).where(roles.c.code.in_(role_codes))):
            op.bulk_insert(links, [{"role_id": role_id, "permission_id": permission_id}])


def upgrade() -> None:
    op.create_table(
        "announcements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "status", sa.Enum("published", "archived", name="announcement_status"), nullable=False
        ),
        sa.Column(
            "published_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(100), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("audience_type", sa.Enum(*AUDIENCE_TYPES, name="audience_type"), nullable=False),
        *(sa.Column(column, sa.Uuid(), nullable=True) for column in TARGETS),
        sa.CheckConstraint(audience_check(), name=op.f("ck_announcements_one_audience_target")),
        sa.ForeignKeyConstraint(
            ["academic_group_id"],
            ["academic_groups.id"],
            name=op.f("fk_announcements_academic_group_id_academic_groups"),
        ),
        sa.ForeignKeyConstraint(
            ["course_offering_id"],
            ["course_offerings.id"],
            name=op.f("fk_announcements_course_offering_id_course_offerings"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_announcements_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["faculty_id"], ["faculties.id"], name=op.f("fk_announcements_faculty_id_faculties")
        ),
        sa.ForeignKeyConstraint(
            ["specialty_id"],
            ["specialties.id"],
            name=op.f("fk_announcements_specialty_id_specialties"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_announcements")),
        sa.UniqueConstraint(
            "created_by",
            "idempotency_key",
            name=op.f("uq_announcements_created_by_idempotency_key"),
        ),
    )
    op.create_index("ix_announcements_published_at", "announcements", ["published_at"])
    op.create_table(
        "announcement_recipients",
        sa.Column("announcement_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["announcement_id"],
            ["announcements.id"],
            name=op.f("fk_announcement_recipients_announcement_id_announcements"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_announcement_recipients_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "announcement_id", "user_id", name=op.f("pk_announcement_recipients")
        ),
    )
    op.create_index(
        op.f("ix_announcement_recipients_user_id"), "announcement_recipients", ["user_id"]
    )
    grant(PERMISSIONS)


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM permissions WHERE code IN :codes").bindparams(
            sa.bindparam("codes", tuple(PERMISSIONS), expanding=True)
        )
    )
    op.drop_table("announcement_recipients")
    op.drop_table("announcements")
    op.execute("DROP TYPE announcement_status")
    op.execute("DROP TYPE audience_type")
