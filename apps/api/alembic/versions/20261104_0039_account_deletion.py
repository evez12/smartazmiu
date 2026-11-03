"""Account deletion: grace-period columns, purge ledger, anonymizable authors (ADR 0005, D-135).

Revision ID: 0039
Revises: 0038
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0039"
down_revision: str | None = "0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Content other people read keeps its text when the author goes (D-091, D-093): the author reference becomes nullable
# and SET NULL, as migration 0036 did for attendance and past papers.
ANONYMIZED = (
    ("feed_posts", "author_id"),
    ("feed_comments", "author_id"),
    ("forum_questions", "author_id"),
    ("forum_answers", "author_id"),
    ("course_tips", "author_id"),
    ("assignment_submissions", "student_id"),
    ("assignment_files", "student_id"),
    ("quiz_attempts", "student_id"),
)

OLD_STATUSES = ("active", "inactive")
NEW_STATUSES = ("pending_deletion", "deleted")


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
    # ALTER TYPE ... ADD VALUE cannot run in a transaction block together with a use of the new value.
    with op.get_context().autocommit_block():
        for value in NEW_STATUSES:
            op.execute(f"ALTER TYPE user_status ADD VALUE IF NOT EXISTS '{value}'")

    # deleted_at: when the person asked; purge_at: when the grace period ends (30 days later).
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("purge_at", sa.DateTime(timezone=True)))
    op.create_check_constraint(
        "deletion_timestamps", "users", "purge_at IS NULL OR deleted_at IS NOT NULL"
    )
    op.create_index(
        "ix_users_purge_at", "users", ["purge_at"], postgresql_where=sa.text("purge_at IS NOT NULL")
    )

    # A hash of the id replaces the actor of audit entries about a deleted person (the id column is set to NULL).
    op.add_column("audit_logs", sa.Column("actor_hash", sa.String(64)))

    deletion_reason = sa.Enum(
        "self_service", "staff", "test_cleanup", name="account_deletion_reason", create_type=False
    )
    deletion_reason.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "account_deletions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        # Keyed HMAC of the user id (ADR 0005): the one stable name of the person once the row is a tombstone, and what
        # the restore runbook matches a backup against.
        sa.Column("subject_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("reason", deletion_reason, nullable=False),
        sa.Column("requested_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column(
            "requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("purge_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        # One timestamp per purge step, so a retry skips what is done (at-least-once, idempotent).
        sa.Column("database_purged_at", sa.DateTime(timezone=True)),
        sa.Column("objects_purged_at", sa.DateTime(timezone=True)),
        sa.Column("identity_removed_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.SmallInteger(), server_default="0", nullable=False),
        # The class of the last failure, never its message: messages can quote personal data.
        sa.Column("last_error", sa.String(80)),
    )
    op.create_index(
        "ix_account_deletions_due",
        "account_deletions",
        ["purge_due_at"],
        postgresql_where=sa.text("completed_at IS NULL AND cancelled_at IS NULL"),
    )
    op.create_index(
        "ix_account_deletions_user_id",
        "account_deletions",
        ["user_id"],
        postgresql_where=sa.text("completed_at IS NULL AND cancelled_at IS NULL"),
        unique=True,
    )

    for table, column in ANONYMIZED:
        op.drop_constraint(_foreign_key_name(table, column), table, type_="foreignkey")
        op.alter_column(table, column, existing_type=sa.Uuid(), nullable=True)
        op.create_foreign_key(
            f"fk_{table}_{column}_users", table, "users", [column], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    bind = op.get_bind()
    for table, column in reversed(ANONYMIZED):
        orphans = bind.scalar(
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
            f"fk_{table}_{column}_users",
            table,
            "users",
            [column],
            ["id"],
            ondelete="CASCADE",
        )

    pending = bind.scalar(
        sa.text("SELECT count(*) FROM users WHERE status::text = ANY(:values)"),
        {"values": list(NEW_STATUSES)},
    )
    if pending:
        raise RuntimeError(
            f"{pending} accounts are pending deletion or deleted; purge or cancel first"
        )

    op.drop_table("account_deletions")
    sa.Enum(name="account_deletion_reason").drop(bind, checkfirst=True)
    op.drop_column("audit_logs", "actor_hash")
    op.drop_index("ix_users_purge_at", "users")
    op.drop_constraint(op.f("ck_users_deletion_timestamps"), "users", type_="check")
    op.drop_column("users", "purge_at")
    op.drop_column("users", "deleted_at")

    # Enum values cannot be dropped: swap in a type that has only the old ones.
    op.execute("ALTER TYPE user_status RENAME TO user_status_old")
    old = sa.Enum(*OLD_STATUSES, name="user_status")
    old.create(bind)
    op.execute("ALTER TABLE users ALTER COLUMN status DROP DEFAULT")
    op.execute(
        "ALTER TABLE users ALTER COLUMN status TYPE user_status USING status::text::user_status"
    )
    op.execute("ALTER TABLE users ALTER COLUMN status SET DEFAULT 'active'")
    op.execute("DROP TYPE user_status_old")
