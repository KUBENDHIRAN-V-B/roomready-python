"""One room's day — every transition for a stay, in `at` order, with the facts each one carries."""
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..clock import as_utc
from ..ids import stay_internal
from ..models import Event, Stay
from ..schemas import EventOut, HistoryOut
from .rooms import current_stay, get_property, get_room


def history(session: Session, slug: str, no: str, stay_public_id: str | None) -> HistoryOut:
    prop = get_property(session, slug)
    room = get_room(session, prop, no)
    if stay_public_id is None:
        stay = current_stay(session, room)
    else:
        internal = stay_internal(stay_public_id)
        stay = session.get(Stay, internal) if internal is not None else None
        if stay is not None and stay.room_id != room.id:
            stay = None  # another room's stay: nothing to show for this one
    rows = session.scalars(select(Event).where(Event.stay_id == stay.id).order_by(Event.at, Event.id)).all() if stay is not None else []
    return HistoryOut(room=room.no, events=[EventOut(at=as_utc(e.at), kind=e.kind, **json.loads(e.data)) for e in rows])
