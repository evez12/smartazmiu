"""Interface language of a user (D-113).

Revision ID: 0037
Revises: 0036
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0037"
down_revision: str | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # NULL means "never chosen": the web app then follows Accept-Language and falls back to Azerbaijani.
    op.add_column("users", sa.Column("locale", sa.String(length=2), nullable=True))
    op.create_check_constraint(
        op.f("ck_users_locale_supported"), "users", "locale IN ('az', 'en', 'ru')"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_users_locale_supported"), "users", type_="check")
    op.drop_column("users", "locale")
