from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import SessionDep
from app.core.errors import COMMON_ERROR_RESPONSES
from app.core.rbac import CurrentUserDep
from app.modules.campus.schemas import (
    BuildingOut,
    BuildingRef,
    FloorPlanOut,
    FloorRef,
    RoomOut,
    RoomShape,
)
from app.modules.campus.service import CampusService, PlacedRoom

router = APIRouter(prefix="/campus", tags=["campus"], responses=COMMON_ERROR_RESPONSES)


def _room_out(placed: PlacedRoom) -> RoomOut:
    room, floor, building = placed.room, placed.floor, placed.building
    return RoomOut(
        code=room.code,
        name=room.name_az,
        type=room.type,
        capacity=room.capacity,
        building=BuildingRef(code=building.code, name=building.name_az),
        floor=FloorRef(level=floor.level, name=floor.name_az),
    )


@router.get(
    "/buildings",
    response_model=list[BuildingOut],
    operation_id="listBuildings",
    summary="Buildings with their floors",
)
async def list_buildings(_: CurrentUserDep, session: SessionDep) -> list[BuildingOut]:
    return [
        BuildingOut(
            code=building.code,
            name=building.name_az,
            address=building.address,
            floors=[FloorRef(level=floor.level, name=floor.name_az) for floor in floors],
        )
        for building, floors in await CampusService(session).buildings()
    ]


@router.get(
    "/buildings/{building_code}/floors/{level}",
    response_model=FloorPlanOut,
    operation_id="readFloorPlan",
    summary="Floor plan: the floor's frame and its rooms",
)
async def read_floor_plan(
    _: CurrentUserDep, session: SessionDep, building_code: str, level: int
) -> FloorPlanOut:
    building, floor, rooms = await CampusService(session).floor_plan(building_code, level)
    return FloorPlanOut(
        building=BuildingRef(code=building.code, name=building.name_az),
        level=floor.level,
        name=floor.name_az,
        width=floor.width,
        height=floor.height,
        rooms=[
            RoomShape(
                code=room.code,
                name=room.name_az,
                type=room.type,
                capacity=room.capacity,
                x=room.x,
                y=room.y,
                width=room.width,
                height=room.height,
            )
            for room in rooms
        ],
    )


@router.get(
    "/rooms",
    response_model=list[RoomOut],
    operation_id="searchRooms",
    summary="Find rooms by code or name (at most 20)",
)
async def search_rooms(
    _: CurrentUserDep,
    session: SessionDep,
    q: Annotated[str, Query(min_length=1, max_length=100)],
) -> list[RoomOut]:
    return [_room_out(placed) for placed in await CampusService(session).search(q)]


@router.get("/rooms/{code}", response_model=RoomOut, operation_id="readRoom", summary="Room")
async def read_room(_: CurrentUserDep, session: SessionDep, code: str) -> RoomOut:
    return _room_out(await CampusService(session).room(code))
