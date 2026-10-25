import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.text import search_key
from app.modules.audit.models import AuditLog
from app.modules.users.models import PersonType, User, UserStatus
from tests.support import FakeIdentityAdmin, TokenFactory


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def signed_in(
    client: AsyncClient,
    tokens: TokenFactory,
    roles: list[str],
    *,
    subject: str | None = None,
    given: str = "Tural",
    family: str = "Babayev",
    email: str | None = None,
    **claims: Any,
) -> tuple[dict[str, str], str]:
    """Signs in once (provisioning the user) and returns headers and the user id."""
    subject = subject or str(uuid.uuid4())
    token = tokens.issue(
        subject,
        roles,
        given_name=given,
        family_name=family,
        email=email or f"{subject}@smartazmiu.test",
        **claims,
    )
    response = await client.get("/api/v1/me", headers=bearer(token))
    assert response.status_code == 200, response.text
    return bearer(token), response.json()["id"]


@pytest.fixture
async def admin(client: AsyncClient, tokens: TokenFactory) -> tuple[dict[str, str], str]:
    return await signed_in(client, tokens, ["admin"], email="tural.babayev@smartazmiu.test")


def imported(university_id: str, given: str, family: str, **values: Any) -> User:
    email = f"{given.lower()}.{university_id}@smartazmiu.test"
    return User(
        idp_subject=None,
        email=email,
        university_id=university_id,
        person_type=PersonType.STUDENT,
        given_name=given,
        family_name=family,
        display_name=f"{given} {family}",
        search_key=search_key(given, family, email, university_id),
        **values,
    )


async def test_admin_screens_need_permissions(client: AsyncClient, tokens: TokenFactory) -> None:
    staff, staff_id = await signed_in(client, tokens, ["staff"])
    assert (await client.get("/api/v1/admin/users", headers=staff)).status_code == 403
    assert (await client.get("/api/v1/admin/audit-logs", headers=staff)).status_code == 403
    response = await client.put(
        f"/api/v1/admin/users/{staff_id}/roles", headers=staff, json={"roles": ["admin"]}
    )
    assert response.status_code == 403


async def test_user_search_is_diacritic_insensitive(
    client: AsyncClient, admin: tuple[dict[str, str], str], db: AsyncSession
) -> None:
    headers, _ = admin
    db.add_all(
        [
            imported("25765201", "Aysel", "Məmmədova"),
            imported("25765209", "Fuad", "Nəbiyev"),
            imported("24764108", "Lamiyə", "Nağıyeva", status=UserStatus.INACTIVE),
        ]
    )
    await db.commit()

    async def names(query: str) -> list[str]:
        response = await client.get(f"/api/v1/admin/users?{query}", headers=headers)
        assert response.status_code == 200
        return [item["display_name"] for item in response.json()["items"]]

    assert await names("q=memmedova") == ["Aysel Məmmədova"]
    assert await names("q=MƏMMƏD") == ["Aysel Məmmədova"]
    assert await names("q=2576520") == ["Aysel Məmmədova", "Fuad Nəbiyev"]
    assert await names("q=100%25") == []
    assert await names("status=inactive") == ["Lamiyə Nağıyeva"]
    assert await names("role=admin") == ["Tural Babayev"]
    page = (await client.get("/api/v1/admin/users?limit=2", headers=headers)).json()
    assert page["total"] == 4
    # Azerbaijani collation orders by family name: Babayev, Məmmədova, Nağıyeva, Nəbiyev.
    assert [item["display_name"] for item in page["items"]] == ["Tural Babayev", "Aysel Məmmədova"]
    item = page["items"][1]
    assert (item["linked"], item["roles"], item["person_type"]) == (False, [], "student")


