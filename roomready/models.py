"""Rooms and housekeepers. A room's state is derived from these rows,
and there is deliberately no `state` column on rooms."""
from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
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
