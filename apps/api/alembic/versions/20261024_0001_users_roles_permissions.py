"""users, roles, permissions

Revision ID: 0001
Revises:
Create Date: 2026-10-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.ids import uuid7

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AZ = "az-x-icu"
GLOBAL_ROLES = ("student", "teacher", "staff", "moderator", "admin", "guest")


def upgrade() -> None:
    user_status = sa.Enum("active", "inactive", name="user_status")

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("idp_subject", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("given_name", sa.String(100, collation=AZ), nullable=False),
        sa.Column("family_name", sa.String(100, collation=AZ), nullable=False),
        sa.Column("display_name", sa.String(200, collation=AZ), nullable=False),
        sa.Column("status", user_status, server_default="active", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("idp_subject", name=op.f("uq_users_idp_subject")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    roles = op.create_table(
        "roles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        sa.UniqueConstraint("code", name=op.f("uq_roles_code")),
    )
    op.create_table(
        "permissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_permissions")),
        sa.UniqueConstraint("code", name=op.f("uq_permissions_code")),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("permission_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name=op.f("fk_role_permissions_role_id_roles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
            name=op.f("fk_role_permissions_permission_id_permissions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("role_id", "permission_id", name=op.f("pk_role_permissions")),
    )
    op.create_index(
        op.f("ix_role_permissions_permission_id"), "role_permissions", ["permission_id"]
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column(
            "granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_roles_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], name=op.f("fk_user_roles_role_id_roles"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "role_id", name=op.f("pk_user_roles")),
    )
    op.create_index(op.f("ix_user_roles_role_id"), "user_roles", ["role_id"])

    # The global role catalogue (§2). Permissions are added by the migrations of the features that use them.
    op.bulk_insert(roles, [{"id": uuid7(), "code": code} for code in GLOBAL_ROLES])


def downgrade() -> None:
    op.drop_index(op.f("ix_user_roles_role_id"), table_name="user_roles")
    op.drop_table("user_roles")
    op.drop_index(op.f("ix_role_permissions_permission_id"), table_name="role_permissions")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("users")
    sa.Enum(name="user_status").drop(op.get_bind(), checkfirst=True)
