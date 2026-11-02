from fastapi import APIRouter

from ..errors import NoSuchHousekeeper, NoSuchRoom, SelfInspection, StepSkipped
from ..handlers import VALIDATION_RESPONSE, responses
from ..ids import inspection_public
from ..schemas import InspectIn, InspectOut
from ..services import inspections
from ..services.rooms import get_property
from ..services.seed import PROPERTY
from . import ClockDep, SessionDep

router = APIRouter(prefix="/inspections", tags=["inspections"])


@router.post(
    "",
    response_model=InspectOut,
    status_code=201,
    summary="Somebody else inspects the room: pass makes it ready and stamps the margin, fail sends it back to dirty",
    responses={**responses(
        (StepSkipped, "Room 214 is cleaning; it needs finish first", {"state": "cleaning", "needs": "finish"}),
        (SelfInspection, "Sunita cleaned room 214; somebody else must inspect it"),
        (NoSuchRoom, "There is no room '999' at harbour-view"),
        (NoSuchHousekeeper, "There is no housekeeper 'HK99' at harbour-view")
    ), **VALIDATION_RESPONSE},
)
def inspect(body: InspectIn, session: SessionDep, clock: ClockDep) -> InspectOut:
    prop = get_property(session, PROPERTY[0])
    outcome = inspections.inspect(session, prop, body.room, body.inspector, body.result, clock)
    row = outcome.inspection
    ready = outcome.readiness
    return InspectOut(
        inspection_id=inspection_public(row.id), room=body.room, cleaned_by=outcome.cleaner.name,
        inspected_by=outcome.inspector.name, result=row.result, state=outcome.state,
        ready_at=ready.ready_at if ready else None,
        arrival_at=ready.arrival_at if ready else None,
        margin_minutes=ready.margin_minutes if ready else None,
    )
