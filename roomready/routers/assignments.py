from fastapi import APIRouter

from ..errors import (AlreadyAssigned, NoSuchAssignment, NoSuchHousekeeper, NoSuchRoom, StepSkipped)
from ..handlers import VALIDATION_RESPONSE, responses
from ..errors import (AlreadyAssigned, NoSuchAssignment, NoSuchHousekeeper, NoSuchRoom, StepSkipped)
from ..handlers import VALIDATION_RESPONSE, responses
from ..schemas import AssignIn, AssignOut, FinishOut, StartOut
from ..services import assignments
from ..services.rooms import get_property
from ..services.seed import PROPERTY
from . import ClockDep, SessionDep, SettingsDep

router = APIRouter(prefix="/assignments", tags=["assignments"])


@router.post(
    "",
    response_model=AssignOut,
    status_code=201,
    summary="Assign a dirty room to a housekeeper",
    responses={**responses(
        (StepSkipped, "Room 214 is occupied; it needs checkout first", {"state": "occupied", "needs": "checkout"}),
        (AlreadyAssigned, "Room 214 is already assigned to Sunita", {"assigned_to": "Sunita"}),
        (NoSuchRoom, "There is no room '999' at harbour-view"),
        (NoSuchHousekeeper, "There is no housekeeper 'HK99' at harbour-view")
    ), **VALIDATION_RESPONSE},
)
def assign(body: AssignIn, session: SessionDep, clock: ClockDep) -> AssignOut:
    prop = get_property(session, PROPERTY[0])
    assignment, housekeeper = assignments.assign(session, prop, body.room, body.housekeeper, clock)
    return AssignOut(assignment_id=assignments.public(assignment), room=body.room,
                     assigned_to=housekeeper.name, assigned_at=assignment.assigned_at)


@router.post(
    "/{assignment_id}/start",
    response_model=StartOut,
    summary="The housekeeper has started; the room is cleaning",
    responses=responses(
        (StepSkipped, "Room 214 is cleaning; it needs finish first", {"state": "cleaning", "needs": "finish"}),
        (NoSuchAssignment, "There is no assignment 'AS999'")
    ),
)
def start(assignment_id: str, session: SessionDep, clock: ClockDep) -> StartOut:
    assignment = assignments.start(session, get_property(session, PROPERTY[0]), assignment_id, clock)
    return StartOut(assignment_id=assignments.public(assignment), started_at=assignment.started_at)


@router.post(
    "/{assignment_id}/finish",
    response_model=FinishOut,
    summary="The clean is done and timed; the room waits for inspection (or is ready, if its type needs none)",
    responses=responses(
        (StepSkipped, "Room 214 is assigned; it needs start first", {"state": "assigned", "needs": "start"}),
        (NoSuchAssignment, "There is no assignment 'AS999'")
    ),
)
def finish(assignment_id: str, session: SessionDep, clock: ClockDep, settings: SettingsDep) -> FinishOut:
    assignment = assignments.finish(session, get_property(session, PROPERTY[0]), assignment_id, clock, settings)
    return FinishOut(assignment_id=assignments.public(assignment), finished_at=assignment.finished_at,
                     clean_minutes=assignment.clean_minutes)
