from pydantic import BaseModel, ConfigDict

from app.modules.campus.models import RoomType


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class FloorRef(_Frozen):
    level: int
    name: str


class BuildingOut(_Frozen):
    code: str
    name: str
    address: str
    floors: list[FloorRef]


class BuildingRef(_Frozen):
    code: str
    name: str


class RoomShape(_Frozen):
    code: str
    name: str
    type: RoomType
    capacity: int | None
    x: int
    y: int
    width: int
    height: int


class FloorPlanOut(_Frozen):
    """One storey drawn in a ``width × height`` frame (decimetres); rooms are rectangles inside it."""

    building: BuildingRef
    level: int
    name: str
    width: int
    height: int
    rooms: list[RoomShape]


class RoomOut(_Frozen):
    code: str
    name: str
    type: RoomType
    capacity: int | None
    building: BuildingRef
    floor: FloorRef
