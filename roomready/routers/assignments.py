from fastapi import APIRouter

from ..schemas import AssignIn, AssignOut, FinishOut, StartOut
from ..services import assignments
from ..services.rooms import get_property
from ..services.seed import PROPERTY
from . import ClockDep, SessionDep

router = APIRouter(prefix="/assignments")


@router.post(
    "",
    response_model=AssignOut,
    status_code=201,
)
def assign(body: AssignIn, session: SessionDep, clock: ClockDep) -> AssignOut:
    prop = get_property(session, PROPERTY[0])
    assignment, housekeeper = assignments.assign(session, prop, body.room, body.housekeeper, clock)
    return AssignOut(assignment_id=assignments.public(assignment), room=body.room,
                     assigned_to=housekeeper.name, assigned_at=assignment.assigned_at)


@router.post(
    "/{assignment_id}/start",
    response_model=StartOut,
)
def start(assignment_id: str, session: SessionDep, clock: ClockDep) -> StartOut:
    assignment = assignments.start(session, get_property(session, PROPERTY[0]), assignment_id, clock)
    return StartOut(assignment_id=assignments.public(assignment), started_at=assignment.started_at)


@router.post(
    "/{assignment_id}/finish",
    response_model=FinishOut,
)
def finish(assignment_id: str, session: SessionDep, clock: ClockDep) -> FinishOut:
    assignment = assignments.finish(session, get_property(session, PROPERTY[0]), assignment_id, clock)
    return FinishOut(assignment_id=assignments.public(assignment), finished_at=assignment.finished_at,
                     clean_minutes=assignment.clean_minutes)
