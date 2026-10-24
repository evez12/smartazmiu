import asyncio
import uuid

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User, UserStatus
from tests.support import TokenFactory


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_me_requires_a_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    error = response.json()["error"]
    assert error["code"] == "auth.unauthenticated"
    assert error["message"] == "Sessiyanızın müddəti bitib. Yenidən daxil olun."
    assert error["request_id"] == response.headers["x-request-id"]


async def test_me_rejects_an_invalid_token(client: AsyncClient, tokens: TokenFactory) -> None:
    expired = tokens.issue(lifetime_seconds=-120)
    response = await client.get("/api/v1/me", headers=bearer(expired))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth.unauthenticated"


async def test_first_request_provisions_the_user(
    client: AsyncClient, tokens: TokenFactory, db: AsyncSession
) -> None:
    subject = str(uuid.uuid4())
    response = await client.get(
        "/api/v1/me", headers=bearer(tokens.issue(subject, ["student", "moderator"]))
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "id": body["id"],
        "display_name": "Aysel Məmmədova",
        "given_name": "Aysel",
        "family_name": "Məmmədova",
        "status": "active",
        "roles": ["moderator", "student"],
        "permissions": [],
    }
    assert uuid.UUID(body["id"]).version == 7
    user = await db.scalar(select(User).where(User.idp_subject == subject))
    assert user is not None
    assert user.email == "aysel.mammadova@smartazmiu.test"


async def test_profile_and_roles_follow_the_identity_provider(
    client: AsyncClient, tokens: TokenFactory
) -> None:
    subject = str(uuid.uuid4())
    first = await client.get("/api/v1/me", headers=bearer(tokens.issue(subject, ["teacher"])))
    second = await client.get(
        "/api/v1/me",
        headers=bearer(
            tokens.issue(
                subject,
                ["staff", "offline_access", "default-roles-smartazmiu", "guest"],
                given_name="Leyla",
                family_name="Həsənova",
            )
        ),
    )

    assert first.json()["id"] == second.json()["id"]
    assert first.json()["roles"] == ["teacher"]
    # Non-catalogue roles and `guest` are never accepted from the token.
    assert second.json()["roles"] == ["staff"]
    assert second.json()["display_name"] == "Leyla Həsənova"


async def test_losing_every_role_leaves_no_roles(client: AsyncClient, tokens: TokenFactory) -> None:
    subject = str(uuid.uuid4())
    await client.get("/api/v1/me", headers=bearer(tokens.issue(subject, ["student"])))
    response = await client.get("/api/v1/me", headers=bearer(tokens.issue(subject, [])))
    assert response.json()["roles"] == []


async def test_concurrent_first_requests_create_one_user(
    client: AsyncClient, tokens: TokenFactory, db: AsyncSession
) -> None:
    subject = str(uuid.uuid4())
    token = tokens.issue(subject, ["student"])

    responses = await asyncio.gather(
        *(client.get("/api/v1/me", headers=bearer(token)) for _ in range(5))
    )

    assert {response.status_code for response in responses} == {200}
    assert len({response.json()["id"] for response in responses}) == 1
    count = await db.scalar(
        select(func.count()).select_from(User).where(User.idp_subject == subject)
    )
    assert count == 1


async def test_inactive_account_is_refused(
    app: FastAPI, client: AsyncClient, tokens: TokenFactory, db: AsyncSession
) -> None:
    subject = str(uuid.uuid4())
    token = tokens.issue(subject, ["student"])
    await client.get("/api/v1/me", headers=bearer(token))
    await db.execute(
        update(User).where(User.idp_subject == subject).values(status=UserStatus.INACTIVE)
    )
    await db.commit()

    response = await client.get(
        "/api/v1/me", headers={**bearer(token), "Accept-Language": "en-GB,en;q=0.9"}
    )

    assert response.status_code == 403
    error = response.json()["error"]
    assert error["code"] == "auth.account_inactive"
    assert error["message"] == "Your account is not active. Contact the dean's office for details."


async def test_second_identity_with_the_same_email_is_rejected(
    client: AsyncClient, tokens: TokenFactory, db: AsyncSession
) -> None:
    first = await client.get("/api/v1/me", headers=bearer(tokens.issue(str(uuid.uuid4()))))
    assert first.status_code == 200

    # E.g. the account was recreated in the identity provider: same e-mail, new subject.
    response = await client.get("/api/v1/me", headers=bearer(tokens.issue(str(uuid.uuid4()))))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "auth.identity_conflict"
    assert await db.scalar(select(func.count()).select_from(User)) == 1
