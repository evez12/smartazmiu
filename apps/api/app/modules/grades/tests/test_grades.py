"""``GET /me/grades``: a student sees only their own finished, graded courses."""

from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academics.models import (
    CourseOffering,
    Enrollment,
    EnrollmentStatus,
    ImportKind,
    Subject,
)
from app.modules.chat.tests.conftest import MakePerson
from app.modules.materials.tests.test_materials import sign_in
from app.modules.users.models import User
from tests.support import TokenFactory

Seed = Callable[..., Awaitable[None]]
URL = "/api/v1/me/grades"


@pytest.fixture
async def seeded(seed: Seed) -> None:
    await seed(ImportKind.ENROLLMENTS)


async def clear_grades(db: AsyncSession, user_email: str) -> User:
    """The seed grades some of the account's courses; start from none."""
    user = await db.scalar(select(User).where(User.email == user_email))
    assert user is not None
    await db.execute(update(Enrollment).where(Enrollment.user_id == user.id).values(grade=None))
    await db.commit()
    return user


async def grade_two(db: AsyncSession, user_email: str) -> list[str]:
    """Give the first two completed enrollments of the account a score; return their subject codes."""
    user = await clear_grades(db, user_email)
    rows = (
        await db.execute(
            select(Enrollment, Subject.code)
            .join(CourseOffering, CourseOffering.id == Enrollment.course_offering_id)
            .join(Subject, Subject.id == CourseOffering.subject_id)
            .where(Enrollment.user_id == user.id, Enrollment.status == EnrollmentStatus.COMPLETED)
            .order_by(Subject.code)
            .limit(2)
        )
    ).all()
    assert len(rows) == 2
    for (enrollment, _), score in zip(rows, (78, 42), strict=True):
        await db.execute(
            update(Enrollment)
            .where(Enrollment.id == enrollment.id)
            .values(grade=score, passed=score >= 51)
        )
    await db.commit()
    return [code for _, code in rows]


async def test_a_student_sees_their_graded_courses_only(
    client: AsyncClient, tokens: TokenFactory, seeded: None, db: AsyncSession, person: MakePerson
) -> None:
    aysel = await sign_in(
        client, tokens, "aysel.mammadova@smartazmiu.test", ["student"], "Aysel", "Məmmədova"
    )
    codes = await grade_two(db, "aysel.mammadova@smartazmiu.test")

    response = await client.get(URL, headers=aysel.headers)

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["subject_code"] for item in items] == codes
    assert [item["score"] for item in items] == [78, 42]
    assert [item["passed"] for item in items] == [True, False]
    assert all(item["credits"] > 0 and item["semester_year"] for item in items)

    stranger = await person("Orxan", "Rzayev")
    assert (await client.get(URL, headers=stranger.headers)).json() == {"items": []}


async def test_courses_without_a_score_are_left_out(
    client: AsyncClient, tokens: TokenFactory, seeded: None, db: AsyncSession
) -> None:
    await clear_grades(db, "aysel.mammadova@smartazmiu.test")
    aysel = await sign_in(
        client, tokens, "aysel.mammadova@smartazmiu.test", ["student"], "Aysel", "Məmmədova"
    )

    response = await client.get(URL, headers=aysel.headers)

    assert response.json() == {"items": []}


async def test_sign_in_is_required(client: AsyncClient) -> None:
    assert (await client.get(URL)).status_code == 401
