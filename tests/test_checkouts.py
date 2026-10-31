"""A checkout makes the room dirty; a room without a guest and a malformed body are refused differently."""
from roomready.models import Stay
from tests.conftest import T0, P, iso, room


def test_a_checkout_stamps_the_stay_and_the_room_shows_dirty(client, clock, db):
    r = client.post("/checkouts", json={"room": "214", "at": "2026-09-28T10:40:00Z"})
    assert r.status_code == 201, r.text
    assert r.json() == {"stay_id": "ST0029", "room": "214", "checked_out_at": "2026-09-28T10:40:00Z", "state": "dirty"}
    assert r.headers["location"] == f"{P}/rooms/214"
    with db() as s:
        stay = s.get(Stay, 29)
        assert stay.checked_out_at is not None and stay.arrival_at is None
    clock.advance(minutes=5)
    assert room(client, "214") == {"no": "214", "floor": 2, "type": "Deluxe", "state": "dirty", "assigned_to": None, "since_minutes": 5}


def test_the_next_arrival_can_be_typed_in_with_the_checkout(client, db):
    r = client.post("/checkouts", json={"room": "214", "at": iso(T0), "arrival_at": "2026-09-28T13:00:00Z"})
    assert r.status_code == 201
    with db() as s:
        assert iso(s.get(Stay, 29).arrival_at.replace(tzinfo=None)) == "2026-09-28T13:00:00Z"


def test_a_room_already_dirty_is_400_not_occupied_and_nothing_is_written(client, db):
    client.post("/checkouts", json={"room": "214", "at": iso(T0)})
    with db() as s:
        before = (s.get(Stay, 29).checked_out_at)
    r = client.post("/checkouts", json={"room": "214", "at": iso(T0)})
    assert r.status_code == 400
    assert r.json()["type"] == "/errors/room-not-occupied" and r.headers["content-type"].startswith("application/problem+json")
    with db() as s:
        assert (s.get(Stay, 29).checked_out_at) == before


def test_a_timestamp_in_the_future_or_before_check_in_is_422_naming_the_field(client, db):
    for at in ("2026-09-28T10:41:00Z", "2026-09-26T09:00:00Z"):
        r = client.post("/checkouts", json={"room": "214", "at": at})
        assert r.status_code == 422, at
        body = r.json()
        assert body["type"] == "/errors/validation" and body["errors"] == [{"field": "at", "message": body["errors"][0]["message"]}]
    with db() as s:
        assert s.get(Stay, 29).checked_out_at is None


def test_a_malformed_body_is_422_naming_each_field(client):
    for body, fields in (({"room": "214"}, {"at"}), ({"at": iso(T0)}, {"room"}), ({"room": "214", "at": "yesterday"}, {"at"}), ({"room": "", "at": ""}, {"room", "at"})):
        r = client.post("/checkouts", json=body)
        assert r.status_code == 422, body
        assert r.json()["type"] == "/errors/validation" and {e["field"] for e in r.json()["errors"]} == fields, body


def test_an_unknown_room_is_404(client):
    r = client.post("/checkouts", json={"room": "999", "at": iso(T0)})
    assert r.status_code == 404 and r.json()["type"] == "/errors/no-such-room"


def test_an_arrival_before_the_checkout_is_422_naming_it(client, db):
    r = client.post("/checkouts", json={"room": "214", "at": iso(T0), "arrival_at": "2026-09-28T10:00:00Z"})
    assert r.status_code == 422 and r.json()["type"] == "/errors/validation"
    assert r.json()["errors"] == [{"field": "arrival_at", "message": "the next arrival cannot be before the checkout"}]
    with db() as s:
        assert s.get(Stay, 29).checked_out_at is None
