"""Append one event row inside the caller's transaction, with who did it. Ids and facts only — never the guest.

Events are written with a plain INSERT and never loaded as objects to change: the code has no update path for them,
and the database triggers refuse an UPDATE or DELETE from anywhere else."""
import json
from datetime import datetime

from sqlalchemy import insert
from sqlalchemy.orm import Session

from ..models import Event, Room

# No request carries an identity, so the desk and the supervisor are recorded by role; housekeepers
# and inspectors are named by their code because the request names them.
FRONT_DESK = "front-desk"
SUPERVISOR = "supervisor"


def record(session: Session, property_id: int, room: Room, stay_id: int, kind: str,
           at: datetime, actor_id: str, data: dict | None = None,
           assignment_id: int | None = None) -> int:
    """Insert the event and return its row id."""
    event_id = session.execute(
        insert(Event).values(
            property_id=property_id, room_id=room.id, stay_id=stay_id, assignment_id=assignment_id,
            kind=kind, at=at, actor_id=actor_id, data=json.dumps(data or {})
        )
        .returning(Event.id)
    ).scalar_one()
    return event_id
