"""Request and response models. Every response goes through one of these; bodies use Field constraints."""
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer


RoomType = Literal["Standard", "Deluxe", "Suite"]
RoomState = Literal["occupied", "dirty", "assigned", "cleaning", "toinspect", "ready", "out_of_order"]
Result = Literal["pass", "fail"]


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
    """This answer's shape: the room's state is not part of it — read the room (it is toinspect, or ready when its type
    needs no inspection)."""
    assignment_id: str
    finished_at: UtcZ
    clean_minutes: int


class InspectIn(BaseModel):
    room: str = Field(min_length=3, max_length=8)
    inspector: str = Field(min_length=3, max_length=8)
    result: Result


class InspectOut(BaseModel):
    inspection_id: str
    room: str
    cleaned_by: str
    inspected_by: str
    result: Result
    state: RoomState
    ready_at: UtcZ | None = None
    arrival_at: UtcZ | None = None
    margin_minutes: int | None = None





EventKind = Literal["checked_out", "assigned", "started", "finished", "inspected", "ready"]


class EventOut(BaseModel):
    """One transition and its facts. Only the facts the kind carries are present (the route drops the rest)."""
    model_config = ConfigDict(extra="forbid")

    at: UtcZ
    kind: EventKind
    housekeeper: str | None = Field(default=None, description="assigned: the housekeeper's id")
    clean_minutes: int | None = Field(default=None, description="finished: the stored duration")
    inspector: str | None = Field(default=None, description="inspected: the inspector's id")
    result: Result | None = Field(default=None, description="inspected: pass or fail")
    margin_minutes: int | None = Field(default=None, description="inspected (pass) or ready: minutes before the arrival; absent when no arrival is known")
    arrival_at: UtcZ | None = Field(default=None, description="inspected (pass) or ready: the arrival the margin was measured against, when known")


class HistoryOut(BaseModel):
    room: str
    events: list[EventOut]


class SettingsOut(BaseModel):
    inspection_required_for: list[RoomType]
    stall_after_minutes: int




class HealthOut(BaseModel):
    status: Literal["ok"]
