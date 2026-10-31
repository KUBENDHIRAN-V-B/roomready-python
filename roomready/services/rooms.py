"""The board. A room's state is derived on read from its rows — the current stay — never stored.
`occupied` while the guest is in, `dirty` once its stay is checked out, `out_of_order` over all."""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..clock import Clock, as_utc, minutes_between
from ..errors import NoSuchProperty, NoSuchRoom
from ..models import Housekeeper, Property, Room, Stay
from ..schemas import BoardOut, HousekeeperOut, HousekeepersOut, RoomOut


@dataclass
class View:
    """One room and the rows its state is derived from."""
    room: Room
    stay: Stay | None
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


def current_stay(session: Session, room: Room) -> Stay | None:
    return session.scalar(select(Stay).where(Stay.room_id == room.id).order_by(Stay.id.desc()).limit(1))


def derive(room: Room, stay: Stay | None) -> tuple[str, datetime | None]:
    """The state machine, read off the rows. Returns the state and when the room entered it."""
    if room.out_of_order:
        return "out_of_order", None
    if stay is None or stay.checked_out_at is None:
        return "occupied", stay.checked_in_at if stay is not None else None
    return "dirty", stay.checked_out_at


def view(session: Session, room: Room) -> View:
    stay = current_stay(session, room)
    state, since = derive(room, stay)
    return View(room, stay, state, since)


def describe(v: View, clock: Clock) -> RoomOut:
    return RoomOut(no=v.room.no, floor=v.room.floor, type=v.room.type, state=v.state,
                   since_minutes=minutes_between(as_utc(v.since), clock.now()) if v.since is not None else None)


def views(session: Session, prop: Property) -> list[View]:
    """Every room of the property in two statements (rooms, stays), not one per room."""
    rooms = session.scalars(select(Room).where(Room.property_id == prop.id).order_by(Room.no)).all()
    stays: dict[int, Stay] = {}
    for stay in session.scalars(select(Stay).where(Stay.property_id == prop.id).order_by(Stay.id)):
        stays[stay.room_id] = stay  # the last one per room wins: the current stay
    out = []
    for room in rooms:
        stay = stays.get(room.id)
        state, since = derive(room, stay)
        out.append(View(room, stay, state, since))
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
    staff = session.scalars(select(Housekeeper).where(
        Housekeeper.property_id == prop.id).order_by(Housekeeper.code)).all()
    return HousekeepersOut(housekeepers=[HousekeeperOut(id=h.code, name=h.name) for h in staff])
