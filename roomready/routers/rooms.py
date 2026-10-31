from typing import Annotated

from fastapi import APIRouter, Query

from ..schemas import (
    BoardOut,
    HousekeepersOut,
    RoomOut,
    RoomState,
    RoomType,
)
from ..services import rooms
from . import SessionDep

router = APIRouter(prefix="/properties/{property}")


@router.get(
    "/rooms",
    response_model=BoardOut,
)
def board(
    property: str,
    session: SessionDep,
    floor: Annotated[int | None, Query(ge=1, le=4)] = None,
    state: RoomState | None = None,
    type_: Annotated[RoomType | None, Query(alias="type")] = None,
) -> BoardOut:
    return rooms.board(session, property, floor, state, type_)


@router.get(
    "/rooms/{no}",
    response_model=RoomOut,
)
def one(property: str, no: str, session: SessionDep) -> RoomOut:
    return rooms.one(session, property, no)


@router.get(
    "/housekeepers",
    response_model=HousekeepersOut,
)
def housekeepers(property: str, session: SessionDep) -> HousekeepersOut:
    return rooms.housekeepers(session, property)
