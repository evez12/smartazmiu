"""Import specifications for buildings, floors and rooms (same wizard and rules as the academic registry)."""

import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy import select

from app.core.text import search_key
from app.modules.academics import parsing
from app.modules.academics.importers import ImportRun, ImportSpec, ParsedRow
from app.modules.academics.models import ImportKind
from app.modules.academics.parsing import Column
from app.modules.campus.models import Building, Floor, Room, RoomType

ROOM_TYPES = {
    **{room_type.value: room_type for room_type in RoomType},
    "muhazire zali": RoomType.LECTURE_HALL,
    "auditoriya": RoomType.CLASSROOM,
    "laboratoriya": RoomType.LABORATORY,
    "komputer otagi": RoomType.COMPUTER_LAB,
    "kompyuter otagi": RoomType.COMPUTER_LAB,
    "emalatxana": RoomType.STUDIO,
    "kitabxana": RoomType.LIBRARY,
    "kabinet": RoomType.OFFICE,
    "xidmeti otaq": RoomType.SERVICE,
}

# Plan units are decimetres; 10 000 is a kilometre, far beyond any building.
_PLAN_SIZE = parsing.integer(1, 10_000)
_PLAN_OFFSET = parsing.integer(0, 10_000)


class BuildingsImport(ImportSpec):
    kind = ImportKind.BUILDINGS
    columns = (
        Column("code", parsing.code()),
        Column("name_az", parsing.text(200)),
        Column("address", parsing.text(255), required=False, default=""),
    )
    unique = (("code",),)

    async def apply(self, run: ImportRun, rows: list[ParsedRow]) -> None:
        existing = await run.lookup(Building, Building.code, (r.values["code"] for r in rows))
        for row in rows:
            values = row.values
            fields = {"name_az": values["name_az"], "address": values["address"]}
            run.upsert(existing.get(values["code"]), Building, fields, code=values["code"])


class FloorsImport(ImportSpec):
    kind = ImportKind.FLOORS
    columns = (
        Column("building_code", parsing.code()),
        Column("level", parsing.integer(-5, 50)),
        Column("name_az", parsing.text(100)),
        Column("width", _PLAN_SIZE),
        Column("height", _PLAN_SIZE),
    )
    unique = (("building_code", "level"),)

    async def apply(self, run: ImportRun, rows: list[ParsedRow]) -> None:
        buildings = await run.lookup(
            Building, Building.code, (r.values["building_code"] for r in rows)
        )
        floors = await _floors(run, buildings.values())
        for row in rows:
            values = row.values
            building = buildings.get(values["building_code"])
            if building is None:
                run.error(row, "unknown_reference", "building_code")
                continue
            fields = {
                "name_az": values["name_az"],
                "width": values["width"],
                "height": values["height"],
            }
            run.upsert(
                floors.get((building.id, values["level"])),
                Floor,
                fields,
                building_id=building.id,
                level=values["level"],
            )


class RoomsImport(ImportSpec):
    kind = ImportKind.ROOMS
    columns = (
        Column("code", parsing.code()),
        Column("building_code", parsing.code()),
        Column("floor_level", parsing.integer(-5, 50)),
        Column("name_az", parsing.text(200), required=False, default=""),
        Column("type", parsing.choice(ROOM_TYPES)),
        Column("capacity", parsing.integer(1, 2000), required=False),
        Column("x", _PLAN_OFFSET),
        Column("y", _PLAN_OFFSET),
        Column("width", _PLAN_SIZE),
        Column("height", _PLAN_SIZE),
    )
    unique = (("code",),)

    async def apply(self, run: ImportRun, rows: list[ParsedRow]) -> None:
        buildings = await run.lookup(
            Building, Building.code, (r.values["building_code"] for r in rows)
        )
        floors = await _floors(run, buildings.values())
        existing = await run.lookup(Room, Room.code, (r.values["code"] for r in rows))
        for row in rows:
            values = row.values
            building = buildings.get(values["building_code"])
            if building is None:
                run.error(row, "unknown_reference", "building_code")
                continue
            floor = floors.get((building.id, values["floor_level"]))
            if floor is None:
                run.error(row, "unknown_reference", "floor_level")
                continue
            # A room drawn outside its floor's frame would be cut off on the plan.
            if values["x"] + values["width"] > floor.width:
                run.error(row, "outside_floor_plan", "width")
                continue
            if values["y"] + values["height"] > floor.height:
                run.error(row, "outside_floor_plan", "height")
                continue
            fields: dict[str, Any] = {
                "floor_id": floor.id,
                "name_az": values["name_az"],
                "type": values["type"],
                "capacity": values["capacity"],
                "x": values["x"],
                "y": values["y"],
                "width": values["width"],
                "height": values["height"],
                "search_key": search_key(values["code"], values["name_az"]),
            }
            run.upsert(existing.get(values["code"]), Room, fields, code=values["code"])


async def _floors(
    run: ImportRun, buildings: Iterable[Building]
) -> dict[tuple[uuid.UUID, int], Floor]:
    ids = [building.id for building in buildings]
    if not ids:
        return {}
    rows = await run.session.scalars(select(Floor).where(Floor.building_id.in_(ids)))
    return {(floor.building_id, floor.level): floor for floor in rows}
