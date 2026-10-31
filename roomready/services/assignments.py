"""Assign a dirty room, start the clean, finish it and store how long it took. Every refusal is raised
here, never in a route."""
from sqlalchemy.orm import Session

from ..clock import Clock, minutes_between
from ..errors import NoSuchAssignment, StepSkipped
from ..ids import assignment_internal, assignment_public
from ..models import Assignment, Housekeeper, Property, Room
from .rooms import View, get_housekeeper, get_room, skipped, view


def _skipped(v: View) -> StepSkipped:
    return skipped(v.room, v.state)


def get_assignment(session: Session, prop: Property, public_id: str) -> Assignment:
    internal = assignment_internal(public_id)
    assignment = session.get(Assignment, internal) if internal is not None else None
    if assignment is None or assignment.property_id != prop.id:
        raise NoSuchAssignment(f"There is no assignment {public_id!r}")
    return assignment


def assign(session: Session, prop: Property, room_no: str, housekeeper_code: str, clock: Clock) -> tuple[Assignment, Housekeeper]:
    room = get_room(session, prop, room_no)
    housekeeper = get_housekeeper(session, prop, housekeeper_code)
    v = view(session, room)
    if v.state != "dirty":
        raise _skipped(v)
    now = clock.now()
    assignment = Assignment(property_id=prop.id, room_id=room.id, stay_id=v.stay.id,
                           housekeeper_id=housekeeper.id, assigned_at=now)
    session.add(assignment)
    session.flush()
    session.commit()
    return assignment, housekeeper


def _open_view(session: Session, assignment: Assignment) -> View:
    """The room's view, refusing with the room's real state when this assignment is not the open one."""
    room = session.get(Room, assignment.room_id)
    v = view(session, room)
    if v.assignment is None or v.assignment.id != assignment.id:
        raise _skipped(v)
    return v


def start(session: Session, prop: Property, public_id: str, clock: Clock) -> Assignment:
    assignment = get_assignment(session, prop, public_id)
    v = _open_view(session, assignment)
    if v.state != "assigned":
        raise _skipped(v)
    now = clock.now()
    assignment.started_at = now
    session.commit()
    return assignment


def finish(session: Session, prop: Property, public_id: str, clock: Clock) -> Assignment:
    assignment = get_assignment(session, prop, public_id)
    v = _open_view(session, assignment)
    if v.state != "cleaning":
        raise _skipped(v)
    now = clock.now()
    assignment.finished_at = now
    assignment.clean_minutes = minutes_between(assignment.started_at, now)  # stamped once, never recomputed
    session.commit()
    return assignment


def public(assignment: Assignment) -> str:
    return assignment_public(assignment.id)
