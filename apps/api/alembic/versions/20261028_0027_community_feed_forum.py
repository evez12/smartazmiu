"""Add feed and Q&A community tables.

Revision ID: 0027
Revises: 0026
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    report_reason = postgresql.ENUM(
        "spam",
        "abuse",
        "misinformation",
        "other",
        name="community_report_reason",
        create_type=False,
    )
    report_reason.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "community_tags",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
    )
    op.create_table(
        "feed_posts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "author_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("version_id", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_index("ix_feed_posts_created_at", "feed_posts", ["created_at", "id"])
    op.create_table(
        "feed_post_tags",
        sa.Column(
            "post_id",
            sa.Uuid(),
            sa.ForeignKey("feed_posts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tag_id",
            sa.Uuid(),
            sa.ForeignKey("community_tags.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_table(
        "feed_comments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "post_id", sa.Uuid(), sa.ForeignKey("feed_posts.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "author_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("version_id", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_index("ix_feed_comments_post_id", "feed_comments", ["post_id"])
    op.create_table(
        "helpful_reactions",
        sa.Column(
            "post_id",
            sa.Uuid(),
            sa.ForeignKey("feed_posts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "community_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "reporter_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("reason", report_reason, nullable=False),
        sa.Column("details", sa.String(500), server_default="", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("reporter_id", "target_type", "target_id"),
    )
    op.create_table(
        "forum_questions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "author_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("accepted_answer_id", sa.Uuid()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("version_id", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_index("ix_forum_questions_created_at", "forum_questions", ["created_at", "id"])
    op.create_table(
        "forum_question_tags",
        sa.Column(
            "question_id",
            sa.Uuid(),
            sa.ForeignKey("forum_questions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tag_id",
            sa.Uuid(),
            sa.ForeignKey("community_tags.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_table(
        "forum_answers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "question_id",
            sa.Uuid(),
            sa.ForeignKey("forum_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("teacher_verified", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("verified_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("version_id", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_index("ix_forum_answers_question_id", "forum_answers", ["question_id"])
    op.create_table(
        "forum_votes",
        sa.Column(
            "answer_id",
            sa.Uuid(),
            sa.ForeignKey("forum_answers.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("value", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    for table in (
        "forum_votes",
        "forum_answers",
        "forum_question_tags",
        "forum_questions",
        "community_reports",
        "helpful_reactions",
        "feed_comments",
        "feed_post_tags",
        "feed_posts",
        "community_tags",
    ):
        op.drop_table(table)
    sa.Enum(name="community_report_reason").drop(op.get_bind(), checkfirst=True)
