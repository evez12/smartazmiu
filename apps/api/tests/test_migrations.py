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
}
APP_ENUMS = (
    "user_status",
    "instruction_language",
    "semester_term",
    "enrollment_status",
    "import_kind",
    "import_status",
    "person_type",
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
        importers = await connection.scalars(
            text(
                "SELECT r.code FROM roles r JOIN role_permissions rp ON rp.role_id = r.id"
                " JOIN permissions p ON p.id = rp.permission_id"
                " WHERE p.code = 'academics.import' ORDER BY r.code"
            )
        )
        assert list(importers) == ["admin", "staff"]


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
