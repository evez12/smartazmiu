"""events with RSVP, tickets and check-in

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.ids import uuid7

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUDIENCE_TYPES = ("university", "faculty", "specialty", "group", "course_offering")
TARGETS = ("faculty_id", "specialty_id", "academic_group_id", "course_offering_id")
TARGET_TABLES = ("faculties", "specialties", "academic_groups", "course_offerings")
PERMISSIONS = {
    "events.manage": ("Publish, edit and cancel events", ("staff", "admin")),
    "events.check_in": ("Check attendees in at events", ("staff", "admin")),
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


def timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def user_fk(table: str, column: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["users.id"], name=op.f(f"fk_{table}_{column}_users"), ondelete=ondelete
    )


def upgrade() -> None:
    # Created by 0008 for announcements; events share it.
    audience_type = postgresql.ENUM(name="audience_type", create_type=False)
    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("room_id", sa.Uuid(), nullable=True),
        sa.Column("location", sa.String(200), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("status", sa.Enum("published", "cancelled", name="event_status"), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(100), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        *timestamps(),
        sa.Column("audience_type", audience_type, nullable=False),
        *(sa.Column(column, sa.Uuid(), nullable=True) for column in TARGETS),
        sa.CheckConstraint(audience_check(), name=op.f("ck_events_one_audience_target")),
        sa.CheckConstraint("ends_at > starts_at", name=op.f("ck_events_times_ordered")),
        sa.CheckConstraint(
            "capacity IS NULL OR capacity > 0", name=op.f("ck_events_positive_capacity")
        ),
        *(
            sa.ForeignKeyConstraint(
                [column], [f"{table}.id"], name=op.f(f"fk_events_{column}_{table}")
            )
            for column, table in zip(TARGETS, TARGET_TABLES, strict=True)
        ),
        sa.ForeignKeyConstraint(
            ["room_id"], ["rooms.id"], name=op.f("fk_events_room_id_rooms"), ondelete="SET NULL"
        ),
        user_fk("events", "created_by", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_events")),
        sa.UniqueConstraint(
            "created_by", "idempotency_key", name=op.f("uq_events_created_by_idempotency_key")
        ),
    )
    op.create_index("ix_events_starts_at", "events", ["starts_at"])

    op.create_table(
        "event_recipients",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name=op.f("fk_event_recipients_event_id_events"),
            ondelete="CASCADE",
        ),
        user_fk("event_recipients", "user_id", "CASCADE"),
        sa.PrimaryKeyConstraint("event_id", "user_id", name=op.f("pk_event_recipients")),
    )
    op.create_index(op.f("ix_event_recipients_user_id"), "event_recipients", ["user_id"])

    op.create_table(
        "event_registrations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status", sa.Enum("going", "cancelled", name="registration_status"), nullable=False
        ),
        sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checked_in_by", sa.Uuid(), nullable=True),
        sa.Column(
            "check_in_method", sa.Enum("scan", "manual", name="check_in_method"), nullable=True
        ),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name=op.f("fk_event_registrations_event_id_events"),
            ondelete="CASCADE",
        ),
        user_fk("event_registrations", "user_id", "CASCADE"),
        user_fk("event_registrations", "checked_in_by", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event_registrations")),
        sa.UniqueConstraint(
            "event_id", "user_id", name=op.f("uq_event_registrations_event_id_user_id")
        ),
    )
    op.create_index(op.f("ix_event_registrations_user_id"), "event_registrations", ["user_id"])
    grant(PERMISSIONS)


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM permissions WHERE code IN :codes").bindparams(
            sa.bindparam("codes", tuple(PERMISSIONS), expanding=True)
        )
    )
    op.drop_table("event_registrations")
    op.drop_table("event_recipients")
    op.drop_table("events")
    for name in ("check_in_method", "registration_status", "event_status"):
        op.execute(f"DROP TYPE {name}")
