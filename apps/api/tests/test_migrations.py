import asyncio

from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from conftest import alembic_config

APP_TABLES = {
    "users",
    "roles",
    "permissions",
    "role_permissions",
    "user_roles",
    "faculties",
    "specialties",
    "academic_groups",
    "subjects",
    "semesters",
    "course_offerings",
    "course_offering_groups",
    "course_offering_teachers",
    "enrollments",
    "academic_imports",
    "audit_logs",
    "consent_records",
    "notifications",
    "notification_deliveries",
    "push_subscriptions",
    "notification_preferences",
    "notification_quiet_hours",
    "announcements",
    "announcement_recipients",
    "events",
    "event_recipients",
    "event_registrations",
    "channels",
    "channel_topics",
    "channel_members",
    "channel_reads",
    "messages",
    "message_client_ids",
    "message_attachments",
    "message_reactions",
    "message_mentions",
    "user_blocks",
    "reports",
    "materials",
    "material_versions",
    "material_reports",
    "feedback",
}
APP_ENUMS = (
    "user_status",
    "instruction_language",
    "semester_term",
    "enrollment_status",
    "import_kind",
    "import_status",
    "person_type",
    "dm_policy",
    "contact_visibility",
    "consent_purpose",
    "notification_category",
    "notification_kind",
    "delivery_channel",
    "delivery_status",
    "audience_type",
    "announcement_status",
    "event_status",
    "registration_status",
    "check_in_method",
    "channel_type",
    "channel_member_role",
    "notify_level",
    "scan_status",
    "report_target",
    "report_reason",
    "report_status",
    "material_type",
    "material_report_reason",
    "material_report_status",
    "feedback_category",
    "feedback_status",
)


async def table_names(engine: AsyncEngine) -> set[str]:
    async with engine.connect() as connection:
        return set(await connection.run_sync(lambda sync: inspect(sync).get_table_names()))


async def test_migrations_are_reversible(settings: Settings, engine: AsyncEngine) -> None:
    config = alembic_config(settings)

    await asyncio.to_thread(command.downgrade, config, "base")
    assert await table_names(engine) & APP_TABLES == set()
    async with engine.connect() as connection:
        enum_count = await connection.scalar(
            text("SELECT count(*) FROM pg_type WHERE typname = ANY(:names)"),
            {"names": list(APP_ENUMS)},
        )
    assert enum_count == 0

    await asyncio.to_thread(command.upgrade, config, "head")
    assert await table_names(engine) >= APP_TABLES
    async with engine.connect() as connection:
        roles = await connection.scalars(text("SELECT code FROM roles ORDER BY code"))
        assert list(roles) == ["admin", "guest", "moderator", "staff", "student", "teacher"]
        for permission in (
            "academics.import",
            "announcements.publish",
            "events.manage",
            "events.check_in",
            "admin.reports.read",
            "admin.reports.handle",
            "materials.manage",
            "admin.feedback.read",
            "admin.feedback.handle",
            "chat.moderate",
        ):
            holders = await connection.scalars(
                text(
                    "SELECT r.code FROM roles r JOIN role_permissions rp ON rp.role_id = r.id"
                    " JOIN permissions p ON p.id = rp.permission_id"
                    " WHERE p.code = :code ORDER BY r.code"
                ),
                {"code": permission},
            )
            expected = (
                ["admin", "moderator", "staff"]
                if permission in {"admin.reports.read", "admin.reports.handle"}
                else ["moderator"]
                if permission == "chat.moderate"
                else ["admin", "staff"]
            )
            assert list(holders) == expected, permission
        # The SQL UUIDv7 generator: version 7, RFC variant, time-ordered.
        first, second = (
            await connection.scalar(text("SELECT uuid7()")),
            await connection.scalar(text("SELECT uuid7()")),
        )
        assert (first.version, first.variant) == (7, "specified in RFC 4122")
        assert first.bytes[:6] <= second.bytes[:6]


async def test_downgrade_removes_people_who_never_signed_in(
    settings: Settings, engine: AsyncEngine
) -> None:
    config = alembic_config(settings)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO users (id, idp_subject, university_id, display_name, given_name,"
                " family_name) VALUES (gen_random_uuid(), NULL, '2025076599', 'Orxan Rzayev',"
                " 'Orxan', 'Rzayev'), (gen_random_uuid(), 'kc-1', NULL, 'Aysel Məmmədova',"
                " 'Aysel', 'Məmmədova')"
            )
        )
    try:
        await asyncio.to_thread(command.downgrade, config, "0001")
        async with engine.connect() as connection:
            subjects = await connection.scalars(text("SELECT idp_subject FROM users"))
            assert list(subjects) == ["kc-1"]
    finally:
        await asyncio.to_thread(command.upgrade, config, "head")
        async with engine.begin() as connection:
            await connection.execute(text("TRUNCATE users CASCADE"))


async def test_messages_are_partitioned_by_month_in_both_directions(
    settings: Settings, engine: AsyncEngine
) -> None:
    """ADR 0002: the chat migrations create the parent with this month and three more, and remove them all."""
    config = alembic_config(settings)
    partitions = text(
        "SELECT count(*) FROM pg_inherits i JOIN pg_class p ON p.oid = i.inhparent"
        " WHERE p.relname = 'messages'"
    )
    leftovers = text("SELECT count(*) FROM pg_class WHERE relname LIKE 'messages\\_y%'")
    try:
        await asyncio.to_thread(command.downgrade, config, "0011")
        async with engine.connect() as connection:
            columns = await connection.run_sync(
                lambda sync: {column["name"] for column in inspect(sync).get_columns("messages")}
            )
            assert "body_tsv" not in columns
            assert await connection.scalar(partitions) == 4
        await asyncio.to_thread(command.downgrade, config, "0010")
        async with engine.connect() as connection:
            assert await connection.scalar(leftovers) == 0
    finally:
        await asyncio.to_thread(command.upgrade, config, "head")
    async with engine.connect() as connection:
        assert await connection.scalar(partitions) == 4
        indexes = await connection.run_sync(
            lambda sync: {index["name"] for index in inspect(sync).get_indexes("messages")}
        )
        assert {"ix_messages_channel_id_id", "ix_messages_parent_id", "ix_messages_body_tsv"} <= (
            indexes
        )
