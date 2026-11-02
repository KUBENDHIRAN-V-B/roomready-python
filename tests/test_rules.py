"""One parametrised table of every refusal, run with the clock overridden under each INSPECTION_REQUIRED_FOR
setting — and only the rows tagged `inspection` move when the setting changes."""
import csv
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from roomready.app import create_app
from roomready.clock import get_clock
from tests.conftest import T0, iso, make_settings

ROWS = list(csv.DictReader((Path(__file__).parent / "rules.csv").open(encoding="utf-8")))
# Deluxe (room 214, the room every generic row uses) needs inspection under all three, so only the two tagged rows can move
SETTINGS = {"all": "Standard,Deluxe,Suite", "deluxe_suite": "Deluxe,Suite", "standard_deluxe": "Standard,Deluxe"}


def step(client, text, last):
    verb, *args = text.split()
    if verb == "checkout":
        last["room"] = args[0]
        return client.post("/checkouts", json={"room": args[0], "at": iso(T0)})
    if verb == "checkout_without_time":
        last["room"] = args[0]
        return client.post("/checkouts", json={"room": args[0]})
    if verb == "assign":
        r = client.post("/assignments", json={"room": args[0], "housekeeper": args[1]})
        if r.status_code == 201:
            last["assignment"] = r.json()["assignment_id"]
        return r
    if verb in ("start", "finish"):
        return client.post(f"/assignments/{last['assignment']}/{verb}")
    if verb == "inspect":
        return client.post("/inspections", json={"room": last["room"], "inspector": args[0], "result": args[1]})
    raise ValueError(text)


def run_case(client, row):
    last = {}
    for text in filter(None, row["setup"].split(";")):
        r = step(client, text, last)
        assert r.status_code in (200, 201), (text, r.text)
    return step(client, row["action"], last)


@pytest.mark.parametrize("mode", list(SETTINGS))
@pytest.mark.parametrize("row", ROWS, ids=[r["case"] for r in ROWS])
def test_rule_table(tmp_path, clock, row, mode):
    app = create_app(make_settings(tmp_path, inspection_required_for=SETTINGS[mode]))
    app.dependency_overrides[get_clock] = lambda: clock
    with TestClient(app) as client:
        r = run_case(client, row)
    assert r.status_code == int(row[f"status_{mode}"]), (row["case"], mode, r.text)
    expected_type = row[f"type_{mode}"]
    if expected_type:
        assert r.json()["type"] == expected_type
    if row["tag"] == "inspection" and expected_type:
        assert r.json()["state"] == "ready" and r.json()["needs"] == "checkin", "the finish already made it ready; a guest checks in next"


def test_only_inspection_rows_move_when_the_setting_changes():
    def outcome(r, mode):
        return (r[f"status_{mode}"], r[f"type_{mode}"])
    moved = {r["case"] for r in ROWS if len({outcome(r, m) for m in SETTINGS}) > 1}
    assert moved == {r["case"] for r in ROWS if r["tag"] == "inspection"}
    assert len(moved) == 2
    moved_by_deluxe_suite = {r["case"] for r in ROWS if outcome(r, "all") != outcome(r, "deluxe_suite")}
    assert moved_by_deluxe_suite == {"finish_standard_no_inspection"}, "a Suite still waits for Grace"
    moved_by_standard_deluxe = {r["case"] for r in ROWS if outcome(r, "all") != outcome(r, "standard_deluxe")}
    assert moved_by_standard_deluxe == {"finish_suite_no_inspection"}


def test_every_refusal_type_has_a_row():
    types = {r[f"type_{m}"] for r in ROWS for m in SETTINGS}
    assert types >= {"/errors/room-not-occupied", "/errors/validation", "/errors/step-skipped", "/errors/already-assigned", "/errors/self-inspection"}
    assert {r["case"] for r in ROWS} == {
        "checkout_ok", "not_occupied", "malformed", "assign_dirty", "assign_occupied", "assign_twice",
        "start_before_assign", "finish_before_start", "inspect_before_finish", "self_inspect", "pass", "fail",
        "finish_standard_no_inspection", "finish_suite_no_inspection",
    }


def test_a_standard_finish_goes_straight_to_ready_with_the_margin_when_no_inspection_is_required(tmp_path, clock):
    app = create_app(make_settings(tmp_path, inspection_required_for="Deluxe,Suite"))
    app.dependency_overrides[get_clock] = lambda: clock
    with TestClient(app) as client:
        client.post("/checkouts", json={"room": "101", "at": iso(T0), "arrival_at": "2026-09-28T13:00:00Z"})
        a = client.post("/assignments", json={"room": "101", "housekeeper": "HK03"}).json()
        client.post(f"/assignments/{a['assignment_id']}/start")
        clean = clock.advance(minutes=30)
        r = client.post(f"/assignments/{a['assignment_id']}/finish")
        assert r.status_code == 200 and r.json()["clean_minutes"] == 30
        assert client.get("/properties/harbour-view/rooms/101").json()["state"] == "ready"
        events = client.get("/properties/harbour-view/rooms/101/history").json()["events"]
        assert events[-2:] == [
            {"at": "2026-09-28T11:10:00Z", "kind": "finished", "clean_minutes": 30},
            {"at": "2026-09-28T11:10:00Z", "kind": "ready", "margin_minutes": 110, "arrival_at": "2026-09-28T13:00:00Z"},
        ]
        assert iso(clean) == "2026-09-28T11:10:00Z"
        refused = client.post("/inspections", json={"room": "101", "inspector": "HK01", "result": "pass"})
        assert refused.json()["type"] == "/errors/step-skipped"
        client.post("/checkouts", json={"room": "214", "at": iso(T0)})
        a = client.post("/assignments", json={"room": "214", "housekeeper": "HK03"}).json()
        client.post(f"/assignments/{a['assignment_id']}/start")
        assert client.post(f"/assignments/{a['assignment_id']}/finish").status_code == 200
        assert client.get("/properties/harbour-view/rooms/214").json()["state"] == "toinspect", "a Deluxe still waits"


def test_settings_endpoint_shows_the_live_values(tmp_path, clock):
    app = create_app(make_settings(tmp_path, inspection_required_for="Deluxe,Suite", stall_after_minutes=45))
    with TestClient(app) as client:
        assert client.get("/settings").json() == {"inspection_required_for": ["Deluxe", "Suite"], "stall_after_minutes": 45}


def test_an_unknown_room_type_in_the_setting_is_refused_at_start(tmp_path):
    with pytest.raises(ValueError, match="Villa"):
        make_settings(tmp_path, inspection_required_for="Standard,Villa")


def test_the_rule_book_shows_the_rows_the_tests_run():
    """The Rule book's rows in app.js are the rows of tests/rules.csv: the same cases, tags and, under each setting,
    the same status and type."""
    js = (Path(__file__).resolve().parent.parent / "roomready" / "static" / "app.js").read_text(encoding="utf-8")
    shown = json.loads(re.search(r"var RULES = (\[.*?\]);\n", js, re.DOTALL).group(1))
    assert [(r["case"], r["tag"]) for r in shown] == [(r["case"], r["tag"]) for r in ROWS]
    for js_row, csv_row in zip(shown, ROWS):
        for mode in SETTINGS:
            assert js_row[mode] == [csv_row[f"status_{mode}"], csv_row[f"type_{mode}"]], (csv_row["case"], mode)
