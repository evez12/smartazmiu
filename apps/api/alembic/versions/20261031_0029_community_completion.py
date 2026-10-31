"""Complete the feed and forum: shared reports, hiding, idempotent creation, a tag catalogue (D-090).

Revision ID: 0029
Revises: 0028
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONTENT_TABLES = ("feed_posts", "feed_comments", "forum_questions", "forum_answers")
NEW_TARGETS = ("post", "comment", "question", "answer")
OLD_TARGETS = ("message", "user", "tip")

# A fixed starting catalogue (§6 "tags"); slugs are ASCII for URLs, names keep Azerbaijani letters (§5.1).
TAGS = (
    ("imtahanlar", "İmtahanlar"),
    ("dersler", "Dərslər"),
    ("kitabxana", "Kitabxana"),
    ("yataqxana", "Yataqxana"),
    ("teqaud", "Təqaüd"),
    ("karyera", "Karyera və təcrübə"),
    ("tedbirler", "Tədbirlər"),
    ("kampus", "Kampus həyatı"),
    ("iqtisadiyyat", "İqtisadiyyat"),
    ("riyaziyyat", "Riyaziyyat"),
    ("proqramlasdirma", "Proqramlaşdırma"),
)


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for target in NEW_TARGETS:
            op.execute(f"ALTER TYPE report_target ADD VALUE IF NOT EXISTS '{target}'")

    # The old community reasons map onto the §5.4 set used by every other report.
    op.execute(
        """
        INSERT INTO reports (id, reporter_id, target_type, target_id, reason, note, status, created_at)
        SELECT id, reporter_id, target_type::report_target, target_id::text,
               (CASE reason::text WHEN 'spam' THEN 'spam' WHEN 'abuse' THEN 'harassment'
                ELSE 'other' END)::report_reason,
               details, 'open', created_at
        FROM community_reports
        ON CONFLICT (reporter_id, target_type, target_id) DO NOTHING
        """
    )
    op.drop_table("community_reports")
    op.execute("DROP TYPE community_report_reason")

    for table in CONTENT_TABLES:
        op.add_column(table, sa.Column("hidden_at", sa.DateTime(timezone=True)))
        op.add_column(table, sa.Column("idempotency_key", sa.String(100)))
        op.create_unique_constraint(
            f"uq_{table}_author_idempotency_key", table, ["author_id", "idempotency_key"]
        )
    op.create_index("ix_feed_comments_post_created", "feed_comments", ["post_id", "created_at"])
    op.create_index("ix_feed_post_tags_tag", "feed_post_tags", ["tag_id"])
    op.create_index("ix_forum_question_tags_tag", "forum_question_tags", ["tag_id"])

    tags = sa.table(
        "community_tags", sa.column("id", sa.Uuid()), sa.column("slug"), sa.column("name")
    )
    op.bulk_insert(tags, [{"id": uuid.uuid4(), "slug": s, "name": n} for s, n in TAGS])


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM community_tags WHERE slug IN :slugs").bindparams(
            sa.bindparam("slugs", tuple(slug for slug, _ in TAGS), expanding=True)
        )
    )
    op.drop_index("ix_forum_question_tags_tag", table_name="forum_question_tags")
    op.drop_index("ix_feed_post_tags_tag", table_name="feed_post_tags")
    op.drop_index("ix_feed_comments_post_created", table_name="feed_comments")
    for table in CONTENT_TABLES:
        op.drop_constraint(f"uq_{table}_author_idempotency_key", table, type_="unique")
        op.drop_column(table, "idempotency_key")
        op.drop_column(table, "hidden_at")

    report_reason = postgresql.ENUM(
        "spam", "abuse", "misinformation", "other", name="community_report_reason"
    )
    report_reason.create(op.get_bind())
    op.create_table(
        "community_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "reporter_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column(
            "reason",
            postgresql.ENUM(name="community_report_reason", create_type=False),
            nullable=False,
        ),
        sa.Column("details", sa.String(500), server_default="", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("reporter_id", "target_type", "target_id"),
    )
    # Reports filed by deleted accounts have no reporter and cannot be kept in the old table.
    op.execute(
        """
        INSERT INTO community_reports (id, reporter_id, target_type, target_id, reason, details, created_at)
        SELECT id, reporter_id, target_type::text, target_id::uuid,
               (CASE reason::text WHEN 'spam' THEN 'spam' WHEN 'harassment' THEN 'abuse'
                WHEN 'hate' THEN 'abuse' ELSE 'other' END)::community_report_reason,
               note, created_at
        FROM reports
        WHERE target_type::text IN ('post', 'comment', 'question', 'answer')
          AND reporter_id IS NOT NULL
        """
    )
    op.execute(
        "DELETE FROM reports WHERE target_type::text IN ('post', 'comment', 'question', 'answer')"
    )
    op.execute("ALTER TYPE report_target RENAME TO report_target_old")
    postgresql.ENUM(*OLD_TARGETS, name="report_target").create(op.get_bind())
    op.execute(
        "ALTER TABLE reports ALTER COLUMN target_type TYPE report_target"
        " USING target_type::text::report_target"
    )
    op.execute("DROP TYPE report_target_old")
