"""Load the property, its 60 rooms and nine housekeepers once, before the first request.
Idempotent: a second start changes nothing."""
import csv
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Housekeeper, Property, Room

PROPERTY = ("harbour-view", "Harbour View")


def seed(session: Session, seed_dir: str) -> None:
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
    session.commit()
