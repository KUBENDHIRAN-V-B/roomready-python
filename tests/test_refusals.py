"""Three refusals — step skipped, already assigned, self-inspection — each its own type, raised from the service, mapped once."""
import ast
from pathlib import Path

from sqlalchemy import select

from roomready.handlers import PROBLEM
from roomready.models import Assignment
from tests.conftest import assign, assigned, cleaned, inspect, room

PKG = Path(__file__).resolve().parent.parent / "roomready"


def test_inspecting_a_room_still_being_cleaned_is_step_skipped_needing_finish(client):
    a = assigned(client, "214", "HK03")
    client.post(f"/assignments/{a['assignment_id']}/start")
    r = inspect(client, "214", "HK01", "pass")
    assert r.status_code == 409
    body = r.json()
    assert body["type"] == "/errors/step-skipped" and body["state"] == "cleaning" and body["needs"] == "finish"


def test_assigning_a_room_twice_is_already_assigned_naming_the_housekeeper(client):
    assigned(client, "214", "HK03")
    r = assign(client, "214", "HK04")
    assert r.status_code == 409
    body = r.json()
    assert body["type"] == "/errors/already-assigned" and body["assigned_to"] == "Sunita"


def test_assigning_an_occupied_room_is_step_skipped_needing_checkout(client):
    r = assign(client, "214", "HK03")
    assert r.status_code == 409 and r.json()["type"] == "/errors/step-skipped"
    assert r.json()["state"] == "occupied" and r.json()["needs"] == "checkout"


def test_the_cleaner_may_not_inspect_her_own_room(client, clock):
    cleaned(client, clock, "214", "HK03")
    r = inspect(client, "214", "HK03", "pass")
    assert r.status_code == 409 and r.json()["type"] == "/errors/self-inspection"
    assert room(client, "214")["state"] == "toinspect"
    assert inspect(client, "214", "HK01", "pass").status_code == 201, "somebody else may"


def test_a_failed_inspection_returns_the_room_to_dirty_and_the_next_assignment_is_a_new_row(client, clock, db):
    cleaned(client, clock, "214", "HK03")
    r = inspect(client, "214", "HK01", "fail")
    assert r.status_code == 201
    body = r.json()
    assert body["result"] == "fail" and body["state"] == "dirty" and body["cleaned_by"] == "Sunita" and body["inspected_by"] == "Grace"
    assert room(client, "214")["state"] == "dirty"
    r = assign(client, "214", "HK04")
    assert r.status_code == 201 and r.json()["assignment_id"] == "AS002"
    with db() as s:
        rows = s.scalars(select(Assignment).order_by(Assignment.id)).all()
    assert rows[0].closed_at is not None and rows[1].closed_at is None and rows[1].housekeeper_id != rows[0].housekeeper_id


def test_refusal_body_has_exactly_the_documented_shape(client, clock):
    """Every domain refusal: problem+json, `status` equal to the HTTP code, exactly the four fields plus the ones its
    type names — step-skipped, already-assigned, self-inspection and room-not-occupied."""
    def shape(r, status):
        assert r.status_code == status and r.headers["content-type"].startswith(PROBLEM) and r.json()["status"] == status
        assert "Traceback" not in r.text
        return set(r.json())

    base = {"type", "title", "status", "detail"}
    assert shape(assign(client, "214", "HK03"), 409) == base | {"state", "needs"}
    assigned(client, "301", "HK03")
    assert shape(assign(client, "301", "HK04"), 409) == base | {"assigned_to"}
    cleaned(client, clock, "214", "HK05")
    assert shape(inspect(client, "214", "HK05", "pass"), 409) == base, "self-inspection names no extra field"
    assert shape(client.post("/checkouts", json={"room": "214", "at": "2026-09-28T10:40:00Z"}), 400) == base


def test_the_order_of_checks_and_the_404s(client):
    r = inspect(client, "999", "HK01", "pass")
    assert r.status_code == 404 and r.json()["type"] == "/errors/no-such-room", "the room is checked first"
    r = inspect(client, "214", "HK99", "pass")
    assert r.status_code == 404 and r.json()["type"] == "/errors/no-such-housekeeper"
    r = inspect(client, "214", "HK01", "pass")
    assert r.status_code == 409 and r.json()["type"] == "/errors/step-skipped" and r.json()["state"] == "occupied"
    r = inspect(client, "214", "HK01", "maybe")
    assert r.status_code == 422 and r.json()["errors"][0]["field"] == "result"


def test_routes_never_build_error_responses():
    for path in (PKG / "routers").glob("*.py"):
        src = path.read_text(encoding="utf-8")
        assert "HTTPException" not in src and "JSONResponse" not in src, path.name
        tree = ast.parse(src)
        assert not any(isinstance(n, ast.Raise) for n in ast.walk(tree)), f"{path.name} raises inside a route"
