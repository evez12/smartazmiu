import uuid
from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient

from app.modules.academics.models import ImportKind
from app.modules.academics.tests.conftest import SEED_DIR, Upload
from tests.support import TokenFactory

Seed = Callable[..., Awaitable[None]]


@pytest.fixture
def student(tokens: TokenFactory) -> dict[str, str]:
    token = tokens.issue(
        str(uuid.uuid4()),
        ["student"],
        given_name="Aysel",
        family_name="Məmmədova",
        email="aysel.mammadova@smartazmiu.test",
    )
    return {"Authorization": f"Bearer {token}"}


async def seed_campus(upload: Upload) -> None:
    for kind in (ImportKind.BUILDINGS, ImportKind.FLOORS, ImportKind.ROOMS):
        await upload(kind, (SEED_DIR / f"{kind.value}.csv").read_bytes(), apply=True)


async def test_campus_import_is_idempotent(upload: Upload) -> None:
    await seed_campus(upload)

    again = await upload(
        ImportKind.ROOMS, (SEED_DIR / "rooms.csv").read_bytes(), file_name="otaqlar.csv"
    )

    assert again["status"] == "ready"
    assert again["summary"] == {"created": 0, "updated": 0, "unchanged": 66, "removed": 0}


async def test_rooms_are_validated_against_their_floor(upload: Upload) -> None:
    await upload(ImportKind.BUILDINGS, "code,name_az,address\n1,Tədris korpusu 1,\n", apply=True)
    await upload(
        ImportKind.FLOORS,
        "building_code,level,name_az,width,height\n1,1,1-ci mərtəbə,600,200\n",
        apply=True,
    )

    preview = await upload(
        ImportKind.ROOMS,
        "code,building_code,floor_level,name_az,type,capacity,x,y,width,height\n"
        "1-101,1,1,Mühazirə zalı,mühazirə zalı,120,0,0,160,80\n"
        "1-120,1,1,,auditoriya,30,560,0,80,80\n"
        "1-130,1,1,,auditoriya,30,0,150,80,80\n"
        "1-201,1,2,,auditoriya,30,0,0,80,80\n"
        "9-101,9,1,,auditoriya,30,0,0,80,80\n"
        "1-140,1,1,,anbar,30,0,0,80,80\n",
    )

    assert preview["status"] == "invalid"
    assert [(e["row"], e["column"], e["code"]) for e in preview["errors"]] == [
        (3, "width", "outside_floor_plan"),
        (4, "height", "outside_floor_plan"),
        (5, "floor_level", "unknown_reference"),
        (6, "building_code", "unknown_reference"),
        (7, "type", "invalid_choice"),
    ]


async def test_buildings_and_floor_plan(
    client: AsyncClient, upload: Upload, student: dict[str, str]
) -> None:
    await seed_campus(upload)

    buildings = (await client.get("/api/v1/campus/buildings", headers=student)).json()
    assert [(b["code"], b["name"]) for b in buildings] == [
        ("1", "Tədris korpusu 1"),
        ("2", "Tədris korpusu 2"),
    ]
    assert [floor["name"] for floor in buildings[0]["floors"]] == [
        "1-ci mərtəbə",
        "2-ci mərtəbə",
        "3-cü mərtəbə",
    ]

    plan = (await client.get("/api/v1/campus/buildings/1/floors/3", headers=student)).json()
    assert (plan["width"], plan["height"], plan["name"]) == (600, 200, "3-cü mərtəbə")
    assert plan["building"] == {"code": "1", "name": "Tədris korpusu 1"}
    room = next(r for r in plan["rooms"] if r["code"] == "1-305")
    assert room == {
        "code": "1-305",
        "name": "",
        "type": "classroom",
        "capacity": 30,
        "x": 410,
        "y": 0,
        "width": 90,
        "height": 80,
    }
    for shape in plan["rooms"]:
        assert shape["x"] + shape["width"] <= plan["width"]
        assert shape["y"] + shape["height"] <= plan["height"]

    missing = await client.get("/api/v1/campus/buildings/1/floors/9", headers=student)
    assert missing.status_code == 404


async def test_room_search_and_lookup(
    client: AsyncClient, upload: Upload, student: dict[str, str]
) -> None:
    await seed_campus(upload)

    async def search(query: str) -> list[str]:
        response = await client.get("/api/v1/campus/rooms", params={"q": query}, headers=student)
        assert response.status_code == 200
        return [room["code"] for room in response.json()]

    # Typed without Azerbaijani letters.
    assert await search("komputer") == ["1-203", "2-310", "2-311"]
    assert await search("KOMPÜTER OTAĞI") == ["1-203", "2-310", "2-311"]
    assert await search("1-30") == ["1-301", "1-302", "1-303", "1-304", "1-305", "1-306"]
    # LIKE wildcards are matched literally.
    assert await search("%") == []
    assert await search("_") == []

    room = (await client.get("/api/v1/campus/rooms/2-204", headers=student)).json()
    assert room == {
        "code": "2-204",
        "name": "Statistika laboratoriyası",
        "type": "laboratory",
        "capacity": 24,
        "building": {"code": "2", "name": "Tədris korpusu 2"},
        "floor": {"level": 2, "name": "2-ci mərtəbə"},
    }
    assert (await client.get("/api/v1/campus/rooms/9-999", headers=student)).status_code == 404


async def test_campus_requires_sign_in(client: AsyncClient) -> None:
    for path in ("/api/v1/campus/buildings", "/api/v1/campus/rooms?q=1", "/api/v1/campus/rooms/1"):
        assert (await client.get(path)).status_code == 401
