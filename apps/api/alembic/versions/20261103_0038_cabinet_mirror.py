"""Personal cabinet mirror: grades, transcript, appeals, sync runs, conflicts (D-126).

Revision ID: 0038
Revises: 0037
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.ids import uuid7

revision: str = "0038"
down_revision: str | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = {
    "cabinet.manage": (
        "Start the personal cabinet sync and read its runs and conflicts (never grade values)",
        ("staff", "admin"),
    ),
}


def _term() -> postgresql.ENUM:
    return postgresql.ENUM(name="semester_term", create_type=False)


def _user_id() -> sa.Column[sa.Uuid]:
    return sa.Column(
        "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )


def upgrade() -> None:
    trigger = postgresql.ENUM("nightly", "manual", name="cabinet_sync_trigger")
    outcome = postgresql.ENUM("succeeded", "failed", name="cabinet_sync_outcome")
    appeal_status = postgresql.ENUM(
        "submitted", "under_review", "upheld", "rejected", name="cabinet_appeal_status"
    )

    op.create_table(
        "cabinet_sync_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("trigger", trigger, nullable=False),
        sa.Column("triggered_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("outcome", outcome, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("students_synced", sa.Integer(), nullable=False),
        sa.Column("students_not_found", sa.Integer(), nullable=False),
        sa.Column("students_mismatched", sa.Integer(), nullable=False),
        sa.Column("conflicts", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(64)),
    )
    op.create_index("ix_cabinet_sync_runs_finished_at", "cabinet_sync_runs", ["finished_at"])

    op.create_table(
        "cabinet_students",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("specialty_name", sa.String(200), nullable=False),
        sa.Column("credits_earned", sa.SmallInteger(), nullable=False),
        sa.Column("cumulative_average", sa.Numeric(5, 2)),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "cabinet_grades",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_id(),
        sa.Column("subject_code", sa.String(20), nullable=False),
        sa.Column("subject_name", sa.String(255), nullable=False),
        sa.Column("credits", sa.SmallInteger(), nullable=False),
        sa.Column("semester_year", sa.SmallInteger(), nullable=False),
        sa.Column("semester_term", _term(), nullable=False),
        sa.Column("score", sa.SmallInteger(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.CheckConstraint("score BETWEEN 0 AND 100", name=op.f("ck_cabinet_grades_score_range")),
        sa.UniqueConstraint(
            "user_id",
            "subject_code",
            "semester_year",
            "semester_term",
            name="uq_cabinet_grades_natural_key",
        ),
    )

    op.create_table(
        "cabinet_semesters",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_id(),
        sa.Column("semester_year", sa.SmallInteger(), nullable=False),
        sa.Column("semester_term", _term(), nullable=False),
        sa.Column("credits_attempted", sa.SmallInteger(), nullable=False),
        sa.Column("credits_earned", sa.SmallInteger(), nullable=False),
        sa.Column("average", sa.Numeric(5, 2)),
        sa.UniqueConstraint(
            "user_id", "semester_year", "semester_term", name="uq_cabinet_semesters_natural_key"
        ),
    )

    op.create_table(
        "cabinet_appeals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_id(),
        sa.Column("reference", sa.String(40), nullable=False),
        sa.Column("subject_code", sa.String(20), nullable=False),
        sa.Column("semester_year", sa.SmallInteger(), nullable=False),
        sa.Column("semester_term", _term(), nullable=False),
        sa.Column("status", appeal_status, nullable=False),
        sa.Column("submitted_on", sa.Date(), nullable=False),
        sa.Column("decided_on", sa.Date()),
        sa.UniqueConstraint("user_id", "reference", name="uq_cabinet_appeals_natural_key"),
    )

    op.create_table(
        "cabinet_conflicts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_id(),
        sa.Column("subject_code", sa.String(20), nullable=False),
        sa.Column("semester_year", sa.SmallInteger(), nullable=False),
        sa.Column("semester_term", _term(), nullable=False),
        sa.Column(
            "detected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "user_id",
            "subject_code",
            "semester_year",
            "semester_term",
            name="uq_cabinet_conflicts_natural_key",
        ),
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
    for table in (
        "cabinet_conflicts",
        "cabinet_appeals",
        "cabinet_semesters",
        "cabinet_grades",
        "cabinet_students",
        "cabinet_sync_runs",
    ):
        op.drop_table(table)
    op.execute("DROP TYPE cabinet_appeal_status")
    op.execute("DROP TYPE cabinet_sync_outcome")
    op.execute("DROP TYPE cabinet_sync_trigger")
