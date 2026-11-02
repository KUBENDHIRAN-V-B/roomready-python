from typing import Annotated

from fastapi import APIRouter, Query

from ..errors import NoSuchProperty, NoSuchRoom
from ..handlers import FILTER_RESPONSE, responses

from ..errors import NoSuchProperty, NoSuchRoom
from ..handlers import FILTER_RESPONSE, responses

from ..schemas import (
    BoardOut,
    HistoryOut,
    HousekeepersOut,
    RoomOut,
    RoomState,
    RoomType,
)
from ..services import history, rooms
from . import ClockDep, SessionDep

router = APIRouter(prefix="/properties/{property}", tags=["rooms"])


@router.get(
    "/rooms",
    response_model=BoardOut,
    summary="The board: every room with its derived state, filterable by floor, state and type",
    responses={**FILTER_RESPONSE, **responses((NoSuchProperty, "There is no property 'sea-view'"))},
)
def board(
    property: str,
    session: SessionDep,
    clock: ClockDep,
    floor: Annotated[int | None, Query(ge=1, le=4)] = None,
    state: RoomState | None = None,
    type_: Annotated[RoomType | None, Query(alias="type")] = None,
) -> BoardOut:
    return rooms.board(session, property, floor, state, type_, clock)


@router.get(
    "/rooms/{no}",
    response_model=RoomOut,
    summary="One room",
    responses=responses((NoSuchRoom, "There is no room '999' at harbour-view"), (NoSuchProperty, "There is no property 'sea-view'")),
)
def one(property: str, no: str, session: SessionDep, clock: ClockDep) -> RoomOut:
    return rooms.one(session, property, no, clock)


@router.get(
    "/rooms/{no}/history",
    response_model=HistoryOut,
    response_model_exclude_none=True,
    summary="One room's day: every transition for a stay, in order, with the facts each carries",
    responses=responses((NoSuchRoom, "There is no room '999' at harbour-view"), (NoSuchProperty, "There is no property 'sea-view'")),
)
def room_history(property: str, no: str, session: SessionDep, stay: str | None = None) -> HistoryOut:
    return history.history(session, property, no, stay)


@router.get(
    "/housekeepers",
    response_model=HousekeepersOut,
    summary="The housekeepers and the room each one is on",
    responses=responses((NoSuchProperty, "There is no property 'sea-view'")),
)
def housekeepers(property: str, session: SessionDep) -> HousekeepersOut:
    return rooms.housekeepers(session, property)
