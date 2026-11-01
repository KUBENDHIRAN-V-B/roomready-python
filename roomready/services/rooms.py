"""The board. A room's state is derived on read from its rows — the current stay and the open assignment —
never stored. `occupied` while the guest is in, `dirty` after checkout, `assigned` / `cleaning` / `toinspect` from
the open assignment's stamps, `out_of_order` over all."""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..clock import Clock, as_utc, minutes_between
from ..errors import NoSuchHousekeeper, NoSuchProperty, NoSuchRoom, StepSkipped
from ..models import Assignment, Housekeeper, Property, Room, Stay
from ..schemas import BoardOut, HousekeeperOut, HousekeepersOut, RoomOut

# What must happen first — the next legal step from each state. Nothing takes a room out of
# order, so that state has no entry and a refusal from it names no step.
NEEDS = {"occupied": "checkout", "dirty": "assign", "assigned": "start", "cleaning": "finish", "toinspect": "inspect"}


@dataclass
class View:
    """One room and the rows its state is derived from."""
    room: Room
    stay: Stay | None
    assignment: Assignment | None          # the open one (closed_at null), if any
    housekeeper: Housekeeper | None
    state: str
    since: datetime | None


def get_property(session: Session, slug: str) -> Property:
    prop = session.scalar(select(Property).where(Property.slug == slug))
    if prop is None:
        raise NoSuchProperty(f"There is no property {slug!r}")
    return prop


def get_room(session: Session, prop: Property, no: str) -> Room:
    room = session.scalar(select(Room).where(Room.property_id == prop.id, Room.no == no))
    if room is None:
        raise NoSuchRoom(f"There is no room {no!r} at {prop.slug}")
    return room


def get_housekeeper(session: Session, prop: Property, code: str) -> Housekeeper:
    hk = session.scalar(select(Housekeeper).where(Housekeeper.property_id == prop.id, Housekeeper.code == code))
    if hk is None:
        raise NoSuchHousekeeper(f"There is no housekeeper {code!r} at {prop.slug}")
    return hk


def current_stay(session: Session, room: Room) -> Stay | None:
    return session.scalar(select(Stay).where(Stay.room_id == room.id).order_by(Stay.id.desc()).limit(1))


def open_assignment(session: Session, room: Room) -> Assignment | None:
    return session.scalar(select(Assignment).where(Assignment.room_id == room.id, Assignment.closed_at.is_(None)).order_by(Assignment.id.desc()).limit(1))


def derive(room: Room, stay: Stay | None, assignment: Assignment | None) -> tuple[str, datetime | None]:
    """The state machine, read off the rows. Returns the state and when the room entered it."""
    if room.out_of_order:
        return "out_of_order", None
    if stay is None or stay.checked_out_at is None:
        return "occupied", stay.checked_in_at if stay is not None else None
    if assignment is not None:
        if assignment.started_at is None:
            return "assigned", assignment.assigned_at
        if assignment.finished_at is None:
            return "cleaning", assignment.started_at
        return "toinspect", assignment.finished_at
    return "dirty", stay.checked_out_at


def skipped(room: Room, state: str) -> StepSkipped:
    """The refusal for an action the room's state does not allow, naming where it is and what comes first."""
    needs = NEEDS.get(state)
    if needs is None:
        return StepSkipped(f"Room {room.no} is {state}", state=state)
    return StepSkipped(f"Room {room.no} is {state}; it needs {needs} first", state=state, needs=needs)


def view(session: Session, room: Room) -> View:
    stay = current_stay(session, room)
    assignment = open_assignment(session, room)
    housekeeper = session.get(Housekeeper, assignment.housekeeper_id) if assignment is not None else None
    state, since = derive(room, stay, assignment)
    return View(room, stay, assignment, housekeeper, state, since)


def describe(v: View, clock: Clock) -> RoomOut:
    return RoomOut(no=v.room.no, floor=v.room.floor, type=v.room.type, state=v.state,
                   assigned_to=v.housekeeper.name if v.housekeeper is not None else None,
                   since_minutes=minutes_between(as_utc(v.since), clock.now()) if v.since is not None else None)


def views(session: Session, prop: Property) -> list[View]:
    """Every room of the property in four statements, not four per room."""
    rooms = session.scalars(select(Room).where(Room.property_id == prop.id).order_by(Room.no)).all()
    stays: dict[int, Stay] = {}
    for stay in session.scalars(select(Stay).where(Stay.property_id == prop.id).order_by(Stay.id)):
        stays[stay.room_id] = stay
    open_by_room = {a.room_id: a for a in session.scalars(select(Assignment).where(Assignment.property_id == prop.id, Assignment.closed_at.is_(None)).order_by(Assignment.id))}
    staff = {h.id: h for h in session.scalars(select(Housekeeper).where(Housekeeper.property_id == prop.id))}
    out = []
    for room in rooms:
        stay = stays.get(room.id)
        assignment = open_by_room.get(room.id)
        state, since = derive(room, stay, assignment)
        out.append(View(room, stay, assignment, staff.get(assignment.housekeeper_id) if assignment else None, state, since))
    return out


def board(session: Session, slug: str, floor: int | None, state: str | None,
          room_type: str | None, clock: Clock) -> BoardOut:
    prop = get_property(session, slug)
    described = [describe(v, clock) for v in views(session, prop)]
    if floor is not None:
        described = [r for r in described if r.floor == floor]
    if room_type is not None:
        described = [r for r in described if r.type == room_type]
    if state is not None:
        described = [r for r in described if r.state == state]
    return BoardOut(property=prop.slug, ready=sum(1 for r in described if r.state == "ready"),
                   dirty=sum(1 for r in described if r.state == "dirty"), rooms=described)


def one(session: Session, slug: str, no: str, clock: Clock) -> RoomOut:
    prop = get_property(session, slug)
    return describe(view(session, get_room(session, prop, no)), clock)


def housekeepers(session: Session, slug: str) -> HousekeepersOut:
    prop = get_property(session, slug)
    staff = session.scalars(select(Housekeeper).where(Housekeeper.property_id == prop.id).order_by(Housekeeper.code)).all()
    open_rooms: dict[int, str] = {}
    rows = session.execute(select(Assignment.housekeeper_id, Room.no).join(Room, Room.id == Assignment.room_id)
                           .where(Assignment.property_id == prop.id, Assignment.closed_at.is_(None)).order_by(Assignment.id))
    for housekeeper_id, room_no in rows:
        open_rooms.setdefault(housekeeper_id, room_no)  # one room at a time: the first still open
    return HousekeepersOut(housekeepers=[HousekeeperOut(id=h.code, name=h.name, open_assignment=open_rooms.get(h.id)) for h in staff])
