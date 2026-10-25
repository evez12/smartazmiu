import uuid
from collections.abc import Awaitable, Callable
from datetime import date

import pytest
from httpx import AsyncClient

from app.modules.academics import service
from tests.support import TokenFactory

from .conftest import Upload

Seed = Callable[..., Awaitable[None]]


@pytest.fixture(autouse=True)
def autumn_2026(monkeypatch: pytest.MonkeyPatch) -> None:
    """The sample data's current semester is 2026 Payız."""
    monkeypatch.setattr(service, "baku_today", lambda: date(2026, 10, 25))


def headers(
    tokens: TokenFactory, email: str, roles: list[str], given: str, family: str
) -> dict[str, str]:
    token = tokens.issue(
        str(uuid.uuid4()), roles, given_name=given, family_name=family, email=email
    )
    return {"Authorization": f"Bearer {token}"}


async def test_student_sees_own_group_and_current_subjects(
    client: AsyncClient, tokens: TokenFactory, seed: Seed
) -> None:
    await seed()
    aysel = headers(tokens, "aysel.mammadova@smartazmiu.test", ["student"], "Aysel", "Məmmədova")

    response = await client.get("/api/v1/me/academics", headers=aysel)

    assert response.status_code == 200
    body = response.json()
    assert body["group"] == {
        "code": "765a2",
        "admission_year": 2025,
        "language": "az",
        "specialty": {"code": "6004004", "name": "İqtisadiyyat"},
        "faculty": {"code": "TIQ", "name": "Tikinti iqtisadiyyatı fakültəsi"},
    }
    # Azerbaijani collation: X comes between H and I, so "Xarici" sorts before "Mikroiqtisadiyyat".
    assert [course["subject"]["name"] for course in body["courses"]] == [
        "Xarici dildə işgüzar və akademik kommunikasiya-3",
        "Mikroiqtisadiyyat",
        "Mülki müdafiə",
        "Sosiologiya",
        "Statistika",
    ]
    micro = body["courses"][1]
    assert micro["semester"] == {"year": 2026, "term": "fall"}
    assert micro["groups"] == ["765a2"]
    assert micro["teachers"] == ["Şəhla Ağayeva", "Fərid İsmayılov"]
    assert body["courses"][2]["groups"] == ["765a1", "765a2"]
    assert body["teaching"] == []
    for forbidden in ("grade", "passed", "email"):
        assert forbidden not in response.text


async def test_teacher_sees_current_teaching(
    client: AsyncClient, tokens: TokenFactory, seed: Seed
) -> None:
    await seed()
    leyla = headers(tokens, "leyla.hasanova@smartazmiu.test", ["teacher"], "Leyla", "Həsənova")

    body = (await client.get("/api/v1/me/academics", headers=leyla)).json()

    assert body["group"] is None
    assert body["courses"] == []
    # 2025 Payız has ended; only the 2026 Payız Statistika offerings are current.
    assert [
        (c["subject"]["code"], c["offering_code"], c["student_count"]) for c in body["teaching"]
    ] == [
        ("IQT-2102", "765a1", 18),
        ("IQT-2102", "765a2", 22),
    ]


async def test_retaking_student_sees_the_retake(
    client: AsyncClient, tokens: TokenFactory, seed: Seed
) -> None:
    await seed()
    anar = headers(tokens, "anar.rustamov@smartazmiu.test", ["student"], "Anar", "Rüstəmov")
    body = (await client.get("/api/v1/me/academics", headers=anar)).json()
    assert body["group"]["code"] == "764a1"
    assert [(c["subject"]["code"], c["offering_code"]) for c in body["courses"]] == [
        ("IQT-2101", "765a2")
    ]


async def test_user_without_academic_data_gets_empty_lists(
    client: AsyncClient, tokens: TokenFactory, upload: Upload
) -> None:
    newcomer = headers(tokens, "kamal.aliyev@smartazmiu.test", ["student"], "Kamal", "Əliyev")
    response = await client.get("/api/v1/me/academics", headers=newcomer)
    assert response.json() == {"group": None, "courses": [], "teaching": []}
