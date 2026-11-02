"""Anonymizable user references (D-108, D-112).

Revision ID: 0036
Revises: 0035
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0036"
down_revision: str | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, column, the ON DELETE rule before this migration); afterwards all three are SET NULL (D-108).
ANONYMIZED = (
    ("attendance_records", "student_id", "CASCADE"),
    ("attendance_sessions", "opened_by", None),
    ("past_papers", "uploader_id", "CASCADE"),
)


def _foreign_key_name(table: str, column: str) -> str:
    inspector = sa.inspect(op.get_bind())
    for foreign_key in inspector.get_foreign_keys(table):
        if (
            foreign_key["constrained_columns"] == [column]
            and foreign_key["referred_table"] == "users"
        ):
            name = foreign_key["name"]
            assert name is not None
            return name
    raise RuntimeError(f"{table}.{column} has no foreign key to users")


def upgrade() -> None:
    for table, column, _ in ANONYMIZED:
        op.drop_constraint(_foreign_key_name(table, column), table, type_="foreignkey")
        op.alter_column(table, column, existing_type=sa.Uuid(), nullable=True)
        op.create_foreign_key(
            f"fk_{table}_{column}_users", table, "users", [column], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    for table, column, rule in reversed(ANONYMIZED):
        orphans = op.get_bind().scalar(
            sa.select(sa.func.count())
            .select_from(sa.table(table))
            .where(sa.column(column).is_(None))
        )
        if orphans:
            raise RuntimeError(
                f"{orphans} rows of {table} belong to deleted accounts; they cannot get a NOT NULL {column} back"
            )
        op.drop_constraint(_foreign_key_name(table, column), table, type_="foreignkey")
        op.alter_column(table, column, existing_type=sa.Uuid(), nullable=False)
        op.create_foreign_key(
            f"fk_{table}_{column}_users", table, "users", [column], ["id"], ondelete=rule
        )
