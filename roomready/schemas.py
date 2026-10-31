"""Request and response models. Every response goes through one of these."""
from typing import Literal

from pydantic import BaseModel


RoomType = Literal["Standard", "Deluxe", "Suite"]
RoomState = Literal["occupied", "dirty", "assigned", "cleaning", "toinspect", "ready", "out_of_order"]


class RoomOut(BaseModel):
    no: str
    floor: int
    type: RoomType
    state: RoomState
    assigned_to: str | None = None
    since_minutes: int | None = None


class BoardOut(BaseModel):
    property: str
    ready: int
    dirty: int
    rooms: list[RoomOut]


class HousekeeperOut(BaseModel):
    id: str
    name: str
    open_assignment: str | None = None


class HousekeepersOut(BaseModel):
    housekeepers: list[HousekeeperOut]
