from dataclasses import dataclass

from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.text import like_pattern, normalize_az
from app.modules.campus.models import Building, Floor, Room

ROOM_SEARCH_LIMIT = 20


@dataclass(frozen=True, slots=True)
class PlacedRoom:
    room: Room
    floor: Floor
    building: Building


class CampusService:
    """Buildings, floors and rooms. Campus data is not personal and is readable by every signed-in user."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def buildings(self) -> list[tuple[Building, list[Floor]]]:
        buildings = list(await self.session.scalars(select(Building).order_by(Building.code)))
        floors = await self.session.scalars(select(Floor).order_by(Floor.level))
        by_building: dict[object, list[Floor]] = {building.id: [] for building in buildings}
        for floor in floors:
            by_building[floor.building_id].append(floor)
        return [(building, by_building[building.id]) for building in buildings]

    async def floor_plan(
        self, building_code: str, level: int
    ) -> tuple[Building, Floor, list[Room]]:
        row = (
            await self.session.execute(
                select(Building, Floor)
                .join(Floor, Floor.building_id == Building.id)
                .where(Building.code == building_code, Floor.level == level)
            )
        ).one_or_none()
        if row is None:
            raise AppError("request.not_found", 404)
        building, floor = row
        rooms = await self.session.scalars(
            select(Room).where(Room.floor_id == floor.id).order_by(Room.code)
        )
        return building, floor, list(rooms)

    async def room(self, code: str) -> PlacedRoom:
        rooms = await self._placed(Room.code == code, limit=1)
        if not rooms:
            raise AppError("request.not_found", 404)
        return rooms[0]

    async def search(self, query: str) -> list[PlacedRoom]:
        """Room codes and names, diacritic-insensitive: "komputer" finds "Kompüter otağı"."""
        needle = normalize_az(query).folded
        if not needle:
            return []
        return await self._placed(
            Room.search_key.like(like_pattern(needle), escape="\\"), limit=ROOM_SEARCH_LIMIT
        )

    async def _placed(self, condition: ColumnElement[bool], *, limit: int) -> list[PlacedRoom]:
        rows = await self.session.execute(
            select(Room, Floor, Building)
            .join(Floor, Floor.id == Room.floor_id)
            .join(Building, Building.id == Floor.building_id)
            .where(condition)
            .order_by(Room.code)
            .limit(limit)
        )
        return [PlacedRoom(room, floor, building) for room, floor, building in rows]
