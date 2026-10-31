from fastapi import APIRouter, Response

from ..ids import stay_public
from ..schemas import CheckoutIn, CheckoutOut
from ..services import checkouts
from ..services.rooms import get_property
from ..services.seed import PROPERTY
from . import ClockDep, SessionDep

router = APIRouter(prefix="/checkouts")


@router.post(
    "",
    response_model=CheckoutOut,
    status_code=201,
)
def checkout(body: CheckoutIn, response: Response, session: SessionDep, clock: ClockDep) -> CheckoutOut:
    prop = get_property(session, PROPERTY[0])
    stay = checkouts.checkout(session, prop, body.room, body.at, body.arrival_at, clock)
    response.headers["Location"] = f"/properties/{prop.slug}/rooms/{body.room}"
    return CheckoutOut(stay_id=stay_public(stay.id), room=body.room,
                       checked_out_at=stay.checked_out_at, state="dirty")
