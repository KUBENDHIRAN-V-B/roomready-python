from roomready.db import get_session
from roomready.models import Assignment
from tests.conftest import P, assign, assigned, checkout, room


def test_dirty_room_assignment_creates_assignment_and_updates_board(client, clock):
    checkout(client, "214")
    r = assign(client, "214", "HK03")
    assert r.status_code == 201, r.text
    assert r.json() == {"assignment_id": "AS001", "room": "214", "assigned_to": "Sunita", "assigned_at": "2026-09-28T10:40:00Z"}
    assert room(client, "214")["state"] == "assigned" and room(client, "214")["assigned_to"] == "Sunita"


def test_start_finish_stores_duration_and_read_does_not_recompute(client, clock, db):
    a = assigned(client, "214", "HK03")
    clock.advance(minutes=15)
    r = client.post(f"/assignments/{a['assignment_id']}/start")
    assert r.status_code == 200 and r.json() == {"assignment_id": "AS001", "started_at": "2026-09-28T10:55:00Z"}
    assert room(client, "214")["state"] == "cleaning"
    clock.advance(minutes=36)
    r = client.post(f"/assignments/{a['assignment_id']}/finish")
    assert r.status_code == 200
    assert r.json() == {"assignment_id": "AS001", "finished_at": "2026-09-28T11:31:00Z", "clean_minutes": 36}, "the shape: no state"
    assert room(client, "214")["state"] == "toinspect"
    clock.advance(hours=3)
    with db() as s:
        assert s.get(Assignment, 1).clean_minutes == 36, "stored at finish, not recomputed on read"
    finished = [e for e in client.get(f"{P}/rooms/214/history").json()["events"] if e["kind"] == "finished"]
    assert finished[0]["clean_minutes"] == 36 and room(client, "214")["since_minutes"] == 180


def test_clean_minutes_are_whole_minutes_rounded_down(client, clock):
    a = assigned(client)
    client.post(f"/assignments/{a['assignment_id']}/start")
    clock.advance(minutes=36, seconds=59)
    assert client.post(f"/assignments/{a['assignment_id']}/finish").json()["clean_minutes"] == 36


def test_step_skipped_for_finish_without_start_start_twice_finish_twice(client):
    a = assigned(client)
    r = client.post(f"/assignments/{a['assignment_id']}/finish")
    body = r.json()
    assert r.status_code == 409 and body["type"] == "/errors/step-skipped" and body["state"] == "assigned" and body["needs"] == "start"
    assert client.post(f"/assignments/{a['assignment_id']}/start").status_code == 200
    r = client.post(f"/assignments/{a['assignment_id']}/start")
    assert r.status_code == 409 and r.json()["state"] == "cleaning" and r.json()["needs"] == "finish"
    assert client.post(f"/assignments/{a['assignment_id']}/finish").status_code == 200
    r = client.post(f"/assignments/{a['assignment_id']}/finish")
    assert r.status_code == 409 and r.json()["state"] == "toinspect" and r.json()["needs"] == "inspect"


def test_404s_and_injected_clock(client, clock):
    checkout(client, "214")
    r = assign(client, "999", "HK03")
    assert r.status_code == 404 and r.json()["type"] == "/errors/no-such-room"
    r = assign(client, "214", "HK99")
    assert r.status_code == 404 and r.json()["type"] == "/errors/no-such-housekeeper"
    for action in ("start", "finish"):
        r = client.post(f"/assignments/AS999/{action}")
        assert r.status_code == 404 and r.json()["type"] == "/errors/no-such-assignment"
    assert assign(client, "214", "HK03").json()["assigned_at"] == "2026-09-28T10:40:00Z"
    clock.advance(hours=1, minutes=5)
    checkout(client, "215", at="2026-09-28T11:45:00Z")
    assert assign(client, "215", "HK04").json()["assigned_at"] == "2026-09-28T11:45:00Z", "the stamp moved with the injected clock"


def test_session_dependency_can_be_overridden(app, client, db):
    """The routes take their session from `Depends(get_session)`: an override sees every request's session."""
    used = []

    def spy_session():
        with db() as session:
            used.append(session)
            yield session

    app.dependency_overrides[get_session] = spy_session
    checkout(client, "214")
    assert assign(client, "214", "HK03").status_code == 201
    assert room(client, "214")["state"] == "assigned"
    assert len(used) == 3, "checkout, assign and the read each ran on the overridden session"
