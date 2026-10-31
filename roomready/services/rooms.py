"""The board. A room's state is worked out on every read, never stored: today every room is
`occupied`, and `out_of_order` overrides it."""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..errors import NoSuchProperty, NoSuchRoom
from ..models import Housekeeper, Property, Room
from ..schemas import BoardOut, HousekeeperOut, HousekeepersOut, RoomOut


@dataclass
class View:
    """One room and the rows its state is derived from."""
    room: Room
    state: str


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


def derive(room: Room) -> str:
    """The state machine, read off the rows. Returns the state."""
    if room.out_of_order:
        return "out_of_order"
    return "occupied"


def view(session: Session, room: Room) -> View:
    state = derive(room)
    return View(room, state)


def describe(v: View) -> RoomOut:
    return RoomOut(no=v.room.no, floor=v.room.floor, type=v.room.type, state=v.state)


def views(session: Session, prop: Property) -> list[View]:
    """Every room of the property in one statement."""
    rooms = session.scalars(select(Room).where(Room.property_id == prop.id).order_by(Room.no)).all()
    out = []
    for room in rooms:
        state = derive(room)
        out.append(View(room, state))
    return out


def board(session: Session, slug: str, floor: int | None, state: str | None,
          room_type: str | None) -> BoardOut:
    prop = get_property(session, slug)
    described = [describe(v) for v in views(session, prop)]
    if floor is not None:
        described = [r for r in described if r.floor == floor]
    if room_type is not None:
        described = [r for r in described if r.type == room_type]
    if state is not None:
        described = [r for r in described if r.state == state]
    return BoardOut(
        property=prop.slug,
        ready=sum(1 for r in described if r.state == "ready"),
        dirty=sum(1 for r in described if r.state == "dirty"),
        rooms=described,
    )


def one(session: Session, slug: str, no: str) -> RoomOut:
    prop = get_property(session, slug)
    return describe(view(session, get_room(session, prop, no)))


def housekeepers(session: Session, slug: str) -> HousekeepersOut:
    prop = get_property(session, slug)
    staff = session.scalars(select(Housekeeper).where(
        Housekeeper.property_id == prop.id).order_by(Housekeeper.code)).all()
    return HousekeepersOut(housekeepers=[
        HousekeeperOut(id=h.code, name=h.name) for h in staff
    ])
