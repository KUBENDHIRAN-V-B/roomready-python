from fastapi import APIRouter, Response

from ..errors import NoSuchRoom, RoomNotOccupied
from ..handlers import VALIDATION_RESPONSE, responses
from ..errors import NoSuchRoom, RoomNotOccupied
from ..handlers import VALIDATION_RESPONSE, responses
from ..ids import stay_public
from ..schemas import CheckoutIn, CheckoutOut
from ..services import checkouts
from ..services.rooms import get_property
from ..services.seed import PROPERTY
from . import ClockDep, SessionDep

router = APIRouter(prefix="/checkouts", tags=["checkouts"])


@router.post(
    "",
    response_model=CheckoutOut,
    status_code=201,
    summary="A guest has checked out; the room is dirty",
    responses={
        201: {"description": "The room is dirty", "headers": {"Location": {
            "schema": {"type": "string"},
            "description": "The room just checked out: /properties/{property}/rooms/{no}"}}},
        **responses((RoomNotOccupied, "Room 214 has no guest to check out"), (NoSuchRoom, "There is no room '999' at harbour-view")),
        **VALIDATION_RESPONSE,
    },
)
def checkout(body: CheckoutIn, response: Response, session: SessionDep, clock: ClockDep) -> CheckoutOut:
    prop = get_property(session, PROPERTY[0])
    stay = checkouts.checkout(session, prop, body.room, body.at, body.arrival_at, clock)
    response.headers["Location"] = f"/properties/{prop.slug}/rooms/{body.room}"
    return CheckoutOut(stay_id=stay_public(stay.id), room=body.room,
                       checked_out_at=stay.checked_out_at, state="dirty")
