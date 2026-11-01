from datetime import datetime

from sqlalchemy.orm import Session

from ..clock import Clock, as_utc
from ..errors import Malformed, RoomNotOccupied
from ..models import Property, Stay
from . import events
from .rooms import current_stay, get_room


def checkout(session: Session, prop: Property, room_no: str, at: datetime,
             arrival_at: datetime | None, clock: Clock) -> Stay:
    """Checkout validation status. The stay and its event are one transaction."""
    room = get_room(session, prop, room_no)
    stay = current_stay(session, room)
    if stay is None or stay.checked_out_at is not None:
        raise RoomNotOccupied(f"Room {room.no} has no guest to check out")
    at = as_utc(at)
    errors = []
    if at > clock.now():
        errors.append({"field": "at", "message": "must not be in the future"})
    elif at < as_utc(stay.checked_in_at):
        errors.append({"field": "at", "message": f"must not be before check-in at {as_utc(stay.checked_in_at):%Y-%m-%dT%H:%M:%SZ}"})
    if arrival_at is not None and as_utc(arrival_at) < at:
        errors.append({"field": "arrival_at", "message": "the next arrival cannot be before the checkout"})
    if errors:
        raise Malformed(f"{len(errors)} field(s) failed validation", errors=errors)
    stay.checked_out_at = at
    stay.arrival_at = as_utc(arrival_at) if arrival_at is not None else None
    events.record(session, prop.id, room, stay.id, "checked_out", at, events.FRONT_DESK)
    session.commit()
    return stay
