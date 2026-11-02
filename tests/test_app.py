import logging
import subprocess
import sys
from pathlib import Path

from roomready.handlers import PROBLEM

PKG = Path(__file__).resolve().parent.parent / "roomready"
TAG = {
    "/properties/{property}/rooms": "rooms",
    "/properties/{property}/rooms/{no}": "rooms",
    "/properties/{property}/rooms/{no}/history": "rooms",
    "/properties/{property}/housekeepers": "rooms",
    "/checkouts": "checkouts",
    "/assignments": "assignments",
    "/assignments/{assignment_id}/start": "assignments",
    "/assignments/{assignment_id}/finish": "assignments",
    "/inspections": "inspections",
    "/settings": "settings",
    "/healthz": "settings",
}


def test_docs_render_and_list_every_endpoint_with_a_summary_and_its_tag(client):
    assert client.get("/docs").status_code == 200
    spec = client.get("/openapi.json").json()
    paths = spec["paths"]
    assert set(paths) == set(TAG)
    assert {t["name"] for t in spec["tags"]} >= {"rooms", "checkouts", "assignments", "inspections", "settings"}
    for path, ops in paths.items():
        for op in ops.values():
            assert op.get("summary"), path
            assert op["tags"] == [TAG[path]], (path, op["tags"])


def test_every_refusal_is_documented_with_a_problem_example(client):
    spec = client.get("/openapi.json").json()
    inspections = spec["paths"]["/inspections"]["post"]["responses"]
    assert {"404", "409", "422"} <= set(inspections)
    examples = inspections["409"]["content"][PROBLEM]["examples"]
    assert set(examples) == {"/errors/step-skipped", "/errors/self-inspection"}
    assert examples["/errors/step-skipped"]["value"]["needs"] == "finish"
    assert examples["/errors/self-inspection"]["value"]["status"] == 409
    assert {"/errors/no-such-room", "/errors/no-such-housekeeper"} <= set(inspections["404"]["content"][PROBLEM]["examples"])
    assignments = spec["paths"]["/assignments"]["post"]["responses"]
    assert set(assignments["409"]["content"][PROBLEM]["examples"]) == {"/errors/step-skipped", "/errors/already-assigned"}
    checkouts = spec["paths"]["/checkouts"]["post"]["responses"]
    assert checkouts["400"]["content"][PROBLEM]["example"]["type"] == "/errors/room-not-occupied"
    assert "422" in checkouts
    assert checkouts["422"]["content"][PROBLEM]["example"]["errors"][0]["field"] == "at"
    board = spec["paths"]["/properties/{property}/rooms"]["get"]["responses"]
    assert board["400"]["content"][PROBLEM]["example"]["type"] == "/errors/validation"
    assert "404" in board


def test_the_spec_documents_only_what_each_operation_can_answer(client):
    """No stock 422 on an operation without a body; the app's 422 on every body; the 400 validation problem on the
    one operation whose query can fail; a 500 problem on every operation; every problem example well formed."""
    spec = client.get("/openapi.json").json()
    assert "HTTPValidationError" not in spec["components"]["schemas"]
    assert "ValidationError" not in spec["components"]["schemas"]
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            answers = op["responses"]
            has_body = "requestBody" in op
            assert ("422" in answers) == has_body, f"{method} {path}: 422 only where a body can fail"
            fails_in_query = path == "/properties/{property}/rooms"
            assert ("400" in answers) == (fails_in_query or path == "/checkouts"), f"{method} {path}"
            assert answers["500"]["content"][PROBLEM]["example"]["type"] == "/errors/internal"
            for status, entry in answers.items():
                if status.startswith("2"):
                    assert "application/json" in entry["content"]
                    continue
                assert list(entry["content"]) == [PROBLEM], f"{method} {path} {status}"
                content = entry["content"][PROBLEM]
                bodies = [content["example"]] if "example" in content else [v["value"] for v in content["examples"].values()]
                for body in bodies:
                    assert {"type", "title", "status", "detail"} <= set(body)
                    assert str(body["status"]) == status, (path, body)


def test_unexpected_exception_is_a_generic_problem_with_request_id(app, client, caplog):
    @app.get("/boom", include_in_schema=False)
    def boom():
        raise RuntimeError("secret detail")

    caplog.set_level(logging.ERROR)
    r = client.get("/boom")
    assert r.status_code == 500 and r.headers["content-type"].startswith(PROBLEM)
    body = r.json()
    assert body["type"] == "/errors/internal" and "secret detail" not in r.text and "Traceback" not in r.text
    assert len(body["request_id"]) == 12
    assert any(body["request_id"] in rec.getMessage() and "path=/boom" in rec.getMessage() for rec in caplog.records), "the request id and the path are logged"


def test_framework_404_and_405_are_problem_json_too(client):
    r = client.get("/nope")
    assert r.status_code == 404 and r.headers["content-type"].startswith(PROBLEM)
    assert r.json() == {"type": "/errors/not-found", "title": "No such resource", "status": 404, "detail": "There is no resource at /nope"}
    r = client.delete("/properties/harbour-view/rooms")
    assert r.status_code == 405 and r.headers["content-type"].startswith(PROBLEM)
    assert r.json()["type"] == "/errors/method-not-allowed" and r.json()["title"] == "Method not allowed"
    assert r.headers["allow"] == "GET", "the header the framework's refusal carries is kept"
    r = client.get("/static/nothing-here.js")
    assert r.status_code == 404 and r.json()["type"] == "/errors/not-found"


def test_services_import_nothing_from_fastapi_even_indirectly():
    modules = sorted(f"roomready.services.{p.stem}" for p in (PKG / "services").glob("*.py") if p.stem != "__init__")
    code = (
        "import importlib, sys\n"
        f"for m in {modules!r}: importlib.import_module(m)\n"
        "bad = sorted(k for k in sys.modules if k.split('.')[0] in ('fastapi', 'starlette'))\n"
        "print(bad)\nsys.exit(1 if bad else 0)\n"
    )
    done = subprocess.run([sys.executable, "-c", code], cwd=PKG.parent, capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stdout + done.stderr
    assert len(modules) >= 7


def test_one_router_per_resource():
    assert {p.stem for p in (PKG / "routers").glob("*.py")} >= {"rooms", "checkouts", "assignments", "inspections", "settings"}


def test_healthz_returns_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
