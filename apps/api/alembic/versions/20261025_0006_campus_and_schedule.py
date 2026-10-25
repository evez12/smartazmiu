"""campus map and class schedule

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AZ = "az-x-icu"
OLD_IMPORT_KINDS = (
    "faculties",
    "specialties",
    "subjects",
    "semesters",
    "teachers",
    "groups",
    "students",
    "offerings",
    "enrollments",
)
NEW_IMPORT_KINDS = ("buildings", "floors", "rooms", "week_parity", "schedule", "schedule_changes")
ROOM_TYPES = (
    "lecture_hall",
    "classroom",
    "laboratory",
    "computer_lab",
    "studio",
    "library",
    "office",
    "service",
)


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
    for kind in NEW_IMPORT_KINDS:
        op.execute(f"ALTER TYPE import_kind ADD VALUE IF NOT EXISTS '{kind}'")

    op.create_table(
        "buildings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name_az", sa.String(200, collation=AZ), nullable=False),
        sa.Column("address", sa.String(255), nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_buildings")),
        sa.UniqueConstraint("code", name=op.f("uq_buildings_code")),
    )
    op.create_table(
        "floors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("building_id", sa.Uuid(), nullable=False),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column("name_az", sa.String(100, collation=AZ), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        *timestamps(),
        sa.CheckConstraint("width > 0 AND height > 0", name=op.f("ck_floors_positive_size")),
        sa.ForeignKeyConstraint(
            ["building_id"], ["buildings.id"], name=op.f("fk_floors_building_id_buildings")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_floors")),
        sa.UniqueConstraint("building_id", "level", name=op.f("uq_floors_building_id_level")),
    )
    op.create_index(op.f("ix_floors_building_id"), "floors", ["building_id"])
    op.create_table(
        "rooms",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(20, collation=AZ), nullable=False),
        sa.Column("floor_id", sa.Uuid(), nullable=False),
        sa.Column("name_az", sa.String(200, collation=AZ), nullable=False),
        sa.Column("type", sa.Enum(*ROOM_TYPES, name="room_type"), nullable=False),
        sa.Column("capacity", sa.SmallInteger(), nullable=True),
        sa.Column("x", sa.Integer(), nullable=False),
        sa.Column("y", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("search_key", sa.String(300), nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "width > 0 AND height > 0 AND x >= 0 AND y >= 0", name=op.f("ck_rooms_geometry")
        ),
        sa.CheckConstraint(
            "capacity IS NULL OR capacity > 0", name=op.f("ck_rooms_positive_capacity")
        ),
        sa.ForeignKeyConstraint(["floor_id"], ["floors.id"], name=op.f("fk_rooms_floor_id_floors")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rooms")),
        sa.UniqueConstraint("code", name=op.f("uq_rooms_code")),
    )
    op.create_index(op.f("ix_rooms_floor_id"), "rooms", ["floor_id"])

    week_parity = postgresql.ENUM("every", "upper", "lower", name="week_parity")
    week_parity.create(op.get_bind())
    parity_column = postgresql.ENUM(name="week_parity", create_type=False)
    op.create_table(
        "schedule_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("course_offering_id", sa.Uuid(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("starts_at", sa.Time(), nullable=False),
        sa.Column("ends_at", sa.Time(), nullable=False),
        sa.Column("week_parity", parity_column, nullable=False),
        sa.Column(
            "class_type",
            sa.Enum("lecture", "seminar", "laboratory", name="class_type"),
            nullable=False,
        ),
        sa.Column("room_id", sa.Uuid(), nullable=True),
        sa.Column("teacher_id", sa.Uuid(), nullable=True),
        sa.Column("active_from", sa.Date(), nullable=False),
        sa.Column("active_until", sa.Date(), nullable=True),
        *timestamps(),
        sa.CheckConstraint("weekday BETWEEN 1 AND 7", name=op.f("ck_schedule_entries_iso_weekday")),
        sa.CheckConstraint("ends_at > starts_at", name=op.f("ck_schedule_entries_times_ordered")),
        sa.CheckConstraint(
            "active_until IS NULL OR active_until >= active_from",
            name=op.f("ck_schedule_entries_active_range"),
        ),
        sa.ForeignKeyConstraint(
            ["course_offering_id"],
            ["course_offerings.id"],
            name=op.f("fk_schedule_entries_course_offering_id_course_offerings"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["room_id"],
            ["rooms.id"],
            name=op.f("fk_schedule_entries_room_id_rooms"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["teacher_id"],
            ["users.id"],
            name=op.f("fk_schedule_entries_teacher_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_schedule_entries")),
    )
    op.create_index(
        "ix_schedule_entries_offering_weekday",
        "schedule_entries",
        ["course_offering_id", "weekday"],
    )
    op.create_index(op.f("ix_schedule_entries_room_id"), "schedule_entries", ["room_id"])
    op.create_index(op.f("ix_schedule_entries_teacher_id"), "schedule_entries", ["teacher_id"])
    op.create_table(
        "schedule_entry_groups",
        sa.Column("schedule_entry_id", sa.Uuid(), nullable=False),
        sa.Column("academic_group_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["schedule_entry_id"],
            ["schedule_entries.id"],
            name=op.f("fk_schedule_entry_groups_schedule_entry_id_schedule_entries"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["academic_group_id"],
            ["academic_groups.id"],
            name=op.f("fk_schedule_entry_groups_academic_group_id_academic_groups"),
        ),
        sa.PrimaryKeyConstraint(
            "schedule_entry_id", "academic_group_id", name=op.f("pk_schedule_entry_groups")
        ),
    )
    op.create_index(
        op.f("ix_schedule_entry_groups_academic_group_id"),
        "schedule_entry_groups",
        ["academic_group_id"],
    )
    op.create_table(
        "schedule_changes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("schedule_entry_id", sa.Uuid(), nullable=False),
        sa.Column("occurs_on", sa.Date(), nullable=False),
        sa.Column("cancelled", sa.Boolean(), nullable=False),
        sa.Column("new_date", sa.Date(), nullable=True),
        sa.Column("new_starts_at", sa.Time(), nullable=True),
        sa.Column("new_ends_at", sa.Time(), nullable=True),
        sa.Column("room_id", sa.Uuid(), nullable=True),
        sa.Column("teacher_id", sa.Uuid(), nullable=True),
        sa.Column("note", sa.String(300), nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "NOT cancelled OR (new_date IS NULL AND new_starts_at IS NULL AND new_ends_at IS NULL"
            " AND room_id IS NULL AND teacher_id IS NULL)",
            name=op.f("ck_schedule_changes_cancel_has_no_changes"),
        ),
        sa.CheckConstraint(
            "(new_starts_at IS NULL) = (new_ends_at IS NULL)",
            name=op.f("ck_schedule_changes_new_times_together"),
        ),
        sa.CheckConstraint(
            "new_ends_at IS NULL OR new_ends_at > new_starts_at",
            name=op.f("ck_schedule_changes_new_times_ordered"),
        ),
        sa.ForeignKeyConstraint(
            ["schedule_entry_id"],
            ["schedule_entries.id"],
            name=op.f("fk_schedule_changes_schedule_entry_id_schedule_entries"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["room_id"],
            ["rooms.id"],
            name=op.f("fk_schedule_changes_room_id_rooms"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["teacher_id"],
            ["users.id"],
            name=op.f("fk_schedule_changes_teacher_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_schedule_changes")),
        sa.UniqueConstraint(
            "schedule_entry_id",
            "occurs_on",
            name=op.f("uq_schedule_changes_schedule_entry_id_occurs_on"),
        ),
    )
    op.create_index("ix_schedule_changes_new_date", "schedule_changes", ["new_date"])
    op.create_index(op.f("ix_schedule_changes_teacher_id"), "schedule_changes", ["teacher_id"])
    op.create_table(
        "week_parity_overrides",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("semester_id", sa.Uuid(), nullable=False),
        sa.Column("week_starts_on", sa.Date(), nullable=False),
        sa.Column("parity", parity_column, nullable=False),
        sa.CheckConstraint(
            "extract(isodow from week_starts_on) = 1",
            name=op.f("ck_week_parity_overrides_starts_on_monday"),
        ),
        sa.CheckConstraint(
            "parity <> 'every'", name=op.f("ck_week_parity_overrides_upper_or_lower")
        ),
        sa.ForeignKeyConstraint(
            ["semester_id"],
            ["semesters.id"],
            name=op.f("fk_week_parity_overrides_semester_id_semesters"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_week_parity_overrides")),
        sa.UniqueConstraint(
            "semester_id",
            "week_starts_on",
            name=op.f("uq_week_parity_overrides_semester_id_week_starts_on"),
        ),
    )
    op.create_index(
        op.f("ix_week_parity_overrides_semester_id"), "week_parity_overrides", ["semester_id"]
    )


def downgrade() -> None:
    op.drop_table("week_parity_overrides")
    op.drop_table("schedule_changes")
    op.drop_table("schedule_entry_groups")
    op.drop_table("schedule_entries")
    op.execute("DROP TYPE class_type")
    op.execute("DROP TYPE week_parity")
    op.drop_table("rooms")
    op.execute("DROP TYPE room_type")
    op.drop_table("floors")
    op.drop_table("buildings")

    # Postgres cannot drop enum values: imports of the new kinds go, then the type is rebuilt.
    op.execute(
        sa.text("DELETE FROM academic_imports WHERE kind::text IN :kinds").bindparams(
            sa.bindparam("kinds", NEW_IMPORT_KINDS, expanding=True)
        )
    )
    op.execute("ALTER TYPE import_kind RENAME TO import_kind_old")
    postgresql.ENUM(*OLD_IMPORT_KINDS, name="import_kind").create(op.get_bind())
    op.execute(
        "ALTER TABLE academic_imports ALTER COLUMN kind TYPE import_kind"
        " USING kind::text::import_kind"
    )
    op.execute("DROP TYPE import_kind_old")
