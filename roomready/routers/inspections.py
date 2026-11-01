from fastapi import APIRouter

from ..ids import inspection_public
from ..schemas import InspectIn, InspectOut
from ..services import inspections
from ..services.rooms import get_property
from ..services.seed import PROPERTY
from . import ClockDep, SessionDep

router = APIRouter(prefix="/inspections")


@router.post(
    "",
    response_model=InspectOut,
    status_code=201,
)
def inspect(body: InspectIn, session: SessionDep, clock: ClockDep) -> InspectOut:
    o = inspections.inspect(session, get_property(session, PROPERTY[0]), body.room, body.inspector, body.result, clock)
    r = o.readiness
    return InspectOut(
        inspection_id=inspection_public(o.inspection.id), room=body.room, cleaned_by=o.cleaner.name, inspected_by=o.inspector.name,
        result=body.result, state=o.state, ready_at=r.ready_at if r else None, arrival_at=r.arrival_at if r else None,
        margin_minutes=r.margin_minutes if r else None
    )
