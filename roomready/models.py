"""Rooms, stays, assignments and inspections. A room's state is derived on read from its rows,
and there is deliberately no `state` column on rooms. Durations are stamped once and never
recomputed."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(80))


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (UniqueConstraint("property_id", "no"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"))
    no: Mapped[str] = mapped_column(String(8))
    floor: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(12))  # Standard | Deluxe | Suite
    out_of_order: Mapped[bool] = mapped_column(Boolean, default=False)


class Housekeeper(Base):
    __tablename__ = "housekeepers"
    __table_args__ = (UniqueConstraint("property_id", "code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"))
    code: Mapped[str] = mapped_column(String(8))  # HK03 — the id on the wire
    name: Mapped[str] = mapped_column(String(60))


class Stay(Base):
    """The current stay is the one with checked_out_at null. arrival_at is when the next guest for this
    room is due, typed in with the checkout."""
    __tablename__ = "stays"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"))
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"))
    guest_ref: Mapped[str] = mapped_column(String(24))  # the stay's guest reference, never a name
    checked_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    checked_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    arrival_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)




class Assignment(Base):
    """One row per clean. Open while closed_at is null; assigned / cleaning / toinspect from the stamps."""
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"))
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"))
    stay_id: Mapped[int] = mapped_column(ForeignKey("stays.id"))
    housekeeper_id: Mapped[int] = mapped_column(ForeignKey("housekeepers.id"))
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clean_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)  # stamped at finish, never recomputed

    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)   # a failed inspection closes it


class Inspection(Base):
    __tablename__ = "inspections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"))
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"))
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"))
    inspector_id: Mapped[int] = mapped_column(ForeignKey("housekeepers.id"))
    result: Mapped[str] = mapped_column(String(4))                     # pass | fail
    inspected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


