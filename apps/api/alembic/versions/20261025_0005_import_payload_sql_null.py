"""import payloads: cleared files are SQL NULL, not JSON null

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-25
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE academic_imports SET payload = NULL WHERE payload = 'null'::jsonb")


def downgrade() -> None:
    # Nothing to restore: JSON null and SQL NULL both meant "file contents removed" (D-038).
    pass
