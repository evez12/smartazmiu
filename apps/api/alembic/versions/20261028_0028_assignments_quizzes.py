"""Add assignments and quizzes.

Revision ID: 0028
Revises: 0027
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    late_policy = sa.Enum("accept", "penalize", "reject", name="late_policy")
    submission_status = sa.Enum("draft", "submitted", "returned", name="submission_status")
    question_type = sa.Enum("mcq", "multi_select", "short_answer", name="question_type")
    attempt_status = sa.Enum("in_progress", "submitted", "auto_submitted", name="attempt_status")
    for enum in (late_policy, submission_status, question_type, attempt_status):
        enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "assignments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "course_offering_id",
            sa.Uuid(),
            sa.ForeignKey("course_offerings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("instructions", sa.Text(), server_default="", nullable=False),
        sa.Column("available_from", sa.DateTime(timezone=True)),
        sa.Column("deadline", sa.DateTime(timezone=True)),
        sa.Column("max_points", sa.Numeric(7, 2), server_default="100", nullable=False),
        sa.Column("late_policy", late_policy, server_default="reject", nullable=False),
        sa.Column("late_penalty_percent", sa.Numeric(5, 2), server_default="0", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("max_points > 0", name="positive_max_points"),
        sa.CheckConstraint(
            "late_penalty_percent >= 0 AND late_penalty_percent <= 100",
            name="late_penalty_percent_range",
        ),
        sa.CheckConstraint(
            "available_from IS NULL OR deadline IS NULL OR deadline > available_from",
            name="assignment_dates_ordered",
        ),
    )
    op.create_index("ix_assignments_course_offering_id", "assignments", ["course_offering_id"])
    op.create_index(
        "ix_assignments_course_offering_deadline", "assignments", ["course_offering_id", "deadline"]
    )

    op.create_table(
        "assignment_submissions",
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
        sa.Column("status", submission_status, server_default="draft", nullable=False),
        sa.Column("object_key", sa.String(300)),
        sa.Column("filename", sa.String(255)),
        sa.Column("mime", sa.String(127)),
        sa.Column("size_bytes", sa.Integer()),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("is_late", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("assignment_id", "student_id"),
        sa.CheckConstraint("size_bytes IS NULL OR size_bytes >= 0", name="non_negative_size_bytes"),
    )
    op.create_index(
        "ix_assignment_submissions_assignment_id", "assignment_submissions", ["assignment_id"]
    )
    op.create_index(
        "ix_assignment_submissions_student_id", "assignment_submissions", ["student_id"]
    )
    op.create_index(
        "ix_assignment_submissions_student_status",
        "assignment_submissions",
        ["student_id", "status"],
    )

    op.create_table(
        "assignment_grades",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "submission_id",
            sa.Uuid(),
            sa.ForeignKey("assignment_submissions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("graded_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("points", sa.Numeric(7, 2), nullable=False),
        sa.Column("feedback", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "graded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("submission_id"),
        sa.CheckConstraint("points >= 0", name="non_negative_points"),
    )
    op.create_index("ix_assignment_grades_submission_id", "assignment_grades", ["submission_id"])

    op.create_table(
        "quizzes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "course_offering_id",
            sa.Uuid(),
            sa.ForeignKey("course_offerings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("instructions", sa.Text(), server_default="", nullable=False),
        sa.Column("available_from", sa.DateTime(timezone=True)),
        sa.Column("deadline", sa.DateTime(timezone=True)),
        sa.Column("time_limit_seconds", sa.Integer()),
        sa.Column("max_attempts", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "time_limit_seconds IS NULL OR time_limit_seconds > 0", name="positive_time_limit"
        ),
        sa.CheckConstraint("max_attempts > 0", name="positive_max_attempts"),
    )
    op.create_index("ix_quizzes_course_offering_id", "quizzes", ["course_offering_id"])
    op.create_index(
        "ix_quizzes_course_offering_published", "quizzes", ["course_offering_id", "published_at"]
    )

    op.create_table(
        "quiz_questions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "quiz_id", sa.Uuid(), sa.ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("type", question_type, nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("points", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column(
            "options", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False
        ),
        sa.Column("correct_answer", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_required", sa.Boolean(), server_default="true", nullable=False),
        sa.UniqueConstraint("quiz_id", "position"),
        sa.CheckConstraint("points > 0", name="positive_question_points"),
    )
    op.create_index("ix_quiz_questions_quiz_id", "quiz_questions", ["quiz_id"])
    op.create_index("ix_quiz_questions_quiz_position", "quiz_questions", ["quiz_id", "position"])

    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "quiz_id", sa.Uuid(), sa.ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "student_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("attempt_number", sa.SmallInteger(), nullable=False),
        sa.Column("status", attempt_status, server_default="in_progress", nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column(
            "answers", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("score", sa.Integer()),
        sa.Column("max_score", sa.Integer()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("quiz_id", "student_id", "attempt_number"),
        sa.CheckConstraint("attempt_number > 0", name="positive_attempt_number"),
    )
    op.create_index("ix_quiz_attempts_quiz_id", "quiz_attempts", ["quiz_id"])
    op.create_index("ix_quiz_attempts_student_id", "quiz_attempts", ["student_id"])
    op.create_index("ix_quiz_attempts_quiz_status", "quiz_attempts", ["quiz_id", "status"])
    op.create_index("ix_quiz_attempts_student", "quiz_attempts", ["student_id", "created_at"])


def downgrade() -> None:
    for table in (
        "quiz_attempts",
        "quiz_questions",
        "quizzes",
        "assignment_grades",
        "assignment_submissions",
        "assignments",
    ):
        op.drop_table(table)
    for enum_name in ("attempt_status", "question_type", "submission_status", "late_policy"):
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
