"""Somebody else inspects the room. A pass stamps the readiness and closes the assignment in the same
transaction as the inspection row; a fail returns the room to dirty and closes the assignment."""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..clock import Clock
from ..errors import SelfInspection
from ..models import Housekeeper, Inspection, Property, Readiness
from .assignments import mark_ready
from .rooms import get_housekeeper, get_room, skipped, view


@dataclass
class Outcome:
    inspection: Inspection
    cleaner: Housekeeper
    inspector: Housekeeper
    state: str
    readiness: Readiness | None



def inspect(session: Session, prop: Property, room_no: str, inspector_code: str, result: str, clock: Clock) -> Outcome:
    room = get_room(session, prop, room_no)
    inspector = get_housekeeper(session, prop, inspector_code)
    v = view(session, room)
    if v.state != "toinspect":
        raise skipped(room, v.state)
    if v.assignment.housekeeper_id == inspector.id:
        raise SelfInspection(f"{inspector.name} cleaned room {room.no}; somebody else must inspect it")
    now = clock.now()
    inspection = Inspection(
        property_id=prop.id, room_id=room.id, assignment_id=v.assignment.id, inspector_id=inspector.id,
        result=result, inspected_at=now
    )
    session.add(inspection)
    session.flush()
    readiness = None
    if result == "fail":
        v.assignment.closed_at = now                                  # back to dirty; the next assignment is a new row
    else:
        readiness = mark_ready(session, prop, v, now)                 # ready + margin + close, one transaction
    session.commit()
    return Outcome(inspection, v.housekeeper, inspector, view(session, room).state, readiness)   # derived from the rows
