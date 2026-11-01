"""Every transition writes an event in the same transaction, with who did it; events can never be updated or deleted."""
from unittest.mock import patch

import pytest
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import DBAPIError

from roomready.models import Event, Stay
from tests.conftest import P, T0, checkout, cleaned, inspect, iso


def test_pass_writes_one_inspected_event_and_failed_transaction_writes_none(client, clock, db):
    cleaned(client, clock, "214", "HK03", arrival_at="2026-09-28T13:00:00Z")
    clock.advance(minutes=64)
    response = inspect(client, "214", "HK01", "pass")
    assert response.status_code == 201, response.text
    with db() as s:
        rows = s.scalars(select(Event).where(Event.kind == "inspected")).all()
        assert len(rows) == 1 and rows[0].actor_id == "HK01" and rows[0].assignment_id == 1
        assert all(fact in rows[0].data for fact in ('"inspector": "HK01"', '"result": "pass"', '"margin_minutes": 40'))

    cleaned(client, clock, "301", "HK03")
    with db() as s:
        before = s.scalar(select(func.count()).select_from(Event))
    with patch("roomready.services.inspections.events.record", side_effect=RuntimeError("boom")):
        failed = inspect(client, "301", "HK01", "pass")
        assert failed.status_code == 500
    with db() as s:
        assert s.scalar(select(func.count()).select_from(Event)) == before


def test_events_are_append_only(client, db):
    checkout(client, "214")
    with db() as s, pytest.raises(DBAPIError):
        s.execute(update(Event).values(kind="edited"))
        s.commit()
    with db() as s, pytest.raises(DBAPIError):
        s.execute(delete(Event))
        s.commit()
    with db() as s, pytest.raises(DBAPIError):
        s.execute(text("DELETE FROM events WHERE id = 1"))
        s.commit()
    with db() as s:
        assert s.scalar(select(func.count()).select_from(Event)) == 1


def test_room_history_orders_transitions_and_excludes_actor(client, clock):
    checkout(client, "214", at=iso(T0), arrival_at="2026-09-28T13:00:00Z")
    clock.advance(minutes=12)
    assignment = client.post("/assignments", json={"room": "214", "housekeeper": "HK03"}).json()
    clock.advance(minutes=3)
    client.post(f"/assignments/{assignment['assignment_id']}/start")
    clock.advance(minutes=36)
    client.post(f"/assignments/{assignment['assignment_id']}/finish")
    clock.advance(minutes=49)
    assert inspect(client, "214", "HK01", "pass").status_code == 201
    body = client.get(f"{P}/rooms/214/history").json()
    assert body["room"] == "214"
    events = body["events"]
    assert [e["kind"] for e in events] == ["checked_out", "assigned", "started", "finished", "inspected"]
    assert events[0]["at"] == "2026-09-28T10:40:00Z"
    assert events[1]["housekeeper"] == "HK03"
    assert events[3]["clean_minutes"] == 36
    assert events[-1] == {"at": "2026-09-28T12:20:00Z", "kind": "inspected", "inspector": "HK01",
                          "result": "pass", "margin_minutes": 40, "arrival_at": "2026-09-28T13:00:00Z"}
    assert all("actor" not in e and "actor_id" not in e for e in events)


def test_history_is_per_stay_and_unknown_or_other_room_stays_are_empty(client, clock, db):
    cleaned(client, clock, "214", "HK03")
    assert inspect(client, "214", "HK01", "pass").status_code == 201
    with db() as s:
        s.add(Stay(property_id=1, room_id=29, guest_ref="BK-214-2", checked_in_at=clock.now()))
        s.commit()
    clock.advance(days=1)
    checkout(client, "214", at=iso(clock.now()))
    current = client.get(f"{P}/rooms/214/history").json()["events"]
    first = client.get(f"{P}/rooms/214/history?stay=ST0029").json()["events"]
    assert [e["kind"] for e in current] == ["checked_out"]
    assert [e["kind"] for e in first] == ["checked_out", "assigned", "started", "finished", "inspected"]
    checkout(client, "101", at=iso(clock.now()))
    assert client.get(f"{P}/rooms/214/history?stay=ST0001").json()["events"] == []
    assert client.get(f"{P}/rooms/214/history?stay=ST9999").json()["events"] == []


def test_no_guest_reference_in_event_data_or_history(client, clock, db):
    cleaned(client, clock, "214", "HK03")
    assert inspect(client, "214", "HK01", "pass").status_code == 201
    with db() as s:
        guest = s.get(Stay, 29).guest_ref
        assert guest and all(guest not in e.data for e in s.scalars(select(Event)))
    assert guest not in client.get(f"{P}/rooms/214/history").text
