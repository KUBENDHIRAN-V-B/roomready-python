from datetime import datetime

from sqlalchemy.orm import Session

from ..clock import Clock, as_utc, minutes_between
from ..errors import AlreadyAssigned, NoSuchAssignment, StepSkipped
from ..ids import assignment_internal, assignment_public
from ..models import Assignment, Housekeeper, Property, Readiness, Room
from ..settings import Settings
from . import events
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
    # The order of checks is fixed so a test can target each refusal — room, housekeeper, already assigned, step
    room = get_room(session, prop, room_no)
    housekeeper = get_housekeeper(session, prop, housekeeper_code)
    v = view(session, room)
    if v.assignment is not None and v.assignment.closed_at is None:
        raise AlreadyAssigned(f"Room {room.no} is already assigned to {v.housekeeper.name}", assigned_to=v.housekeeper.name)
    if v.state != "dirty":
        raise _skipped(v)
    now = clock.now()
    assignment = Assignment(property_id=prop.id, room_id=room.id, stay_id=v.stay.id,
                           housekeeper_id=housekeeper.id, assigned_at=now)
    session.add(assignment)
    session.flush()
    events.record(session, prop.id, room, v.stay.id, "assigned", now, events.SUPERVISOR, {"housekeeper": housekeeper.code}, assignment_id=assignment.id)
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
    events.record(session, prop.id, v.room, v.stay.id, "started", now, v.housekeeper.code, assignment_id=assignment.id)
    session.commit()
    return assignment


def mark_ready(session: Session, prop: Property, v: View, now: datetime) -> Readiness:
    """The readiness stamp — when the room was ready, the arrival it was ready for, and the margin, stored once."""
    arrival = as_utc(v.stay.arrival_at) if v.stay.arrival_at is not None else None
    readiness = Readiness(
        property_id=prop.id, room_id=v.room.id, stay_id=v.stay.id, ready_at=now, arrival_at=arrival,
        margin_minutes=minutes_between(now, arrival) if arrival is not None else None
    )
    session.add(readiness)
    v.assignment.closed_at = now
    session.flush()
    return readiness


def readiness_facts(readiness: Readiness) -> dict:
    """What the inspected/ready event records about the stamp: the margin and the arrival it was measured against."""
    if readiness.arrival_at is None:
        return {}
    return {"margin_minutes": readiness.margin_minutes, "arrival_at": f"{as_utc(readiness.arrival_at):%Y-%m-%dT%H:%M:%SZ}"}


def finish(session: Session, prop: Property, public_id: str, clock: Clock, settings: Settings) -> Assignment:
    assignment = get_assignment(session, prop, public_id)
    v = _open_view(session, assignment)
    if v.state != "cleaning":
        raise _skipped(v)
    now = clock.now()
    assignment.finished_at = now
    assignment.clean_minutes = minutes_between(assignment.started_at, now)  # stamped once, never recomputed
    events.record(session, prop.id, v.room, v.stay.id, "finished", now, v.housekeeper.code,
                  {"clean_minutes": assignment.clean_minutes}, assignment_id=assignment.id)
    if not settings.needs_inspection(v.room.type):
        # This room type needs no second pair of eyes — the finish is the moment it becomes ready
        readiness = mark_ready(session, prop, v, now)
        events.record(session, prop.id, v.room, v.stay.id, "ready", now, v.housekeeper.code,
                      readiness_facts(readiness), assignment_id=assignment.id)
    session.commit()
    return assignment


def public(assignment: Assignment) -> str:
    return assignment_public(assignment.id)
