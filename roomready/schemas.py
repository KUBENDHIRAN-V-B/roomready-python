"""Request and response models. Every response goes through one of these; bodies use Field constraints."""
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, Field, PlainSerializer


RoomType = Literal["Standard", "Deluxe", "Suite"]
RoomState = Literal["occupied", "dirty", "assigned", "cleaning", "toinspect", "ready", "out_of_order"]


def _iso_z(dt: datetime) -> str:
    """SQLite hands naive datetimes back; everything the app stores is UTC, so a naive value is UTC, never local time."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


UtcZ = Annotated[datetime, PlainSerializer(_iso_z, return_type=str)]


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


class CheckoutIn(BaseModel):
    room: str = Field(min_length=3, max_length=8)
    at: datetime
    arrival_at: datetime | None = Field(default=None, description="when the next guest for this room is due, if known")


class CheckoutOut(BaseModel):
    stay_id: str
    room: str
    checked_out_at: UtcZ
    state: RoomState


class AssignIn(BaseModel):
    room: str = Field(min_length=3, max_length=8)
    housekeeper: str = Field(min_length=3, max_length=8)


class AssignOut(BaseModel):
    assignment_id: str
    room: str
    assigned_to: str
    assigned_at: UtcZ


class StartOut(BaseModel):
    assignment_id: str
    started_at: UtcZ


class FinishOut(BaseModel):
    """This answer's shape: the room's state is not part of it — read the room (it is toinspect)."""
    assignment_id: str
    finished_at: UtcZ
    clean_minutes: int