async def test_assigning_roles_goes_through_keycloak_and_is_audited(
    client: AsyncClient,
    tokens: TokenFactory,
    admin: tuple[dict[str, str], str],
    identity_admin: FakeIdentityAdmin,
    db: AsyncSession,
) -> None:
    headers, admin_id = admin
    subject = str(uuid.uuid4())
    identity_admin.roles[subject] = {"student"}
    old_token = tokens.issue(subject, ["student"], iat=int(time.time()) - 60)
    student_id = (await client.get("/api/v1/me", headers=bearer(old_token))).json()["id"]

    response = await client.put(
        f"/api/v1/admin/users/{student_id}/roles",
        headers=headers,
        json={"roles": ["student", "moderator"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["roles"] == ["student", "moderator"]
    assert identity_admin.changes == [(subject, {"moderator"}, set())]
    [entry] = body["recent_activity"][:1]
    assert entry["action"] == "user.roles_changed"
    assert entry["actor"] == {"id": admin_id, "display_name": "Tural Babayev"}
    assert entry["details"] == {"added": ["moderator"], "removed": []}

    # The student's access token predates the change and must not undo it.
    me = await client.get("/api/v1/me", headers=bearer(old_token))
    assert sorted(me.json()["roles"]) == ["moderator", "student"]
    synced = await db.scalars(
        select(AuditLog.details).where(
            AuditLog.target_id == student_id, AuditLog.action == "user.roles_synced"
        )
    )
    assert list(synced) == [{"added": ["student"], "removed": []}]

    # A token issued after the change is mirrored again as usual.
    fresh = tokens.issue(subject, ["student"], iat=int(time.time()) + 5)
    assert (await client.get("/api/v1/me", headers=bearer(fresh))).json()["roles"] == ["student"]


async def test_removing_a_role_and_no_op_assignments(
    client: AsyncClient,
    tokens: TokenFactory,
    admin: tuple[dict[str, str], str],
    identity_admin: FakeIdentityAdmin,
) -> None:
    headers, _ = admin
    _, teacher_id = await signed_in(client, tokens, ["teacher", "moderator"], subject="kc-leyla")
    identity_admin.roles["kc-leyla"] = {"teacher", "moderator"}
    url = f"/api/v1/admin/users/{teacher_id}/roles"

    removed = await client.put(url, headers=headers, json={"roles": ["teacher"]})
    unchanged = await client.put(url, headers=headers, json={"roles": ["teacher"]})

    assert removed.json()["roles"] == unchanged.json()["roles"] == ["teacher"]
    assert identity_admin.changes == [("kc-leyla", set(), {"moderator"})]
    actions = [e["action"] for e in unchanged.json()["recent_activity"]]
    assert actions.count("user.roles_changed") == 1


@pytest.mark.parametrize(
    ("roles", "status"),
    [(["guest"], 422), (["rector"], 422)],
)
async def test_only_catalogue_roles_can_be_assigned(
    client: AsyncClient, admin: tuple[dict[str, str], str], roles: list[str], status: int
) -> None:
    headers, admin_id = admin
    response = await client.put(
        f"/api/v1/admin/users/{admin_id}/roles", headers=headers, json={"roles": roles}
    )
    assert response.status_code == status


async def test_role_assignment_guards(
    client: AsyncClient,
    admin: tuple[dict[str, str], str],
    identity_admin: FakeIdentityAdmin,
    db: AsyncSession,
) -> None:
    headers, admin_id = admin
    own = await client.put(
        f"/api/v1/admin/users/{admin_id}/roles", headers=headers, json={"roles": ["staff"]}
    )
    assert own.status_code == 409
    assert own.json()["error"]["code"] == "admin.own_admin_role"

    person = imported("25765210", "Abdullayeva", "Günel")
    db.add(person)
    await db.commit()
    unlinked = await client.put(
        f"/api/v1/admin/users/{person.id}/roles", headers=headers, json={"roles": ["moderator"]}
    )
    assert unlinked.status_code == 409
    assert unlinked.json()["error"]["code"] == "admin.user_not_linked"

    missing = await client.get(f"/api/v1/admin/users/{uuid.uuid4()}", headers=headers)
    assert missing.status_code == 404
    assert identity_admin.changes == []


async def test_identity_provider_outage_changes_nothing(
    client: AsyncClient,
    tokens: TokenFactory,
    admin: tuple[dict[str, str], str],
    identity_admin: FakeIdentityAdmin,
) -> None:
    headers, _ = admin
    _, student_id = await signed_in(client, tokens, ["student"])
    identity_admin.available = False

    response = await client.put(
        f"/api/v1/admin/users/{student_id}/roles",
        headers=headers,
        json={"roles": ["student", "moderator"]},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "identity.unavailable"
    detail = await client.get(f"/api/v1/admin/users/{student_id}", headers=headers)
    assert detail.json()["roles"] == ["student"]


async def test_audit_log_filters_and_labels(
    client: AsyncClient,
    tokens: TokenFactory,
    admin: tuple[dict[str, str], str],
    identity_admin: FakeIdentityAdmin,
    db: AsyncSession,
) -> None:
    headers, admin_id = admin
    _, student_id = await signed_in(client, tokens, ["student"], given="Ramin", family="Əliyev")
    await client.put(
        f"/api/v1/admin/users/{student_id}/roles",
        headers=headers,
        json={"roles": ["student", "moderator"]},
    )
    # One older entry, to check the date filter (Baku calendar days).
    await db.execute(
        update(AuditLog)
        .where(AuditLog.target_id == admin_id)
        .values(occurred_at=datetime(2026, 9, 30, 21, 30, tzinfo=UTC))  # 1 October 01:30 Baku
    )
    await db.commit()

    async def listing(query: str = "") -> dict[str, Any]:
        response = await client.get(f"/api/v1/admin/audit-logs?{query}", headers=headers)
        assert response.status_code == 200
        body: dict[str, Any] = response.json()
        return body

    everything = await listing()
    assert everything["total"] == 3
    changed = await listing("action=user.roles_changed")
    [entry] = changed["items"]
    assert entry["target_label"] == "Ramin Əliyev"
    assert entry["actor"]["display_name"] == "Tural Babayev"
    by_actor = await listing(f"actor_id={admin_id}")
    assert by_actor["total"] == 1
    october = await listing("occurred_from=2026-10-01&occurred_to=2026-10-01")
    assert [item["target_id"] for item in october["items"]] == [admin_id]
    september = await listing("occurred_to=2026-09-30")
    assert september["total"] == 0
    today = (datetime.now(UTC) + timedelta(hours=4)).date().isoformat()
    assert (await listing(f"occurred_from={today}"))["total"] == 2
