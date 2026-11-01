from fastapi.testclient import TestClient
from sqlalchemy import func, select

from roomready.app import create_app
from roomready.models import Housekeeper, Room, Stay
from tests.conftest import P, checkout, make_settings, room


def test_seeding_is_idempotent_across_two_starts(tmp_path, clock):
    settings = make_settings(tmp_path)
    for _ in range(2):
        app = create_app(settings)
        with TestClient(app) as c:
            assert len(c.get(f"{P}/rooms").json()["rooms"]) == 60
        with app.state.sessionmaker() as s:
            assert s.scalar(select(func.count()).select_from(Room)) == 60
            assert s.scalar(select(func.count()).select_from(Housekeeper)) == 9
            assert s.scalar(select(func.count()).select_from(Stay)) == 60


def test_the_board_has_sixty_rooms_on_four_floors_all_occupied(client):
    r = client.get(f"{P}/rooms")
    assert r.status_code == 200
    body = r.json()
    assert body["property"] == "harbour-view" and body["ready"] == 0 and body["dirty"] == 0 and len(body["rooms"]) == 60
    assert all(set(x) == {"no", "floor", "type", "state", "assigned_to", "since_minutes"} for x in body["rooms"])
    assert all(x["state"] == "occupied" for x in body["rooms"])
    assert [x["floor"] for x in body["rooms"]].count(2) == 15 and {x["floor"] for x in body["rooms"]} == {1, 2, 3, 4}
    types = [x["type"] for x in body["rooms"]]
    assert types.count("Standard") == 40 and types.count("Deluxe") == 12 and types.count("Suite") == 8
    assert body["rooms"][0]["no"] == "101" and body["rooms"][-1]["no"] == "415"


def test_nine_housekeepers_are_listed_with_the_room_each_is_on(client):
    r = client.get(f"{P}/housekeepers")
    assert r.status_code == 200
    staff = r.json()["housekeepers"]
    assert len(staff) == 9 and staff[0] == {"id": "HK01", "name": "Grace", "open_assignment": None}


def test_floor_and_state_filters_show_only_those_rooms_and_their_counts(client):
    checkout(client, "214"); checkout(client, "215"); checkout(client, "301")
    body = client.get(f"{P}/rooms?floor=2&state=dirty").json()
    assert [x["no"] for x in body["rooms"]] == ["214", "215"] and body["dirty"] == 2 and body["ready"] == 0
    body = client.get(f"{P}/rooms?floor=2").json()
    assert len(body["rooms"]) == 15 and body["dirty"] == 2
    body = client.get(f"{P}/rooms?type=Suite").json()
    assert len(body["rooms"]) == 8 and all(x["type"] == "Suite" for x in body["rooms"])
    assert client.get(f"{P}/rooms?state=ready").json()["rooms"] == []
    assert client.get(f"{P}/rooms?state=out_of_order").json()["rooms"] == []


def test_unknown_filter_values_are_400_not_an_empty_list(client):
    for query, field in (("state=painting", "state"), ("floor=9", "floor"), ("floor=x", "floor"), ("type=Villa", "type")):
        r = client.get(f"{P}/rooms?{query}")
        assert r.status_code == 400, query
        body = r.json()
        assert body["type"] == "/errors/validation" and body["errors"][0]["field"] == field
        assert r.headers["content-type"].startswith("application/problem+json")


def test_one_room_and_the_404s(client):
    r = client.get(f"{P}/rooms/214")
    assert r.status_code == 200
    body = r.json()
    assert body["since_minutes"] == 1440, "the guest checked in a day ago"
    body.pop("since_minutes")
    assert body == {"no": "214", "floor": 2, "type": "Deluxe", "state": "occupied", "assigned_to": None}
    r = client.get(f"{P}/rooms/999")
    assert r.status_code == 404 and r.json()["type"] == "/errors/no-such-room"
    for path in ("/rooms", "/rooms/214", "/housekeepers", "/rooms/214/history"):
        r = client.get(f"/properties/sea-view{path}")
        assert r.status_code == 404 and r.json()["type"] == "/errors/no-such-property", path


def test_state_is_derived_from_rows_and_there_is_no_state_column(client):
    assert "state" not in Room.__table__.columns
    assert room(client, "214")["state"] == "occupied"
    checkout(client, "214")
    assert room(client, "214")["state"] == "dirty"
    assert room(client, "214")["state"] == "dirty", "a second read derives the same state from the same rows"


def test_housekeeper_list_shows_room_assignment(client):
    from tests.conftest import assigned
    assigned(client, "214", "HK03")
    staff = client.get(f"{P}/housekeepers").json()["housekeepers"]
    assert {h["id"]: h["open_assignment"] for h in staff}["HK03"] == "214"
    assert all(h["open_assignment"] is None for h in staff if h["id"] != "HK03")


def test_board_shows_assignee_and_elapsed_assigned_minutes(client, clock):
    from tests.conftest import assigned
    assigned(client, "214", "HK03")
    clock.advance(minutes=22)
    body = client.get(f"{P}/rooms?state=assigned").json()
    assert body["rooms"] == [{"no": "214", "floor": 2, "type": "Deluxe", "state": "assigned", "assigned_to": "Sunita", "since_minutes": 22}]
