"""A pass moves the room to ready and stamps the margin before arrival — inspection, readiness and close in one transaction."""
from sqlalchemy import func, select, text

from roomready.models import Assignment, Inspection, Readiness
from tests.conftest import P, cleaned, inspect, room


def test_a_pass_at_twelve_twenty_for_a_one_oclock_arrival_is_forty_minutes_of_margin(client, clock, db):
    cleaned(client, clock, "214", "HK03", minutes=36, arrival_at="2026-09-28T13:00:00Z")   # finished 11:16
    clock.advance(minutes=64)                                                                # 12:20
    r = inspect(client, "214", "HK01", "pass")
    assert r.status_code == 201, r.text
    assert r.json() == {
        "inspection_id": "IN001", "room": "214", "cleaned_by": "Sunita", "inspected_by": "Grace",
        "result": "pass", "state": "ready", "ready_at": "2026-09-28T12:20:00Z",
        "arrival_at": "2026-09-28T13:00:00Z", "margin_minutes": 40
    }
    assert room(client, "214")["state"] == "ready"
    with db() as s:
        assert s.get(Assignment, 1).closed_at is not None
        readiness = s.scalar(select(Readiness))
        assert readiness.margin_minutes == 40 and readiness.stay_id == 29
    clock.advance(hours=2)
    with db() as s:
        assert s.scalar(select(Readiness)).margin_minutes == 40, "stored, not recomputed"
    board = client.get(f"{P}/rooms").json()
    assert board["ready"] == 1 and board["dirty"] == 0


def test_a_failure_after_the_inspection_insert_rolls_everything_back(client, clock, db):
    cleaned(client, clock, "214", "HK03", arrival_at="2026-09-28T13:00:00Z")
    with db() as s:   # the readiness stamp is written after the inspection row: make the database refuse it
        s.execute(text(
            "CREATE TRIGGER fail_readiness AFTER INSERT ON room_readiness "
            "BEGIN SELECT RAISE(ABORT, 'injected failure'); END;"
        ))
        s.commit()
    r = inspect(client, "214", "HK01", "pass")
    with db() as s:
        s.execute(text("DROP TRIGGER fail_readiness"))
        s.commit()
    assert r.status_code == 500
    assert room(client, "214")["state"] == "toinspect"
    with db() as s:
        assert s.scalar(select(func.count()).select_from(Inspection)) == 0
        assert s.scalar(select(func.count()).select_from(Readiness)) == 0
        assert s.get(Assignment, 1).closed_at is None
    assert inspect(client, "214", "HK01", "pass").status_code == 201, "nothing was left half-done"


def test_no_arrival_known_means_a_null_margin(client, clock):
    cleaned(client, clock, "214", "HK03")
    r = inspect(client, "214", "HK01", "pass")
    assert r.status_code == 201
    assert r.json()["state"] == "ready" and r.json()["ready_at"] == "2026-09-28T11:16:00Z"
    assert r.json()["arrival_at"] is None and r.json()["margin_minutes"] is None


def test_a_late_room_has_a_negative_margin(client, clock):
    cleaned(client, clock, "214", "HK03", arrival_at="2026-09-28T11:00:00Z")   # finished 11:16, guest was due at 11:00
    assert inspect(client, "214", "HK01", "pass").json()["margin_minutes"] == -16


def test_the_board_never_shows_ready_with_an_open_assignment(client, clock, db):
    cleaned(client, clock, "214", "HK03")
    inspect(client, "214", "HK01", "pass")
    with db() as s:
        open_rows = s.scalar(select(func.count()).select_from(Assignment).where(Assignment.closed_at.is_(None)))
    assert room(client, "214")["state"] == "ready" and open_rows == 0
