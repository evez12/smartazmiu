import uuid
from typing import Annotated, Any

import pytest
from fastapi import Depends, FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import require_permission
from app.modules.users.models import Permission, Role, RolePermission
from app.modules.users.service import CurrentUser
from tests.support import TokenFactory

REPORT_QUEUE = "moderation.reports.read"


async def grant(db: AsyncSession, permission_code: str, *role_codes: str) -> None:
    permission = Permission(code=permission_code, description="Read the report queue")
    db.add(permission)
    await db.flush()
    for role_id in await db.scalars(select(Role.id).where(Role.code.in_(role_codes))):
        db.add(RolePermission(role_id=role_id, permission_id=permission.id))
    await db.commit()


@pytest.fixture
def protected_app(app: FastAPI) -> FastAPI:
    async def report_queue(
        user: Annotated[CurrentUser, Depends(require_permission(REPORT_QUEUE))],
    ) -> dict[str, str]:
        return {"user_id": str(user.id)}

    app.add_api_route("/api/v1/test/reports", report_queue, methods=["GET"])
    return app


async def call(
    client: AsyncClient, tokens: TokenFactory, roles: list[str]
) -> tuple[int, dict[str, Any]]:
    token = tokens.issue(str(uuid.uuid4()), roles)
    response = await client.get(
        "/api/v1/test/reports", headers={"Authorization": f"Bearer {token}"}
    )
    return response.status_code, response.json()


async def test_permission_granted_through_a_role(
    protected_app: FastAPI, client: AsyncClient, tokens: TokenFactory, db: AsyncSession
) -> None:
    await grant(db, REPORT_QUEUE, "moderator")
    status, _ = await call(client, tokens, ["moderator"])
    assert status == 200


async def test_permissions_are_the_union_of_roles(
    protected_app: FastAPI, client: AsyncClient, tokens: TokenFactory, db: AsyncSession
) -> None:
    await grant(db, REPORT_QUEUE, "moderator")
    status, _ = await call(client, tokens, ["student", "moderator"])
    assert status == 200


async def test_missing_permission_is_forbidden(
    protected_app: FastAPI, client: AsyncClient, tokens: TokenFactory, db: AsyncSession
) -> None:
    await grant(db, REPORT_QUEUE, "moderator")
    status, body = await call(client, tokens, ["student"])
    assert status == 403
    assert body["error"]["code"] == "auth.forbidden"
    assert body["error"]["details"] == {"permission": REPORT_QUEUE}


async def test_unauthenticated_request_is_rejected_before_permission_check(
    protected_app: FastAPI, client: AsyncClient
) -> None:
    response = await client.get("/api/v1/test/reports")
    assert response.status_code == 401
