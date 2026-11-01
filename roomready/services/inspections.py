"""Somebody else inspects the room. A fail returns the room to dirty and closes the assignment; a pass is
recorded, and the room stays toinspect."""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..clock import Clock
from ..errors import SelfInspection
from ..models import Housekeeper, Inspection, Property
from .rooms import get_housekeeper, get_room, skipped, view


@dataclass
class Outcome:
    inspection: Inspection
    cleaner: Housekeeper
    inspector: Housekeeper
    state: str



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
    if result == "fail":
        v.assignment.closed_at = now                                  # back to dirty; the next assignment is a new row
    session.commit()
    return Outcome(inspection, v.housekeeper, inspector, view(session, room).state)   # derived from the rows
