"""Load the property, its 60 rooms and nine housekeepers once, before the first request, and give every room
its current guest. Idempotent: a second start changes nothing."""
import csv
import logging
from datetime import timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..clock import Clock
from ..models import Housekeeper, Property, Room, Stay

log = logging.getLogger("roomready.seed")

PROPERTY = ("harbour-view", "Harbour View")


def seed(session: Session, seed_dir: str, clock: Clock) -> None:
    prop = session.scalar(select(Property).where(Property.slug == PROPERTY[0]))
    if prop is None:
        prop = Property(slug=PROPERTY[0], name=PROPERTY[1])
        session.add(prop)
        session.flush()

    if session.scalar(select(Room.id).where(Room.property_id == prop.id).limit(1)) is None:
        with (Path(seed_dir) / "rooms.csv").open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                session.add(Room(property_id=prop.id, no=row["no"], floor=int(row["floor"]),
                                type=row["type"], out_of_order=False))

    if session.scalar(select(Housekeeper.id).where(Housekeeper.property_id == prop.id).limit(1)) is None:
        with (Path(seed_dir) / "housekeepers.csv").open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                session.add(Housekeeper(property_id=prop.id, code=row["id"], name=row["name"]))

    session.flush()
    # the hotel is full when the app first starts: every room has a guest who checked in yesterday
    if session.scalar(select(Stay.id).where(Stay.property_id == prop.id).limit(1)) is None:
        checked_in = clock.now() - timedelta(days=1)
        for room in session.scalars(select(Room).where(Room.property_id == prop.id)):
            session.add(Stay(property_id=prop.id, room_id=room.id,
                            guest_ref=f"BK-{room.no}-1", checked_in_at=checked_in))
    session.flush()
    session.commit()
    rooms = session.scalar(select(func.count()).select_from(Room).where(Room.property_id == prop.id))
    staff = session.scalar(select(func.count()).select_from(Housekeeper).where(Housekeeper.property_id == prop.id))
    log.info("seed complete property=%s rooms=%s housekeepers=%s", prop.slug, rooms, staff)
