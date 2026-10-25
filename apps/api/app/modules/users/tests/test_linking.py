"""Imported people are linked to their first sign-in by verified e-mail (D-029); role changes are audited."""

import asyncio
import uuid

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog
from app.modules.users.models import PersonType, User
from tests.support import TokenFactory

EMAIL = "aysel.mammadova@smartazmiu.test"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def imported_student(db: AsyncSession, email: str = EMAIL) -> User:
    user = User(
        idp_subject=None,
        email=email,
        university_id="2025076512",
        person_type=PersonType.STUDENT,
        given_name="Aysel",
        family_name="Məmmədova",
        display_name="Aysel Məmmədova",
        search_key="aysel memmedova",
    )
    db.add(user)
    await db.commit()
    return user


async def audit_actions(
    db: AsyncSession, user_id: uuid.UUID
) -> list[tuple[str, dict[str, object]]]:
    rows = await db.execute(
        select(AuditLog.action, AuditLog.details)
        .where(AuditLog.target_id == str(user_id))
        .order_by(AuditLog.occurred_at, AuditLog.id)
    )
    return [(action, details) for action, details in rows]


async def test_first_sign_in_links_the_imported_person(
    client: AsyncClient, tokens: TokenFactory, db: AsyncSession
) -> None:
    person = await imported_student(db)
    subject = str(uuid.uuid4())

    # The identity provider spells the name without Azerbaijani letters; the registry wins.
    response = await client.get(
        "/api/v1/me",
        headers=bearer(
            tokens.issue(subject, ["student"], given_name="Aysel", family_name="Mammadova")
        ),
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(person.id)
    assert response.json()["display_name"] == "Aysel Məmmədova"
    await db.refresh(person)
    assert person.idp_subject == subject
    assert await audit_actions(db, person.id) == [
        ("user.account_linked", {}),
        ("user.roles_synced", {"added": ["student"], "removed": []}),
    ]


async def test_unverified_email_never_claims_an_imported_person(
    client: AsyncClient, tokens: TokenFactory, db: AsyncSession
) -> None:
    person = await imported_student(db)

    response = await client.get(
        "/api/v1/me", headers=bearer(tokens.issue(str(uuid.uuid4()), email_verified=False))
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "auth.identity_conflict"
    await db.refresh(person)
    assert person.idp_subject is None


async def test_a_linked_person_is_not_relinked_to_another_account(
    client: AsyncClient, tokens: TokenFactory, db: AsyncSession
) -> None:
    await imported_student(db)
    first = await client.get("/api/v1/me", headers=bearer(tokens.issue(str(uuid.uuid4()))))
    second = await client.get("/api/v1/me", headers=bearer(tokens.issue(str(uuid.uuid4()))))

    assert first.status_code == 200
    assert second.status_code == 409


async def test_concurrent_first_requests_link_once(
    client: AsyncClient, tokens: TokenFactory, db: AsyncSession
) -> None:
    person = await imported_student(db)
    token = tokens.issue(str(uuid.uuid4()), ["student"])

    responses = await asyncio.gather(
        *(client.get("/api/v1/me", headers=bearer(token)) for _ in range(5))
    )

    assert {response.status_code for response in responses} == {200}
    assert {response.json()["id"] for response in responses} == {str(person.id)}
    assert await db.scalar(select(func.count()).select_from(User)) == 1


async def test_email_changes_still_follow_the_identity_provider(
    client: AsyncClient, tokens: TokenFactory, db: AsyncSession
) -> None:
    person = await imported_student(db)
    subject = str(uuid.uuid4())
    await client.get("/api/v1/me", headers=bearer(tokens.issue(subject)))

    await client.get(
        "/api/v1/me", headers=bearer(tokens.issue(subject, email="aysel.m@smartazmiu.test"))
    )

    await db.refresh(person)
    assert person.email == "aysel.m@smartazmiu.test"
    assert person.display_name == "Aysel Məmmədova"
    assert "aysel.m@smartazmiu.test" in person.search_key


async def test_every_role_change_is_audited_once(
    client: AsyncClient, tokens: TokenFactory, db: AsyncSession
) -> None:
    subject = str(uuid.uuid4())
    for roles in (["student"], ["student"], ["student", "moderator"], ["moderator"]):
        await client.get("/api/v1/me", headers=bearer(tokens.issue(subject, roles)))

    user = await db.scalar(select(User).where(User.idp_subject == subject))
    assert user is not None
    assert await audit_actions(db, user.id) == [
        ("user.roles_synced", {"added": ["student"], "removed": []}),
        ("user.roles_synced", {"added": ["moderator"], "removed": []}),
        ("user.roles_synced", {"added": [], "removed": ["student"]}),
    ]
